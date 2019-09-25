variable "assume_role_name" {
  description = "Name of the IAM role to assume in the target account (case sensitive)"
  type        = string
}

variable "update_role_name" {
  description = "Name of the IAM role to update in the target account (case sensitive)"
  type        = string
}

variable "trust_policy" {
  description = "JSON string representing the trust policy to apply to the role being updated"
  type        = string
}

variable "log_level" {
  default     = "Info"
  description = "Log level of the lambda output, one of: Debug, Info, Warning, Error, Critical"
  type        = string
}
