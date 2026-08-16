variable "project_id" {
  description = "GCP project for the synthetic reference deployment"
  type        = string
}

variable "region" {
  description = "Primary deployment region"
  type        = string
  default     = "us-central1"
}

variable "container_image" {
  description = "Immutable image URI built by CI"
  type        = string
}

variable "raw_retention_days" {
  description = "Retention for synthetic raw event objects"
  type        = number
  default     = 30
}

