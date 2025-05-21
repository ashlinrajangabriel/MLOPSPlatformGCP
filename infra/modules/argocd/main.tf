terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }
}

resource "kubernetes_namespace" "argocd" {
  metadata {
    name = "argocd"
    labels = {
      name = "argocd"
    }
  }
}

resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = "5.46.7"  # Specify a fixed version for stability
  namespace  = kubernetes_namespace.argocd.metadata[0].name

  values = [
    yamlencode({
      server = {
        extraArgs = ["--insecure"]  # Remove if using HTTPS
        service = {
          type = "ClusterIP"
        }
        ingress = {
          enabled = true
          annotations = {
            "kubernetes.io/ingress.class" = "nginx"
            "cert-manager.io/cluster-issuer" = "letsencrypt-prod"
          }
          hosts = [var.argocd_hostname]
          tls = [{
            secretName = "argocd-server-tls"
            hosts = [var.argocd_hostname]
          }]
        }
      }
      configs = {
        secret = {
          argocdServerAdminPassword = var.admin_password_hash
        }
      }
      applicationSet = {
        enabled = true
      }
    })
  ]

  depends_on = [kubernetes_namespace.argocd]
} 