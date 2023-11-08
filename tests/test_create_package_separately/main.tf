module "test_create_package" {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-lambda.git?ref=v6.4.0"

  create_function = false
  create_package  = true

  recreate_missing_package = false

  runtime     = "python3.8"
  source_path = "${path.module}/../../lambda/src"
}

module "test_create_function" {
  source = "../.."

  assume_role_name = "FOO"
  update_role_name = "BAR"
  trust_policy     = jsonencode({})

  lambda = {
    local_existing_package = "${path.module}/${module.test_create_package.local_filename}"
    create_package         = false
  }
}
