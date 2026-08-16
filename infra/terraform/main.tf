locals {
  services = toset([
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "monitoring.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com"
  ])
}

resource "google_project_service" "required" {
  for_each           = local.services
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "collector" {
  account_id   = "synthetic-feed-collector"
  display_name = "Synthetic feed collector runtime"
}

resource "google_pubsub_topic" "events" {
  name       = "synthetic-market-events"
  depends_on = [google_project_service.required]

  message_retention_duration = "86600s"
}

resource "google_pubsub_subscription" "normalizer" {
  name  = "synthetic-market-normalizer"
  topic = google_pubsub_topic.events.id

  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_topic" "dead_letter" {
  name = "synthetic-market-events-dlq"
}

resource "google_storage_bucket" "raw" {
  name                        = "${var.project_id}-synthetic-market-raw"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning { enabled = true }
  retention_policy {
    retention_period = var.raw_retention_days * 86400
  }
  lifecycle_rule {
    condition { age = var.raw_retention_days }
    action { type = "Delete" }
  }
}

resource "google_bigquery_dataset" "analytics" {
  dataset_id                 = "synthetic_market_signal_demo"
  location                   = var.region
  delete_contents_on_destroy = false
  description                = "Synthetic normalized records, state and explainable signals"
}

resource "google_secret_manager_secret" "feed_key" {
  secret_id = "synthetic-feed-api-key"
  replication { auto {} }
}

resource "google_cloud_run_v2_job" "collector" {
  name     = "synthetic-feed-collector"
  location = var.region

  template {
    task_count = 1
    template {
      service_account = google_service_account.collector.email
      max_retries     = 3
      timeout         = "86400s"
      containers {
        image = var.container_image
        args  = ["--config", "/app/configs/subscriptions.json", "--output", "/tmp/evidence"]
        env {
          name = "MLINK_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.feed_key.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }
  depends_on = [google_project_service.required]
}

resource "google_project_iam_member" "collector_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.collector.email}"
}

resource "google_project_iam_member" "collector_secret" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.collector.email}"
}

resource "google_monitoring_alert_policy" "no_events" {
  display_name = "Synthetic collector has no published events"
  combiner     = "OR"
  conditions {
    display_name = "No Pub/Sub publish operations"
    condition_threshold {
      filter          = "resource.type=\"pubsub_topic\" AND metric.type=\"pubsub.googleapis.com/topic/send_request_count\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "300s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }
  documentation {
    content   = "Check collector health, authentication, heartbeat freshness and subscription acknowledgements."
    mime_type = "text/markdown"
  }
}

