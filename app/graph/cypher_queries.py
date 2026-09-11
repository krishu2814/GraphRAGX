"""Catalog of parameterized Cypher queries for node/edge ingestion and graph querying."""

# Node Ingestion
MERGE_ENTITY_NODE = """
MERGE (e:Entity {id: $id})
SET e.name = $name,
    e.type = $type,
    e.description = $description,
    e.aliases = $aliases,
    e.updated_at = timestamp()
RETURN e.id AS id
"""

MERGE_DOCUMENT_NODE = """
MERGE (d:Document {id: $id})
SET d.title = $title,
    d.department = $department,
    d.access_tier = $access_tier,
    d.version = $version,
    d.updated_at = timestamp()
RETURN d.id AS id
"""

MERGE_CHUNK_NODE = """
MERGE (c:Chunk {id: $id})
SET c.document_id = $document_id,
    c.text = $text,
    c.section_title = $section_title,
    c.section_path = $section_path,
    c.index = $index,
    c.updated_at = timestamp()
RETURN c.id AS id
"""

# Structural Linking
LINK_CHUNK_TO_DOCUMENT = """
MATCH (c:Chunk {id: $chunk_id})
MATCH (d:Document {id: $document_id})
MERGE (c)-[r:PART_OF]->(d)
RETURN type(r) AS rel
"""

LINK_CHUNK_TO_ENTITY = """
MATCH (c:Chunk {id: $chunk_id})
MATCH (e:Entity {id: $entity_id})
MERGE (c)-[r:MENTIONS]->(e)
RETURN type(r) AS rel
"""

# Dynamic Entity Relationship Query Builder
def build_merge_relationship_query(rel_type: str) -> str:
    """Dynamically construct a parameterized MERGE query for a specific relationship type."""
    # Sanitize relationship type to valid Cypher identifier
    safe_rel_type = "".join(c for c in rel_type if c.isalnum() or c == "_").upper()
    return f"""
    MATCH (s:Entity {{id: $source_id}})
    MATCH (t:Entity {{id: $target_id}})
    MERGE (s)-[r:{safe_rel_type}]->(t)
    SET r.description = $description,
        r.weight = $weight,
        r.evidence = $evidence,
        r.updated_at = timestamp()
    RETURN id(r) AS rel_id
    """

# Graph Inspection & Retrieval
GET_ENTITY_BY_ID = """
MATCH (e:Entity {id: $id})
RETURN e.id AS id, e.name AS name, e.type AS type, e.description AS description, e.aliases AS aliases
"""

GET_ENTITY_BY_NAME = """
MATCH (e:Entity)
WHERE toLower(e.name) = toLower($name) OR toLower($name) IN [a IN e.aliases | toLower(a)]
RETURN e.id AS id, e.name AS name, e.type AS type, e.description AS description, e.aliases AS aliases
LIMIT 1
"""

GET_NEIGHBORS_1HOP = """
MATCH (s:Entity {id: $id})-[r]-(t:Entity)
RETURN s.id AS source_id,
       s.name AS source_name,
       type(r) AS relation,
       r.description AS description,
       r.evidence AS evidence,
       t.id AS target_id,
       t.name AS target_name,
       t.type AS target_type
LIMIT $limit
"""

GET_CHUNK_BY_ID = """
MATCH (c:Chunk {id: $id})
RETURN c.id AS id,
       c.document_id AS document_id,
       c.text AS text,
       c.section_title AS section_title,
       c.section_path AS section_path,
       c.index AS index
"""

GET_GRAPH_STATS = """
CALL {
    MATCH (e:Entity) RETURN count(e) AS entity_count
}
CALL {
    MATCH (d:Document) RETURN count(d) AS document_count
}
CALL {
    MATCH (c:Chunk) RETURN count(c) AS chunk_count
}
CALL {
    MATCH ()-[r]->() WHERE NOT type(r) IN ['PART_OF', 'MENTIONS'] RETURN count(r) AS relationship_count
}
RETURN entity_count, document_count, chunk_count, relationship_count
"""

