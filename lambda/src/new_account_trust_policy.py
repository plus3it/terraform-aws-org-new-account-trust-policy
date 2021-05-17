#!/usr/bin/env python3
"""Respond to new account events by updating trust policy in the account."""
import argparse
import json
import os
import sys
import time

from aws_lambda_powertools import Logger
from aws_assume_role_lib import assume_role
import boto3
import botocore

LOG_LEVEL = os.environ.get("LOG_LEVEL", "info")

LOG = Logger(
    service="new_account_trust_policy",
    level=LOG_LEVEL,
    stream=sys.stderr,
    location="%(name)s.%(funcName)s:%(lineno)d",
    timestamp="%(asctime)s.%(msecs)03dZ",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


class TrustPolicyInvalidArgumentsError(Exception):
    """Account creation failed."""


# ---------------------------------------------------------------------
# Logic specific to handling the event provided to the Lambda handler.


class AccountCreationFailedException(Exception):
    """Account creation failed."""


def get_new_account_id(event):
    """Return account id for new account events."""
    create_account_status_id = (
        event["detail"]
        .get("responseElements", {})
        .get("createAccountStatus", {})["id"]  # fmt: no
    )
    LOG.info("createAccountStatus = %s", create_account_status_id)

    org = boto3.client("organizations")
    while True:
        account_status = org.describe_create_account_status(
            CreateAccountRequestId=create_account_status_id
        )
        state = account_status["CreateAccountStatus"]["State"].upper()
        if state == "SUCCEEDED":
            return account_status["CreateAccountStatus"]["AccountId"]
        if state == "FAILED":
            LOG.error("Account creation failed:\n%s", json.dumps(account_status))
            raise AccountCreationFailedException
        LOG.info("Account state: %s. Sleeping 5 seconds and will try again...", state)
        time.sleep(5)


def get_invite_account_id(event):
    """Return account id for invite account events."""
    return event["detail"]["requestParameters"]["target"]["id"]


def get_account_id(event):
    """Return account id for supported events."""
    event_name = event["detail"]["eventName"]
    get_account_id_strategy = {
        "CreateAccount": get_new_account_id,
        "CreateGovCloudAccount": get_new_account_id,
        "InviteAccountToOrganization": get_invite_account_id,
    }

    return get_account_id_strategy[event_name](event)


def get_partition():
    """Return AWS partition."""
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Arn"].split(":")[1]


# ---------------------------------------------------------------------


def get_session(assume_role_arn):
    """Return boto3 session established using a role arn or AWS profile."""
    function_name = os.environ.get(
        "AWS_LAMBDA_FUNCTION_NAME", os.path.basename(__file__)
    )
    return assume_role(
        boto3.Session(),
        assume_role_arn,
        RoleSessionName=function_name,
        DurationSeconds=3600,
        validate=False,
    )


def main(role_arn, role_name, trust_policy):
    """Assume role and update role trust policy."""
    # Validate trust policy contains properly formatted JSON.  This is
    # not a validation against a schema, so the JSON could still be bad.
    try:
        json.loads(trust_policy)
    except json.decoder.JSONDecodeError as exc:
        # pylint: disable=raise-missing-from
        raise TrustPolicyInvalidArgumentsError(
            f"'trust-policy' contains badly formed JSON: {exc}"
        )

    # Create a session using an assumed role in the new account.
    assumed_role_session = get_session(role_arn)

    # Update the role trust policy.
    iam_client = assumed_role_session.client("iam")
    try:
        iam_client.update_assume_role_policy(
            RoleName=role_name, PolicyDocument=trust_policy
        )
    except (
        botocore.exceptions.ClientError,
        botocore.parsers.ResponseParserError,
    ) as exc:
        LOG.error(
            {
                "role_name": role_name,
                "failure_msg": "Unable to update assume role policy",
                "failure": exc,
            }
        )
        raise TrustPolicyInvalidArgumentsError(exc) from exc
    return 0


def check_for_null_envvars(assume_role_name, update_role_name, trust_policy):
    """Verify the given envvars values are non-null."""
    if not assume_role_name:
        errmsg = (
            "Environment variable 'ASSUME_ROLE_NAME' must provide the "
            "name of the IAM role to assume in target account.",
        )
        LOG.error(errmsg)
        raise TrustPolicyInvalidArgumentsError(errmsg)

    if not update_role_name:
        errmsg = (
            "Environment variable 'UPDATE_ROLE_NAME' must be the name "
            "of the IAM role to update in target account.",
        )
        LOG.error(errmsg)
        raise TrustPolicyInvalidArgumentsError(errmsg)

    if not trust_policy:
        errmsg = (
            "Environment variable 'TRUST_POLICY' must be a "
            "JSON-formatted string containing the role trust policy.",
        )
        LOG.error(errmsg)
        raise TrustPolicyInvalidArgumentsError(errmsg)


@LOG.inject_lambda_context(log_event=True)
def lambda_handler(event, context):  # pylint: disable=unused-argument
    """Entry point for the lambda handler."""
    assume_role_name = os.environ.get("ASSUME_ROLE_NAME")
    update_role_name = os.environ.get("UPDATE_ROLE_NAME")
    trust_policy = os.environ.get("TRUST_POLICY")
    LOG.info(
        {
            "ASSUME_ROLE_NAME": assume_role_name,
            "UPDATE_ROLE_NAME": update_role_name,
            "TRUST_POLICY": trust_policy,
        }
    )
    check_for_null_envvars(assume_role_name, update_role_name, trust_policy)

    # If this handler is invoked for an integration test, exit before
    # invoking any boto3 APIs.
    if os.environ.get("LOCALSTACK_HOSTNAME"):
        return

    try:
        account_id = get_account_id(event)
        partition = get_partition()
        role_arn = f"arn:{partition}:iam::{account_id}:role/{assume_role_name}"

        # Assume the role and update the role trust policy.
        main(role_arn, update_role_name, trust_policy)
    except Exception as exc:
        LOG.critical("Caught error: %s", exc, exc_info=exc)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update a role trust policy in another account."
    )
    parser.add_argument(
        "--role-arn",
        required=True,
        help="ARN of the IAM role to assume in the target account (case sensitive)",
    )
    parser.add_argument(
        "--role-name",
        required=True,
        help="Name of the IAM role to update in the target account (case sensitive)",
    )
    parser.add_argument(
        "--trust-policy",
        required=True,
        help="Trust policy to apply to the role in the target account",
    )

    args = parser.parse_args()
    sys.exit(main(**vars(args)))
