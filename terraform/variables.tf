variable "linode_token" {
  description = "Linode API token"
  type        = string
  sensitive   = true
}

variable "cluster_label" {
  description = "Label for the LKE cluster"
  type        = string
  default     = "feed-digest"
}

variable "k8s_version" {
  description = "Kubernetes version for the LKE cluster"
  type        = string
  default     = "1.34"
}

variable "region" {
  description = "Linode region for the cluster"
  type        = string
  default     = "us-sea"
}

variable "cpu_node_type" {
  description = "Linode instance type for CPU nodes (app, worker, crawler, KServe control plane)"
  type        = string
  default     = "g6-standard-4"
}

variable "gpu_node_type" {
  description = "Linode instance type for GPU node (1x RTX 4000 Ada for vLLM)"
  type        = string
  default     = "g2-gpu-rtx4000a1-m"
}

variable "db_node_type" {
  description = "Linode managed database node type"
  type        = string
  default     = "g6-nanode-1"
}

variable "tags" {
  description = "Tags to apply to the cluster"
  type        = list(string)
  default     = ["feed-digest"]
}
