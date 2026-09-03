"""Comprehensive test suite for unstructured data ingestion, NLP extraction, OCR, normalization, and generalization."""
from pathlib import Path
import pytest
from app.main import app, ROOT, SessionLocal, Entity, Relation, Document, Case
from app.services.nlp_extraction import NLPExtractionService
from app.services.parsers.fir_parser import FIRParser
from app.services.parsers.cdr_parser import CDRParser
from app.services.parsers.transaction_parser import TransactionParser
from app.services.parsers.surveillance_parser import SurveillanceParser
from app.services.parsers.social_media_parser import SocialMediaParser
from app.services.ocr_service import OCRService
from app.services.entity_normalization import EntityNormalizationService
from app.services.document_processing import DocumentProcessingPipeline
from fastapi.testclient import TestClient

client = TestClient(app)

def auth_headers(email="admin@example.com"):
    res = client.post("/api/auth/login", json={"email": email, "password": "TriNetraDemo!2026"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}

def test_nlp_extraction_english_fir():
    text = (ROOT / "seed" / "sample_fir.txt").read_text(encoding="utf-8")
    service = NLPExtractionService()
    entities = service.extract_entities(text)
    
    # Verify Person entities extracted
    person_names = {e.value for e in entities if e.entity_type == "Person"}
    assert "Rahul Sharma" in person_names or any("Rahul" in n for n in person_names)
    assert "Amit Kumar" in person_names or any("Amit" in n for n in person_names)
    assert "Imran" in person_names or any("Imran" in n for n in person_names)
    
    # Verify Vehicle and Phone
    vehicles = {e.normalized_value for e in entities if e.entity_type == "Vehicle"}
    phones = {e.normalized_value for e in entities if e.entity_type == "Phone"}
    assert "MP09AB1234" in vehicles
    assert any("98765" in p for p in phones)

    # Relationships
    rels = service.extract_relationships(text, entities)
    assert len(rels) >= 2
    rel_types = {r.relationship_type for r in rels}
    assert "MET" in rel_types or "ASSOCIATED_WITH" in rel_types or "USED_VEHICLE" in rel_types

def test_nlp_extraction_hindi_fir():
    text = (ROOT / "seed" / "sample_fir_hindi.txt").read_text(encoding="utf-8")
    service = NLPExtractionService()
    
    lang = service.detect_language(text)
    assert lang == "hi"
    
    entities = service.extract_entities(text)
    person_names = {e.value for e in entities if e.entity_type == "Person"}
    assert "राहुल शर्मा" in person_names
    assert "अमित कुमार" in person_names or any("अमित" in n for n in person_names)
    assert "इमरान" in person_names
    
    vehicles = {e.normalized_value for e in entities if e.entity_type == "Vehicle"}
    assert "MP09AB1234" in vehicles

def test_nlp_extraction_phone_vehicle_location_amount():
    text = (
        "On 15 January 2026 at 14:00, suspect transferred ₹50,000 to partner near Bhopal railway station. "
        "Contact number was +91 9876543210 and getaway car was MP09CD5678."
    )
    service = NLPExtractionService()
    entities = service.extract_entities(text)

    types = {e.entity_type for e in entities}
    assert "Phone" in types
    assert "Vehicle" in types
    assert "Amount" in types
    assert "Location" in types or "DateTime" in types

    phone_ent = next(e for e in entities if e.entity_type == "Phone")
    assert phone_ent.confidence >= 0.90
    assert phone_ent.extraction_method == "REGEX"
    assert phone_ent.normalized_value == "+91 98765 43210"

    amt_ent = next(e for e in entities if e.entity_type == "Amount")
    assert amt_ent.confidence >= 0.90
    assert "50,000" in amt_ent.value or "50000" in amt_ent.normalized_value

def test_multilingual_language_detection():
    service = NLPExtractionService()
    assert service.detect_language("FIR No. 102/2026 registered at Police Station.") == "en"
    assert service.detect_language("FIR संख्या 103/2026 थाना एमपी नगर में दर्ज की गई।") == "hi"
    assert service.detect_language("Rahul ne Amit ko phone kiya tha aur meeting confirm ki.") == "hinglish"

def test_fir_parser_structured_output():
    text = (ROOT / "seed" / "sample_fir.txt").read_text(encoding="utf-8")
    parser = FIRParser()
    res = parser.parse(text)
    assert res["document_type"] == "FIR"
    assert res["metadata"]["fir_number"] == "102/2026"
    assert "MP Nagar" in res["metadata"]["police_station"]
    assert len(res["entities"]) >= 4
    assert len(res["relationships"]) >= 2

def test_cdr_csv_parser_and_weighting():
    content = (ROOT / "seed" / "sample_cdr.csv").read_text(encoding="utf-8")
    parser = CDRParser()
    res = parser.parse(content)
    assert res["document_type"] == "CDR"
    assert res["total_calls"] == 3
    assert res["unique_phone_count"] >= 3
    
    # Check CALLED relationships
    rels = res["relationships"]
    assert len(rels) >= 2
    called_rel = rels[0]
    assert called_rel["relationship_type"] == "CALLED"
    assert called_rel["confidence"] >= 0.70
    assert called_rel["frequency"] >= 1

def test_transaction_parser_circular_flow_detection():
    content = (ROOT / "seed" / "sample_transactions.csv").read_text(encoding="utf-8")
    parser = TransactionParser()
    res = parser.parse(content)
    assert res["document_type"] == "FINANCIAL_TRANSACTIONS"
    assert res["total_transactions"] == 3
    assert len(res["relationships"]) == 3

    # Verify circular flow detection (Rahul -> Amit -> Imran -> Rahul)
    patterns = res["patterns_detected"]
    assert any(p["pattern_type"] == "CIRCULAR_FLOW" for p in patterns)
    circ_p = next(p for p in patterns if p["pattern_type"] == "CIRCULAR_FLOW")
    assert circ_p["severity"] == "HIGH"
    assert "Rahul Sharma" in circ_p["entities_involved"]

def test_surveillance_parser():
    content = (ROOT / "seed" / "sample_surveillance.txt").read_text(encoding="utf-8")
    parser = SurveillanceParser()
    res = parser.parse(content)
    assert res["document_type"] == "SURVEILLANCE_REPORT"
    assert "City Mall, Bhopal" in res["metadata"]["location"]
    entities = res["entities"]
    names = {e["value"] for e in entities if e["entity_type"] == "Person"}
    assert "Amit Kumar" in names or any("Amit" in n for n in names)
    assert "Rahul Sharma" in names or any("Rahul" in n for n in names)
    assert any(e["entity_type"] == "Vehicle" and "MP09AB1234" in e["normalized_value"] for e in entities)

def test_social_media_parser():
    json_dump = """
    {
        "posts": [
            {
                "author": "@rahul_ops",
                "text": "Meeting at City Center",
                "following": ["@amit_driver", "@imran_bhopal"],
                "mentions": ["@amit_driver"],
                "location": "City Center, Bhopal",
                "timestamp": "2026-01-14T20:00:00Z"
            }
        ]
    }
    """
    parser = SocialMediaParser()
    res = parser.parse(json_dump)
    assert res["document_type"] == "SOCIAL_MEDIA"
    rel_types = {r["relationship_type"] for r in res["relationships"]}
    assert "FOLLOWS" in rel_types
    assert "INTERACTED_WITH" in rel_types
    assert "POSTED_AT" in rel_types

def test_ocr_service_graceful_fallback():
    ocr = OCRService()
    # Test text file direct read
    sample_file = ROOT / "seed" / "sample_fir.txt"
    read_res = ocr.extract_text_from_file(sample_file)
    assert read_res["success"] is True
    assert "FIR No. 102/2026" in read_res["text"]

    # Test image fallback or processing without crashing
    img_res = ocr.extract_text_from_image(b"fake image bytes")
    assert "notice" in img_res

def test_entity_normalization_and_duplicate_candidates():
    norm = EntityNormalizationService()
    # Phone normalization
    assert norm.normalize_phone("9876543210") == "+91 98765 43210"
    assert norm.normalize_phone("+91 9876543210") == "+91 98765 43210"
    assert norm.normalize_phone("09876543210") == "+91 98765 43210"

    # Vehicle normalization
    assert norm.normalize_vehicle("dl 01 ab 1234") == "DL01AB1234"
    assert norm.normalize_vehicle("MP-09-CD-5678") == "MP09CD5678"

    # Amount parsing
    assert norm.normalize_amount("₹50,000") == 50000.0
    assert norm.normalize_amount("Rs. 45000") == 45000.0
    assert norm.normalize_amount("50K") == 50000.0
    assert norm.normalize_amount("1.5 Lakh") == 150000.0

    # Person name normalization and candidate detection
    assert norm.normalize_person_name("Shri Mohd. Imran") == "Mohammad Imran"
    assert norm.normalize_person_name("Mr. Rajesh Kr.") == "Rajesh Kumar"

    # Similarity checks
    sim_phone = norm.calculate_similarity("Phone", "9876543210", "+91 98765 43210")
    assert sim_phone == 1.0

    sim_name = norm.calculate_similarity("Person", "Rahul Sharma", "Rahul")
    assert sim_name >= 0.80

    candidates = norm.generate_merge_candidates(
        {"entity_type": "Person", "canonical_name": "Rahul Sharma"},
        [{"id": "1", "entity_type": "Person", "canonical_name": "Rahul"}, {"id": "2", "entity_type": "Person", "canonical_name": "Zoya Mirza"}]
    )
    assert len(candidates) >= 1
    assert candidates[0]["candidate_value"] == "Rahul"
    assert candidates[0]["requires_confirmation"] is True

def test_unseen_fir_generalization():
    """Requirement 11: System must work on UNSEEN data formats without overfitting."""
    unseen_text = (ROOT / "seed" / "test_unseen_fir.txt").read_text(encoding="utf-8")
    service = NLPExtractionService()
    entities = service.extract_entities(unseen_text)

    persons = [e for e in entities if e.entity_type == "Person"]
    vehicles = [e for e in entities if e.entity_type == "Vehicle"]
    phones = [e for e in entities if e.entity_type == "Phone"]

    assert len(persons) >= 2, f"Expected >= 2 persons, got: {[p.value for p in persons]}"
    assert len(vehicles) >= 1, f"Expected >= 1 vehicle, got: {[v.value for v in vehicles]}"
    assert len(phones) >= 1, f"Expected >= 1 phone, got: {[p.value for p in phones]}"

    # Verify extracted values
    person_vals = {p.value for p in persons}
    assert any("Vikram" in n for n in person_vals)
    assert any("Rohit" in n for n in person_vals)
    assert any("DL3CAF5678" in v.normalized_value for v in vehicles)
    assert any("9988776655" in p.normalized_value.replace(" ", "") for p in phones)

def test_end_to_end_document_upload_and_pipeline_integration():
    """End-to-end integration: Upload raw FIR file, verify entities and relationships in DB, graph, and timeline."""
    headers = auth_headers()
    cases = client.get("/api/cases", headers=headers).json()
    case_id = cases[0]["id"]

    fir_content = b"""FIR No. 999/2026
Date: 25 January 2026
Police Station: MP Nagar, Bhopal

Incident: SI Sharma questioned Deepak Verma regarding vehicle MP04XY9999.
Deepak called partner at 9826011111 while near Bhopal railway station.

Accused:
Deepak Verma
"""
    # 1. Upload
    up_res = client.post(
        f"/api/cases/{case_id}/documents",
        headers=headers,
        files={"file": ("fir_999.txt", fir_content, "text/plain")},
    )
    assert up_res.status_code == 200
    doc_id = up_res.json()["document"]["id"]
    assert up_res.json()["entities_extracted"] >= 2

    # 2. Document content inspect
    doc_content = client.get(f"/api/documents/{doc_id}/content", headers=headers).json()
    assert "Deepak Verma" in doc_content["content"]
    assert len(doc_content["entities"]) >= 2

    # 3. Verify Graph has Deepak Verma and MP04XY9999
    graph = client.get(f"/api/cases/{case_id}/graph", headers=headers).json()
    node_labels = {n["label"] for n in graph["nodes"]}
    assert any("Deepak Verma" in l for l in node_labels)
    assert any("MP04XY9999" in l for l in node_labels)

    # 4. Verify Timeline contains events from this case
    timeline = client.get(f"/api/cases/{case_id}/timeline", headers=headers).json()
    assert timeline["total_events"] > 0

    # 5. Verify Grounded Copilot query on new data
    copilot_res = client.post(
        f"/api/cases/{case_id}/copilot/query",
        headers=headers,
        json={"query": "What vehicles are associated with Deepak Verma?"}
    ).json()
    assert "MP04XY9999" in copilot_res["direct_answer"] or len(copilot_res["evidence_used"]) >= 1

    # 6. Test manual entity addition and deletion
    new_ent = client.post(
        f"/api/cases/{case_id}/entities",
        headers=headers,
        json={"canonical_name": "Manoj Tiwari", "entity_type": "Person", "confidence": 0.95}
    ).json()
    assert new_ent["canonical_name"] == "Manoj Tiwari"

    # Edit entity
    edit_res = client.patch(
        f"/api/entities/{new_ent['id']}",
        headers=headers,
        json={"verification_status": "CONFIRMED"}
    ).json()
    assert edit_res["verification_status"] == "CONFIRMED"

    # Delete entity
    del_res = client.delete(f"/api/entities/{new_ent['id']}", headers=headers).json()
    assert del_res["ok"] is True
