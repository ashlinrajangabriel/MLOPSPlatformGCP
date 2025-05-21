variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The region to host the cluster in"
  type        = string
}

variable "cluster_name" {
  description = "The name of the cluster"
  type        = string
}

variable "environment" {
  description = "The environment this cluster is for (e.g. 'prod', 'staging')"
  type        = string
}

variable "network" {
  description = "The VPC network to host the cluster in"
  type        = string
}

variable "subnetwork" {
  description = "The subnetwork to host the cluster in"
  type        = string
}

variable "pods_range_name" {
  description = "The name of the secondary range for pods"
  type        = string
}

variable "services_range_name" {
  description = "The name of the secondary range for services"
  type        = string
}

variable "node_service_account" {
  description = "The service account to use for the node pools"
  type        = string
}

variable "standard_node_count" {
  description = "Number of nodes in the standard pool"
  type        = number
  default     = 1
}

variable "highmem_node_count" {
  description = "Number of nodes in the highmem pool"
  type        = number
  default     = 1
}

variable "gpu_node_count" {
  description = "Number of nodes in the GPU pool"
  type        = number
  default     = 0
} 