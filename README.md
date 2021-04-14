# terraform-aws-org-new-account-trust-policy

A Terraform module to help set the trust policy on a specified role when new
accounts are added or invited to an AWS Organization.

When creating a new account via AWS Organizations, an admin role is created in
the account with a trust policy that allows the master account to assume it. If
your identity principals are in the master account, this is fine. You will be
able to assume role into the new account with no problem.

However, when you use a _different_ account for your identity principals, those
principals will not have permission to assume role into the new account's admin
role because the trust policy will not allow _your_ identity account to assume
the role.

This module uses CloudWatch Events to identify when new accounts are added or
invited to an AWS Organization, and triggers a Lambda function that will
assume role into the account and update the trust policy.

## CloudFormation Support

If you prefer CloudFormation, a CloudFormation template is provided that does
the same thing as the Terraform module. To deploy it, first create the package,
then deploy it:

```bash
aws cloudformation package --template new_account_trust_policy.yaml --output-template-file package.yaml --s3-bucket <your-s3-bucket>
aws cloudformation deploy --profile mock-dev --template package.yaml --capabilities CAPABILITY_IAM --stack-name <stack-name> --parameter-overrides AssumeRoleName=<role-to-assume> UpdateRoleName=<role-to-update> TrustPolicy=<trust-policy-to-apply>
```

<!-- BEGIN TFDOCS -->
## Requirements

| Name | Version |
|------|---------|
| terraform | >= 0.12 |

## Providers

| Name | Version |
|------|---------|
| aws | n/a |
| random | n/a |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| assume\_role\_name | Name of the IAM role to assume in the target account (case sensitive) | `string` | n/a | yes |
| trust\_policy | JSON string representing the trust policy to apply to the role being updated | `string` | n/a | yes |
| update\_role\_name | Name of the IAM role to update in the target account (case sensitive) | `string` | n/a | yes |
| log\_level | Log level of the lambda output, one of: debug, info, warning, error, critical | `string` | `"info"` | no |

## Outputs

| Name | Description |
|------|-------------|
| aws\_cloudwatch\_event\_rule | The cloudwatch event rule object |
| aws\_cloudwatch\_event\_target | The cloudWatch event target object |
| aws\_lambda\_permission\_events | The lambda permission object for cloudwatch event triggers |
| lambda | The lambda module object |

<!-- END TFDOCS -->
