import os
os.environ["DATABASE_URL"]="sqlite:///./test_trinetra.db"
from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)
def login(email="admin@example.com"):
    return client.post("/api/auth/login",json={"email":email,"password":"TriNetraDemo!2026"})
def test_health_and_login():
    assert client.get("/api/health").status_code==200
    assert login().status_code==200
def test_passwordless_demo_login():
    reply=client.post("/api/auth/demo-login")
    assert reply.status_code==200 and reply.json()["user"]["role"]=="ADMIN"
def test_protected_case_graph_and_copilot():
    t=login().json()["access_token"];h={"Authorization":f"Bearer {t}"}; cases=client.get("/api/cases",headers=h).json(); assert cases
    cid=cases[0]["id"]; assert client.get(f"/api/cases/{cid}/graph",headers=h).json()["nodes"]
    reply=client.post(f"/api/cases/{cid}/copilot/query",headers=h,json={"query":"What data gaps affect this case?"});assert reply.status_code==200 and "evidence_used" in reply.json()
def test_viewer_cannot_create_case():
    t=login("viewer@example.com").json()["access_token"];r=client.post("/api/cases",headers={"Authorization":f"Bearer {t}"},json={"title":"Test case","description":"synthetic test","priority":"LOW"});assert r.status_code==403
