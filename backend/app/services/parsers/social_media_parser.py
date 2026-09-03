"""Social media interaction and network dump parser."""
from __future__ import annotations

import json
import re
from typing import Any

class SocialMediaParser:
    """Parses social media JSON exports or structured interaction logs."""

    def parse(self, raw_content: str) -> dict[str, Any]:
        data: Any = None
        try:
            data = json.loads(raw_content)
        except Exception:
            # If not pure JSON, parse line-by-line or regex
            return self._parse_text_feed(raw_content)

        if isinstance(data, dict):
            posts = data.get("posts", data.get("interactions", [data]))
        elif isinstance(data, list):
            posts = data
        else:
            posts = []

        entities: dict[str, dict[str, Any]] = {}
        relationships: list[dict[str, Any]] = []

        for p in posts:
            author = p.get("author") or p.get("user") or p.get("handle")
            if not author:
                continue

            author = str(author).strip()
            entities[author] = {
                "entity_type": "Person",
                "value": author,
                "normalized_value": author.lower(),
                "confidence": 0.88,
                "extraction_method": "RULE_BASED",
                "source_text": f"Social user {author}",
            }

            # Following/Followers
            for f in p.get("following", []):
                f_name = str(f).strip()
                entities[f_name] = {
                    "entity_type": "Person",
                    "value": f_name,
                    "normalized_value": f_name.lower(),
                    "confidence": 0.85,
                    "extraction_method": "RULE_BASED",
                    "source_text": f_name,
                }
                relationships.append({
                    "source_value": author,
                    "source_type": "Person",
                    "relationship_type": "FOLLOWS",
                    "target_value": f_name,
                    "target_type": "Person",
                    "confidence": 0.90,
                    "relationship_origin": "OBSERVED",
                    "explanation": f"{author} follows {f_name} on social media platform.",
                    "evidence_text": "Social graph connection",
                })

            # Mentions / Interactions
            for m in p.get("mentions", []):
                m_name = str(m).strip()
                entities[m_name] = {
                    "entity_type": "Person",
                    "value": m_name,
                    "normalized_value": m_name.lower(),
                    "confidence": 0.85,
                    "extraction_method": "RULE_BASED",
                    "source_text": m_name,
                }
                relationships.append({
                    "source_value": author,
                    "source_type": "Person",
                    "relationship_type": "INTERACTED_WITH",
                    "target_value": m_name,
                    "target_type": "Person",
                    "confidence": 0.85,
                    "relationship_origin": "OBSERVED",
                    "explanation": f"{author} interacted with {m_name} (mention/reply).",
                    "evidence_text": p.get("text", "Mention in post"),
                    "timestamp": p.get("timestamp"),
                })

            # Geolocation / Location tag
            geo = p.get("location") or p.get("geotag")
            if geo:
                geo = str(geo).strip()
                entities[geo] = {
                    "entity_type": "Location",
                    "value": geo,
                    "normalized_value": geo.lower(),
                    "confidence": 0.88,
                    "extraction_method": "RULE_BASED",
                    "source_text": geo,
                }
                relationships.append({
                    "source_value": author,
                    "source_type": "Person",
                    "relationship_type": "POSTED_AT",
                    "target_value": geo,
                    "target_type": "Location",
                    "confidence": 0.86,
                    "relationship_origin": "OBSERVED",
                    "explanation": f"{author} posted with verified geotag {geo}",
                    "evidence_text": f"Geotagged social post at {geo}",
                    "timestamp": p.get("timestamp"),
                })

        return {
            "document_type": "SOCIAL_MEDIA",
            "entities": list(entities.values()),
            "relationships": relationships,
        }

    def _parse_text_feed(self, text: str) -> dict[str, Any]:
        handles = set(re.findall(r"@([A-Za-z0-9_]{3,25})", text))
        entities = [
            {
                "entity_type": "Person",
                "value": f"@{h}",
                "normalized_value": f"@{h.lower()}",
                "confidence": 0.82,
                "extraction_method": "REGEX",
                "source_text": f"@{h}",
            }
            for h in handles
        ]
        return {
            "document_type": "SOCIAL_MEDIA",
            "entities": entities,
            "relationships": [],
        }
