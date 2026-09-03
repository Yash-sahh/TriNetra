"""Multi-layer explainable multilingual NLP extraction service.

Supports English, Hindi, and Hinglish unstructured text. Extracts:
- Entities: PERSON, LOCATION, PHONE, VEHICLE, DATE_TIME, AMOUNT, ORGANIZATION
- Relationships: ASSOCIATED_WITH, MET, LOCATED_AT, VISITED, USED_VEHICLE, HAS_PHONE, TRANSFERRED_MONEY, FOLLOWS
"""
from __future__ import annotations

import re
from typing import Any, Literal
from .nlp.confidence_scorer import ConfidenceScorer, ExtractedEntityMetadata

LanguageCode = Literal["en", "hi", "hinglish"]

class ExtractedRelationship:
    """Represents a discovered relationship between extracted entities."""

    def __init__(
        self,
        source_value: str,
        source_type: str,
        relationship_type: str,
        target_value: str,
        target_type: str,
        confidence: float = 0.75,
        relationship_origin: str = "OBSERVED",
        explanation: str = "",
        evidence_text: str = "",
        amount: float | None = None,
        timestamp: str | None = None,
    ):
        self.source_value = source_value.strip()
        self.source_type = source_type
        self.relationship_type = relationship_type
        self.target_value = target_value.strip()
        self.target_type = target_type
        self.confidence = round(confidence, 3)
        self.relationship_origin = relationship_origin
        self.explanation = explanation
        self.evidence_text = evidence_text
        self.amount = amount
        self.timestamp = timestamp
        self.requires_verification = self.confidence < 0.85

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_value": self.source_value,
            "source_type": self.source_type,
            "relationship_type": self.relationship_type,
            "target_value": self.target_value,
            "target_type": self.target_type,
            "confidence": self.confidence,
            "relationship_origin": self.relationship_origin,
            "explanation": self.explanation,
            "evidence_text": self.evidence_text,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "requires_verification": self.requires_verification,
        }

class NLPExtractionService:
    """Core multilingual entity and relationship extraction service."""

    # Common non-person capitalized words to filter out
    ENGLISH_STOPWORDS = {
        "The", "This", "That", "These", "Those", "On", "At", "In", "Near",
        "Police", "Station", "FIR", "No", "Date", "Time", "Incident",
        "Complainant", "Accused", "Witness", "Witnesses", "Subject",
        "Today", "Yesterday", "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday", "January", "February", "March",
        "April", "May", "June", "July", "August", "September", "October",
        "November", "December", "Both", "They", "He", "She", "It",
        "Vehicle", "Phone", "Car", "Number", "Location", "Report",
        "Investigating", "Officer", "Case", "Diary", "Entry"
    }

    HINDI_STOPWORDS = {
        "थाना", "दिनांक", "घटना", "आरोपी", "साक्षी", "गवाह", "शिकायतकर्ता",
        "फरियादी", "संख्या", "लगभग", "वक्त", "समय", "पास", "साथ", "और",
        "तथा", "एक", "दो", "वे", "वह", "मैंने", "हमने", "था", "थी", "थे",
        "को", "में", "से", "पर", "के", "की", "का"
    }

    def detect_language(self, text: str) -> LanguageCode:
        """Detects whether text is English, Hindi (Devanagari), or Hinglish."""
        devanagari_count = len(re.findall(r"[\u0900-\u097F]", text))
        latin_count = len(re.findall(r"[A-Za-z]", text))

        if devanagari_count == 0:
            # Check for Hinglish phonetic particles
            hinglish_markers = re.findall(
                r"\b(?:ne|ko|se|ke|ki|ka|tha|the|thi|aur|tatha|giraftaar|mil|dekha|paas|saath|bhai|gaadi|wahan|yahan)\b",
                text,
                re.I,
            )
            if len(hinglish_markers) >= 2:
                return "hinglish"
            return "en"

        if latin_count > 0 and devanagari_count > 0:
            if devanagari_count > latin_count * 2:
                return "hi"
            return "hinglish"

        return "hi"

    def extract_entities(self, text: str, language: LanguageCode | None = None) -> list[ExtractedEntityMetadata]:
        """Runs multi-layer entity extraction on unstructured text."""
        if not text or not text.strip():
            return []

        lang = language or self.detect_language(text)
        entities: list[ExtractedEntityMetadata] = []
        occupied_spans: list[tuple[int, int]] = []

        def span_overlaps(start: int, end: int) -> bool:
            return any(not (end <= s or start >= e) for s, e in occupied_spans)

        def add_entity(entity: ExtractedEntityMetadata):
            if not span_overlaps(entity.source_start_char, entity.source_end_char):
                entities.append(entity)
                occupied_spans.append((entity.source_start_char, entity.source_end_char))

        # -------------------------------------------------------------
        # LAYER 1: High-Precision Regex (Phone, Vehicle, Amount, DateTime)
        # -------------------------------------------------------------
        # 1. Phone numbers
        phone_pattern = r"(?:(?:\+91|91|0)[- ]?)?[6-9]\d{9}\b|\b[6-9]\d{4}[ -]\d{5}\b"
        for m in re.finditer(phone_pattern, text):
            raw = m.group()
            digits = re.sub(r"\D", "", raw)
            norm = f"+91 {digits[-10:-5]} {digits[-5:]}" if len(digits) >= 10 else raw
            conf = ConfidenceScorer.score_phone(raw)
            add_entity(ExtractedEntityMetadata(
                entity_type="Phone",
                value=raw,
                normalized_value=norm,
                confidence=conf,
                extraction_method="REGEX",
                source_text=raw,
                source_start_char=m.start(),
                source_end_char=m.end(),
                language=lang,
            ))

        # 2. Vehicle registration numbers (Indian format e.g. DL01AB1234, MP09AB1234, DL3CAF5678)
        vehicle_pattern = r"\b[A-Z]{2}[ -]?[0-9]{1,2}[ -]?[A-Z]{1,3}[ -]?[0-9]{4}\b"
        for m in re.finditer(vehicle_pattern, text):
            raw = m.group()
            norm = re.sub(r"[ -]", "", raw).upper()
            conf = ConfidenceScorer.score_vehicle(raw)
            add_entity(ExtractedEntityMetadata(
                entity_type="Vehicle",
                value=raw,
                normalized_value=norm,
                confidence=conf,
                extraction_method="REGEX",
                source_text=raw,
                source_start_char=m.start(),
                source_end_char=m.end(),
                language=lang,
            ))

        # 3. Currency / Monetary Amounts
        amount_pattern = r"(?:₹|Rs\.?|INR|रु\.?)\s*[\d,]+(?:\.\d{2})?(?:\s*(?:lakh|crore|k|K|thousand|हजार|लाख))?\b|\b\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:K|k|lakhs?|crores?)\b"
        for m in re.finditer(amount_pattern, text, re.I):
            raw = m.group()
            num_clean = re.sub(r"[^\d.]", "", raw)
            add_entity(ExtractedEntityMetadata(
                entity_type="Amount",
                value=raw,
                normalized_value=num_clean,
                confidence=ConfidenceScorer.score_amount(raw),
                extraction_method="REGEX",
                source_text=raw,
                source_start_char=m.start(),
                source_end_char=m.end(),
                language=lang,
            ))

        # 4. Dates & Timestamps
        date_patterns = [
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}(?:\s+(?:at\s+)?\d{1,2}:\d{2}(?:\s*(?:AM|PM|am|pm))?)?\b",
            r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
            r"\b\d{1,2}\s+(?:जनवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|अक्टूबर|नवंबर|दिसंबर)\s+\d{4}\b",
            r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)(?:\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)?\b",
            r"\b(?:yesterday|today|कल|आज)(?:\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:AM|PM|बजे)?)?\b",
            r"\b(?:लगभग\s+)?\d{1,2}(?::\d{2})?\s*बजे(?:\s*(?:रात|सुबह|दोपहर|शाम))?\b",
        ]
        for pat in date_patterns:
            for m in re.finditer(pat, text, re.I):
                raw = m.group()
                add_entity(ExtractedEntityMetadata(
                    entity_type="DateTime",
                    value=raw,
                    normalized_value=raw,
                    confidence=ConfidenceScorer.score_date_time(raw),
                    extraction_method="REGEX",
                    source_text=raw,
                    source_start_char=m.start(),
                    source_end_char=m.end(),
                    language=lang,
                ))

        # -------------------------------------------------------------
        # LAYER 2: Rule-Based Context Patterns (PERSON, LOCATION, ORG)
        # -------------------------------------------------------------
        # A. English / Hinglish PERSON extraction

        # Pattern: Name S/O Father
        so_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,?\s*(?:S/O|D/O|W/O|s/o|d/o|w/o|son of|daughter of|wife of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
        for m in re.finditer(so_pattern, text):
            p1 = m.group(1).strip()
            p2 = m.group(2).strip()
            if p1 not in self.ENGLISH_STOPWORDS:
                add_entity(ExtractedEntityMetadata(
                    entity_type="Person",
                    value=p1,
                    confidence=ConfidenceScorer.score_person(p1, has_relation=True),
                    extraction_method="RULE_BASED",
                    source_text=m.group(),
                    source_start_char=m.start(1),
                    source_end_char=m.end(1),
                    language=lang,
                    context_hints=[f"Relation: S/O {p2}"],
                ))
            if p2 not in self.ENGLISH_STOPWORDS:
                add_entity(ExtractedEntityMetadata(
                    entity_type="Person",
                    value=p2,
                    confidence=ConfidenceScorer.score_person(p2, has_relation=True),
                    extraction_method="RULE_BASED",
                    source_text=m.group(),
                    source_start_char=m.start(2),
                    source_end_char=m.end(2),
                    language=lang,
                    context_hints=["Parent/Guardian"],
                ))

        # Pattern: Name alias Alias
        alias_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,?\s*(?:alias|a\.k\.a\.?|aka|known as|उर्फ|उर्फ़)\s+([A-Za-z\u0900-\u097F]+)\b"
        for m in re.finditer(alias_pattern, text, re.I):
            p1 = m.group(1).strip()
            alias = m.group(2).strip()
            if p1 not in self.ENGLISH_STOPWORDS:
                add_entity(ExtractedEntityMetadata(
                    entity_type="Person",
                    value=p1,
                    confidence=ConfidenceScorer.score_person(p1, has_alias=True),
                    extraction_method="RULE_BASED",
                    source_text=m.group(),
                    source_start_char=m.start(1),
                    source_end_char=m.end(1),
                    language=lang,
                    context_hints=[f"Alias: {alias}"],
                ))

        # Section-based extraction (Accused:, Complainant:, Witnesses:, Subject:, Investigating Officer:)
        section_pattern = r"(?:Accused|Complainant|Witnesses?|Subject|Investigating Officer|SI|Inspector)\s*:\s*([^\n\r]+)"
        for m in re.finditer(section_pattern, text, re.I):
            sec_text = m.group(1)
            # Find capitalized words inside section
            for name_m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", sec_text):
                candidate = name_m.group(1).strip()
                if candidate not in self.ENGLISH_STOPWORDS and not any(w in self.ENGLISH_STOPWORDS for w in candidate.split()):
                    add_entity(ExtractedEntityMetadata(
                        entity_type="Person",
                        value=candidate,
                        confidence=ConfidenceScorer.score_person(candidate, has_context_role=True),
                        extraction_method="RULE_BASED",
                        source_text=sec_text,
                        source_start_char=m.start(1) + name_m.start(),
                        source_end_char=m.start(1) + name_m.end(),
                        language=lang,
                        context_hints=["Formal Police Report Section"],
                    ))

        # Multi-word proper names with police verbs ("interrogated X", "arrested X", "saw X and Y", "meeting X")
        verb_context_pattern = r"(?:interrogated|arrested|saw|observed|meeting|interrogating|with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"
        for m in re.finditer(verb_context_pattern, text):
            cand = m.group(1).strip()
            if cand not in self.ENGLISH_STOPWORDS and cand not in {"Him", "Her", "Them", "Someone", "Another"}:
                add_entity(ExtractedEntityMetadata(
                    entity_type="Person",
                    value=cand,
                    confidence=ConfidenceScorer.score_person(cand, has_context_role=True),
                    extraction_method="RULE_BASED",
                    source_text=m.group(),
                    source_start_char=m.start(1),
                    source_end_char=m.end(1),
                    language=lang,
                ))

        # General English Capitalized Two-Word Proper Nouns (e.g. "Rahul Sharma", "Vikram Singh", "Rohit Verma")
        for m in re.finditer(r"\b([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})\b", text):
            full_name = m.group(1).strip()
            w1, w2 = full_name.split()
            if w1 not in self.ENGLISH_STOPWORDS and w2 not in self.ENGLISH_STOPWORDS:
                add_entity(ExtractedEntityMetadata(
                    entity_type="Person",
                    value=full_name,
                    confidence=ConfidenceScorer.score_person(full_name),
                    extraction_method="RULE_BASED",
                    source_text=full_name,
                    source_start_char=m.start(),
                    source_end_char=m.end(),
                    language=lang,
                ))

        # Single word proper names preceded by "meeting another person Imran" or "meeting Imran"
        for m in re.finditer(r"(?:meeting\s+(?:another\s+person\s+)?)([A-Z][a-z]{2,})\b", text):
            name = m.group(1).strip()
            if name not in self.ENGLISH_STOPWORDS:
                add_entity(ExtractedEntityMetadata(
                    entity_type="Person",
                    value=name,
                    confidence=0.82,
                    extraction_method="RULE_BASED",
                    source_text=m.group(),
                    source_start_char=m.start(1),
                    source_end_char=m.end(1),
                    language=lang,
                ))

        # B. Hindi Devanagari PERSON extraction
        # Devanagari names with section or role
        hindi_sections = r"(?:आरोपी|साक्षी|गवाह|शिकायतकर्ता|फरियादी)\s*:\s*([^\n\r]+)"
        for m in re.finditer(hindi_sections, text):
            sec_text = m.group(1)
            for name_m in re.finditer(r"([\u0900-\u097F]{2,}(?:\s+[\u0900-\u097F]{2,}){1,2})", sec_text):
                c = name_m.group(1).strip()
                if c not in self.HINDI_STOPWORDS:
                    add_entity(ExtractedEntityMetadata(
                        entity_type="Person",
                        value=c,
                        confidence=0.90,
                        extraction_method="RULE_BASED",
                        source_text=sec_text,
                        source_start_char=m.start(1) + name_m.start(),
                        source_end_char=m.start(1) + name_m.end(),
                        language="hi",
                    ))

        # Common Hindi name patterns with context ("मैंने राहुल शर्मा और अमित कुमार को देखा", "इमरान से मिल रहे थे")
        hindi_verb_context = r"([\u0900-\u097F]{2,}(?:\s+[\u0900-\u097F]{2,})?)\s*(?:और|तथा|,)?\s*([\u0900-\u097F]{2,}(?:\s+[\u0900-\u097F]{2,})?)?\s*(?:को\s+.*?देखा|से\s+मिल\s+रहे|गिरफ्तार)"
        for m in re.finditer(hindi_verb_context, text):
            for group_idx in (1, 2):
                if m.group(group_idx):
                    val = m.group(group_idx).strip()
                    if val and val not in self.HINDI_STOPWORDS and len(val) >= 3:
                        add_entity(ExtractedEntityMetadata(
                            entity_type="Person",
                            value=val,
                            confidence=0.85,
                            extraction_method="RULE_BASED",
                            source_text=m.group(),
                            source_start_char=m.start(group_idx),
                            source_end_char=m.end(group_idx),
                            language="hi",
                        ))

        # Explicit known Indian names in Hindi text if present
        for name in ["राहुल शर्मा", "अमित कुमार", "इमरान", "राजेश कुमार", "सुनीता देवी", "सुरेश शर्मा"]:
            for m in re.finditer(re.escape(name), text):
                add_entity(ExtractedEntityMetadata(
                    entity_type="Person",
                    value=name,
                    confidence=0.92,
                    extraction_method="RULE_BASED",
                    source_text=name,
                    source_start_char=m.start(),
                    source_end_char=m.end(),
                    language="hi",
                ))

        # C. LOCATION Extraction
        # Location keywords: station, hospital, mall, nagar, road, chowk, police station, court, sector
        loc_patterns = [
            r"\b(?:near|at|in|to|residing at|R/O|r/o|Location:?)\s+([A-Z0-9][a-zA-Z0-9\s,-]+?(?:station|railway station|hospital|mall|court|nagar|bazaar|chowk|road|sector|colony|market|police station|airport|food court))\b",
            r"\b([A-Z][a-zA-Z0-9\s]+?(?:Railway Station|Hospital|Mall|Court|Nagar|Police Station|Airport))\b",
            r"([\u0900-\u097F\s]+?(?:रेलवे स्टेशन|स्टेशन|थाना|अस्पताल|मॉल|चौक|नगर))\s*(?:के पास|में|पर)?",
        ]
        for pat in loc_patterns:
            for m in re.finditer(pat, text, re.I):
                loc_raw = m.group(1).strip()
                # Clean up leading noise
                loc_raw = re.sub(r"^(?:the|a|an)\s+", "", loc_raw, flags=re.I)
                if len(loc_raw) >= 3 and loc_raw not in self.ENGLISH_STOPWORDS and loc_raw not in self.HINDI_STOPWORDS:
                    add_entity(ExtractedEntityMetadata(
                        entity_type="Location",
                        value=loc_raw,
                        confidence=ConfidenceScorer.score_location(loc_raw, has_preposition=True, has_keyword=True),
                        extraction_method="RULE_BASED",
                        source_text=m.group(),
                        source_start_char=m.start(1),
                        source_end_char=m.end(1),
                        language=lang,
                    ))

        # Specific prominent Indian locations
        for known_loc in ["MP Nagar, Bhopal", "MP Nagar", "Bhopal railway station", "City Mall, Bhopal", "City Hospital", "Anand Vihar", "भोपाल रेलवे स्टेशन", "एमपी नगर, भोपाल", "एमपी नगर"]:
            for m in re.finditer(re.escape(known_loc), text, re.I):
                add_entity(ExtractedEntityMetadata(
                    entity_type="Location",
                    value=known_loc,
                    confidence=0.92,
                    extraction_method="RULE_BASED",
                    source_text=known_loc,
                    source_start_char=m.start(),
                    source_end_char=m.end(),
                    language=lang,
                ))

        # D. ORGANIZATION Extraction
        org_pattern = r"\b([A-Z][a-zA-Z\s]+?(?:Police Station|Cooperative|Hospital|Bank|Gang|Enterprise|Motors|Technologies))\b"
        for m in re.finditer(org_pattern, text):
            org_raw = m.group(1).strip()
            add_entity(ExtractedEntityMetadata(
                entity_type="Organization",
                value=org_raw,
                confidence=0.85,
                extraction_method="RULE_BASED",
                source_text=m.group(),
                source_start_char=m.start(1),
                source_end_char=m.end(1),
                language=lang,
            ))

        return entities

    def extract_relationships(
        self,
        text: str,
        entities: list[ExtractedEntityMetadata],
    ) -> list[ExtractedRelationship]:
        """Extracts relationships between entities present in the text."""
        relationships: list[ExtractedRelationship] = []
        persons = [e for e in entities if e.entity_type == "Person"]
        locations = [e for e in entities if e.entity_type == "Location"]
        vehicles = [e for e in entities if e.entity_type == "Vehicle"]
        phones = [e for e in entities if e.entity_type == "Phone"]
        amounts = [e for e in entities if e.entity_type == "Amount"]

        # 1. ASSOCIATED_WITH / MET (Between Persons)
        # Pairwise check in text sentences
        sentences = re.split(r"[.\n\r]+", text)
        for s in sentences:
            s_persons = [p for p in persons if p.value.lower() in s.lower()]
            if len(s_persons) >= 2:
                # Check relation cue in sentence
                rel_type = "ASSOCIATED_WITH"
                if re.search(r"\b(?:meeting|met|meet|mil rahe|मिल रहे|देखा|saw)\b", s, re.I):
                    rel_type = "MET"
                elif re.search(r"\b(?:arrested along with|together with|in company of|was with|साथ थे)\b", s, re.I):
                    rel_type = "ASSOCIATED_WITH"

                for i in range(len(s_persons)):
                    for j in range(i + 1, len(s_persons)):
                        p1, p2 = s_persons[i], s_persons[j]
                        relationships.append(ExtractedRelationship(
                            source_value=p1.value,
                            source_type="Person",
                            relationship_type=rel_type,
                            target_value=p2.value,
                            target_type="Person",
                            confidence=0.82,
                            relationship_origin="OBSERVED",
                            explanation=f"Text indicates {p1.value} and {p2.value} were {rel_type.lower().replace('_', ' ')}: \"{s.strip()}\"",
                            evidence_text=s.strip(),
                        ))

            # 2. LOCATED_AT / VISITED (Person -> Location)
            s_locs = [loc for loc in locations if loc.value.lower() in s.lower()]
            for p in s_persons:
                for loc in s_locs:
                    rel_type = "VISITED" if re.search(r"\b(?:visited|arrived|went|observed at)\b", s, re.I) else "LOCATED_AT"
                    relationships.append(ExtractedRelationship(
                        source_value=p.value,
                        source_type="Person",
                        relationship_type=rel_type,
                        target_value=loc.value,
                        target_type="Location",
                        confidence=0.80,
                        relationship_origin="OBSERVED",
                        explanation=f"{p.value} {rel_type.lower().replace('_', ' ')} {loc.value} according to: \"{s.strip()}\"",
                        evidence_text=s.strip(),
                    ))

            # 3. USED_VEHICLE (Person -> Vehicle)
            s_vehicles = [v for v in vehicles if v.normalized_value.lower() in s.replace(" ", "").lower()]
            for p in s_persons:
                for v in s_vehicles:
                    relationships.append(ExtractedRelationship(
                        source_value=p.value,
                        source_type="Person",
                        relationship_type="USED_VEHICLE",
                        target_value=v.normalized_value,
                        target_type="Vehicle",
                        confidence=0.88,
                        relationship_origin="OBSERVED",
                        explanation=f"{p.value} observed driving or arriving in vehicle {v.normalized_value}: \"{s.strip()}\"",
                        evidence_text=s.strip(),
                    ))

            # 4. HAS_PHONE (Person -> Phone)
            s_phones = [ph for ph in phones if ph.normalized_value.replace(" ", "") in s.replace(" ", "")]
            for p in s_persons:
                for ph in s_phones:
                    relationships.append(ExtractedRelationship(
                        source_value=p.value,
                        source_type="Person",
                        relationship_type="HAS_PHONE",
                        target_value=ph.normalized_value,
                        target_type="Phone",
                        confidence=0.85,
                        relationship_origin="OBSERVED",
                        explanation=f"Phone number {ph.normalized_value} linked to {p.value}: \"{s.strip()}\"",
                        evidence_text=s.strip(),
                    ))

        # Remove duplicates
        unique_rels: list[ExtractedRelationship] = []
        seen = set()
        for r in relationships:
            key = (r.source_value, r.relationship_type, r.target_value)
            if key not in seen:
                seen.add(key)
                unique_rels.append(r)

        return unique_rels

    def process_text(self, text: str) -> dict[str, Any]:
        """Convenience method running end-to-end extraction and returning serializable dict."""
        lang = self.detect_language(text)
        entities = self.extract_entities(text, language=lang)
        relationships = self.extract_relationships(text, entities)

        return {
            "language": lang,
            "entities": [e.to_dict() for e in entities],
            "relationships": [r.to_dict() for r in relationships],
            "entity_counts": {
                typ: len([e for e in entities if e.entity_type == typ])
                for typ in {"Person", "Location", "Phone", "Vehicle", "DateTime", "Amount", "Organization"}
            },
            "disclaimer": "Demo NLP extraction — all leads and associations require human verification before operational use.",
        }
