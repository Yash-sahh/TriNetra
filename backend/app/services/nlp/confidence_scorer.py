"""Confidence scoring and provenance metadata for NLP extraction."""
from __future__ import annotations

from typing import Any, Literal

ExtractionMethod = Literal["REGEX", "RULE_BASED", "STATISTICAL", "OCR", "FALLBACK"]

class ExtractedEntityMetadata:
    """Standard container for entity extraction metadata and confidence."""

    def __init__(
        self,
        entity_type: str,
        value: str,
        confidence: float,
        extraction_method: ExtractionMethod,
        source_text: str,
        source_start_char: int = 0,
        source_end_char: int = 0,
        source_page: int = 1,
        language: str = "en",
        normalized_value: str | None = None,
        context_hints: list[str] | None = None,
    ):
        self.entity_type = entity_type
        self.value = value.strip()
        self.normalized_value = (normalized_value or value).strip()
        self.confidence = max(0.0, min(1.0, round(confidence, 3)))
        self.extraction_method = extraction_method
        self.source_text = source_text
        self.source_start_char = source_start_char
        self.source_end_char = source_end_char
        self.source_page = source_page
        self.language = language
        self.context_hints = context_hints or []
        self.requires_verification = self.confidence < 0.85

    @property
    def confidence_level(self) -> Literal["HIGH", "MEDIUM", "LOW"]:
        if self.confidence >= 0.80:
            return "HIGH"
        if self.confidence >= 0.50:
            return "MEDIUM"
        return "LOW"

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "value": self.value,
            "normalized_value": self.normalized_value,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level,
            "extraction_method": self.extraction_method,
            "source_text": self.source_text,
            "source_start_char": self.source_start_char,
            "source_end_char": self.source_end_char,
            "source_page": self.source_page,
            "language": self.language,
            "requires_verification": self.requires_verification,
            "context_hints": self.context_hints,
        }

class ConfidenceScorer:
    """Calculates extraction confidence based on entity type, structure, and surrounding context."""

    @staticmethod
    def score_phone(raw: str, method: ExtractionMethod = "REGEX") -> float:
        digits = "".join(c for c in raw if c.isdigit())
        if len(digits) == 10:
            return 0.95
        if len(digits) in (11, 12) and (raw.startswith("+91") or digits.startswith("91")):
            return 0.96
        return 0.70

    @staticmethod
    def score_vehicle(raw: str, method: ExtractionMethod = "REGEX") -> float:
        cleaned = raw.replace(" ", "").upper()
        # Standard Indian format: 2 letters (state) + 1-2 digits (district) + 1-3 letters + 4 digits
        if len(cleaned) in (9, 10, 11) and cleaned[:2].isalpha():
            return 0.95
        return 0.75

    @staticmethod
    def score_person(raw: str, has_context_role: bool = False, has_relation: bool = False, has_alias: bool = False) -> float:
        score = 0.65
        tokens = raw.split()
        if len(tokens) >= 2:
            score += 0.10
        if has_context_role:  # Accused, Complainant, Witness, arrested
            score += 0.15
        if has_relation:      # S/O, D/O, W/O
            score += 0.10
        if has_alias:         # alias, उर्फ
            score += 0.05
        return min(0.96, score)

    @staticmethod
    def score_location(raw: str, has_preposition: bool = False, has_keyword: bool = False) -> float:
        score = 0.55
        if has_preposition:   # near, at, in, के पास
            score += 0.15
        if has_keyword:       # station, hospital, mall, nagar, road
            score += 0.18
        return min(0.92, score)

    @staticmethod
    def score_amount(raw: str) -> float:
        if "₹" in raw or "Rs" in raw or "INR" in raw or "रु" in raw:
            return 0.95
        return 0.80

    @staticmethod
    def score_date_time(raw: str) -> float:
        return 0.90
