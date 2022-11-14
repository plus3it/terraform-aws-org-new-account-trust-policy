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

## Testing

To set up and run tests: 

```
# Ensure the dependencies are installed on your system.
make python/deps
make pytest/deps

# Start up a mock AWS stack:
make mockstack/up

# Run unit tests:
make docker/run target=pytest/lambda/tests

# Run the tests:
make mockstack/pytest/lambda

# Shut down the mock AWS stack and clean up docker images:
make mockstack/clean
```

<!-- BEGIN TFDOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 0.13.1 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | >= 4.9 |
| <a name="requirement_external"></a> [external](#requirement\_external) | >= 1.0 |
| <a name="requirement_local"></a> [local](#requirement\_local) | >= 1.0 |
| <a name="requirement_null"></a> [null](#requirement\_null) | >= 2.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | >= 4.9 |
| <a name="provider_random"></a> [random](#provider\_random) | n/a |

## Resources

| Name | Type |
|------|------|
| [aws_iam_policy_document.lambda](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_partition.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/partition) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_assume_role_name"></a> [assume\_role\_name](#input\_assume\_role\_name) | Name of the IAM role to assume in the target account (case sensitive) | `string` | n/a | yes |
| <a name="input_trust_policy"></a> [trust\_policy](#input\_trust\_policy) | JSON string representing the trust policy to apply to the role being updated | `string` | n/a | yes |
| <a name="input_update_role_name"></a> [update\_role\_name](#input\_update\_role\_name) | Name of the IAM role to update in the target account (case sensitive) | `string` | n/a | yes |
| <a name="input_event_types"></a> [event\_types](#input\_event\_types) | Event types that will trigger this lambda | `set(string)` | <pre>[<br>  "CreateAccountResult",<br>  "InviteAccountToOrganization"<br>]</pre> | no |
| <a name="input_lambda"></a> [lambda](#input\_lambda) | Map of any additional arguments for the upstream lambda module. See <https://github.com/terraform-aws-modules/terraform-aws-lambda> | `any` | `{}` | no |
| <a name="input_log_level"></a> [log\_level](#input\_log\_level) | Log level of the lambda output, one of: debug, info, warning, error, critical | `string` | `"info"` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags that are passed to resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_aws_cloudwatch_event_rule"></a> [aws\_cloudwatch\_event\_rule](#output\_aws\_cloudwatch\_event\_rule) | The cloudwatch event rule object |
| <a name="output_aws_cloudwatch_event_target"></a> [aws\_cloudwatch\_event\_target](#output\_aws\_cloudwatch\_event\_target) | The cloudWatch event target object |
| <a name="output_aws_lambda_permission_events"></a> [aws\_lambda\_permission\_events](#output\_aws\_lambda\_permission\_events) | The lambda permission object for cloudwatch event triggers |
| <a name="output_lambda"></a> [lambda](#output\_lambda) | The lambda module object |

<!-- END TFDOCS -->
