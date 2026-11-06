# Agent Instructions

Before starting any task in this repository:

1. Run `make agents/sync`. It writes the shared Plus3 IT instructions for this repository's tardigrade-ci version to `.agents/plus3it/AGENTS.md`.
2. Read `.agents/plus3it/AGENTS.md` and follow it together with this file. If the sync fails, tell the user, and don't guess the conventions.

These rules always apply, even without the shared instructions:

- Don't push, open pull requests, publish releases, or apply infrastructure changes unless the user asks. List those steps for a person in your final report.
- Don't edit files under `.agents/plus3it/`; they are generated and overwritten by the sync.

@.agents/plus3it/AGENTS.md

## Repository-specific

### Purpose

This Terraform module deploys a Python Lambda function that updates the trust policy of an IAM role in an AWS account when that account is created in, or invited to, an AWS Organization. The function assumes a role in the new account (`assume_role_name`) and applies the given trust policy to another role (`update_role_name`). EventBridge rules for the `CreateAccountResult` and `InviteAccountToOrganization` events trigger the function. The main inputs are `assume_role_name`, `update_role_name` and `trust_policy`; the outputs are `lambda`, `aws_cloudwatch_event_rule`, `aws_cloudwatch_event_target` and `aws_lambda_permission_events`.

### Module-specific files

- `lambda/src/` — Source of the Lambda function (`new_account_trust_policy.py`), packaged by the module through the upstream Lambda module; `requirements.txt` lists the runtime packages
- `lambda/tests/` — Python unit tests for the Lambda function (`test_new_account_trust_policy.py`)
- `requirements/` — `requirements_common.txt`, `requirements_dev.txt` (pytest and moto for the unit tests) and `requirements_test.txt` (tftest and localstack-client for the Terraform tests)
- `tests/` — `test_terraform_install.py` (pytest with tftest against LocalStack), `localstack.tf` (AWS provider endpoints for LocalStack), `docker-compose-localstack.yml`, and the scenario directories `test_create_all/` and `test_create_package_separately/`
- `Dockerfile` and `Dockerfile_test` — Images that install the Python requirements on top of the tardigrade-ci image; see Deviations
- `new_account_trust_policy.yaml` — CloudFormation template for the same function, as an alternative to the Terraform module
- `examples/create_new_account_trust_policy/` — Example usage of the module

### Deviations from the terraform-module profile

- The Python unit tests run in CI as a separate `unit-test` job in `.github/workflows/test.yml`, next to the shared `test` job. The job runs `make docker/run target=pytest/lambda/tests`, which runs `pytest lambda/tests` inside a container. The tardigrade-ci `docker/run` target uses the image named after the repository directory and builds it from `Dockerfile` if it is not found, and that image installs `lambda/src/requirements.txt` and the files in `requirements/`.
- The Makefile exports `PYTHONPATH` with `./lambda/src` appended, and sets `TERRAFORM_PYTEST_DIR` to `$(PWD)/tests`. The second setting makes the tardigrade-ci `mockstack/up`, `mockstack/down`, `mockstack/pytest` and `terraform/pytest` targets use `tests/` (its `docker-compose-localstack.yml` and `test_terraform_install.py`) instead of the default test directory in tardigrade-ci. The shared `test` job runs `make mockstack/pytest`, which uses the image built from `Dockerfile`.
- `mockstack/pytest/lambda` is a custom target. It runs `terraform/pytest` in a container on the LocalStack network, with `LOCALSTACK_HOST=localstack`, built from `Dockerfile_test` (which installs only `requirements/requirements_test.txt`) and tagged `new-account-trust-policy-integration-test:latest`. The README uses it after `make mockstack/up`, and cleanup is `make mockstack/clean`. CI does not call it.
- `python/deps` is a custom target that runs `python -m pip install -r lambda/src/requirements.txt`. `pytest/deps` is a custom target that installs `lambda/tests/requirements_dev.txt` and `tests/requirements_test.txt`. Neither file exists; the requirements files are in `requirements/`, so `pytest/deps` fails as written. CI does not call either target.
- `tests/test_terraform_install.py` applies the module at the repository root (the first directory at or above the current one that holds `*.tf` files) together with `tests/localstack.tf`. It does not use the scenario directories under `tests/`.
