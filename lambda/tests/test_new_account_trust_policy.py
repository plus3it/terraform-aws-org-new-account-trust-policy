"""Test event handler and main() of new_account_trust_policy.

This is testing a rather basic lambda function, so the tests are
basic as well:

    - test arguments to main()
    - test event handler arguments
"""
from datetime import datetime
import json
import os
import uuid

import boto3
import jsonpickle
from moto import mock_iam
from moto import mock_sts
from moto import mock_organizations
from moto.core import ACCOUNT_ID
import pytest

import new_account_trust_policy as lambda_func

AWS_REGION = os.getenv("AWS_REGION", default="aws-global")

MOCK_ORG_NAME = "test_account"
MOCK_ORG_EMAIL = f"{MOCK_ORG_NAME}@mock.org"


@pytest.fixture
def lambda_context():
    """Create mocked lambda context injected by the powertools logger."""

    class LambdaContext:  # pylint: disable=too-few-public-methods
        """Mock lambda context."""

        def __init__(self):
            """Initialize context variables."""
            self.function_name = "test"
            self.memory_limit_in_mb = 128
            self.invoked_function_arn = (
                f"arn:aws:lambda:{AWS_REGION}:{ACCOUNT_ID}:function:test"
            )
            self.aws_request_id = str(uuid.uuid4())

    return LambdaContext()


@pytest.fixture(scope="function")
def aws_credentials(tmpdir, monkeypatch):
    """Create mocked AWS credentials for moto.

    In addition to using the aws_credentials fixture, the test functions
    must also use a mocked client.  For this test file, that would be the
    test fixture "iam_client", which invokes "mock_iam()", or "sts_client".
    """
    # Create a temporary AWS credentials file for calls to boto.Session().
    aws_creds = [
        "[testing]",
        "aws_access_key_id = testing",
        "aws_secret_access_key = testing",
    ]
    path = tmpdir.join("aws_test_creds")
    path.write("\n".join(aws_creds))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(path))

    # Ensure that any existing environment variables are overridden with
    # 'mock' values.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_PROFILE", "testing")  # Not standard, but in use locally.


@pytest.fixture(scope="function")
def iam_client(aws_credentials):
    """Yield a mock IAM client that will not affect a real AWS account."""
    with mock_iam():
        yield boto3.client("iam", region_name=AWS_REGION)


@pytest.fixture(scope="function")
def sts_client(aws_credentials):
    """Yield a mock STS client that will not affect a real AWS account."""
    with mock_sts():
        yield boto3.client("sts", region_name=AWS_REGION)


@pytest.fixture(scope="function")
def org_client(aws_credentials):
    """Yield a mock organization that will not affect a real AWS account."""
    with mock_organizations():
        yield boto3.client("organizations", region_name=AWS_REGION)


@pytest.fixture(scope="function")
def mock_event(org_client):
    """Create an event used as an argument to the Lambda handler."""
    org_client.create_organization(FeatureSet="ALL")
    account_id = org_client.create_account(
        AccountName=MOCK_ORG_NAME, Email=MOCK_ORG_EMAIL
    )["CreateAccountStatus"]["Id"]
    return {
        "version": "0",
        "id": str(uuid.uuid4()),
        "detail-type": "AWS API Call via CloudTrail",
        "source": "aws.organizations",
        "account": "222222222222",
        "time": datetime.now().isoformat(),
        "region": AWS_REGION,
        "resources": [],
        "detail": {
            "eventName": "CreateAccount",
            "eventSource": "organizations.amazonaws.com",
            "responseElements": {
                "createAccountStatus": {
                    "id": account_id,
                }
            },
        },
    }


@pytest.fixture(scope="session")
def initial_trust_policy():
    """Return AssumeRolePolicyDocument used when creating a role."""
    initial_json = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT_ID}:root"},
                "Effect": "Allow",
            }
        ],
    }
    return jsonpickle.encode(initial_json)


@pytest.fixture(scope="session")
def replacement_trust_policy():
    """Return JSON policy used for updating the AssumeRolePolicyDocument."""
    arn = f"arn:aws:iam::{ACCOUNT_ID}:saml-provider/saml-provider"
    valid_json = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT_ID}:root"},
                "Effect": "Allow",
            },
            {
                "Action": "sts:AssumeRoleWithSAML",
                "Principal": {
                    "Federated": arn,
                },
                "Effect": "Allow",
            },
        ],
    }
    return json.dumps(valid_json)


def reset_roles(
    iam_client, trust_policy, role_name_list
):  # pylint: disable=redefined-outer-name
    """Create role(s) with the same initial AssumeRolePolicyDocument.

    If the roles already exist, they will be deleted.
    """
    role_names = [role["RoleName"] for role in iam_client.list_roles()["Roles"]]

    for role_name in set(role_name_list):
        if role_name in role_names:
            iam_client.delete_role(RoleName=role_name)

        iam_client.create_role(
            RoleName=role_name, AssumeRolePolicyDocument=trust_policy
        )


def test_invalid_trust_policy():
    """Test an invalid JSON string for trust_policy argument."""
    with pytest.raises(Exception) as exc:
        # JSON string is missing a bracket in the 'Statement' field.
        lambda_func.main(
            role_arn=f"arn:aws:iam::{ACCOUNT_ID}:root",
            role_name="TEST_TRUST_POLICY_INVALID_JSON",
            trust_policy=(
                f'{{"Version": "2012-10-17", "Statement": '
                f'[{{"Action": "sts:AssumeRole", '
                f'"Principal": {{"AWS": "arn:aws:iam::{ACCOUNT_ID}:root"}}, '
                f'"Effect": "Allow"}}'
            ),
        )
    assert "'trust-policy' contains badly formed JSON" in str(exc.value)


def test_main_func_uncreated_role_arg(
    sts_client, iam_client, initial_trust_policy, replacement_trust_policy
):
    """Invoke main() with a role name for a non-existent role."""
    assume_role_name = "TEST_TRUST_POLICY_NONEXISTENT_ROLE"
    update_role_name = "TEST_ROLE_DOES_NOT_EXIST"

    # Don't create role for bad role name as we don't want an error
    # for the creation of the role.
    reset_roles(iam_client, initial_trust_policy, [assume_role_name])

    with pytest.raises(lambda_func.TrustPolicyInvalidArgumentsError) as exc:
        lambda_func.main(
            role_arn=f"arn:aws:iam::{ACCOUNT_ID}:role/{assume_role_name}",
            role_name=update_role_name,
            trust_policy=replacement_trust_policy,
        )
    assert (
        f"An error occurred (NoSuchEntity) when calling the "
        f"UpdateAssumeRolePolicy operation: Role {update_role_name}"
    ) in str(exc.value)


def test_main_func_valid_arguments(
    sts_client,
    iam_client,
    initial_trust_policy,
    replacement_trust_policy,
):
    """Test the use of valid arguments for main()."""
    assume_role_name = "TEST_TRUST_POLICY_MAIN_VALID_ASSUME_ROLE"
    update_role_name = "TEST_TRUST_POLICY_MAIN_VALID_UPDATE_ROLE"
    reset_roles(iam_client, initial_trust_policy, [assume_role_name, update_role_name])

    return_code = lambda_func.main(
        role_arn=f"arn:aws:iam::{ACCOUNT_ID}:role/{assume_role_name}",
        role_name=update_role_name,
        trust_policy=replacement_trust_policy,
    )
    assert return_code == 0

    # Validate the assumed role's AssumeRolePolicyDocument is unchanged.
    role_info = iam_client.get_role(RoleName=assume_role_name)
    assume_policy = jsonpickle.encode(role_info["Role"]["AssumeRolePolicyDocument"])
    assert assume_policy == initial_trust_policy

    # Validate the updated role's AssumeRolePolicyDocument has been updated.
    role_info = iam_client.get_role(RoleName=update_role_name)
    update_policy = json.dumps(role_info["Role"]["AssumeRolePolicyDocument"])
    assert update_policy == replacement_trust_policy


def test_lambda_handler_valid_arguments(
    lambda_context,
    sts_client,
    iam_client,
    mock_event,
    initial_trust_policy,
    replacement_trust_policy,
    monkeypatch,
):  # pylint: disable=too-many-arguments
    """Invoke the lambda handler with only valid arguments."""
    assume_role_name = "TEST_TRUST_POLICY_VALID_ASSUME_ROLE"
    update_role_name = "TEST_TRUST_POLICY_VALID_UPDATE_ROLE"
    monkeypatch.setenv("ASSUME_ROLE_NAME", assume_role_name)
    monkeypatch.setenv("UPDATE_ROLE_NAME", update_role_name)
    monkeypatch.setenv("TRUST_POLICY", replacement_trust_policy)

    reset_roles(iam_client, initial_trust_policy, [assume_role_name, update_role_name])

    # The lambda function doesn't return anything, so returning nothing versus
    # aborting with an exception is considered success.
    assert not lambda_func.lambda_handler(mock_event, lambda_context)

    # Validate the assumed role's AssumeRolePolicyDocument is unchanged.
    role_info = iam_client.get_role(RoleName=assume_role_name)
    assume_policy = jsonpickle.encode(role_info["Role"]["AssumeRolePolicyDocument"])
    assert assume_policy == initial_trust_policy

    # Validate the updated role's AssumeRolePolicyDocument has been updated.
    role_info = iam_client.get_role(RoleName=update_role_name)
    update_policy = json.dumps(role_info["Role"]["AssumeRolePolicyDocument"])
    assert update_policy == replacement_trust_policy


def test_lambda_handler_same_roles(
    lambda_context,
    sts_client,
    iam_client,
    mock_event,
    initial_trust_policy,
    replacement_trust_policy,
    monkeypatch,
):  # pylint: disable=too-many-arguments
    """Invoke the lambda handler with the same assume and update role."""
    assume_role_name = "TEST_TRUST_POLICY_VALID_ROLE"
    monkeypatch.setenv("ASSUME_ROLE_NAME", assume_role_name)
    monkeypatch.setenv("UPDATE_ROLE_NAME", assume_role_name)
    monkeypatch.setenv("TRUST_POLICY", replacement_trust_policy)

    reset_roles(iam_client, initial_trust_policy, [assume_role_name])

    # The lambda function doesn't return anything, so returning nothing versus
    # aborting with an exception is considered success.
    assert not lambda_func.lambda_handler(mock_event, lambda_context)

    # Validate the assumed role's AssumeRolePolicyDocument has been updated.
    role_info = iam_client.get_role(RoleName=assume_role_name)
    assume_policy = jsonpickle.encode(role_info["Role"]["AssumeRolePolicyDocument"])
    assert assume_policy == replacement_trust_policy


def test_lambda_handler_missing_assume_role_name(
    mock_event,
    lambda_context,
    monkeypatch,
    replacement_trust_policy,
):
    """Invoke the lambda handler with no assume role name."""
    monkeypatch.delenv("ASSUME_ROLE_NAME", raising=False)
    monkeypatch.setenv("UPDATE_ROLE_NAME", "TEST_TRUST_POLICY_MISSING_ASSUME_ROLE")
    monkeypatch.setenv("TRUST_POLICY", replacement_trust_policy)

    with pytest.raises(lambda_func.TrustPolicyInvalidArgumentsError) as exc:
        lambda_func.lambda_handler(mock_event, lambda_context)
    assert (
        "Environment variable 'ASSUME_ROLE_NAME' must provide the name of the "
        "IAM role to assume in target account."
    ) in str(exc.value)


def test_lambda_handler_missing_update_role_name(
    mock_event,
    lambda_context,
    monkeypatch,
    replacement_trust_policy,
):
    """Invoke the lambda handler with no update role name."""
    monkeypatch.setenv("ASSUME_ROLE_NAME", "TEST_TRUST_POLICY_MISSING_UPDATE_ROLE")
    monkeypatch.delenv("UPDATE_ROLE_NAME", raising=False)
    monkeypatch.setenv("TRUST_POLICY", replacement_trust_policy)

    with pytest.raises(lambda_func.TrustPolicyInvalidArgumentsError) as exc:
        lambda_func.lambda_handler(mock_event, lambda_context)
    assert (
        "Environment variable 'UPDATE_ROLE_NAME' must be the name of the "
        "IAM role to update in target account."
    ) in str(exc.value)


def test_lambda_handler_missing_trust_policy(
    mock_event,
    lambda_context,
    monkeypatch,
    replacement_trust_policy,
):
    """Invoke the lambda handler with no trust policy JSON."""
    monkeypatch.setenv(
        "ASSUME_ROLE_NAME", "TEST_TRUST_POLICY_MISSING_POLICY_ASSUME_ROLE"
    )
    monkeypatch.setenv(
        "UPDATE_ROLE_NAME", "TEST_TRUST_POLICY_MISSING_POLICY_UPDATE_ROLE"
    )
    monkeypatch.delenv("TRUST_POLICY", raising=False)

    with pytest.raises(lambda_func.TrustPolicyInvalidArgumentsError) as exc:
        lambda_func.lambda_handler(mock_event, lambda_context)
    assert (
        "Environment variable 'TRUST_POLICY' must be a JSON-formatted string "
        "containing the role trust policy."
    ) in str(exc.value)
