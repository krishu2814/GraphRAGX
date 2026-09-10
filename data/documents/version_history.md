---
title: CloudScale Systems Platform Version History & Changelog
document_id: version_history
department: Product & Release Management
access_tier: Public
version: 3.2
last_updated: 2026-03-06
---

# CloudScale Systems Platform — Version History & Changelog

This changelog outlines major, minor, and breaking changes across CloudScale Systems platform releases, detailing architectural enhancements, deprecated capabilities, and migration requirements.

## Version 3.2 (Released: January 2026) — "Polaris"

### Major Enhancements
- **Identity Service Upgrade**: Full transition to **OAuth 2.1** specifications. Introduced PASETO v4 token support and Ed25519 cryptographic signatures.
- **Product Nova Optimization**: Apache Arrow columnar memory caching enabled by default, yielding 4x faster aggregation queries.
- **Product Atlas Governance**: Automated SOC2 Type II continuous evidence collection and GDPR "Right to be Forgotten" cascading deletion flows.
- **Data Anonymization Service**: Added Differential Privacy noise injection for multi-tenant analytics queries.

### Breaking Changes & Deprecations
- **BREAKING**: OAuth 2.0 Implicit Grant flow is permanently removed from **Identity Service**. Clients connecting to **Product Nova** or **Product Orion** must use Authorization Code with PKCE.
- **BREAKING**: Long-lived refresh tokens (>24 hours) deprecated; single-use refresh token rotation is now enforced.
- **DEPRECATED**: Legacy REST metrics ingestion endpoint in **Product Vega** deprecated in favor of gRPC over mTLS.

---

## Version 3.1 (Released: August 2025) — "Centauri"

### Major Features
- **Product Vega Launch**: High-throughput time-series engine released into production, capable of 10M metrics/second.
- **Policy Engine RBAC & ABAC**: Unified attribute-based access control engine integrated into **Product Nova** and **Product Orion**.
- **Azure AKS Support**: General availability of multi-cloud deployment topologies across AWS and Microsoft Azure.

### Compatibility Notes
- Standardized on OAuth 2.0 with JWT tokens.
- Supported both implicit and code authorization flows.

---

## Version 3.0 (Released: January 2025) — "Genesis"

### Foundational Architecture
- Initial production release of **Product Nova** and **Product Orion**.
- Shared infrastructure services established: **Gateway Service**, **Identity Service**, and **Billing Engine**.
- SOC2 Type I attestation achieved.
