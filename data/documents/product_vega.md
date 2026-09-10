---
title: Product Vega Time-Series Telemetry Engine
document_id: product_vega
department: Engineering
access_tier: Internal
version: 3.2
last_updated: 2026-02-12
---

# Product Vega — High-Throughput Time-Series Telemetry Engine

Product Vega is the real-time metrics ingestion, compression, and analysis powerhouse within CloudScale Systems. It is specifically designed to ingest server telemetry, sensor data, and application performance metrics at massive scale.

## Architecture and Stream Pipeline

Product Vega utilizes a distributed LSM-tree (Log-Structured Merge-tree) storage architecture with Gorilla-based delta-of-delta floating-point compression:
- **Ingestion Pipeline**: Ingests metrics from edge agents via gRPC over mTLS.
- **Inter-Product Integration**:
  - Delivers pre-aggregated metric summaries to **Product Nova** for interactive analytics dashboards.
  - Generates alert threshold breach events and pushes them into **Product Orion** topics for downstream notification workflows.
- **Security & Authorization**: Ingestion endpoints are protected by **Gateway Service** rate limiting, while query authorization is evaluated by **Policy Engine**.

## Deployments and Customer Footprint

- **Infrastructure**: Supported across AWS compute instances and on-premise physical hardware.
- **Enterprise Adoption**: Extensively deployed by **Initech** to monitor distributed manufacturing sensors and internal software operations.
