---
title: Multi-Cloud Infrastructure and Deployment Specifications
document_id: deployment
department: Infrastructure
access_tier: Internal
version: 3.2
last_updated: 2026-02-25
---

# Multi-Cloud Infrastructure & Deployment Specifications

CloudScale Systems supports multi-cloud and hybrid on-premise operational topologies to provide maximum flexibility and operational resilience.

## Supported Cloud Infrastructure Providers

### 1. Amazon Web Services (AWS)
- **Primary Workloads**: **Product Nova** analytics clusters and **Product Vega** metric collectors.
- **Compute Layer**: Managed AWS Elastic Kubernetes Service (EKS) utilizing Graviton3 (ARM64) and Intel Ice Lake (x86_64) node pools with Karpenter autoscaling.
- **Storage & Networking**: Amazon Aurora PostgreSQL, Amazon S3 with AWS KMS customer-managed keys, and Transit Gateway VPC peering.
- **Primary Customer on AWS**: **Acme Corp** operates in a dedicated AWS VPC peering architecture connected to us-east-1.

### 2. Microsoft Azure
- **Primary Workloads**: **Product Orion** streaming brokers and the **Product Atlas** governance portal.
- **Compute Layer**: Azure Kubernetes Service (AKS) with Ephemeral OS disks and accelerated networking.
- **Storage & Networking**: Azure Cosmos DB, Azure Blob Storage with customer-managed keys in Azure Key Vault, and Azure ExpressRoute interconnects.
- **Primary Customer on Azure**: **Globex Corp** deploys Orion and Atlas on Azure AKS within European data zones.

### 3. On-Premise & Hybrid Kubernetes
- **Primary Workloads**: Private instances of **Product Nova**, **Product Orion**, and **Product Vega**.
- **Supported Distributions**: Red Hat OpenShift 4.14+ and upstream Kubernetes 1.28+.
- **Requirements**: Hardware Security Module (HSM) or HashiCorp Vault for local key management, and air-gapped container registries.
- **Primary Customer On-Prem**: **Initech** runs an entirely self-hosted deployment of Nova and Orion on their private data center clusters.
