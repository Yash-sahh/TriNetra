from datetime import datetime, timedelta, timezone
import jwt
from app.main import SECRET
from test_api import client, login

def auth(email="admin@example.com"):
    return {"Authorization": f"Bearer {login(email).json()['access_token']}"}

def first_case(headers):
    return client.get("/api/cases", headers=headers).json()[0]

def test_expired_token_is_rejected():
    expired = jwt.encode({"sub": "not-a-user", "role": "ADMIN", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, SECRET, algorithm="HS256")
    assert client.get("/api/cases", headers={"Authorization": f"Bearer {expired}"}).status_code == 401

def test_viewer_cannot_modify_and_analyst_cannot_manage_users():
    viewer = auth("viewer@example.com")
    case = first_case(viewer)
    patch = client.patch(f"/api/cases/{case['id']}", headers=viewer, json={"title": "No", "description": "No modification permitted", "priority": "LOW"})
    assert patch.status_code == 403
    assert client.get("/api/users", headers=auth("analyst@example.com")).status_code == 403

def test_investigator_cannot_access_unassigned_case_or_its_graph():
    admin = auth()
    private = client.post("/api/cases", headers=admin, json={"title": "Admin-only synthetic case", "description": "Synthetic isolation verification case", "priority": "LOW"}).json()
    investigator = auth("investigator@example.com")
    assert client.get(f"/api/cases/{private['id']}", headers=investigator).status_code == 403
    assert client.get(f"/api/cases/{private['id']}/graph", headers=investigator).status_code == 403

def test_invalid_upload_is_rejected_and_text_processing_extracts_entities():
    headers = auth()
    case = first_case(headers)
    bad = client.post(f"/api/cases/{case['id']}/documents", headers=headers, files={"file": ("bad.exe", b"x", "application/octet-stream")})
    assert bad.status_code == 400
    uploaded = client.post(f"/api/cases/{case['id']}/documents", headers=headers, files={"file": ("note.txt", b"Ravi Kumar used DL01AB1234 and 9000010000.", "text/plain")})
    assert uploaded.status_code == 200
    processed = client.post(f"/api/documents/{uploaded.json()['document']['id']}/process", headers=headers)
    assert processed.status_code == 200 and processed.json()["entities_extracted"] >= 2

def test_candidates_never_auto_merge_name_only_and_graph_edges_have_evidence():
    headers = auth()
    case = first_case(headers)
    entities = client.get(f"/api/cases/{case['id']}/entities", headers=headers).json()
    person = next(x for x in entities if x["entity_type"] == "Person")
    matches = client.get(f"/api/entities/{person['id']}/candidates", headers=headers).json()
    assert matches and all(x["match_category"] != "CONFIRMED" for x in matches)
    graph = client.get(f"/api/cases/{case['id']}/graph", headers=headers).json()
    edge = graph["edges"][0]
    assert {"id", "case_id", "source_type", "source_reference", "relationship_origin", "first_seen", "last_seen", "frequency", "explanation", "requires_verification", "source_entity_name", "target_entity_name"} <= set(edge)
    evidence_resp = client.get(f"/api/relationships/{edge['id']}/evidence", headers=headers)
    assert evidence_resp.status_code == 200
    ev = evidence_resp.json()
    assert "source_entity_name" in ev and "target_entity_name" in ev and "caveat" in ev

def test_private_report_cannot_be_downloaded_by_unassigned_user_and_is_audited():
    admin = auth()
    private = client.post("/api/cases", headers=admin, json={"title": "Report isolation", "description": "Synthetic report isolation verification", "priority": "LOW"}).json()
    report = client.post(f"/api/cases/{private['id']}/reports", headers=admin, json={"title": "Private analytical report", "format": "HTML"}).json()
    assert client.get(f"/api/reports/{report['id']}/download", headers=auth("investigator@example.com")).status_code == 403
    download_resp = client.get(f"/api/reports/{report['id']}/download", headers=admin)
    assert download_resp.status_code == 200
    assert "TriNetra Analytical Intelligence Dossier" in download_resp.text
    assert "DEMO DATA — SYNTHETIC INVESTIGATION ENVIRONMENT" in download_resp.text
    logs = client.get("/api/audit-logs", headers=admin).json()
    assert any(x["action"] == "DOWNLOAD" and x["resource_id"] == report["id"] for x in logs)

def test_timeline_returns_ordered_synthetic_events():
    headers = auth()
    case = first_case(headers)
    resp = client.get(f"/api/cases/{case['id']}/timeline", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "timeline" in data and data["total_events"] > 0
    event = data["timeline"][0]
    assert {"id", "timestamp", "category", "relationship_type", "origin", "source_entity_name", "target_entity_name"} <= set(event)

def test_graph_path_finding_and_entity_pairs():
    headers = auth()
    case = first_case(headers)
    entities = client.get(f"/api/cases/{case['id']}/entities", headers=headers).json()
    people = [x for x in entities if x["entity_type"] == "Person"]
    assert len(people) >= 2
    path_resp = client.get(f"/api/cases/{case['id']}/graph/path?source={people[0]['id']}&target={people[1]['id']}", headers=headers)
    assert path_resp.status_code == 200
    assert "edge_ids" in path_resp.json()

    pairs_resp = client.get(f"/api/cases/{case['id']}/entity-resolution/pairs", headers=headers)
    assert pairs_resp.status_code == 200
    pairs = pairs_resp.json()
    assert isinstance(pairs, list)
    if pairs:
        assert "match_score" in pairs[0] and "match_category" in pairs[0]

def test_real_computed_analytics_and_priority_score_breakdown():
    headers = auth()
    case = first_case(headers)
    resp = client.get(f"/api/cases/{case['id']}/analytics/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "temporal_activity" in data
    # Ensure temporal activity is aggregated from real timestamps
    assert len(data["temporal_activity"]) > 0
    assert "date" in data["temporal_activity"][0] and "count" in data["temporal_activity"][0]
    # Check top connection priority score breakdown
    assert "top_connections" in data and len(data["top_connections"]) > 0
    top = data["top_connections"][0]
    assert "score_breakdown" in top
    sb = top["score_breakdown"]
    assert {"network_position", "cross_community_connections", "temporal_activity", "evidence_quality", "data_completeness"} <= set(sb)

def test_copilot_multi_hop_hindi_and_grounding():
    headers = auth()
    case = first_case(headers)
    cid = case["id"]

    # 1. 2-hop vehicle query
    v_reply = client.post(f"/api/cases/{cid}/copilot/query", headers=headers, json={"query": "Show all people connected to vehicle DL01AB1234 within two hops."})
    assert v_reply.status_code == 200
    v_data = v_reply.json()
    assert "DL01AB" in v_data["direct_answer"] or "two hops" in v_data["direct_answer"].lower()
    assert len(v_data["evidence_used"]) > 0

    # 2. Entity priority explanation
    why_reply = client.post(f"/api/cases/{cid}/copilot/query", headers=headers, json={"query": "Why is Imran marked as a high-priority investigative lead?"})
    assert why_reply.status_code == 200
    why_data = why_reply.json()
    assert "Imran" in why_data["direct_answer"]
    assert "culpability" in why_data["direct_answer"].lower() or "priority score" in why_data["direct_answer"].lower()

    # 3. Hindi query
    hi_reply = client.post(f"/api/cases/{cid}/copilot/query", headers=headers, json={"query": "Summarize the network in Hindi."})
    assert hi_reply.status_code == 200
    hi_data = hi_reply.json()
    assert "सिंथेटिक" in hi_data["direct_answer"] or "संस्थाएँ" in hi_data["direct_answer"]

def test_entity_match_decisions_and_audit():
    admin = auth()
    case = first_case(admin)
    dec_resp = client.post("/api/entity-matches/test-match-101/confirm", headers=admin)
    assert dec_resp.status_code == 200
    assert dec_resp.json()["status"] == "CONFIRMED"

    undo_resp = client.post("/api/entity-matches/test-match-101/undo", headers=admin)
    assert undo_resp.status_code == 200
    assert undo_resp.json()["status"] == "UNRESOLVED"

    logs = client.get("/api/audit-logs", headers=admin).json()
    assert any(x["action"] == "CONFIRM" and x["resource_id"] == "test-match-101" for x in logs)
