---
title: Metered Billing Architecture and Billing Engine Specifications
document_id: billing
department: Finance & Billing
access_tier: Confidential
version: 3.2
last_updated: 2026-02-26
---

# Metered Billing Architecture & Billing Engine Specifications

The **Billing Engine** is CloudScale Systems' specialized financial telemetry and metering microservice responsible for real-time usage calculation, invoice reconciliation, and subscription lifecycle management.

## Metering Architecture

Billing Engine aggregates consumption signals emitted from across all product instances:
- **Product Nova Metering**: Measures query compute units (QCU-hours) and active columnar cache gigabytes stored in memory.
- **Product Orion Metering**: Tracks event ingress volume (in gigabytes) and active consumer group connection hours.
- **Product Vega Metering**: Measures time-series write operations (per 100,000 metrics ingested).
- **Product Atlas Metering**: Charged as a flat monthly platform subscription based on monitored user seats.

## Invoicing & Payment Gateways

- **Stripe Billing Integration**: Credit card and ACH debit transactions for Starter and Growth tier accounts are processed automatically via Stripe APIs.
- **Enterprise Invoicing**: Custom payment terms (Net-30, Net-60) and multi-year master service agreements (MSAs) are invoiced through enterprise ERP connectors.
- **Quota & Throttle Signals**: When tenants exhaust monthly allowances, Billing Engine communicates directly with **Gateway Service** to enforce rate-limiting throttles or burst overage billing.
