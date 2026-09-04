"""Entity normalization, duplicate detection, and candidate resolution."""
from __future__ import annotations

import re
from typing import Any

class EntityNormalizationService:
    """Handles phone, vehicle, amount, and person entity normalization and duplicate detection."""

    # Common honorifics and prefixes to normalize in names
    NAME_PREFIXES = {
        "mr", "mr.", "shri", "sh.", "smt", "smt.", "dr", "dr.", "si", "inspector",
        "constable", "asi", "dsp", "advocate", "adv."
    }

    # Common name spelling variations / abbreviations
    NAME_VARIATION_MAP = {
        "mohd": "mohammad",
        "mohd.": "mohammad",
        "mohammed": "mohammad",
        "muhammad": "mohammad",
        "kr": "kumar",
        "kr.": "kumar",
        "sing": "singh",
        "shrm": "sharma",
    }

    @staticmethod
    def normalize_phone(raw: str) -> str:
        """Normalizes Indian phone numbers to canonical '+91 XXXXX XXXXX' format."""
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 10:
            return f"+91 {digits[:5]} {digits[5:]}"
        if len(digits) == 12 and digits.startswith("91"):
            return f"+91 {digits[2:7]} {digits[7:]}"
        if len(digits) == 11 and digits.startswith("0"):
            return f"+91 {digits[1:6]} {digits[6:]}"
        return raw.strip()

    @staticmethod
    def normalize_vehicle(raw: str) -> str:
        """Normalizes Indian vehicle registration numbers (e.g. 'DL 01 AB 1234' -> 'DL01AB1234')."""
        return re.sub(r"[^A-Za-z0-9]", "", raw).upper()

    @staticmethod
    def normalize_amount(raw: str) -> float:
        """Parses currency strings into raw float INR numbers."""
        clean = raw.replace(",", "").replace("₹", "").replace("Rs", "").replace("रु", "").strip()
        multiplier = 1.0
        # In compact values such as ``50K`` the digit and K are both word
        # characters, so a leading word-boundary would not match.
        if re.search(r"(?:\d\s*[kK]\b|\b(?:thousand|हजार)\b)", clean, re.I):
            multiplier = 1000.0
            clean = re.sub(r"[kK]|thousand|हजार", "", clean, flags=re.I).strip()
        elif re.search(r"\b(?:lakh|lakhs|लाख)\b", clean, re.I):
            multiplier = 100000.0
            clean = re.sub(r"lakhs?|लाख", "", clean, flags=re.I).strip()
        elif re.search(r"\b(?:crore|crores|करोड़)\b", clean, re.I):
            multiplier = 10000000.0
            clean = re.sub(r"crores?|करोड़", "", clean, flags=re.I).strip()

        nums = re.findall(r"\d+(?:\.\d+)?", clean)
        if nums:
            try:
                return float(nums[0]) * multiplier
            except ValueError:
                return 0.0
        return 0.0

    @classmethod
    def normalize_person_name(cls, raw: str) -> str:
        """Cleans titles, extra spacing, and standardizes name tokens."""
        tokens = raw.strip().split()
        filtered = []
        for t in tokens:
            cleaned_t = t.strip(",.()").lower()
            if cleaned_t not in cls.NAME_PREFIXES:
                canonical = cls.NAME_VARIATION_MAP.get(cleaned_t, cleaned_t)
                filtered.append(canonical.capitalize())
        return " ".join(filtered) if filtered else raw.strip()

    @classmethod
    def calculate_similarity(cls, entity_type: str, val1: str, val2: str) -> float:
        """Computes similarity score between two values of the same entity type."""
        if val1.strip().lower() == val2.strip().lower():
            return 1.0

        if entity_type == "Phone":
            p1 = re.sub(r"\D", "", val1)
            p2 = re.sub(r"\D", "", val2)
            if p1 and p2 and p1[-10:] == p2[-10:]:
                return 1.0
            return 0.0

        if entity_type == "Vehicle":
            v1 = cls.normalize_vehicle(val1)
            v2 = cls.normalize_vehicle(val2)
            if v1 == v2:
                return 1.0
            # Check 1-char typo
            if len(v1) == len(v2) and sum(c1 != c2 for c1, c2 in zip(v1, v2)) == 1:
                return 0.85
            return 0.0

        if entity_type == "Person":
            n1 = cls.normalize_person_name(val1).lower()
            n2 = cls.normalize_person_name(val2).lower()
            if n1 == n2:
                return 1.0

            tokens1 = set(n1.split())
            tokens2 = set(n2.split())
            overlap = tokens1 & tokens2
            if overlap and (len(overlap) == min(len(tokens1), len(tokens2))):
                return 0.88  # Subset match (e.g. "Rahul" vs "Rahul Sharma" or "Amitu" alias)
            if overlap:
                jaccard = len(overlap) / len(tokens1 | tokens2)
                return round(0.50 + jaccard * 0.40, 2)

        return 0.20

    @classmethod
    def generate_merge_candidates(
        cls,
        new_entity: dict[str, Any],
        existing_entities: list[dict[str, Any]],
        threshold: float = 0.55,
    ) -> list[dict[str, Any]]:
        """Generates resolution candidates between a new entity and existing case records."""
        candidates = []
        e_type = new_entity.get("entity_type")
        e_val = new_entity.get("canonical_name") or new_entity.get("value", "")

        for existing in existing_entities:
            if existing.get("id") == new_entity.get("id"):
                continue
            if existing.get("entity_type") != e_type:
                continue

            ex_val = existing.get("canonical_name") or existing.get("value", "")
            sim = cls.calculate_similarity(e_type, e_val, ex_val)
            if sim >= threshold:
                cat = "CONFIRMED" if sim >= 0.95 else ("PROBABLE" if sim >= 0.75 else "POSSIBLE")
                candidates.append({
                    "existing_entity": existing,
                    "candidate_value": ex_val,
                    "match_score": sim,
                    "match_category": cat,
                    "requires_confirmation": True,
                    "rationale": f"High lexical/identifier similarity ({int(sim*100)}%) for {e_type}",
                })

        return sorted(candidates, key=lambda x: x["match_score"], reverse=True)
