---
title: Authorization Architecture and Policy Engine Specifications
document_id: authorization
department: Security
access_tier: Internal
version: 3.2
last_updated: 2026-02-18
---

# Authorization Architecture & Policy Engine Specifications

Authorization within CloudScale Systems is governed centrally by **Policy Engine** and supported by **Authz Service**. Together, they decouple business logic from permissions across all products in the ecosystem.

## Dual Authorization Model: RBAC & ABAC

Policy Engine implements a hybrid permission model:
- **Role-Based Access Control (RBAC)**: Assigns users coarse-grained system roles (`SystemAdmin`, `OrgOwner`, `DataAnalyst`, `ComplianceAuditor`, `ReadOnlyViewer`).
- **Attribute-Based Access Control (ABAC)**: Evaluates dynamic context attributes at query evaluation time, including:
  - `user.department`: Restricts data visibility to the user's specific business unit.
  - `user.clearance_level`: Required for viewing PII or financial transaction data.
  - `request.time` and `request.ip_cidr`: Enforces geofencing and working-hours compliance.
  - `tenant.tier`: Restricts advanced capabilities like multi-hop graph exploration or raw export to `Enterprise Tier` accounts.

## Inter-Service Policy Enforcement

1. **Product Nova**: Evaluates table and row permissions through Policy Engine prior to compiling SQL/Arrow query plans.
2. **Product Orion**: Verifies topic publication and subscription rights based on tenant isolation policies.
3. **Product Atlas**: Allows enterprise administrators to create custom ABAC policies visually, which are then compiled into Rego/Open Policy Agent (OPA) rules by Policy Engine.
4. **Gateway Service**: Caches compiled policy bundles for sub-millisecond route gating at edge ingress.
