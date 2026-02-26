output "cluster_id" {
  description = "ID of the LKE cluster"
  value       = linode_lke_cluster.feed_digest.id
}

output "cluster_status" {
  description = "Status of the LKE cluster"
  value       = linode_lke_cluster.feed_digest.status
}

output "kubeconfig" {
  description = "Base64-encoded kubeconfig for the LKE cluster"
  value       = linode_lke_cluster.feed_digest.kubeconfig
  sensitive   = true
}

output "api_endpoints" {
  description = "Kubernetes API server endpoints"
  value       = linode_lke_cluster.feed_digest.api_endpoints
}

output "pool_ids" {
  description = "IDs of the node pools"
  value       = linode_lke_cluster.feed_digest.pool[*].id
}

output "database_host" {
  description = "PostgreSQL database host"
  value       = linode_database_postgresql_v2.feed_digest.host_primary
  sensitive   = true
}

output "database_port" {
  description = "PostgreSQL database port"
  value       = linode_database_postgresql_v2.feed_digest.port
}

output "database_name" {
  description = "PostgreSQL database name"
  value       = "defaultdb"
}

output "database_username" {
  description = "PostgreSQL database username"
  value       = linode_database_postgresql_v2.feed_digest.root_username
  sensitive   = true
}

output "database_password" {
  description = "PostgreSQL database password"
  value       = linode_database_postgresql_v2.feed_digest.root_password
  sensitive   = true
}

output "database_url" {
  description = "Full PostgreSQL connection string"
  value       = "postgresql://${linode_database_postgresql_v2.feed_digest.root_username}:${linode_database_postgresql_v2.feed_digest.root_password}@${linode_database_postgresql_v2.feed_digest.host_primary}:${linode_database_postgresql_v2.feed_digest.port}/defaultdb?sslmode=require"
  sensitive   = true
}

output "deployment_instructions" {
  description = "Instructions for deploying the application"
  value       = <<-EOT

  ===== LKE CLUSTER READY =====

  Cluster: ${var.cluster_label}
  Region:  ${var.region}

  Next steps:

  1. Save kubeconfig:
     terraform output -raw kubeconfig | base64 -d > kubeconfig.yaml
     export KUBECONFIG=$(pwd)/kubeconfig.yaml

  2. Verify cluster:
     kubectl get nodes

  3. Install KServe (one-time):
     ./k8s/install-kserve.sh

  4. Set environment variables and deploy:
     export DOCKERHUB_USER=your-dockerhub-username
     export DATABASE_URL=$(terraform output -raw database_url)
     ./k8s/deploy.sh

  5. Get external IP:
     kubectl get svc app-service -n feed-digest

  6. Access at: http://<external-ip>

  =============================
  EOT
}
