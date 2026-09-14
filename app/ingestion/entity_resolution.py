"""Entity resolution, canonicalization, and alias deduplication engine."""

import logging
import re
from typing import Any
from pydantic import BaseModel, Field

from app.models.entities import CanonicalEntity, Entity, EntityType
from app.models.relationships import Relationship

logger = logging.getLogger(__name__)


class EntityResolver:
    """Consolidates disparate surface mentions and aliases into unified CanonicalEntity clusters."""

    # Curated canonical dictionaries for domain terms with known aliases
    CANONICAL_CLUSTERS: list[dict[str, Any]] = [
        {
            "canonical_id": "entity:product:nova",
            "canonical_name": "Product Nova",
            "type": EntityType.PRODUCT,
            "description": "CloudScale's flagship distributed cloud analytics platform",
            "aliases": ["Nova", "Product Nova", "Nova Platform", "Nova Analytics"],
        },
        {
            "canonical_id": "entity:product:orion",
            "canonical_name": "Product Orion",
            "type": EntityType.PRODUCT,
            "description": "Distributed event broker and stream routing engine backed by Apache Kafka",
            "aliases": ["Orion", "Product Orion", "Orion Broker", "Orion Streaming"],
        },
        {
            "canonical_id": "entity:product:atlas",
            "canonical_name": "Product Atlas",
            "type": EntityType.PRODUCT,
            "description": "Enterprise compliance, policy administration, and audit portal",
            "aliases": ["Atlas", "Product Atlas", "Atlas Portal", "Governance Portal"],
        },
        {
            "canonical_id": "entity:product:vega",
            "canonical_name": "Product Vega",
            "type": EntityType.PRODUCT,
            "description": "High-throughput time-series telemetry and metric engine",
            "aliases": ["Vega", "Product Vega", "Vega Engine", "Vega Telemetry"],
        },
        {
            "canonical_id": "entity:service:identity_service",
            "canonical_name": "Identity Service",
            "type": EntityType.SERVICE,
            "description": "Centralized authentication and OAuth token issuance service",
            "aliases": ["Identity Service", "IdP", "Identity Provider", "Auth Service"],
        },
        {
            "canonical_id": "entity:service:policy_engine",
            "canonical_name": "Policy Engine",
            "type": EntityType.SERVICE,
            "description": "Centralized authorization engine evaluating RBAC and ABAC policies",
            "aliases": ["Policy Engine", "Centralized Policy Engine", "OPA Engine"],
        },
        {
            "canonical_id": "entity:service:gateway_service",
            "canonical_name": "Gateway Service",
            "type": EntityType.SERVICE,
            "description": "Envoy-based API edge gateway enforcing mTLS and rate limiting",
            "aliases": ["Gateway Service", "API Gateway", "Gateway Proxy"],
        },
        {
            "canonical_id": "entity:service:data_anonymization_service",
            "canonical_name": "Data Anonymization Service",
            "type": EntityType.SERVICE,
            "description": "Privacy engineering microservice performing PII redaction and tokenization",
            "aliases": ["Data Anonymization Service", "Anonymization Service", "Privacy Service"],
        },
        {
            "canonical_id": "entity:service:billing_engine",
            "canonical_name": "Billing Engine",
            "type": EntityType.SERVICE,
            "description": "Financial metering and tenant invoicing calculation engine",
            "aliases": ["Billing Engine", "Metering Engine"],
        },
        {
            "canonical_id": "entity:customer:acme_corp",
            "canonical_name": "Acme Corp",
            "type": EntityType.CUSTOMER,
            "description": "Multinational retail and logistics enterprise subscriber on AWS",
            "aliases": ["Acme Corp", "Acme", "Acme Corporation"],
        },
        {
            "canonical_id": "entity:customer:globex_corp",
            "canonical_name": "Globex Corp",
            "type": EntityType.CUSTOMER,
            "description": "European financial services and fintech conglomerate on Azure",
            "aliases": ["Globex Corp", "Globex", "Globex Corporation"],
        },
        {
            "canonical_id": "entity:customer:initech",
            "canonical_name": "Initech",
            "type": EntityType.CUSTOMER,
            "description": "Defense, aerospace, and high-security manufacturing contractor",
            "aliases": ["Initech", "Initech Defense"],
        },
        {
            "canonical_id": "entity:version:version_3_2",
            "canonical_name": "Version 3.2",
            "type": EntityType.VERSION,
            "description": "Platform release enforcing OAuth 2.1 and Arrow columnar caching",
            "aliases": ["Version 3.2", "v3.2", "3.2", "Polaris", "Release 3.2"],
        },
        {
            "canonical_id": "entity:version:version_3_1",
            "canonical_name": "Version 3.1",
            "type": EntityType.VERSION,
            "description": "Platform release launching Product Vega and Azure AKS support",
            "aliases": ["Version 3.1", "v3.1", "3.1", "Centauri"],
        },
        {
            "canonical_id": "entity:technology:oauth_2_1",
            "canonical_name": "OAuth 2.1",
            "type": EntityType.TECHNOLOGY,
            "description": "Modern authorization framework requiring PKCE and deprecating implicit grant",
            "aliases": ["OAuth 2.1", "OAuth2.1"],
        },
        {
            "canonical_id": "entity:technology:oauth_2_0",
            "canonical_name": "OAuth 2.0",
            "type": EntityType.TECHNOLOGY,
            "description": "Legacy authorization framework with implicit grant support",
            "aliases": ["OAuth 2.0", "OAuth2.0", "OAuth 2"],
        },
        {
            "canonical_id": "entity:incident:inc_402",
            "canonical_name": "INC-402",
            "type": EntityType.INCIDENT,
            "description": "Version 3.2 token invalidation outage impacting Acme Corp ETL pipeline",
            "aliases": ["INC-402", "Incident 402", "Incident INC-402"],
        },
        {
            "canonical_id": "entity:policy:soc2_type_ii",
            "canonical_name": "SOC2 Type II",
            "type": EntityType.POLICY,
            "description": "Security, availability, and confidentiality audit certification",
            "aliases": ["SOC2 Type II", "SOC2", "SOC 2", "SOC 2 Type II"],
        },
        {
            "canonical_id": "entity:policy:gdpr",
            "canonical_name": "GDPR",
            "type": EntityType.POLICY,
            "description": "General Data Protection Regulation governing EU data privacy and residency",
            "aliases": ["GDPR", "General Data Protection Regulation"],
        },
        {
            "canonical_id": "entity:organization:cloudscale",
            "canonical_name": "CloudScale Systems",
            "type": EntityType.ORGANIZATION,
            "description": "Enterprise cloud intelligence and distributed data infrastructure provider",
            "aliases": ["CloudScale Systems", "CloudScale", "CloudScale Corp"],
        },
        {
            "canonical_id": "entity:technology:kafka",
            "canonical_name": "Apache Kafka",
            "type": EntityType.TECHNOLOGY,
            "description": "Distributed streaming event bus backing Product Orion",
            "aliases": ["Apache Kafka", "Kafka", "Kafka Cluster"],
        },
        {
            "canonical_id": "entity:technology:arrow",
            "canonical_name": "Apache Arrow",
            "type": EntityType.TECHNOLOGY,
            "description": "In-memory columnar data format used for Nova analytics caching",
            "aliases": ["Apache Arrow", "Arrow", "Arrow Format"],
        },
        {
            "canonical_id": "entity:technology:redis",
            "canonical_name": "Redis",
            "type": EntityType.TECHNOLOGY,
            "description": "In-memory key-value cache used for session and token management",
            "aliases": ["Redis", "Redis Cache"],
        },
        {
            "canonical_id": "entity:technology:envoy",
            "canonical_name": "Envoy Proxy",
            "type": EntityType.TECHNOLOGY,
            "description": "High-performance edge proxy underpinning Gateway Service",
            "aliases": ["Envoy Proxy", "Envoy"],
        },
        {
            "canonical_id": "entity:plan:developer",
            "canonical_name": "Developer Plan",
            "type": EntityType.PLAN,
            "description": "Entry-level free tier for prototyping and individual developers",
            "aliases": ["Developer Plan", "Free Tier", "Developer Tier", "Free Plan", "Starter Tier"],
        },
        {
            "canonical_id": "entity:plan:pro",
            "canonical_name": "Pro Plan",
            "type": EntityType.PLAN,
            "description": "Standard business plan with 99.9% SLA and dedicated support",
            "aliases": ["Pro Plan", "Pro Tier", "Professional Plan", "Growth Tier"],
        },
        {
            "canonical_id": "entity:plan:enterprise",
            "canonical_name": "Enterprise Plan",
            "type": EntityType.PLAN,
            "description": "Mission-critical custom enterprise plan with 99.99% SLA and HIPAA/SOC2",
            "aliases": ["Enterprise Plan", "Enterprise Tier", "Custom Tier"],
        },
    ]

    def __init__(self) -> None:
        self.alias_to_canonical_map: dict[str, dict[str, Any]] = {}
        self._build_alias_index()

    def _build_alias_index(self) -> None:
        """Populate lookup index mapping lowercase alias strings and IDs to canonical clusters."""
        for cluster in self.CANONICAL_CLUSTERS:
            cid = cluster["canonical_id"].lower().strip()
            self.alias_to_canonical_map[cid] = cluster
            slug = cid.split(":")[-1]
            self.alias_to_canonical_map[slug] = cluster
            self.alias_to_canonical_map[f"entity:{slug}"] = cluster

            for alias in cluster["aliases"]:
                self.alias_to_canonical_map[alias.lower().strip()] = cluster
            self.alias_to_canonical_map[cluster["canonical_name"].lower().strip()] = cluster

    def resolve_entity(self, raw_entity: Entity) -> CanonicalEntity:
        """Map an individual raw entity mention to its canonical representation."""
        raw_clean = raw_entity.name.strip().lower()

        # 1. Exact alias or ID lookup
        if raw_clean in self.alias_to_canonical_map:
            cluster = self.alias_to_canonical_map[raw_clean]
            return CanonicalEntity(
                canonical_id=cluster["canonical_id"],
                canonical_name=cluster["canonical_name"],
                primary_type=cluster["type"],
                description=cluster["description"],
                aliases=cluster["aliases"],
                source_mentions=[raw_entity.name],
                metadata=raw_entity.metadata,
            )

        # 2. Token boundary containment matching (longest match first)
        for alias_key in sorted(self.alias_to_canonical_map.keys(), key=len, reverse=True):
            if len(alias_key) < 3:
                continue
            pattern_str = r"(?<![a-zA-Z0-9])" + re.escape(alias_key) + r"(?![a-zA-Z0-9])"
            if re.search(pattern_str, raw_clean):
                cluster = self.alias_to_canonical_map[alias_key]
                return CanonicalEntity(
                    canonical_id=cluster["canonical_id"],
                    canonical_name=cluster["canonical_name"],
                    primary_type=cluster["type"],
                    description=cluster["description"],
                    aliases=cluster["aliases"],
                    source_mentions=[raw_entity.name],
                    metadata=raw_entity.metadata,
                )

        # 3. Fallback: Create ad-hoc canonical entity
        slug = re.sub(r"[^a-z0-9]+", "_", raw_entity.name.lower()).strip("_")
        canonical_id = f"entity:{raw_entity.type.value.lower()}:{slug}"
        return CanonicalEntity(
            canonical_id=canonical_id,
            canonical_name=raw_entity.name.strip(),
            primary_type=raw_entity.type,
            description=raw_entity.description,
            aliases=raw_entity.aliases,
            source_mentions=[raw_entity.name],
            metadata=raw_entity.metadata,
        )

    def resolve_entities(self, raw_entities: list[Entity]) -> list[CanonicalEntity]:
        """Deduplicate a list of raw entities into unique CanonicalEntity records."""
        resolved_clusters: dict[str, CanonicalEntity] = {}

        for ent in raw_entities:
            canonical = self.resolve_entity(ent)
            cid = canonical.canonical_id

            if cid not in resolved_clusters:
                resolved_clusters[cid] = canonical
            else:
                existing = resolved_clusters[cid]
                # Merge mentions and aliases
                for m in canonical.source_mentions:
                    if m not in existing.source_mentions:
                        existing.source_mentions.append(m)
                for a in canonical.aliases:
                    if a not in existing.aliases:
                        existing.aliases.append(a)
                # Keep richer description
                if len(canonical.description) > len(existing.description):
                    existing.description = canonical.description

        return list(resolved_clusters.values())

    def resolve_relationships(
        self,
        relationships: list[Relationship],
        canonical_entities: list[CanonicalEntity] | None = None,
    ) -> list[Relationship]:
        """Re-map relationship endpoints to canonical entity IDs and merge duplicate edges."""
        # Create map from mention/alias/id to canonical ID
        name_to_id: dict[str, str] = {}

        # 1. Pre-populate from known canonical clusters
        for cluster in self.CANONICAL_CLUSTERS:
            cid = cluster["canonical_id"]
            name_to_id[cid] = cid
            slug = cid.split(":")[-1]
            name_to_id[slug] = cid
            name_to_id[f"entity:{slug}"] = cid
            variants = [cluster["canonical_name"]] + cluster.get("aliases", [])
            for v in variants:
                v_low = v.strip().lower()
                name_to_id[v_low] = cid
                v_space = re.sub(r"[^a-z0-9]+", " ", v_low).strip()
                v_under = re.sub(r"[^a-z0-9]+", "_", v_low).strip("_")
                name_to_id[v_space] = cid
                name_to_id[v_under] = cid
                name_to_id[f"entity:{v_under}"] = cid

        # 2. Enrich with provided canonical entities
        if canonical_entities:
            for ce in canonical_entities:
                cid = ce.canonical_id
                name_to_id[cid] = cid

                # Index slug suffix (e.g. "inc_402" and "entity:inc_402")
                slug = cid.split(":")[-1]
                name_to_id[slug] = cid
                name_to_id[f"entity:{slug}"] = cid

                # Index canonical name, aliases, mentions and normalized variations
                variants = [ce.canonical_name] + ce.aliases + ce.source_mentions
                for v in variants:
                    v_low = v.strip().lower()
                    name_to_id[v_low] = cid
                    v_space = re.sub(r"[^a-z0-9]+", " ", v_low).strip()
                    v_under = re.sub(r"[^a-z0-9]+", "_", v_low).strip("_")
                    name_to_id[v_space] = cid
                    name_to_id[v_under] = cid
                    name_to_id[f"entity:{v_under}"] = cid

        resolved_rels: dict[str, Relationship] = {}

        for rel in relationships:
            # Map source and target to canonical IDs
            clean_src = rel.source_id.replace("entity:", "").replace("_", " ").lower()
            clean_tgt = rel.target_id.replace("entity:", "").replace("_", " ").lower()

            src_cid = name_to_id.get(rel.source_id) or name_to_id.get(clean_src) or self._fallback_cid(rel.source_id)
            tgt_cid = name_to_id.get(rel.target_id) or name_to_id.get(clean_tgt) or self._fallback_cid(rel.target_id)

            # Avoid self-loops post-resolution
            if src_cid == tgt_cid:
                continue

            rel_type = rel.type
            src_key = src_cid.replace("entity:", "").replace(":", "_")
            tgt_key = tgt_cid.replace("entity:", "").replace(":", "_")
            canonical_rel_id = f"rel:{src_key}:{rel_type.value.lower()}:{tgt_key}"

            if canonical_rel_id in resolved_rels:
                # Merge evidence
                existing = resolved_rels[canonical_rel_id]
                for ev in rel.evidence:
                    existing.add_evidence(ev.chunk_id, ev.document_id, ev.text, ev.confidence)
                existing.weight += 0.5  # Boost weight for repeated mentions
            else:
                updated_rel = Relationship(
                    id=canonical_rel_id,
                    source_id=src_cid,
                    target_id=tgt_cid,
                    type=rel_type,
                    description=rel.description,
                    weight=rel.weight,
                    evidence=rel.evidence,
                    metadata=rel.metadata,
                )
                resolved_rels[canonical_rel_id] = updated_rel

        return list(resolved_rels.values())

    def _fallback_cid(self, name: str) -> str:
        """Construct fallback ID if not present in lookup."""
        clean = name.strip().lower()
        if clean in self.alias_to_canonical_map:
            return self.alias_to_canonical_map[clean]["canonical_id"]
        # Strip entity: prefix and possible type prefix (e.g. entity:customer:acme_corp -> acme corp)
        stripped = re.sub(r"^entity:(?:[a-z]+:)?", "", clean)
        stripped_clean = stripped.replace("_", " ").strip()
        if stripped_clean in self.alias_to_canonical_map:
            return self.alias_to_canonical_map[stripped_clean]["canonical_id"]
        slug = re.sub(r"[^a-z0-9]+", "_", stripped).strip("_")
        return f"entity:{slug}"
