#!/usr/bin/env python3
"""Respond to new account events by updating trust policy in the account."""
import argparse
import json
import os
import sys

from aws_lambda_powertools import Logger
from aws_assume_role_lib import assume_role, generate_lambda_session_name
import boto3

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


def exception_hook(exc_type, exc_value, exc_traceback):
    """Log all exceptions with hook for sys.excepthook."""
    LOG.exception(
        "%s: %s",
        exc_type.__name__,
        exc_value,
        exc_info=(exc_type, exc_value, exc_traceback),
    )


def get_new_account_id(event):
    """Return account id for new account events."""
    return event["detail"]["serviceEventDetails"]["createAccountStatus"]["accountId"]


def get_invite_account_id(event):
    """Return account id for invite account events."""
    return event["detail"]["requestParameters"]["target"]["id"]


def get_account_id(event):
    """Return account id for supported events."""
    event_name = event["detail"]["eventName"]
    get_account_id_strategy = {
        "CreateAccountResult": get_new_account_id,
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
    if not assume_role_arn:
        return boto3.session.Session()

    function_name = os.environ.get(
        "AWS_LAMBDA_FUNCTION_NAME", os.path.basename(__file__)
    )

    LOG.info(
        {
            "comment": f"Assuming role ARN ({assume_role_arn})",
            "assume_role_arn": assume_role_arn,
        }
    )

    return assume_role(
        boto3.Session(),
        assume_role_arn,
        RoleSessionName=generate_lambda_session_name(function_name),
        validate=False,
    )


def main(role_arn, role_name, trust_policy):
    """Assume role and update role trust policy."""
    # Validate trust policy contains properly formatted JSON.  This is
    # not a validation against a schema, so the JSON could still be bad.
    json.loads(trust_policy)

    # Create a session using an assumed role in the new account.
    session = get_session(role_arn)

    # Update the role trust policy.
    LOG.info(
        {
            "comment": f"Updating IAM role ({role_name})",
            "role_name": role_name,
            "trust_policy": trust_policy,
        }
    )
    iam_client = session.client("iam")
    iam_client.update_assume_role_policy(
        RoleName=role_name, PolicyDocument=trust_policy
    )


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

    account_id = get_account_id(event)
    partition = get_partition()
    role_arn = f"arn:{partition}:iam::{account_id}:role/{assume_role_name}"

    # Assume the role and update the role trust policy.
    main(role_arn, update_role_name, trust_policy)


# Configure exception handler
sys.excepthook = exception_hook

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
