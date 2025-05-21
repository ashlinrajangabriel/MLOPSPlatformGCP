terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }

  backend "gcs" {
    bucket = "developer-platform-tfstate"
    prefix = "prod"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "kubernetes" {
  host                   = "https://${module.gke.cluster_endpoint}"
  token                  = data.google_client_config.current.access_token
  cluster_ca_certificate = base64decode(module.gke.cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = "https://${module.gke.cluster_endpoint}"
    token                  = data.google_client_config.current.access_token
    cluster_ca_certificate = base64decode(module.gke.cluster_ca_certificate)
  }
}

data "google_client_config" "current" {}

module "vpc" {
  source = "../../modules/vpc"

  project_id         = var.project_id
  region            = var.region
  network_name      = "developer-platform-prod"
  subnet_name       = "developer-platform-prod-subnet"
  subnet_ip_range   = "10.0.0.0/20"
  pods_range_name   = "pods"
  pods_ip_range     = "10.16.0.0/14"
  services_range_name = "services"
  services_ip_range  = "10.20.0.0/20"
}

module "gke" {
  source = "../../modules/gke"

  project_id           = var.project_id
  region              = var.region
  cluster_name        = "developer-platform-prod"
  environment         = "prod"
  network             = module.vpc.network_name
  subnetwork          = module.vpc.subnet_name
  pods_range_name     = module.vpc.pods_range_name
  services_range_name = module.vpc.services_range_name
  node_service_account = var.node_service_account

  standard_node_count = 2
  highmem_node_count  = 1
  gpu_node_count      = 1
}

module "argocd" {
  source = "../../modules/argocd"
  
  argocd_hostname     = "argocd.${var.domain}"
  admin_password_hash = var.argocd_admin_password_hash

  depends_on = [module.gke]
}

# IAM for workload identity
resource "google_service_account" "jupyterhub" {
  account_id   = "jupyterhub-sa"
  display_name = "JupyterHub Service Account"
}

resource "google_project_iam_member" "jupyterhub_artifact_registry" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.jupyterhub.email}"
}

resource "google_service_account_iam_binding" "jupyterhub_workload_identity" {
  service_account_id = google_service_account.jupyterhub.name
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[developer-platform/jupyterhub]"
  ]
}

# Artifact Registry repository
resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "developer-platform"
  description   = "Docker repository for developer platform images"
  format        = "DOCKER"
} 