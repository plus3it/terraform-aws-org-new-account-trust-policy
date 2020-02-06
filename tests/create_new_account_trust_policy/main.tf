terraform {
  required_version = "~> 0.12.0"
}

locals {
  trust_policy = <<-EOF
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Action": "sts:AssumeRole",
          "Principal": {
            "AWS": "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"
          },
          "Effect": "Allow"
        }
      ]
    }
    EOF

  update_trust_policy = <<-EOF
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Action": "sts:AssumeRole",
          "Principal": {
            "AWS": "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"
          },
          "Effect": "Allow",
        },
        {
          "Action": "sts:AssumeRoleWithSAML",
          "Principal": {
            "Federated": "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:saml-provider/saml-provider"
          },
          "Effect": "Allow",
        }
      ]
    }
    EOF
}

data "aws_partition" "current" {
}

data "aws_caller_identity" "current" {
}

resource "aws_iam_role" "this" {
  assume_role_policy = local.trust_policy
}

module "new_account_trust_policy" {
  source = "../../"

  assume_role_name = aws_iam_role.this.name
  update_role_name = aws_iam_role.this.name
  trust_policy     = local.update_trust_policy
}
