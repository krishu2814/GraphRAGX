---
title: Authentication Architecture and Identity Service Specifications
document_id: authentication
department: Security
access_tier: Internal
version: 3.2
last_updated: 2026-02-15
---

# Authentication Architecture & Identity Service Specifications

Identity Service is the central authentication authority for all CloudScale Systems products, customer portals, and internal microservices. It manages user credentials, single sign-on (SSO) integrations, multi-factor authentication (MFA), and cryptographic token issuance.

## The Version 3.2 Authentication Migration

A critical milestone in the CloudScale Systems engineering roadmap occurred with the release of **Version 3.2**.

### Breaking Changes: OAuth 2.0 Deprecation vs OAuth 2.1 Enforcement
- **Legacy Version 3.1 Architecture**:
  - Utilized OAuth 2.0 with standard Bearer tokens.
  - Allowed implicit grant flow for single-page applications.
  - Refresh tokens were long-lived (90 days) without mandatory rotation.
- **Modern Version 3.2 Architecture**:
  - Strictly enforces **OAuth 2.1** standards across all products and APIs.
  - **Implicit Flow Removed**: Single-page applications and client SDKs must adopt Authorization Code Flow with PKCE (Proof Key for Code Exchange).
  - **Token Format Upgrade**: Introduced PASETO (Platform-Agnostic Security Tokens) v4 public tokens alongside signed JSON Web Tokens (JWT) using Ed25519 signatures.
  - **Mandatory Refresh Token Rotation**: Refresh tokens expire upon single use and must be exchanged immediately.

### Products Impacted by Version 3.2 Authentication Migration
The following products and services directly integrate with Identity Service and require client updates for Version 3.2 compatibility:
1. **Product Nova**: Migrated in release v3.2.0; legacy API clients connecting to Nova with OAuth 2.0 implicit tokens will receive HTTP 401 Unauthorized.
2. **Product Orion**: Streaming client SDKs require Ed25519 token signatures as of v3.2.1.
3. **Gateway Service**: Updated to reject non-PKCE token exchanges.

### Customer Operational Impact
Enterprise customers using dedicated client integrations against Product Nova or Product Orion must upgrade their authentication libraries before migrating to Version 3.2. In particular, **Acme Corp** experienced initial configuration challenges during their v3.2 staging migration (tracked under incident INC-402).
