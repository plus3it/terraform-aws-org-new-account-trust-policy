terraform {
  required_version = ">= 0.12"
}

locals {
  name = "new_account_trust_policy_${random_string.id.result}"
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
  source = "git::https://github.com/plus3it/terraform-aws-lambda.git?ref=v1.2.0"

  function_name = local.name
  description   = "Update trust policy on IAM Account Role"
  handler       = "new_account_trust_policy.lambda_handler"
  policy        = data.aws_iam_policy_document.lambda
  runtime       = "python3.6"
  source_path   = "${path.module}/lambda/src"
  timeout       = 300

  environment = {
    variables = {
      ASSUME_ROLE_NAME = var.assume_role_name
      UPDATE_ROLE_NAME = var.update_role_name
      TRUST_POLICY     = var.trust_policy
      LOG_LEVEL        = var.log_level
    }
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
}

resource "aws_cloudwatch_event_target" "this" {
  rule = aws_cloudwatch_event_rule.this.name
  arn  = module.lambda.function_arn
}

resource "aws_lambda_permission" "events" {
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.this.arn
}
