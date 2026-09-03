"""FIR (First Information Report) and police report document parser."""
from __future__ import annotations

import re
from typing import Any
from ..nlp_extraction import ExtractedRelationship, NLPExtractionService
from ..nlp.confidence_scorer import ExtractedEntityMetadata

class FIRParser:
    """Specialized parser for FIRs and Police Investigation Reports (English and Hindi)."""

    def __init__(self, nlp_service: NLPExtractionService | None = None):
        self.nlp = nlp_service or NLPExtractionService()

    def parse(self, text: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "fir_number": None,
            "fir_date": None,
            "police_station": None,
            "complainants": [],
            "accused": [],
            "witnesses": [],
            "incident_description": "",
            "crime_location": None,
            "incident_time": None,
        }

        # 1. FIR Number
        fir_m = re.search(r"(?:FIR\s*(?:No\.?|Number|संख्या))\s*:?\s*([A-Za-z0-9/_-]+)", text, re.I)
        if fir_m:
            metadata["fir_number"] = fir_m.group(1).strip()

        # 2. Date
        date_m = re.search(r"(?:Date|दिनांक)\s*:\s*([^\n\r]+)", text, re.I)
        if date_m:
            metadata["fir_date"] = date_m.group(1).strip()

        # 3. Police Station
        ps_m = re.search(r"(?:Police\s*Station|थाना)\s*:\s*([^\n\r]+)", text, re.I)
        if ps_m:
            metadata["police_station"] = ps_m.group(1).strip()

        # 4. Complainant
        comp_m = re.search(r"(?:Complainant|शिकायतकर्ता|फरियादी)\s*:\s*([^\n\r]+)", text, re.I)
        if comp_m:
            raw_comp = comp_m.group(1).strip()
            # Extract just name
            name_cand = re.split(r",|\s+(?:S/O|D/O|W/O|R/O|पुत्र|पिता)", raw_comp)[0].strip()
            if name_cand:
                metadata["complainants"].append(name_cand)

        # 5. Accused
        acc_m = re.search(r"(?:Accused|आरोपी)\s*:\s*([\s\S]+?)(?=(?:Witnesses?|साक्षी|Incident|घटना|Details|$))", text, re.I)
        if acc_m:
            lines = [l.strip() for l in acc_m.group(1).splitlines() if l.strip()]
            for line in lines:
                name_cand = re.split(r",|\s+(?:S/O|D/O|W/O|alias|उर्फ़|उर्फ|\()", line)[0].strip()
                if name_cand and name_cand not in {"None", "Unknown", "अज्ञात"}:
                    metadata["accused"].append(name_cand)

        # 6. Witnesses
        wit_m = re.search(r"(?:Witnesses?|साक्षी|गवाह)\s*:\s*([^\n\r]+)", text, re.I)
        if wit_m:
            for w in re.split(r",|and|तथा|और", wit_m.group(1)):
                clean_w = w.strip()
                if clean_w:
                    metadata["witnesses"].append(clean_w)

        # Run multi-layer NLP extraction on full text
        extracted_entities = self.nlp.extract_entities(text)

        # Ensure FIR number is captured as a CrimeEvent entity
        if metadata["fir_number"]:
            extracted_entities.append(ExtractedEntityMetadata(
                entity_type="CrimeEvent",
                value=f"FIR-{metadata['fir_number']}",
                confidence=0.98,
                extraction_method="RULE_BASED",
                source_text=f"FIR No. {metadata['fir_number']}",
                source_start_char=0,
                source_end_char=0,
            ))

        # Ensure complainant / accused / witnesses are registered as Person entities
        known_names = {e.value.lower() for e in extracted_entities if e.entity_type == "Person"}
        for role_list in (metadata["complainants"], metadata["accused"], metadata["witnesses"]):
            for name in role_list:
                if name.lower() not in known_names and len(name) >= 3:
                    extracted_entities.append(ExtractedEntityMetadata(
                        entity_type="Person",
                        value=name,
                        confidence=0.94,
                        extraction_method="RULE_BASED",
                        source_text=name,
                    ))
                    known_names.add(name.lower())

        # Extract relationships
        relationships = self.nlp.extract_relationships(text, extracted_entities)

        # Connect accused with CrimeEvent
        if metadata["fir_number"]:
            fir_val = f"FIR-{metadata['fir_number']}"
            for acc in metadata["accused"]:
                relationships.append(ExtractedRelationship(
                    source_value=acc,
                    source_type="Person",
                    relationship_type="MENTIONED_IN",
                    target_value=fir_val,
                    target_type="CrimeEvent",
                    confidence=0.92,
                    relationship_origin="OBSERVED",
                    explanation=f"Named as accused in {fir_val}",
                    evidence_text=f"Accused in FIR {metadata['fir_number']}",
                ))

        return {
            "document_type": "FIR",
            "metadata": metadata,
            "entities": [e.to_dict() for e in extracted_entities],
            "relationships": [r.to_dict() for r in relationships],
            "total_entities": len(extracted_entities),
            "total_relationships": len(relationships),
        }
