## terraform-aws-org-new-account-trust-policy Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/) and this project adheres to [Semantic Versioning](http://semver.org/).

### [2.0.1](https://github.com/plus3it/terraform-aws-org-new-account-trust-policy/releases/tag/2.0.1)

**Released**: 2023.04.18

**Summary**:

* Simplifies event rule patterns, relying only on details from cloudtrail event

### 1.0.0

**Commit Delta**: [Change from 0.2.2 release](https://github.com/plus3it/terraform-aws-org-new-account-support-case/compare/0.2.2...1.0.0)

**Released**: 2022.11.14

**Summary**:

*   Simplifies exception handling with a global handler that logs all exceptions
*   Improves event pattern to eliminate loop/wait logic in lambda function.
*   Separates the CreateAccountResult and InviteAccountToOrganization patterns into two event rules.
*   Changed lambda module to one published by terraform-aws-modules, for better long-term support
*   Exposed new `lambda` variable that wraps arguments for the upstream lambda module
*   Added support for creating multiple instances of this module. This achieved by either:
    *   Tailoring the artifact location, by setting `lambda.artifacts_dir` to a different location for each instance
    *   Creating the package separately from the lambda functions, see `tests/test_create_package_separately` for an example

### 0.2.2

**Commit Delta**: [Change from 0.2.1 release](https://github.com/plus3it/terraform-aws-org-new-account-trust-policy/compare/0.2.1...0.2.2)

**Released**: 2021.07.22

**Summary**:

*   Moved common requirements to `requirements_common.txt`.  Dependabot
    does not want to see duplicate requirements.

*   Updated the `Makefile` to take advantage of new targets in tardigrade-ci.

*   Updated the Travis workflow to reflect changes in tardigrade-ci

### 0.2.1

**Commit Delta**: [Change from 0.2.0 release](https://github.com/plus3it/terraform-aws-org-new-account-trust-policy/compare/0.2.0...0.2.1)

**Released**: 2021.05.18

**Summary**:

*   Update aws-assume-role-lib to fix issue where session name exceeded the 64
    character limit.

### 0.2.0

**Commit Delta**: [Change from 0.1.1 release](https://github.com/plus3it/terraform-aws-org-new-account-trust-policy/compare/0.1.1...0.2.0)

**Released**: 2021.05.03

**Summary**:

*   Revise integration test so it can successfully complete the lambda
    invocation.

### 0.1.1

**Commit Delta**: [Change from 0.1.0 release](https://github.com/plus3it/terraform-aws-org-new-account-trust-policy/compare/0.1.0...0.1.1)

**Released**: 2021.04.28

**Summary**:

*   Use a different docker name for the integration tests.

### 0.1.0

**Commit Delta**: [Change from 0.0.0 release](https://github.com/plus3it/terraform-aws-org-new-account-trust-policy/compare/0.0.0...0.1.0)

**Released**: 2021.04.20

**Summary**:

*   Replaced assume_role boilerplate with the aws_assume_role_lib library.
*   Added unit and integration tests.

### 0.0.0

**Commit Delta**: N/A

**Released**: 2019.09.23

**Summary**:

*   Initial release!
