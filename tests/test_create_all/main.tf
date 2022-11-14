module "test_create_all" {
  source = "../.."

  assume_role_name = "FOO"
  update_role_name = "BAR"
  trust_policy     = jsonencode({})
}
