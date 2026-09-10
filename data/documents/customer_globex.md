---
title: Customer Case Profile: Globex Corp
document_id: customer_globex
department: Customer Success
access_tier: Confidential
version: 3.2
last_updated: 2026-03-03
---

# Customer Case Profile — Globex Corp

Globex Corp is a premier European financial services and fintech conglomerate operating across 14 countries. Globex processes over 50 million daily financial transactions through CloudScale Systems.

## Licensed Solutions & Architecture

- **Contract Level**: Enterprise Tier with European Union Data Sovereign Addendum.
- **Core Products in Production**:
  - **Product Orion**: Acts as the central transaction event bus, handling asynchronous trade processing and payment messaging.
  - **Product Atlas**: Serves as the primary compliance and audit portal for Globex's European regulatory filing teams.
- **Deployment Model**: Hosted in Microsoft Azure Kubernetes Service (AKS) within the Germany West Central (Frankfurt) region with Azure Key Vault HSM encryption.

## Regulatory & Compliance Requirements

- **GDPR Compliance**: Globex relies on **Data Anonymization Service** to automatically tokenize bank account numbers (IBANs) and cardholder details before events are committed to Orion topics.
- **Audit Logging**: **Product Atlas** produces weekly automated compliance manifests proving no PII leaves EU territorial boundaries.
- **Authentication Setup**: Fully migrated to **Identity Service v3.2** utilizing Azure AD SAML federated SSO coupled with OAuth 2.1 PKCE client tokens.
