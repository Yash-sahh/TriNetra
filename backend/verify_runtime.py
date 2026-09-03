"""Comprehensive end-to-end verification script for TriNetra."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("--- 1. Health & Disclaimer ---")
h = client.get("/api/health")
assert h.status_code == 200
print("Health OK:", h.json())

print("--- 2. Login Flow ---")
login_res = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "TriNetraDemo!2026"})
assert login_res.status_code == 200
token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("Login OK, user:", login_res.json()["user"]["name"], "Role:", login_res.json()["user"]["role"])

print("--- 3. Case List & Selection ---")
cases = client.get("/api/cases", headers=headers).json()
assert len(cases) > 0
case_id = cases[0]["id"]
print("Active case:", cases[0]["case_number"], "-", cases[0]["title"])

print("--- 4. Graph & Edge Evidence ---")
graph = client.get(f"/api/cases/{case_id}/graph", headers=headers).json()
assert len(graph["nodes"]) >= 20
assert len(graph["edges"]) >= 50
print(f"Graph loaded: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
edge = graph["edges"][0]
print(f"Sample Edge: {edge['source_entity_name']} -> {edge['target_entity_name']} ({edge['relationship_type']}, {edge['relationship_origin']})")

ev = client.get(f"/api/relationships/{edge['id']}/evidence", headers=headers).json()
assert "caveat" in ev and "source_reference" in ev
print(f"Evidence citation verified: {ev['source_reference']} | Caveat: {ev['caveat']}")

print("--- 5. Path Finding ---")
path_res = client.get(f"/api/cases/{case_id}/graph/path?source={graph['nodes'][0]['id']}&target={graph['nodes'][1]['id']}", headers=headers).json()
print("Path result:", path_res["message"])

print("--- 6. Chronological Timeline ---")
timeline = client.get(f"/api/cases/{case_id}/timeline", headers=headers).json()
assert len(timeline["timeline"]) > 0
print(f"Timeline verified: {timeline['total_events']} events. Latest: {timeline['timeline'][0]['relationship_type']} at {timeline['timeline'][0]['timestamp']}")

print("--- 7. Analytics & Explainable Score ---")
analytics = client.get(f"/api/cases/{case_id}/analytics/summary", headers=headers).json()
assert len(analytics["temporal_activity"]) > 0
assert len(analytics["top_connections"]) > 0
top = analytics["top_connections"][0]
print(f"Top Lead: {top['name']} (Score {top['investigation_priority_score']}/100)")
print("Score breakdown:", top["score_breakdown"])

print("--- 8. Alerts & Data Gaps ---")
alerts = client.get(f"/api/cases/{case_id}/alerts", headers=headers).json()
gaps = client.get(f"/api/cases/{case_id}/data-gaps", headers=headers).json()
print(f"Alerts: {len(alerts)}, Data Gaps: {len(gaps)}")

print("--- 9. Grounded Copilot ---")
for q in [
    "Show all people connected to vehicle DL01AB1234 within two hops.",
    "Why is Imran marked as a high-priority investigative lead?",
    "Summarize the network in Hindi.",
    "What data gaps affect this case?",
]:
    ans = client.post(f"/api/cases/{case_id}/copilot/query", headers=headers, json={"query": q}).json()
    print(f"Query: {q}")
    print(f"Answer preview: {ans['direct_answer'][:90].encode('ascii', 'replace').decode()}...")
    print(f"Evidence used: {ans['evidence_used'][:2]} | Conf: {int(ans['confidence']*100)}%")

print("--- 10. Report Generation & HTML Download ---")
rep = client.post(f"/api/cases/{case_id}/reports", headers=headers, json={"title": "Live Verification Briefing Dossier", "format": "HTML"}).json()
dossier = client.get(f"/api/reports/{rep['id']}/download", headers=headers)
assert dossier.status_code == 200
assert "TriNetra Analytical Intelligence Dossier" in dossier.text
assert "DEMO DATA — SYNTHETIC INVESTIGATION ENVIRONMENT" in dossier.text
print(f"Report dossier HTML generated and verified (size: {len(dossier.text)} bytes)")

print("--- 11. Entity Resolution Pairs & Decision ---")
pairs = client.get(f"/api/cases/{case_id}/entity-resolution/pairs", headers=headers).json()
print(f"Entity pairs available for human review: {len(pairs)}")
if pairs:
    pair = pairs[0]
    dec = client.post(f"/api/entity-matches/{pair['id']}/confirm", headers=headers).json()
    print("Match decision recorded:", dec["message"])

print("--- 12. Audit Trail ---")
audit_logs = client.get("/api/audit-logs", headers=headers).json()
assert len(audit_logs) > 0
print(f"Audit trail verified: {len(audit_logs)} logs recorded. Latest action: {audit_logs[0]['action']} on {audit_logs[0]['resource_type']}")

print("=============================================")
print("ALL 12 CORE FUNCTIONAL VERIFICATION PHASES PASSED!")
print("=============================================")
