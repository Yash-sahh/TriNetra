"""End-to-end document processing pipeline integrating parsers, OCR, NLP, and database persistence."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .entity_normalization import EntityNormalizationService
from .nlp_extraction import NLPExtractionService
from .ocr_service import OCRService
from .parsers.cdr_parser import CDRParser
from .parsers.fir_parser import FIRParser
from .parsers.social_media_parser import SocialMediaParser
from .parsers.surveillance_parser import SurveillanceParser
from .parsers.transaction_parser import TransactionParser

logger = logging.getLogger("trinetra.pipeline")

class DocumentProcessingPipeline:
    """Orchestrates file reading, parser selection, NLP extraction, and database persistence."""

    def __init__(self):
        self.nlp = NLPExtractionService()
        self.ocr = OCRService()
        self.fir_parser = FIRParser(self.nlp)
        self.cdr_parser = CDRParser()
        self.txn_parser = TransactionParser()
        self.surv_parser = SurveillanceParser(self.nlp)
        self.social_parser = SocialMediaParser()

    def process_file(
        self,
        file_path: Path,
        case_id: str,
        document_id: str,
        db_session: Session,
        entity_model: Any,
        relation_model: Any,
        document_model: Any,
    ) -> dict[str, Any]:
        """Reads file, extracts text, runs specialized parser, and persists entities/relations."""
        doc = db_session.get(document_model, document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        doc.processing_status = "PROCESSING"
        db_session.commit()

        # 1. Text Extraction
        read_res = self.ocr.extract_text_from_file(file_path)
        content = read_res.get("text", "")
        suffix = file_path.suffix.lower()

        if not content and not read_res.get("success"):
            doc.processing_status = "REQUIRES_MANUAL_REVIEW"
            db_session.commit()
            return {
                "status": "REQUIRES_MANUAL_REVIEW",
                "entities_extracted": 0,
                "relationships_extracted": 0,
                "notice": read_res.get("notice", "Unable to extract text automatically."),
            }

        # 2. Routing & Parsing
        parser_name = "Generic NLP"
        extracted_entities: list[dict[str, Any]] = []
        extracted_relationships: list[dict[str, Any]] = []
        detected_lang = "en"
        patterns_detected = []

        if suffix == ".csv":
            first_line = content.strip().splitlines()[0].lower() if content.strip() else ""
            if any(k in first_line for k in ("caller", "dialed", "duration", "tower", "cell", "msisdn")):
                parser_name = "CDR Parser"
                cdr_res = self.cdr_parser.parse(content)
                extracted_entities = cdr_res["entities"]
                extracted_relationships = cdr_res["relationships"]
            elif any(k in first_line for k in ("account", "amount", "debit", "credit", "txn", "remitter", "beneficiary")):
                parser_name = "Transaction Parser"
                txn_res = self.txn_parser.parse(content)
                extracted_entities = txn_res["entities"]
                extracted_relationships = txn_res["relationships"]
                patterns_detected = txn_res.get("patterns_detected", [])
            else:
                parser_name = "Generic Table NLP"
                nlp_res = self.nlp.process_text(content)
                extracted_entities = nlp_res["entities"]
                extracted_relationships = nlp_res["relationships"]
                detected_lang = nlp_res["language"]

        elif suffix == ".json":
            parser_name = "Social Media Parser"
            soc_res = self.social_parser.parse(content)
            extracted_entities = soc_res["entities"]
            extracted_relationships = soc_res["relationships"]

        else:
            # Free-text: TXT, PDF, DOCX, or OCR
            detected_lang = self.nlp.detect_language(content)
            if any(k in content for k in ("FIR No", "FIR संख्या", "Police Station", "थाना:", "Complainant:", "आरोपी:", "Case Diary")):
                parser_name = "FIR Parser"
                fir_res = self.fir_parser.parse(content)
                extracted_entities = fir_res["entities"]
                extracted_relationships = fir_res["relationships"]
            elif "Surveillance Report" in content or "Observation:" in content or "Subject: " in content:
                parser_name = "Surveillance Parser"
                surv_res = self.surv_parser.parse(content)
                extracted_entities = surv_res["entities"]
                extracted_relationships = surv_res["relationships"]
            else:
                parser_name = "Generic Multilingual NLP"
                nlp_res = self.nlp.process_text(content)
                extracted_entities = nlp_res["entities"]
                extracted_relationships = nlp_res["relationships"]

        # 3. Database Entity Persistence (Deduplicating within Case Scope)
        existing_entities = db_session.scalars(
            select(entity_model).where(entity_model.case_id == case_id)
        ).all()
        entity_map: dict[str, Any] = {}  # normalized_val/val.lower() -> Entity DB instance
        for e in existing_entities:
            entity_map[e.canonical_name.lower()] = e
            entity_map[e.normalized_value.lower()] = e

        persisted_entity_map: dict[str, Any] = {}  # raw_val -> DB instance

        for ent_data in extracted_entities:
            e_type = ent_data.get("entity_type", "Entity")
            raw_val = ent_data.get("value", "").strip()
            if not raw_val or len(raw_val) < 2:
                continue

            norm_val = ent_data.get("normalized_value") or raw_val
            if e_type == "Phone":
                norm_val = EntityNormalizationService.normalize_phone(raw_val)
            elif e_type == "Vehicle":
                norm_val = EntityNormalizationService.normalize_vehicle(raw_val)
            elif e_type == "Person":
                norm_val = EntityNormalizationService.normalize_person_name(raw_val)

            key = norm_val.lower()
            existing_db = entity_map.get(key) or entity_map.get(raw_val.lower())

            if existing_db:
                persisted_entity_map[raw_val] = existing_db
                persisted_entity_map[norm_val] = existing_db
            else:
                conf = ent_data.get("confidence", 0.80)
                ver_status = "VERIFIED" if conf >= 0.88 else "PROBABLE"
                db_ent = entity_model(
                    id=str(uuid.uuid4()),
                    case_id=case_id,
                    entity_type=e_type,
                    canonical_name=norm_val,
                    raw_text=raw_val,
                    normalized_value=norm_val.lower(),
                    confidence=conf,
                    verification_status=ver_status,
                    source_document_id=document_id,
                    source_page=ent_data.get("source_page", 1),
                    source_text_span=str(ent_data.get("source_text", raw_val))[:200],
                    extraction_method=ent_data.get("extraction_method", "RULE_BASED"),
                    source_start_char=ent_data.get("source_start_char", 0),
                    source_end_char=ent_data.get("source_end_char", 0),
                    language=ent_data.get("language", detected_lang),
                    requires_verification=ent_data.get("requires_verification", conf < 0.85),
                    created_at=datetime.now(timezone.utc),
                )
                db_session.add(db_ent)
                db_session.flush()
                entity_map[key] = db_ent
                entity_map[raw_val.lower()] = db_ent
                persisted_entity_map[raw_val] = db_ent
                persisted_entity_map[norm_val] = db_ent

        # 4. Database Relationship Persistence
        new_relations_count = 0
        now = datetime.now(timezone.utc)
        for rel_data in extracted_relationships:
            src_val = rel_data.get("source_value")
            tgt_val = rel_data.get("target_value")
            src_ent = persisted_entity_map.get(src_val)
            tgt_ent = persisted_entity_map.get(tgt_val)

            if not src_ent or not tgt_ent or src_ent.id == tgt_ent.id:
                continue

            rel_type = rel_data.get("relationship_type", "ASSOCIATED_WITH")
            conf = rel_data.get("confidence", 0.75)
            origin = rel_data.get("relationship_origin", "OBSERVED")
            explanation = rel_data.get("explanation") or f"Extracted association between {src_ent.canonical_name} and {tgt_ent.canonical_name}"

            db_rel = relation_model(
                id=str(uuid.uuid4()),
                case_id=case_id,
                source_entity_id=src_ent.id,
                target_entity_id=tgt_ent.id,
                relationship_type=rel_type,
                direction="DIRECTED",
                confidence=conf,
                evidence_type=f"Unstructured {parser_name}",
                source_document_id=document_id,
                source_reference=f"DOC-{doc.filename[:12]}",
                observed_at=now,
                first_seen=now,
                last_seen=now,
                verification_status="VERIFIED" if conf >= 0.88 else "PROBABLE",
                explanation=explanation,
                relationship_origin=origin,
                requires_verification=conf < 0.88,
                frequency=rel_data.get("frequency", 1),
                amount=rel_data.get("amount"),
                created_at=now,
            )
            db_session.add(db_rel)
            new_relations_count += 1

        doc.processing_status = "COMPLETED"
        doc.language = detected_lang
        db_session.commit()

        return {
            "status": "COMPLETED",
            "parser_used": parser_name,
            "language": detected_lang,
            "entities_extracted": len(extracted_entities),
            "relationships_extracted": new_relations_count,
            "patterns_detected": patterns_detected,
            "notice": f"Processed via {parser_name}. Associations require investigator corroboration.",
        }
