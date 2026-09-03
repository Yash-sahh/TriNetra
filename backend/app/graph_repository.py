"""Case-scoped graph repository boundary.

The local adapter is the default zero-setup implementation. The optional Neo4j
adapter uses only parameterized Cypher; it is intentionally not selected unless
``GRAPH_MODE=neo4j`` and a driver is installed/configured.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

class GraphRepository(ABC):
    @abstractmethod
    def graph_for_case(self, case_id: str, min_confidence: float = 0) -> dict[str, list[dict[str, Any]]]: ...

class LocalGraphRepository(GraphRepository):
    def __init__(self, session: Session, entity_model: Any, relation_model: Any, serializer: Any):
        self.session, self.Entity, self.Relation, self.serialize = session, entity_model, relation_model, serializer
    def graph_for_case(self, case_id: str, min_confidence: float = 0) -> dict[str, list[dict[str, Any]]]:
        return {
            "nodes": [self.serialize(x) for x in self.session.scalars(select(self.Entity).where(self.Entity.case_id == case_id)).all()],
            "edges": [self.serialize(x) for x in self.session.scalars(select(self.Relation).where(self.Relation.case_id == case_id, self.Relation.confidence >= min_confidence)).all()],
        }

class Neo4jGraphRepository(GraphRepository):
    """Optional adapter skeleton. Use a private Neo4j deployment in production."""
    def __init__(self, driver: Any): self.driver = driver
    def graph_for_case(self, case_id: str, min_confidence: float = 0) -> dict[str, list[dict[str, Any]]]:
        statement = """MATCH (a {case_id: $case_id})-[r {case_id: $case_id}]->(b {case_id: $case_id})
        WHERE r.confidence >= $min_confidence
        RETURN a, r, b"""
        with self.driver.session() as session:
            records=list(session.run(statement, case_id=case_id, min_confidence=min_confidence))
        nodes={}; edges=[]
        for record in records:
            for key in ("a","b"):
                node=dict(record[key]); nodes[node["id"]]=node
            edges.append(dict(record["r"]))
        return {"nodes":list(nodes.values()),"edges":edges}
