---
title: Product Nova Architecture and Specifications
document_id: product_nova
department: Engineering
access_tier: Internal
version: 3.2
last_updated: 2026-02-01
---

# Product Nova — Architecture & Operational Specifications

Product Nova is CloudScale Systems' flagship cloud analytics platform, designed to deliver high-performance analytical queries and interactive business intelligence across terabyte-scale enterprise datasets.

## Core Capabilities & Architecture

Product Nova is engineered as a distributed multi-tenant service running on AWS Elastic Kubernetes Service (EKS). It leverages columnar data caching in Apache Arrow format, vector execution, and distributed worker nodes coordinated via Raft consensus.

### Service Dependencies
1. **Identity Service**: Product Nova delegates all user authentication and token exchange to Identity Service. In version 3.2, Nova completed its mandatory migration from legacy OAuth 2.0 to **OAuth 2.1**, deprecating implicit grants in favor of PKCE (Proof Key for Code Exchange).
2. **Policy Engine**: Before executing any query, Nova evaluates user access tokens against Policy Engine to enforce row-level security and column-masking policies.
3. **Product Vega**: Nova queries Product Vega directly to retrieve real-time operational metrics and time-series telemetry.
4. **Billing Engine**: Nova reports query compute seconds and storage consumption to Billing Engine for metered tenant billing.

## Deployment Specifications

- **Primary Cloud Infrastructure**: AWS us-east-1 and eu-west-1.
- **Compute Sizing**: EKS clusters with m6i.4xlarge compute instances.
- **Storage Layer**: AWS Aurora PostgreSQL for tenant metadata, AWS S3 for parquet data lakes.
- **Customer Deployments**: Widely utilized by tier-1 enterprise customers, notably **Acme Corp** and **Initech**, both of which rely on Nova for production data intelligence pipelines.
