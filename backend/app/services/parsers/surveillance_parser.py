"""Surveillance report free-text parser."""
from __future__ import annotations

import re
from typing import Any
from ..nlp_extraction import ExtractedRelationship, NLPExtractionService

class SurveillanceParser:
    """Specialized parser for field surveillance logs and observation memos."""

    def __init__(self, nlp_service: NLPExtractionService | None = None):
        self.nlp = nlp_service or NLPExtractionService()

    def parse(self, text: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "report_date": None,
            "location": None,
            "observation_window": None,
            "subjects": [],
        }

        # Date
        date_m = re.search(r"(?:Surveillance\s*Report\s*[-—:]?\s*)?(\d{1,2}\s+[A-Za-z]+\s+\d{4})", text, re.I)
        if date_m:
            metadata["report_date"] = date_m.group(1).strip()

        # Location header
        loc_m = re.search(r"Location\s*:\s*([^\n\r]+)", text, re.I)
        if loc_m:
            metadata["location"] = loc_m.group(1).strip()

        # Observation window
        time_m = re.search(r"Time\s*:\s*([^\n\r]+)", text, re.I)
        if time_m:
            metadata["observation_window"] = time_m.group(1).strip()

        # Extract entities using NLP service
        entities = self.nlp.extract_entities(text)
        relationships = self.nlp.extract_relationships(text, entities)

        # Connect subjects to top-level surveillance location if present
        if metadata["location"]:
            top_loc = metadata["location"]
            for p in [e for e in entities if e.entity_type == "Person"]:
                relationships.append(ExtractedRelationship(
                    source_value=p.value,
                    source_type="Person",
                    relationship_type="VISITED",
                    target_value=top_loc,
                    target_type="Location",
                    confidence=0.88,
                    relationship_origin="OBSERVED",
                    explanation=f"Subject {p.value} observed during surveillance at {top_loc}",
                    evidence_text=f"Surveillance log observation at {top_loc}",
                    timestamp=metadata["report_date"],
                ))

        # Deduplicate relationships
        unique_rels: list[dict[str, Any]] = []
        seen = set()
        for r in relationships:
            d = r.to_dict() if hasattr(r, "to_dict") else r
            key = (d["source_value"], d["relationship_type"], d["target_value"])
            if key not in seen:
                seen.add(key)
                unique_rels.append(d)

        return {
            "document_type": "SURVEILLANCE_REPORT",
            "metadata": metadata,
            "entities": [e.to_dict() for e in entities],
            "relationships": unique_rels,
            "total_entities": len(entities),
            "total_relationships": len(unique_rels),
        }
