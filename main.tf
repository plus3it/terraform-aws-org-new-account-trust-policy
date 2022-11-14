locals {
  name = "new-account-trust-policy-${random_string.id.result}"
}

data "aws_partition" "current" {}

data "aws_iam_policy_document" "lambda" {
  statement {
    actions = [
      "organizations:DescribeCreateAccountStatus"
    ]

    resources = [
      "*",
    ]
  }

  statement {
    actions = [
      "sts:AssumeRole"
    ]

    resources = [
      "arn:${data.aws_partition.current.partition}:iam::*:role/${var.assume_role_name}",
    ]
  }
}

resource "random_string" "id" {
  length  = 13
  special = false
}

module "lambda" {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-lambda.git?ref=v4.7.1"

  function_name = local.name

  description = "Update trust policy on IAM Account Role"
  handler     = "new_account_trust_policy.lambda_handler"
  runtime     = "python3.8"
  tags        = var.tags
  timeout     = 300

  attach_policy_json = true
  policy_json        = data.aws_iam_policy_document.lambda.json

  source_path = [
    {
      path             = "${path.module}/lambda/src"
      pip_requirements = true
      patterns         = try(var.lambda.source_patterns, ["!\\.terragrunt-source-manifest"])
    }
  ]

  artifacts_dir            = try(var.lambda.artifacts_dir, "builds")
  create_package           = try(var.lambda.create_package, true)
  ignore_source_code_hash  = try(var.lambda.ignore_source_code_hash, true)
  local_existing_package   = try(var.lambda.local_existing_package, null)
  recreate_missing_package = try(var.lambda.recreate_missing_package, false)
  ephemeral_storage_size   = try(var.lambda.ephemeral_storage_size, null)

  environment_variables = {
    ASSUME_ROLE_NAME = var.assume_role_name
    UPDATE_ROLE_NAME = var.update_role_name
    TRUST_POLICY     = var.trust_policy
    LOG_LEVEL        = var.log_level
  }
}

resource "aws_cloudwatch_event_rule" "this" {
  name          = local.name
  description   = "Managed by Terraform"
  event_pattern = <<-PATTERN
    {
      "source": ["aws.organizations"],
      "detail-type": ["AWS API Call via CloudTrail"],
      "detail": {
        "eventSource": ["organizations.amazonaws.com"],
        "eventName": [
            "InviteAccountToOrganization",
            "CreateAccount",
            "CreateGovCloudAccount"
        ]
      }
    }
    PATTERN
  tags          = var.tags
}

resource "aws_cloudwatch_event_target" "this" {
  rule = aws_cloudwatch_event_rule.this.name
  arn  = module.lambda.lambda_function_arn
}

resource "aws_lambda_permission" "events" {
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.this.arn
}
