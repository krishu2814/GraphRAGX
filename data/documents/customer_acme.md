---
title: Customer Case Profile: Acme Corp
document_id: customer_acme
department: Customer Success
access_tier: Confidential
version: 3.2
last_updated: 2026-03-02
---

# Customer Case Profile — Acme Corp

Acme Corp is a multinational retail and logistics enterprise with over $12B in annual revenue. Acme Corp relies on CloudScale Systems to power real-time inventory tracking, supply chain analytics, and predictive fleet re-routing.

## Licensed Solutions & Architecture

- **Contract Level**: Enterprise Tier (Dedicated Account Management).
- **Core Product in Production**: **Product Nova**.
- **Deployment Model**: Deployed in a dedicated single-tenant AWS VPC in us-east-1, peered directly with Acme's internal enterprise network.
- **Underlying Microservice Dependencies**:
  - Authenticates thousands of internal analysts via **Identity Service**.
  - Enforces corporate data classification rules using **Policy Engine**.
  - Ingests logistics telemetry streams through custom pipelines.

## The Version 3.2 Migration & Incident INC-402

During the scheduled maintenance window for the **Version 3.2** upgrade, Acme Corp was the first major enterprise customer transitioned to the new release.
- **Problem**: Acme's custom data connector had hardcoded the legacy OAuth 2.0 implicit token flow. When Version 3.2 of Identity Service strictly enforced **OAuth 2.1** and revoked implicit tokens, Acme's automated ETL jobs received HTTP 401 errors.
- **Operational Impact**: Resulted in a 42-minute data ingestion delay, tracked internally under incident **INC-402**.
- **Resolution**: CloudScale Solutions Architects assisted Acme engineers in updating their client configuration to use Authorization Code Flow with PKCE and PASETO token exchange, fully restoring operations.
