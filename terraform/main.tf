# Terraform configuration for Feed Digest on LKE
# Creates an LKE cluster with CPU and GPU node pools + managed PostgreSQL
# GPU node stays warm; KServe handles pod-level scale-to-zero

terraform {
  required_version = ">= 1.0"

  required_providers {
    linode = {
      source  = "linode/linode"
      version = "~> 2.0"
    }
  }
}

provider "linode" {
  token = var.linode_token
}

# LKE Kubernetes Cluster
resource "linode_lke_cluster" "feed_digest" {
  label       = var.cluster_label
  k8s_version = var.k8s_version
  region      = var.region
  tags        = var.tags

  # CPU node pool for app, worker, crawler, and KServe control plane
  pool {
    type  = var.cpu_node_type
    count = 3

    autoscaler {
      min = 3
      max = 4
    }
  }

  # GPU node pool for vLLM inference (1x RTX 4000 Ada)
  # Node stays warm; KServe manages pod-level scale-to-zero
  pool {
    type  = var.gpu_node_type
    count = 1

    autoscaler {
      min = 1
      max = 1
    }
  }
}

# Managed PostgreSQL database
resource "linode_database_postgresql_v2" "feed_digest" {
  label     = "${var.cluster_label}-db"
  engine_id = "postgresql/16"
  region    = var.region
  type      = var.db_node_type

  allow_list = []
}
