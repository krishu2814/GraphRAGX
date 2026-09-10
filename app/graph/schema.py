"""Graph database schema definitions, node labels, uniqueness constraints, and indexes."""

NODE_LABEL_ENTITY = "Entity"
NODE_LABEL_DOCUMENT = "Document"
NODE_LABEL_CHUNK = "Chunk"

# Cypher statements for uniqueness constraints
CONSTRAINTS = [
    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
]

# Cypher statements for performance indexes
INDEXES = [
    "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name)",
    "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type)",
    "CREATE INDEX chunk_doc_id_idx IF NOT EXISTS FOR (c:Chunk) ON (c.document_id)",
]


def get_schema_initialization_queries() -> list[str]:
    """Return an ordered list of Cypher queries to initialize constraints and indexes."""
    return CONSTRAINTS + INDEXES
