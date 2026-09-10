---
title: API Platform and Gateway Service Specifications
document_id: api_platform
department: Infrastructure
access_tier: Internal
version: 3.2
last_updated: 2026-02-20
---

# API Platform & Gateway Service Specifications

Gateway Service is the unified ingress and edge routing proxy for all external customer and internal service traffic across CloudScale Systems.

## Architecture and Traffic Management

Gateway Service is built on an Envoy-based reverse proxy architecture with custom WebAssembly (Wasm) filters:
- **Protocol Support**: Ingress traffic accepts HTTP/1.1, HTTP/2, gRPC, and WebSocket protocols.
- **OpenAPI 3.1 & Schema Validation**: Inbound request payloads are strictly validated against versioned OpenAPI specifications before routing to downstream backend services.
- **Mutual TLS (mTLS)**: Enforces end-to-end mTLS across internal microservice communication meshes.

## Rate Limiting & Tier Enforcement

Gateway Service checks tenant plan tiers defined by **Billing Engine**:
- **Starter Tier**: 100 requests per second (RPS), burst allowance of 200.
- **Growth Tier**: 1,000 RPS, burst allowance of 2,500.
- **Enterprise Tier**: Custom SLA up to 25,000 RPS with dedicated gateway instances and IP whitelisting.

## Security Integrations

- Integrates with **Identity Service** for edge token introspection and PKCE validation under OAuth 2.1.
- Evaluates token revocation lists (CRL) to instantly block compromised sessions.
- Directly routes analytical telemetry into **Product Orion** and **Product Vega** for real-time edge monitoring.
