"""Call Detail Record (CDR) dynamic parser."""
from __future__ import annotations

import csv
import io
import re
from typing import Any
from ..nlp_extraction import ExtractedRelationship
from ..nlp.confidence_scorer import ExtractedEntityMetadata

class CDRParser:
    """Dynamic CSV/tabular parser for Call Detail Records (CDRs)."""

    CALLER_ALIASES = {"caller", "caller_number", "calling_number", "from", "mobile1", "msisdn1", "source", "a_party", "originating_number"}
    RECEIVER_ALIASES = {"receiver", "receiver_number", "called_number", "to", "mobile2", "msisdn2", "destination", "b_party", "called", "dialed"}
    DATE_ALIASES = {"date", "calldate", "call_date", "datetime", "timestamp", "start_time"}
    TIME_ALIASES = {"time", "calltime", "call_time", "duration_time"}
    DURATION_ALIASES = {"duration", "duration_sec", "dur", "call_duration", "duration_seconds"}
    TOWER_ALIASES = {"tower", "tower_location", "cell", "cell_id", "location", "azimuth", "bts"}

    def _match_column(self, header: str, aliases: set[str]) -> bool:
        clean = re.sub(r"[^a-z0-9]", "", header.lower())
        return any(clean == re.sub(r"[^a-z0-9]", "", a) or a in clean for a in aliases)

    def parse(self, content: str) -> dict[str, Any]:
        reader = csv.reader(io.StringIO(content.strip()))
        rows = list(reader)
        if not rows:
            return {"entities": [], "relationships": [], "total_calls": 0}

        headers = [h.strip() for h in rows[0]]
        caller_idx = None
        receiver_idx = None
        date_idx = None
        time_idx = None
        duration_idx = None
        tower_idx = None

        for idx, h in enumerate(headers):
            if caller_idx is None and self._match_column(h, self.CALLER_ALIASES):
                caller_idx = idx
            elif receiver_idx is None and self._match_column(h, self.RECEIVER_ALIASES):
                receiver_idx = idx
            elif date_idx is None and self._match_column(h, self.DATE_ALIASES):
                date_idx = idx
            elif time_idx is None and self._match_column(h, self.TIME_ALIASES):
                time_idx = idx
            elif duration_idx is None and self._match_column(h, self.DURATION_ALIASES):
                duration_idx = idx
            elif tower_idx is None and self._match_column(h, self.TOWER_ALIASES):
                tower_idx = idx

        # Fallback if first two columns look like phone numbers
        if caller_idx is None or receiver_idx is None:
            if len(headers) >= 2:
                caller_idx = 0
                receiver_idx = 1

        unique_phones: set[str] = set()
        pair_aggregates: dict[tuple[str, str], dict[str, Any]] = {}
        total_calls = 0

        for row in rows[1:]:
            if not row or len(row) <= max(caller_idx or 0, receiver_idx or 0):
                continue

            raw_caller = row[caller_idx].strip()
            raw_receiver = row[receiver_idx].strip()
            if not raw_caller or not raw_receiver or raw_caller == raw_receiver:
                continue

            caller = self._normalize_phone(raw_caller)
            receiver = self._normalize_phone(raw_receiver)

            unique_phones.add(caller)
            unique_phones.add(receiver)
            total_calls += 1

            date_val = row[date_idx].strip() if date_idx is not None and len(row) > date_idx else ""
            time_val = row[time_idx].strip() if time_idx is not None and len(row) > time_idx else ""
            dur_val = 0
            if duration_idx is not None and len(row) > duration_idx:
                try:
                    dur_val = int(re.sub(r"[^\d]", "", row[duration_idx]))
                except ValueError:
                    dur_val = 0

            tower_val = row[tower_idx].strip() if tower_idx is not None and len(row) > tower_idx else None
            timestamp = f"{date_val} {time_val}".strip() or None

            pair_key = (caller, receiver)
            if pair_key not in pair_aggregates:
                pair_aggregates[pair_key] = {
                    "count": 0,
                    "total_duration": 0,
                    "latest_timestamp": timestamp,
                    "towers": set(),
                }

            agg = pair_aggregates[pair_key]
            agg["count"] += 1
            agg["total_duration"] += dur_val
            if timestamp:
                agg["latest_timestamp"] = timestamp
            if tower_val:
                agg["towers"].add(tower_val)

        # Build Phone entities
        entities: list[dict[str, Any]] = []
        for phone in unique_phones:
            entities.append({
                "entity_type": "Phone",
                "value": phone,
                "normalized_value": phone,
                "confidence": 0.96,
                "extraction_method": "REGEX",
                "source_text": phone,
                "requires_verification": False,
            })

        # Build CALLED relationships with dynamic weighting
        relationships: list[dict[str, Any]] = []
        for (c_num, r_num), agg in pair_aggregates.items():
            call_count = agg["count"]
            weight = min(1.0, round(call_count / 10.0, 2))
            conf = min(0.98, round(0.70 + weight * 0.28, 2))
            explanation = (
                f"Synthetic CDR shows {call_count} call(s) from {c_num} to {r_num} "
                f"(total duration: {agg['total_duration']}s, weight: {weight})"
            )
            if agg["towers"]:
                explanation += f" via tower(s): {', '.join(sorted(agg['towers']))}"

            relationships.append({
                "source_value": c_num,
                "source_type": "Phone",
                "relationship_type": "CALLED",
                "target_value": r_num,
                "target_type": "Phone",
                "confidence": conf,
                "frequency": call_count,
                "relationship_origin": "OBSERVED",
                "explanation": explanation,
                "evidence_text": f"CDR call frequency: {call_count}, total sec: {agg['total_duration']}",
                "timestamp": agg["latest_timestamp"],
                "requires_verification": False,
            })

        return {
            "document_type": "CDR",
            "total_calls": total_calls,
            "unique_phone_count": len(unique_phones),
            "entities": entities,
            "relationships": relationships,
        }

    def _normalize_phone(self, raw: str) -> str:
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 10:
            return f"+91 {digits[:5]} {digits[5:]}"
        if len(digits) == 12 and digits.startswith("91"):
            return f"+91 {digits[2:7]} {digits[7:]}"
        return raw.strip()
