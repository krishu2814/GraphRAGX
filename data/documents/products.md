---
title: Product Portfolio Catalog
document_id: products
department: Product
access_tier: Public
version: 3.2
last_updated: 2026-01-20
---

# CloudScale Systems — Product Portfolio Catalog

CloudScale Systems provides a cohesive ecosystem of four enterprise products designed to function independently or in a unified multi-cloud architecture.

## Product Portfolio Summary

### 1. Product Nova
- **Category**: Enterprise Cloud Analytics Platform
- **Primary Capabilities**: Real-time distributed data analysis, machine learning inference visualization, and automated query optimization.
- **Underlying Microservices**: Relies directly on **Identity Service** for token authentication, **Policy Engine** for row-level authorization, and ingests metrics from **Product Vega**.
- **Primary Cloud Target**: Deployed natively on AWS using Elastic Kubernetes Service (EKS) and Aurora PostgreSQL.

### 2. Product Orion
- **Category**: Distributed Event Broker & Messaging Backbone
- **Primary Capabilities**: Low-latency stream routing, durable event replay, and partitioned pub/sub messaging.
- **Underlying Microservices**: Backed by Apache Kafka clusters, integrated with **Gateway Service** for rate-limited public ingress, and regulated by **Policy Engine**.
- **Primary Cloud Target**: Deployed on Microsoft Azure Kubernetes Service (AKS) and AWS.

### 3. Product Atlas
- **Category**: Enterprise Governance and Compliance Portal
- **Primary Capabilities**: Centralized policy definition, access audit log inspection, SOC2 evidence gathering, and automated data retention enforcement.
- **Underlying Microservices**: Depends on **Product Nova** for analytical audit queries, **Policy Engine** for policy compilation, and **Data Anonymization Service** for privacy redaction.
- **Primary Cloud Target**: Multi-cloud management portal hosted across AWS and Azure.

### 4. Product Vega
- **Category**: High-Throughput Time-Series Engine
- **Primary Capabilities**: Ingestion and indexing of over 10 million telemetry data points per second with nanosecond timestamps.
- **Underlying Microservices**: Streams aggregated summaries into **Product Nova** and publishes operational alert events into **Product Orion**.
- **Primary Cloud Target**: Bare-metal on-premise clusters and AWS compute instances.
