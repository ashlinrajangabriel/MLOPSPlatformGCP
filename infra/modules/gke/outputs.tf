output "cluster_id" {
  description = "The ID of the cluster"
  value       = google_container_cluster.primary.id
}

output "cluster_endpoint" {
  description = "The endpoint for the cluster's Kubernetes API"
  value       = google_container_cluster.primary.endpoint
}

output "cluster_ca_certificate" {
  description = "The public certificate authority of the cluster"
  value       = google_container_cluster.primary.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "standard_node_pool" {
  description = "The name of the standard node pool"
  value       = google_container_node_pool.standard.name
}

output "highmem_node_pool" {
  description = "The name of the highmem node pool"
  value       = google_container_node_pool.highmem.name
}

output "gpu_node_pool" {
  description = "The name of the GPU node pool"
  value       = google_container_node_pool.gpu.name
} 