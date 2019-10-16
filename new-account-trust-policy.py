"""Respond to new account events and update trust policy in the account."""
from __future__ import (absolute_import, division, generator_stop, generators,
                        nested_scopes, print_function, unicode_literals,
                        with_statement)

import argparse
import collections
import json
import logging
import os
import sys
import time

import boto3
import botocore

BOTOCORE_CACHE_DIR = os.environ.get('BOTOCORE_CACHE_DIR')

DEFAULT_LOG_LEVEL = logging.INFO
LOG_LEVELS = collections.defaultdict(
    lambda: DEFAULT_LOG_LEVEL,
    {
        'critical': logging.CRITICAL,
        'error': logging.ERROR,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }
)

# Lambda initializes a root logger that needs to be removed in order to set a
# different logging config
root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)

logging.basicConfig(
    format='%(asctime)s.%(msecs)03dZ [%(name)s][%(levelname)-5s]: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    level=LOG_LEVELS[os.environ.get('LOG_LEVEL', '').lower()])
log = logging.getLogger(__name__)


class AccountCreationFailedException(Exception):
    """Account creation failed."""


class AssumeRoleProvider(object):
    """Provide refreshable credentials for assumed role."""

    METHOD = 'assume-role'

    def __init__(self, fetcher):
        self._fetcher = fetcher

    def load(self):
        """Provide refreshable credentials for assumed role."""
        return botocore.credentials.DeferredRefreshableCredentials(
            self._fetcher.fetch_credentials,
            self.METHOD
        )


def filter_none_values(data):
    """Return a new dictionary excluding items where value was None."""
    return {k: v for k, v in data.items() if v is not None}


def assume_role(
    session,
    role_arn,
    duration=3600,
    session_name=None,
    serial_number=None,
    cache_dir=None,
):
    """Assume a role with refreshable credentials."""
    cache_dir = cache_dir or botocore.credentials.JSONFileCache.CACHE_DIR

    fetcher = botocore.credentials.AssumeRoleCredentialFetcher(
        session.create_client,
        session.get_credentials(),
        role_arn,
        extra_args=filter_none_values({
            'DurationSeconds': duration,
            'RoleSessionName': session_name,
            'SerialNumber': serial_number
        }),
        cache=botocore.credentials.JSONFileCache(working_dir=cache_dir)
    )
    role_session = botocore.session.Session()
    role_session.register_component(
        'credential_provider',
        botocore.credentials.CredentialResolver([AssumeRoleProvider(fetcher)])
    )
    return role_session


def get_new_account_id(event):
    """Return account id for new account events."""
    create_account_status_id = event['detail']['responseElements']['createAccountStatus']['id']  # noqa: E501
    log.info('createAccountStatus = %s', create_account_status_id)

    org = boto3.client('organizations')
    while True:
        account_status = org.describe_create_account_status(
            CreateAccountRequestId=create_account_status_id
        )
        state = account_status['CreateAccountStatus']['State'].upper()
        if state == 'SUCCEEDED':
            return account_status['CreateAccountStatus']['AccountId']
        elif state == 'FAILED':
            log.error(
                'Account creation failed:\n%s', json.dumps(account_status)
            )
            raise AccountCreationFailedException
        else:
            log.info(
                'Account state: %s. Sleeping 5 seconds and will try again...',
                state
            )
            time.sleep(5)


def get_invite_account_id(event):
    """Return account id for invite account events."""
    return event['detail']['requestParameters']['target']['id']


def get_account_id(event):
    """Return account id for supported events."""
    event_name = event['detail']['eventName']
    get_account_id_strategy = {
        'CreateAccount': get_new_account_id,
        'InviteAccountToOrganization': get_invite_account_id,
    }

    return get_account_id_strategy[event_name](event)


def get_caller_identity(sts=None):
    """Return caller identity from STS."""
    if not sts:
        sts = boto3.client('sts')
    return sts.get_caller_identity()


def get_partition():
    """Return AWS partition."""
    return get_caller_identity()['Arn'].split(':')[1]


def main(
    role_arn,
    role_name,
    trust_policy,
    botocore_cache_dir=BOTOCORE_CACHE_DIR,
):
    """Assume role and update role trust policy."""
    # Create a session with an assumed role in the new account
    log.info('Assuming role: %s', role_arn)
    session = assume_role(
        botocore.session.Session(),
        role_arn,
        cache_dir=botocore_cache_dir,
    )

    # Update the role trust policy
    log.info('Updating role: %s', role_name)
    log.info('Applying trust policy:\n%s', trust_policy)
    iam = session.create_client('iam')
    iam.update_assume_role_policy(
        RoleName=role_name,
        PolicyDocument=trust_policy
    )

    log.info('Updated role successfully!')


def lambda_handler(event, context):
    """Entry point for the lambda handler."""
    try:
        log.info('Received event:\n%s', json.dumps(event))

        # Get vars required to update the role
        account_id = get_account_id(event)
        partition = get_partition()
        assume_role_name = os.environ['ASSUME_ROLE_NAME']
        update_role_name = os.environ['UPDATE_ROLE_NAME']
        role_arn = f'arn:{partition}:iam::{account_id}:role/{assume_role_name}'
        trust_policy = os.environ['TRUST_POLICY']
        botocore_cache_dir = BOTOCORE_CACHE_DIR or '/tmp/.aws/boto/cache'

        # Assume the role and update the role trust policy
        main(
            role_arn,
            update_role_name,
            trust_policy,
            botocore_cache_dir=botocore_cache_dir,
        )
    except Exception as exc:
        log.critical('Caught error: %s', exc, exc_info=exc)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Update a role trust policy in another account.'
    )
    parser.add_argument(
        '--role-arn', required=True,
        help='ARN of the IAM role to assume in the target account (case sensitive)'
    )
    parser.add_argument(
        '--role-name', required=True,
        help='Name of the IAM role to update in the target account (case sensitive)'
    )
    parser.add_argument(
        '--trust-policy', required=True,
        help='Trust policy to apply to the role in the target account'
    )

    args = parser.parse_args()
    sys.exit(main(**vars(args)))
