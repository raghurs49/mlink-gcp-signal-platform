output "collector_service_account" {
  value = google_service_account.collector.email
}

output "raw_bucket" {
  value = google_storage_bucket.raw.name
}

output "events_topic" {
  value = google_pubsub_topic.events.name
}

output "analytics_dataset" {
  value = google_bigquery_dataset.analytics.dataset_id
}

