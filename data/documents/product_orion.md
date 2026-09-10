---
title: Product Orion Distributed Event Broker
document_id: product_orion
department: Engineering
access_tier: Internal
version: 3.2
last_updated: 2026-02-05
---

# Product Orion — Distributed Event Broker & Streaming Engine

Product Orion provides CloudScale Systems with an enterprise-grade message queuing, event streaming, and pub/sub routing infrastructure capable of processing millions of concurrent messages per second with sub-5ms latency.

## Architecture and Core Components

Product Orion is architected around managed Apache Kafka clusters with an abstraction layer written in Go and Rust for high-throughput stream multiplexing.

### Inter-Service Connections
1. **Gateway Service**: All public API requests to publish or subscribe to Orion topics are proxied through Gateway Service, which enforces token validation, SSL termination, and rate limiting.
2. **Policy Engine**: Access to individual topics and stream partitions is governed by Policy Engine. Topic policies determine whether a client can consume, publish, or configure retention policies.
3. **Product Vega**: Orion streams high-priority metric events into Product Vega for immediate time-series indexing.
4. **Identity Service**: Orion validates service account tokens against Identity Service. Following the version 3.2 upgrade, Orion client libraries require PASETO or signed JWT tokens.

## Cloud & Customer Deployments

- **Azure Deployment**: Deployed on Azure Kubernetes Service (AKS) across North Europe and East US regions, utilizing Azure Managed Disks for high IOPS broker storage.
- **Key Customers**:
  - **Globex Corp**: Utilizes Product Orion as its primary enterprise event bus connecting disparate Azure microservices.
  - **Initech**: Utilizes Orion in a hybrid on-premise Kubernetes configuration coupled with Product Nova.
