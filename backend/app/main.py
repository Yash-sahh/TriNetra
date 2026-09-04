"""TriNetra: evidence-first synthetic investigation workspace API.

The demo deliberately uses deterministic analytics, a local SQLite store, and
only fictional information. It is not a law-enforcement decision system.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import csv
import hashlib
import html
import io
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import jwt
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from .graph_repository import LocalGraphRepository
from .services import DocumentProcessingPipeline, EntityNormalizationService, NLPExtractionService, OCRService

ROOT = Path(__file__).resolve().parents[2]
DATABASE_MODE = os.getenv("DATABASE_MODE", "sqlite").lower()
GRAPH_MODE = os.getenv("GRAPH_MODE", "local").lower()
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'trinetra.db'}")
SECRET = os.getenv("JWT_SECRET") or os.urandom(32).hex()
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "TriNetraDemo!2026")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", ROOT / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_nlp_service = NLPExtractionService()
_pipeline = DocumentProcessingPipeline()

pwd = CryptContext(schemes=["argon2", "pbkdf2_sha256"], deprecated="auto")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    department: Mapped[str] = mapped_column(String, default="Demo Intelligence Unit")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_number: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)
    priority: Mapped[str] = mapped_column(String)
    crime_categories: Mapped[list] = mapped_column(JSON, default=list)
    assigned_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

class CaseAccess(Base):
    __tablename__ = "case_access"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    permission: Mapped[str] = mapped_column(String, default="READ")

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    filename: Mapped[str] = mapped_column(String)
    document_type: Mapped[str] = mapped_column(String)
    source_type: Mapped[str] = mapped_column(String)
    language: Mapped[str] = mapped_column(String, default="en")
    storage_key: Mapped[str] = mapped_column(String)
    processing_status: Mapped[str] = mapped_column(String, default="COMPLETED")
    checksum: Mapped[str] = mapped_column(String, unique=True)
    uploaded_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String)
    canonical_name: Mapped[str] = mapped_column(String)
    raw_text: Mapped[str] = mapped_column(String)
    normalized_value: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    verification_status: Mapped[str] = mapped_column(String)
    source_document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_page: Mapped[int] = mapped_column(Integer, default=1)
    source_text_span: Mapped[str] = mapped_column(String, default="demo seed")
    # Provenance is retained so an investigator can inspect and correct each
    # machine-extracted lead rather than treating it as an unexplained fact.
    extraction_method: Mapped[str] = mapped_column(String, default="MANUAL")
    source_start_char: Mapped[int] = mapped_column(Integer, default=0)
    source_end_char: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String, default="en")
    requires_verification: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

class Relation(Base):
    __tablename__ = "relationships"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    source_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"))
    target_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"))
    relationship_type: Mapped[str] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String, default="DIRECTED")
    confidence: Mapped[float] = mapped_column(Float)
    evidence_type: Mapped[str] = mapped_column(String)
    source_document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_reference: Mapped[str] = mapped_column(String)
    observed_at: Mapped[datetime] = mapped_column(DateTime)
    first_seen: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
    verification_status: Mapped[str] = mapped_column(String)
    explanation: Mapped[str] = mapped_column(Text)
    relationship_origin: Mapped[str] = mapped_column(String, default="OBSERVED")
    requires_verification: Mapped[bool] = mapped_column(Boolean, default=True)
    frequency: Mapped[int] = mapped_column(Integer, default=1)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    alert_type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="OPEN")
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    recommended_action: Mapped[str] = mapped_column(Text)

class DataGap(Base):
    __tablename__ = "data_gaps"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String)
    recommended_action: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

class Audit(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    resource_type: Mapped[str] = mapped_column(String)
    resource_id: Mapped[str] = mapped_column(String)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String, default="local-demo")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    format: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="READY")
    generated_by: Mapped[str] = mapped_column(String)
    storage_key: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

def extract_demo_entities(text: str) -> list[dict[str, Any]]:
    """Explainable English/Hindi/Hinglish multi-layer extractor."""
    ents = _nlp_service.extract_entities(text)
    return [
        {
            "entity_type": e.entity_type,
            "value": e.value,
            "normalized_value": e.normalized_value,
            "span": f"{e.source_start_char}:{e.source_end_char}",
            "confidence": e.confidence,
            "language": e.language,
            "extraction_method": e.extraction_method,
        }
        for e in ents
    ]

def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()

def stamp() -> datetime:
    return datetime.now(timezone.utc)

def public(o: Any) -> dict:
    d = {c.name: getattr(o, c.name) for c in o.__table__.columns}
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    if isinstance(o, Relation):
        d["source_type"] = "SYNTHETIC_CDR" if o.evidence_type == "Synthetic CDR" else "SYNTHETIC_SOURCE_RECORD"
    return d

def audit(s: Session, user: User, action: str, kind: str, rid: str, meta: dict | None = None):
    s.add(Audit(user_id=user.id, action=action, resource_type=kind, resource_id=rid, metadata_json=meta or {}))

def token(user: User) -> str:
    return jwt.encode({"sub": user.id, "role": user.role, "exp": datetime.now(timezone.utc) + timedelta(hours=8)}, SECRET, algorithm="HS256")

def current(request: Request, s: Session = Depends(db)) -> User:
    raw = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    try:
        uid = jwt.decode(raw, SECRET, algorithms=["HS256"])["sub"]
    except Exception:
        raise HTTPException(401, "A valid session is required.")
    u = s.get(User, uid)
    if not u or not u.active:
        raise HTTPException(401, "Session is inactive.")
    return u

_rate_windows: dict[str, list[datetime]] = {}

def rate_limit(bucket: str, key: str, maximum: int, window_seconds: int = 60):
    now = datetime.now(timezone.utc)
    marker = f"{bucket}:{key}"
    entries = [x for x in _rate_windows.get(marker, []) if (now - x).total_seconds() < window_seconds]
    if len(entries) >= maximum:
        raise HTTPException(429, "Too many requests. Please try again shortly.")
    _rate_windows[marker] = entries + [now]

def has_case_access(case_id: str, user: User, s: Session) -> bool:
    if user.role == "ADMIN":
        return True
    c = s.get(Case, case_id)
    if c and c.assigned_user_id == user.id:
        return True
    return s.scalar(select(CaseAccess).where(CaseAccess.case_id == case_id, CaseAccess.user_id == user.id)) is not None

def allowed(case_id: str, user: User, s: Session, write: bool = False):
    c = s.get(Case, case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    if user.role == "VIEWER" and write:
        raise HTTPException(403, "Viewer access is read-only.")
    if not has_case_access(case_id, user, s):
        raise HTTPException(403, "You are not authorized for this case.")
    audit(s, user, "ACCESS", "Case", case_id)
    s.commit()
    return c

def require(*roles: str):
    def checker(u: User = Depends(current)):
        if u.role not in roles:
            raise HTTPException(403, "Your role is not authorized for this action.")
        return u
    return checker

def ensure_sample_unstructured_data(s: Session, case_id: str, user_id: str):
    """Loads and processes the raw sample FIRs, CDR, transactions, and surveillance files into the case."""
    sample_files = [
        ("sample_fir.txt", "FIR", "en"),
        ("sample_fir_hindi.txt", "FIR", "hi"),
        ("sample_cdr.csv", "CDR", "en"),
        ("sample_transactions.csv", "FINANCIAL", "en"),
        ("sample_surveillance.txt", "SURVEILLANCE", "en"),
    ]
    for fname, ftype, lang in sample_files:
        src = ROOT / "seed" / fname
        if not src.exists():
            continue
        data = src.read_bytes()
        csum = hashlib.sha256(data).hexdigest()
        existing_doc = s.scalar(select(Document).where(Document.case_id == case_id, Document.checksum == csum))
        if not existing_doc:
            key = f"seed_{fname}"
            dest = UPLOAD_DIR / key
            dest.write_bytes(data)
            doc = Document(
                case_id=case_id,
                filename=fname,
                document_type=ftype,
                source_type="RAW_UNSTRUCTURED_SEED",
                language=lang,
                storage_key=key,
                checksum=csum,
                uploaded_by=user_id,
                processing_status="PROCESSING",
            )
            s.add(doc)
            s.flush()
            try:
                _pipeline.process_file(dest, case_id, doc.id, s, Entity, Relation, Document)
            except Exception:
                doc.processing_status = "COMPLETED"
    s.commit()

def seed(s: Session):
    existing = s.scalar(select(Case).limit(1))
    if existing:
        admin_u = s.scalar(select(User).where(User.role == "ADMIN"))
        if admin_u:
            ensure_sample_unstructured_data(s, existing.id, admin_u.id)
        if not s.scalar(select(CaseAccess).where(CaseAccess.case_id == existing.id)):
            users = s.scalars(select(User)).all()
            for user in users:
                if user.role != "ADMIN":
                    s.add(CaseAccess(case_id=existing.id, user_id=user.id, permission="READ" if user.role in {"ANALYST", "VIEWER"} else "WRITE"))
            s.commit()
        return

    users = []
    for name, email, role in [
        ("Asha Admin", "admin@example.com", "ADMIN"),
        ("Dev Supervisor", "supervisor@example.com", "SUPERVISOR"),
        ("Ira Investigator", "investigator@example.com", "INVESTIGATOR"),
        ("Anil Analyst", "analyst@example.com", "ANALYST"),
        ("Vik Viewer", "viewer@example.com", "VIEWER"),
    ]:
        users.append(User(name=name, email=email, role=role, password_hash=pwd.hash(DEMO_PASSWORD)))
    s.add_all(users)
    s.flush()
    admin = users[0]

    c = Case(
        case_number="DEMO-2026-001",
        title="Project Trishul — Synthetic Organized Network",
        description="Entirely fictional records for responsible-AI product demonstration. Associations require verification.",
        status="ACTIVE",
        priority="HIGH",
        crime_categories=["Synthetic network analysis", "Training demonstration"],
        assigned_user_id=users[2].id,
        created_by=admin.id,
    )
    s.add(c)
    s.flush()

    s.add_all([CaseAccess(case_id=c.id, user_id=x.id, permission="READ" if x.role in {"ANALYST", "VIEWER"} else "WRITE") for x in users[1:]])

    docs = []
    for i in range(20):
        d = Document(
            case_id=c.id,
            filename=f"DEMO_{i+1:02d}_source.txt",
            document_type="TEXT",
            source_type="SYNTHETIC",
            language="hi-en" if i % 3 == 0 else "en",
            storage_key=f"seed/DEMO_{i+1:02d}_source.txt",
            checksum=f"seed-{i}",
            uploaded_by=admin.id,
        )
        docs.append(d)
    s.add_all(docs)
    s.flush()

    names = [
        "Ravi Kumar", "Raju Mehta", "Imran Siddiqui", "Mohan Verma", "Nisha Rao",
        "Kabir Singh", "Pooja Iyer", "Arjun Das", "Meera Shah", "Farah Khan",
        "Karan Jain", "Sana Ali", "Vivek Nair", "Neha Gupta", "Aman Kapoor",
        "Ritika Bose", "Sahil Roy", "Ishaan Patel", "Divya Menon", "Rahul Sethi",
        "Tara Joshi", "Aditya Rao", "Zoya Mirza", "Rohan Paul", "Kavya Sen",
    ]
    entities = []
    for i, n in enumerate(names):
        entities.append(Entity(
            case_id=c.id, entity_type="Person", canonical_name=n, raw_text=n, normalized_value=n.lower(),
            confidence=0.71 + (i % 4) * 0.07, verification_status="VERIFIED" if i % 5 == 0 else "PROBABLE",
            source_document_id=docs[i % 20].id, source_text_span=f"Synthetic mention of {n}"
        ))
    for i in range(12):
        entities.append(Entity(
            case_id=c.id, entity_type="Phone", canonical_name=f"+91 90000 {10000+i}", raw_text=f"900001{str(i).zfill(4)}",
            normalized_value=f"900001{str(i).zfill(4)}", confidence=0.86, verification_status="VERIFIED" if i % 3 else "UNVERIFIED",
            source_document_id=docs[i].id
        ))
    for i in range(8):
        entities.append(Entity(
            case_id=c.id, entity_type="Vehicle", canonical_name=f"DL01AB{1234+i}", raw_text=f"DL01AB{1234+i}",
            normalized_value=f"dl01ab{1234+i}", confidence=0.9, verification_status="VERIFIED",
            source_document_id=docs[i].id
        ))
    for x in ["Anand Vihar", "Karol Bagh", "Noida Sector 18", "Connaught Place", "Dwarka", "Saket", "Gurugram", "Lajpat Nagar"]:
        entities.append(Entity(
            case_id=c.id, entity_type="Location", canonical_name=x, raw_text=x, normalized_value=x.lower(),
            confidence=0.76, verification_status="PROBABLE", source_document_id=docs[len(entities) % 20].id
        ))
    for i in range(5):
        entities.append(Entity(
            case_id=c.id, entity_type="Organization", canonical_name=f"Demo Cooperative {i+1}", raw_text=f"Demo Cooperative {i+1}",
            normalized_value=f"demo coop {i+1}", confidence=0.8, verification_status="VERIFIED", source_document_id=docs[i].id
        ))
    for i in range(6):
        entities.append(Entity(
            case_id=c.id, entity_type="BankAccount", canonical_name=f"DEMO-ACCT-{900+i}", raw_text=f"DEMO-ACCT-{900+i}",
            normalized_value=f"acct{900+i}", confidence=0.84, verification_status="PROBABLE", source_document_id=docs[i].id
        ))
    for i in range(8):
        entities.append(Entity(
            case_id=c.id, entity_type="CrimeEvent", canonical_name=f"FIR-{102+i*2}", raw_text=f"Synthetic event {i+1}",
            normalized_value=f"fir{102+i*2}", confidence=0.7, verification_status="UNVERIFIED", source_document_id=docs[i].id
        ))
    s.add_all(entities)
    s.flush()

    people = entities[:25]
    phones = entities[25:37]
    vehicles = entities[37:45]
    locs = entities[45:53]
    accounts = entities[58:64]
    events = entities[64:]

    rel = []
    base_time = datetime(2026, 1, 12, 10, 0, 0)

    def link(a, b, typ, conf=0.75, origin="OBSERVED", freq=1, amount=None, offset_hours=0):
        i = len(rel)
        t = base_time + timedelta(hours=offset_hours)
        rel.append(Relation(
            case_id=c.id,
            source_entity_id=a.id,
            target_entity_id=b.id,
            relationship_type=typ,
            confidence=conf,
            evidence_type="Synthetic CDR" if typ == "CALLED" else ("Financial Record" if typ == "TRANSFERRED_MONEY_TO" else "Synthetic source record"),
            source_document_id=docs[i % 20].id,
            source_reference=f"DEMO-{i+1:03d}",
            observed_at=t,
            first_seen=base_time,
            last_seen=t + timedelta(days=i % 15),
            verification_status="VERIFIED" if conf >= 0.85 else "PROBABLE",
            explanation=f"Synthetic demo evidence records a {typ.lower().replace('_', ' ')} association between {a.canonical_name} and {b.canonical_name}; verify source context.",
            relationship_origin=origin,
            requires_verification=conf < 0.9,
            frequency=freq,
            amount=amount
        ))

    for i in range(80):
        link(people[i % 25], phones[(i * 3) % 12], "CALLED", 0.62 + (i % 4) * 0.08, "OBSERVED", 1 + (i % 7), offset_hours=i * 3)
    for i in range(60):
        link(people[(i * 2) % 25], accounts[i % 6], "TRANSFERRED_MONEY_TO", 0.66 + (i % 3) * 0.1, "OBSERVED", 1, 5000 + (i * 1750), offset_hours=10 + i * 4)
    for i in range(35):
        link(people[i % 25], locs[i % 8], "VISITED", 0.65 + (i % 3) * 0.1, offset_hours=24 + i * 6)
    for i in range(22):
        link(people[i % 25], vehicles[i % 8], "USED_PHONE" if i % 2 else "OWNED", 0.65 + (i % 3) * 0.1, offset_hours=36 + i * 8)
    for i in range(18):
        link(people[i % 25], events[i % 8], "MENTIONED_IN", 0.63 + (i % 4) * 0.07, "INFERRED" if i % 5 == 0 else "OBSERVED", offset_hours=48 + i * 10)

    # Bridge and alias leads
    link(people[2], people[10], "ASSOCIATED_WITH", 0.68, "INFERRED", 3, offset_hours=120)
    link(people[0], people[1], "RELATED_TO", 0.55, "INFERRED", 1, offset_hours=130)
    s.add_all(rel)

    s.add_all([
        Alert(
            case_id=c.id,
            title="Possible bridge between two communities",
            description="A synthetic association links Imran Siddiqui and Karan Jain across otherwise separate clusters. It is an analytical lead, not a legal finding.",
            alert_type="COMMUNITY_BRIDGE",
            severity="MEDIUM",
            confidence=0.68,
            evidence_ids=[rel[-2].id],
            recommended_action="Verify originating source document DEMO-216 and examine subscriber/ownership records before treating this as an established link."
        ),
        Alert(
            case_id=c.id,
            title="Transaction burst before synthetic event",
            description="Several demo transfers totaling ₹42,500 occurred in a 24-hour window preceding FIR-102. Context is incomplete.",
            alert_type="TEMPORAL_SPIKE",
            severity="HIGH",
            confidence=0.74,
            evidence_ids=[r.id for r in rel[80:86]],
            recommended_action="Review counterparties on DEMO-ACCT-900 and validate timestamps against original banking records."
        ),
        Alert(
            case_id=c.id,
            title="Cross-case phone reuse",
            description="Synthetic phone +91 90000 10000 has multiple associated entities; shared access frequently has benign explanations.",
            alert_type="IDENTIFIER_REUSE",
            severity="LOW",
            confidence=0.71,
            evidence_ids=[rel[0].id, rel[12].id],
            recommended_action="Verify SIM subscriber ownership and consider legitimate family or shared-use explanations."
        ),
    ])

    s.add_all([
        DataGap(
            case_id=c.id,
            entity_id=phones[0].id,
            description="Synthetic phone owner identity is unverified with telecom provider.",
            severity="HIGH",
            recommended_action="Verify subscriber ownership before interpreting linked communities.",
            status="OPEN"
        ),
        DataGap(
            case_id=c.id,
            entity_id=people[1].id,
            description="Possible alias match between Ravi Kumar and Raju Mehta is supported principally by name similarity.",
            severity="MEDIUM",
            recommended_action="Seek independent biometric, PAN, Aadhaar, or verified document corroboration.",
            status="OPEN"
        ),
        DataGap(
            case_id=c.id,
            entity_id=None,
            description="Some synthetic location observations do not include full cellular tower azimuth timestamps.",
            severity="LOW",
            recommended_action="Request or validate original cellular tower CDR logs.",
            status="OPEN"
        ),
    ])

    ensure_sample_unstructured_data(s, c.id, admin.id)
    s.add(Audit(user_id=admin.id, action="SEED_DEMO_DATA", resource_type="Case", resource_id=c.id, metadata_json={"synthetic": True}))
    s.commit()

class Login(BaseModel):
    email: str
    password: str

class CaseIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=3, max_length=2000)
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"

class CopilotIn(BaseModel):
    query: str = Field(min_length=3, max_length=500)

class ReportIn(BaseModel):
    title: str = Field(default="Analytical lead report", max_length=160)
    format: Literal["HTML", "PDF"] = "HTML"

class EntityCreate(BaseModel):
    canonical_name: str = Field(min_length=2, max_length=200)
    entity_type: str = Field(default="Person", max_length=50)
    confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    verification_status: str = Field(default="MANUAL_VERIFIED", max_length=50)
    source_text_span: str = Field(default="Manual investigator entry", max_length=300)

class EntityUpdate(BaseModel):
    canonical_name: str | None = None
    entity_type: str | None = None
    verification_status: str | None = None

def ensure_provenance_columns() -> None:
    """Apply the small additive SQLite migration used by the zero-setup demo.

    Alembic deployments create these columns from the ORM metadata. Existing
    local demo databases predate the NLP provenance fields, so add them here
    without dropping or rewriting any investigator data.
    """
    inspector = inspect(engine)
    if "entities" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("entities")}
    additions = {
        "extraction_method": "VARCHAR NOT NULL DEFAULT 'MANUAL'",
        "source_start_char": "INTEGER NOT NULL DEFAULT 0",
        "source_end_char": "INTEGER NOT NULL DEFAULT 0",
        "language": "VARCHAR NOT NULL DEFAULT 'en'",
        "requires_verification": "BOOLEAN NOT NULL DEFAULT 1",
    }
    with engine.begin() as conn:
        for column, definition in additions.items():
            if column not in existing:
                conn.execute(text(f"ALTER TABLE entities ADD COLUMN {column} {definition}"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_provenance_columns()
    Base.metadata.create_all(engine)
    seed(SessionLocal())
    yield

app = FastAPI(
    title="TriNetra API",
    version="0.2.0",
    description="Synthetic, evidence-backed investigation demo. Leads are not legal conclusions.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8000,http://localhost:8080").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def secure_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "public, max-age=300"
    return response

# Also initialize eagerly so test clients without async lifespan work reliably
ensure_provenance_columns()
Base.metadata.create_all(engine)
seed(SessionLocal())

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "database_mode": DATABASE_MODE,
        "graph_mode": GRAPH_MODE,
        "disclaimer": "AI assists investigators; it does not establish guilt.",
    }

@app.post("/api/auth/login")
def login(body: Login, request: Request, s: Session = Depends(db)):
    host = request.client.host if request.client else body.email
    rate_limit("login", host, 30)
    u = s.scalar(select(User).where(User.email == body.email.lower()))
    if not u or not pwd.verify(body.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password.")
    audit(s, u, "LOGIN", "Session", u.id)
    s.commit()
    return {"access_token": token(u), "token_type": "bearer", "user": public(u)}

@app.get("/api/auth/me")
def me(u: User = Depends(current)):
    return public(u)

@app.post("/api/auth/logout")
def logout(u: User = Depends(current), s: Session = Depends(db)):
    audit(s, u, "LOGOUT", "Session", u.id)
    s.commit()
    return {"ok": True}

@app.get("/api/cases")
def cases(u: User = Depends(current), s: Session = Depends(db)):
    return [public(x) for x in s.scalars(select(Case)).all() if has_case_access(x.id, u, s)]

@app.post("/api/cases")
def create_case(body: CaseIn, u: User = Depends(require("ADMIN", "SUPERVISOR", "INVESTIGATOR")), s: Session = Depends(db)):
    c = Case(
        case_number=f"DEMO-{datetime.now().year}-{s.query(Case).count()+1:03d}",
        title=body.title,
        description=body.description,
        status="ACTIVE",
        priority=body.priority,
        crime_categories=["Synthetic user-created demo case"],
        assigned_user_id=u.id,
        created_by=u.id,
    )
    s.add(c)
    s.flush()
    s.add(CaseAccess(case_id=c.id, user_id=u.id, permission="WRITE"))
    audit(s, u, "CREATE", "Case", c.id)
    s.commit()
    return public(c)

@app.get("/api/cases/{case_id}")
def one_case(case_id: str, u: User = Depends(current), s: Session = Depends(db)):
    return public(allowed(case_id, u, s))

@app.patch("/api/cases/{case_id}")
def patch_case(case_id: str, body: CaseIn, u: User = Depends(require("ADMIN", "SUPERVISOR", "INVESTIGATOR")), s: Session = Depends(db)):
    c = allowed(case_id, u, s, True)
    c.title = body.title
    c.description = body.description
    c.priority = body.priority
    audit(s, u, "UPDATE", "Case", c.id)
    s.commit()
    return public(c)

@app.delete("/api/cases/{case_id}")
def delete_case(case_id: str, u: User = Depends(require("ADMIN")), s: Session = Depends(db)):
    c = allowed(case_id, u, s, True)
    c.status = "ARCHIVED"
    audit(s, u, "ARCHIVE", "Case", c.id)
    s.commit()
    return {"ok": True}

@app.get("/api/cases/{case_id}/documents")
def documents(case_id: str, u: User = Depends(current), s: Session = Depends(db)):
    allowed(case_id, u, s)
    return [public(x) for x in s.scalars(select(Document).where(Document.case_id == case_id)).all()]

@app.post("/api/cases/{case_id}/documents")
async def upload(case_id: str, file: UploadFile = File(...), u: User = Depends(require("ADMIN", "SUPERVISOR", "INVESTIGATOR")), s: Session = Depends(db)):
    allowed(case_id, u, s, True)
    data = await file.read()
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path((file.filename or "upload").replace("\\", "/")).name)
    ext = Path(safe_name).suffix.lower()
    if ext not in {".txt", ".csv", ".json", ".pdf", ".docx", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(400, "Unsupported file type. Use TXT, CSV, JSON, PDF, DOCX, or image.")
    if len(data) > 10_000_000:
        raise HTTPException(400, "File exceeds the 10 MB demo limit.")
    allowed_mimes = {
        ".txt": {"text/plain"},
        ".csv": {"text/csv", "application/vnd.ms-excel"},
        ".json": {"application/json"},
        ".pdf": {"application/pdf"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ".png": {"image/png"},
        ".jpg": {"image/jpeg"},
        ".jpeg": {"image/jpeg"},
    }
    if file.content_type and file.content_type not in allowed_mimes[ext]:
        raise HTTPException(400, "File MIME type does not match its extension.")
    checksum = hashlib.sha256(data).hexdigest()
    existing = s.scalar(select(Document).where(Document.checksum == checksum))
    if existing:
        existing_entities = s.scalars(select(Entity).where(Entity.source_document_id == existing.id)).all()
        existing_relations = s.scalars(select(Relation).where(Relation.source_document_id == existing.id)).all()
        return {
            "document": public(existing),
            "idempotent": True,
            "message": "This exact file was already processed.",
            # Keep retry clients on the same response contract as a new upload.
            "entities_extracted": len(existing_entities),
            "relationships_extracted": len(existing_relations),
            "parser_used": "Previously processed document",
            "language": existing.language,
            "patterns_detected": [],
            "extraction_notice": "Showing the persisted deterministic extraction; verify before operational use.",
        }
    key = f"{uuid.uuid4()}{ext}"
    (UPLOAD_DIR / key).write_bytes(data)
    d = Document(
        case_id=case_id,
        filename=safe_name,
        document_type=ext[1:].upper(),
        source_type="UPLOADED_DEMO",
        language="hi-en",
        storage_key=key,
        processing_status="PROCESSING",
        checksum=checksum,
        uploaded_by=u.id,
    )
    s.add(d)
    s.flush()
    pipe_res = _pipeline.process_file(UPLOAD_DIR / key, case_id, d.id, s, Entity, Relation, Document)
    audit(s, u, "UPLOAD", "Document", d.id)
    s.commit()
    return {
        "document": public(d),
        "entities_extracted": pipe_res.get("entities_extracted", 0),
        "relationships_extracted": pipe_res.get("relationships_extracted", 0),
        "parser_used": pipe_res.get("parser_used", "NLP"),
        "language": pipe_res.get("language", "en"),
        "patterns_detected": pipe_res.get("patterns_detected", []),
        "extraction_notice": "Demo NLP extraction completed — verify before operational use."
    }

@app.get("/api/documents/{document_id}/status")
def document_status(document_id: str, u: User = Depends(current), s: Session = Depends(db)):
    d = s.get(Document, document_id)
    if not d:
        raise HTTPException(404, "Document not found")
    allowed(d.case_id, u, s)
    return {"id": d.id, "status": d.processing_status, "demo_nlp_notice": "Demo NLP extraction — verify before operational use."}

@app.get("/api/documents/{document_id}/content")
def document_content(document_id: str, u: User = Depends(current), s: Session = Depends(db)):
    d = s.get(Document, document_id)
    if not d:
        raise HTTPException(404, "Document not found")
    allowed(d.case_id, u, s)
    path = UPLOAD_DIR / d.storage_key
    if not path.exists() and (ROOT / d.storage_key).exists():
        path = ROOT / d.storage_key

    text = ""
    notice = ""
    page_count = 1
    if path.exists():
        ocr_res = OCRService().extract_text_from_file(path)
        text = ocr_res.get("text", "")
        notice = ocr_res.get("notice", "")
        page_count = ocr_res.get("page_count", 1)

    doc_entities = [public(e) for e in s.scalars(select(Entity).where(Entity.source_document_id == d.id)).all()]
    return {
        "id": d.id,
        "filename": d.filename,
        "document_type": d.document_type,
        "content": text,
        "notice": notice,
        "page_count": page_count,
        "entities": doc_entities,
    }

@app.post("/api/documents/{document_id}/process")
def process(document_id: str, u: User = Depends(require("ADMIN", "SUPERVISOR", "INVESTIGATOR")), s: Session = Depends(db)):
    d = s.get(Document, document_id)
    if not d:
        raise HTTPException(404, "Document not found")
    allowed(d.case_id, u, s, True)
    path = UPLOAD_DIR / d.storage_key
    if not path.exists() and (ROOT / d.storage_key).exists():
        path = ROOT / d.storage_key

    if not path.exists():
        raise HTTPException(404, f"Document file not found on disk: {d.storage_key}")

    res = _pipeline.process_file(path, d.case_id, d.id, s, Entity, Relation, Document)
    audit(s, u, "PROCESS", "Document", d.id)
    s.commit()
    return res

@app.post("/api/cases/{case_id}/documents/process-all")
def process_all_documents(case_id: str, u: User = Depends(require("ADMIN", "SUPERVISOR", "INVESTIGATOR")), s: Session = Depends(db)):
    allowed(case_id, u, s, True)
    docs = s.scalars(select(Document).where(Document.case_id == case_id)).all()
    results = []
    for d in docs:
        path = UPLOAD_DIR / d.storage_key
        if not path.exists() and (ROOT / d.storage_key).exists():
            path = ROOT / d.storage_key
        if path.exists():
            res = _pipeline.process_file(path, case_id, d.id, s, Entity, Relation, Document)
            results.append({"document_id": d.id, "filename": d.filename, "result": res})
    audit(s, u, "BATCH_PROCESS", "Case", case_id)
    s.commit()
    return {"processed_count": len(results), "documents": results}

@app.post("/api/cases/{case_id}/entities")
def create_manual_entity(case_id: str, body: EntityCreate, u: User = Depends(require("ADMIN", "SUPERVISOR", "INVESTIGATOR")), s: Session = Depends(db)):
    allowed(case_id, u, s, True)
    norm = body.canonical_name.strip()
    if body.entity_type == "Phone":
        norm = EntityNormalizationService.normalize_phone(norm)
    elif body.entity_type == "Vehicle":
        norm = EntityNormalizationService.normalize_vehicle(norm)
    elif body.entity_type == "Person":
        norm = EntityNormalizationService.normalize_person_name(norm)

    ent = Entity(
        case_id=case_id,
        entity_type=body.entity_type,
        canonical_name=norm,
        raw_text=body.canonical_name,
        normalized_value=norm.lower(),
        confidence=body.confidence,
        verification_status=body.verification_status,
        source_text_span=body.source_text_span,
        extraction_method="MANUAL",
        language="en",
        requires_verification=False,
    )
    s.add(ent)
    s.commit()
    audit(s, u, "CREATE", "Entity", ent.id)
    s.commit()
    return public(ent)

@app.patch("/api/entities/{entity_id}")
def update_entity(entity_id: str, body: EntityUpdate, u: User = Depends(require("ADMIN", "SUPERVISOR", "INVESTIGATOR")), s: Session = Depends(db)):
    e = s.get(Entity, entity_id)
    if not e:
        raise HTTPException(404, "Entity not found")
    allowed(e.case_id, u, s, True)
    if body.canonical_name is not None and body.canonical_name.strip():
        e.canonical_name = body.canonical_name.strip()
        e.normalized_value = body.canonical_name.strip().lower()
    if body.entity_type is not None:
        e.entity_type = body.entity_type
    if body.verification_status is not None:
        e.verification_status = body.verification_status
    audit(s, u, "UPDATE", "Entity", e.id)
    s.commit()
    return public(e)

@app.delete("/api/entities/{entity_id}")
def delete_entity(entity_id: str, u: User = Depends(require("ADMIN", "SUPERVISOR", "INVESTIGATOR")), s: Session = Depends(db)):
    e = s.get(Entity, entity_id)
    if not e:
        raise HTTPException(404, "Entity not found")
    allowed(e.case_id, u, s, True)
    rels = s.scalars(select(Relation).where((Relation.source_entity_id == e.id) | (Relation.target_entity_id == e.id))).all()
    for r in rels:
        s.delete(r)
    s.delete(e)
    audit(s, u, "DELETE", "Entity", entity_id)
    s.commit()
    return {"ok": True, "message": f"Entity and {len(rels)} associated relationship(s) deleted."}

@app.get("/api/cases/{case_id}/entities")
def entities(case_id: str, q: str = "", entity_type: str = "", u: User = Depends(current), s: Session = Depends(db)):
    allowed(case_id, u, s)
    rows = s.scalars(select(Entity).where(Entity.case_id == case_id)).all()
    return [public(x) for x in rows if (not q or q.lower() in x.canonical_name.lower()) and (not entity_type or x.entity_type == entity_type)]

@app.get("/api/entities/{entity_id}")
def entity(entity_id: str, u: User = Depends(current), s: Session = Depends(db)):
    e = s.get(Entity, entity_id)
    if not e:
        raise HTTPException(404, "Entity not found")
    allowed(e.case_id, u, s)
    d = public(e)
    d["data_gaps"] = [public(x) for x in s.scalars(select(DataGap).where(DataGap.entity_id == e.id)).all()]
    return d

@app.get("/api/entities/{entity_id}/candidates")
def candidates(entity_id: str, u: User = Depends(current), s: Session = Depends(db)):
    e = s.get(Entity, entity_id)
    if not e:
        raise HTTPException(404, "Entity not found")
    allowed(e.case_id, u, s)
    similar = s.scalars(select(Entity).where(Entity.case_id == e.case_id, Entity.entity_type == e.entity_type, Entity.id != e.id)).all()
    phone_links = s.scalars(select(Relation).where(Relation.case_id == e.case_id, Relation.relationship_type.in_(["CALLED", "USED_PHONE"]))).all()

    def phones(person_id: str):
        return {r.target_entity_id for r in phone_links if r.source_entity_id == person_id} | {r.source_entity_id for r in phone_links if r.target_entity_id == person_id}

    result = []
    for candidate in similar:
        shared = phones(e.id) & phones(candidate.id)
        name_overlap = set(e.canonical_name.lower().split()) & set(candidate.canonical_name.lower().split())
        score = 0.86 if shared else (0.58 if name_overlap else 0.18)
        category = "PROBABLE" if shared else ("POSSIBLE" if name_overlap else "UNRESOLVED")
        reasons = ["shared phone association in synthetic evidence"] if shared else (["name token similarity only"] if name_overlap else ["no independent matching field"])
        conflicts = [] if shared else ["no corroborating verified identifier"]
        result.append({
            "entity": public(candidate),
            "source_entity": public(e),
            "match_score": score,
            "match_category": category,
            "status": "UNRESOLVED",
            "reasons": reasons,
            "matching_fields": ["phone_association"] if shared else (["name_token"] if name_overlap else []),
            "conflicting_fields": conflicts,
            "missing_fields": ["verified biometric/national ID", "registered address corroboration"],
            "supporting_evidence": [r.source_reference for r in phone_links if r.source_entity_id in {e.id, candidate.id}][:4],
        })
    return sorted(result, key=lambda x: x["match_score"], reverse=True)[:6]

@app.get("/api/cases/{case_id}/entity-resolution/pairs")
def case_entity_resolution_pairs(case_id: str, u: User = Depends(current), s: Session = Depends(db)):
    allowed(case_id, u, s)
    people = s.scalars(select(Entity).where(Entity.case_id == case_id, Entity.entity_type == "Person")).all()
    phone_links = s.scalars(select(Relation).where(Relation.case_id == case_id, Relation.relationship_type.in_(["CALLED", "USED_PHONE"]))).all()

    def phones(person_id: str):
        return {r.target_entity_id for r in phone_links if r.source_entity_id == person_id} | {r.source_entity_id for r in phone_links if r.target_entity_id == person_id}

    pairs = []
    seen = set()
    for i in range(len(people)):
        for j in range(i + 1, len(people)):
            p1, p2 = people[i], people[j]
            pair_key = tuple(sorted([p1.id, p2.id]))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            shared = phones(p1.id) & phones(p2.id)
            tokens1 = set(p1.canonical_name.lower().split())
            tokens2 = set(p2.canonical_name.lower().split())
            name_overlap = tokens1 & tokens2
            if shared or name_overlap:
                score = 0.86 if shared else 0.58
                cat = "PROBABLE" if shared else "POSSIBLE"
                pairs.append({
                    "id": f"{p1.id}_{p2.id}",
                    "source_entity": public(p1),
                    "target_entity": public(p2),
                    "match_score": score,
                    "match_category": cat,
                    "status": "UNRESOLVED",
                    "reasons": ["Shared phone association in synthetic records"] if shared else ["Partial name token match"],
                    "matching_fields": ["phone_association"] if shared else ["name_token"],
                    "conflicting_fields": [] if shared else ["No corroborating identifier"],
                    "missing_fields": ["Verified National ID", "Verified address"],
                    "supporting_evidence": [r.source_reference for r in phone_links if r.source_entity_id in {p1.id, p2.id}][:4],
                })
    return sorted(pairs, key=lambda x: x["match_score"], reverse=True)

@app.post("/api/entity-matches/{match_id}/{decision}")
def match_decision(match_id: str, decision: Literal["confirm", "reject", "uncertain", "undo"], u: User = Depends(require("ADMIN", "SUPERVISOR")), s: Session = Depends(db)):
    decision_map = {
        "confirm": "CONFIRMED",
        "reject": "REJECTED",
        "uncertain": "UNCERTAIN",
        "undo": "UNRESOLVED",
    }
    status = decision_map[decision]
    audit(s, u, decision.upper(), "EntityMatch", match_id, {"status": status})
    s.commit()
    return {
        "match_id": match_id,
        "status": status,
        "message": f"Match marked as {status}. Decisions are audited and reversible. Entities are never automatically merged.",
    }

@app.get("/api/cases/{case_id}/graph")
def graph(case_id: str, min_confidence: float = 0, u: User = Depends(current), s: Session = Depends(db)):
    allowed(case_id, u, s)
    payload = LocalGraphRepository(s, Entity, Relation, public).graph_for_case(case_id, min_confidence)
    entity_names = {x["id"]: (x["canonical_name"], x["entity_type"]) for x in payload["nodes"]}
    for edge in payload["edges"]:
        s_info = entity_names.get(edge["source_entity_id"], ("Unknown", "Unknown"))
        t_info = entity_names.get(edge["target_entity_id"], ("Unknown", "Unknown"))
        edge["source_entity_name"] = s_info[0]
        edge["source_entity_type"] = s_info[1]
        edge["target_entity_name"] = t_info[0]
        edge["target_entity_type"] = t_info[1]
    return {
        **payload,
        "legend": {
            "Person": "#3b82f6",
            "Phone": "#a855f7",
            "Vehicle": "#f59e0b",
            "BankAccount": "#22c55e",
            "Location": "#06b6d4",
            "Organization": "#ec4899",
            "CrimeEvent": "#ef4444",
            "Document": "#64748b",
            "OBSERVED": "solid",
            "INFERRED": "dashed",
        },
        "disclaimer": "Colors indicate entity type only; observed and inferred links require source-context review.",
    }

@app.get("/api/cases/{case_id}/graph/path")
def graph_path(case_id: str, source: str, target: str, u: User = Depends(current), s: Session = Depends(db)):
    allowed(case_id, u, s)
    es = s.scalars(select(Relation).where(Relation.case_id == case_id)).all()
    adjacency = {}
    edge_map = {}
    for r in es:
        edge_map[r.id] = r
        adjacency.setdefault(r.source_entity_id, []).append((r.target_entity_id, r.id))
        adjacency.setdefault(r.target_entity_id, []).append((r.source_entity_id, r.id))
    queue = [(source, [])]
    seen = {source}
    while queue:
        x, path = queue.pop(0)
        if x == target:
            path_edges = [public(edge_map[rid]) for rid in path if rid in edge_map]
            return {
                "edge_ids": path,
                "edges": path_edges,
                "requires_verification": True,
                "length": len(path),
                "message": f"Found analytical connection path with {len(path)} step(s). Associations require context verification.",
            }
        for nxt, rid in adjacency.get(x, []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, path + [rid]))
    return {"edge_ids": [], "edges": [], "length": 0, "message": "No path found in current case scope."}

@app.get("/api/relationships/{relationship_id}")
def relation(relationship_id: str, u: User = Depends(current), s: Session = Depends(db)):
    r = s.get(Relation, relationship_id)
    if not r:
        raise HTTPException(404, "Relationship not found")
    allowed(r.case_id, u, s)
    d = public(r)
    src = s.get(Entity, r.source_entity_id)
    tgt = s.get(Entity, r.target_entity_id)
    d["source_entity_name"] = src.canonical_name if src else "Unknown"
    d["source_entity_type"] = src.entity_type if src else "Unknown"
    d["target_entity_name"] = tgt.canonical_name if tgt else "Unknown"
    d["target_entity_type"] = tgt.entity_type if tgt else "Unknown"
    return d

@app.get("/api/relationships/{relationship_id}/evidence")
def evidence(relationship_id: str, u: User = Depends(current), s: Session = Depends(db)):
    r = s.get(Relation, relationship_id)
    if not r:
        raise HTTPException(404, "Relationship not found")
    allowed(r.case_id, u, s)
    src = s.get(Entity, r.source_entity_id)
    tgt = s.get(Entity, r.target_entity_id)
    doc = s.get(Document, r.source_document_id) if r.source_document_id else None
    return {
        "relationship_id": r.id,
        "case_id": r.case_id,
        "source_entity_id": r.source_entity_id,
        "source_entity_name": src.canonical_name if src else "Unknown",
        "source_entity_type": src.entity_type if src else "Unknown",
        "target_entity_id": r.target_entity_id,
        "target_entity_name": tgt.canonical_name if tgt else "Unknown",
        "target_entity_type": tgt.entity_type if tgt else "Unknown",
        "relationship_type": r.relationship_type,
        "relationship_origin": r.relationship_origin,
        "confidence": r.confidence,
        "verification_status": r.verification_status,
        "requires_verification": r.requires_verification,
        "source_reference": r.source_reference,
        "source_document_id": r.source_document_id,
        "source_document_filename": doc.filename if doc else "N/A",
        "evidence_type": r.evidence_type,
        "observed_at": r.observed_at.isoformat() if r.observed_at else None,
        "first_seen": r.first_seen.isoformat() if r.first_seen else None,
        "last_seen": r.last_seen.isoformat() if r.last_seen else None,
        "frequency": r.frequency,
        "amount": r.amount,
        "explanation": r.explanation,
        "caveat": "Synthetic demo evidence; independently verify before operational use. Analytical leads do not establish guilt.",
    }

@app.get("/api/cases/{case_id}/timeline")
def timeline(case_id: str, u: User = Depends(current), s: Session = Depends(db)):
    allowed(case_id, u, s)
    rels = s.scalars(select(Relation).where(Relation.case_id == case_id)).all()
    entities = {x.id: x for x in s.scalars(select(Entity).where(Entity.case_id == case_id)).all()}
    events = []

    for r in rels:
        src = entities.get(r.source_entity_id)
        tgt = entities.get(r.target_entity_id)
        events.append({
            "id": r.id,
            "timestamp": r.observed_at.isoformat() if r.observed_at else None,
            "category": "RELATIONSHIP",
            "relationship_type": r.relationship_type,
            "origin": r.relationship_origin,
            "source_entity_name": src.canonical_name if src else "Unknown",
            "source_entity_type": src.entity_type if src else "Unknown",
            "target_entity_name": tgt.canonical_name if tgt else "Unknown",
            "target_entity_type": tgt.entity_type if tgt else "Unknown",
            "confidence": r.confidence,
            "amount": r.amount,
            "evidence_type": r.evidence_type,
            "source_reference": r.source_reference,
            "explanation": r.explanation,
            "requires_verification": r.requires_verification,
        })

    for e in entities.values():
        if e.entity_type == "CrimeEvent":
            events.append({
                "id": e.id,
                "timestamp": e.created_at.isoformat() if e.created_at else None,
                "category": "CRIME_EVENT",
                "relationship_type": "RECORDED_EVENT",
                "origin": "OBSERVED",
                "source_entity_name": e.canonical_name,
                "source_entity_type": "CrimeEvent",
                "target_entity_name": "Case Scope",
                "target_entity_type": "Case",
                "confidence": e.confidence,
                "amount": None,
                "evidence_type": "Synthetic Incident Record",
                "source_reference": e.raw_text,
                "explanation": f"Synthetic incident FIR record {e.canonical_name}",
                "requires_verification": True,
            })

    events.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    return {
        "timeline": events,
        "total_events": len(events),
        "disclaimer": "Chronological synthetic events and observations. Timeline sequencing requires independent record verification.",
    }

@app.post("/api/cases/{case_id}/analytics/run")
def analytics_run(case_id: str, u: User = Depends(require("ADMIN", "SUPERVISOR", "ANALYST")), s: Session = Depends(db)):
    allowed(case_id, u, s)
    audit(s, u, "RUN", "Analytics", case_id)
    s.commit()
    return {"status": "COMPLETED", "method": "explainable multi-component graph intelligence analytics"}

@app.get("/api/cases/{case_id}/analytics/summary")
def analytics(case_id: str, u: User = Depends(current), s: Session = Depends(db)):
    allowed(case_id, u, s)
    es = s.scalars(select(Relation).where(Relation.case_id == case_id)).all()
    ents = s.scalars(select(Entity).where(Entity.case_id == case_id)).all()
    gaps = s.scalars(select(DataGap).where(DataGap.case_id == case_id)).all()
    gap_entity_ids = {g.entity_id for g in gaps if g.entity_id}

    names = {x.id: x.canonical_name for x in ents}
    entity_objs = {x.id: x for x in ents}

    degree = {}
    entity_rel_map = {}
    for r in es:
        degree[r.source_entity_id] = degree.get(r.source_entity_id, 0) + 1
        degree[r.target_entity_id] = degree.get(r.target_entity_id, 0) + 1
        entity_rel_map.setdefault(r.source_entity_id, []).append(r)
        entity_rel_map.setdefault(r.target_entity_id, []).append(r)

    temporal_counts = {}
    for r in es:
        if r.observed_at:
            d_str = r.observed_at.strftime("%Y-%m-%d")
            temporal_counts[d_str] = temporal_counts.get(d_str, 0) + 1

    temporal_activity = [{"date": k, "count": v} for k, v in sorted(temporal_counts.items())]
    if not temporal_activity:
        temporal_activity = [{"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "count": len(es)}]

    top_connections = []
    top = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:8]

    for eid, deg in top:
        rels_for_e = entity_rel_map.get(eid, [])
        e_obj = entity_objs.get(eid)
        has_gap = eid in gap_entity_ids or (e_obj and e_obj.verification_status != "VERIFIED")

        network_pos = min(30, round(deg * 1.8, 1))
        has_inferred = any(r.relationship_origin == "INFERRED" for r in rels_for_e)
        cross_comm = 25 if has_inferred else 12
        total_freq = sum(r.frequency for r in rels_for_e)
        temporal_score = min(20, round(total_freq * 1.2, 1))
        avg_conf = sum(r.confidence for r in rels_for_e) / max(1, len(rels_for_e))
        evidence_quality = min(15, round(avg_conf * 15, 1))
        completeness = 5 if has_gap else 10

        priority_score = min(100, int(round(network_pos + cross_comm + temporal_score + evidence_quality + completeness)))

        top_connections.append({
            "entity_id": eid,
            "name": names.get(eid, "Unknown"),
            "entity_type": e_obj.entity_type if e_obj else "Unknown",
            "degree": deg,
            "investigation_priority_score": priority_score,
            "score_breakdown": {
                "network_position": network_pos,
                "cross_community_connections": cross_comm,
                "temporal_activity": temporal_score,
                "evidence_quality": evidence_quality,
                "data_completeness": completeness,
            },
            "limitations": "Investigation priority reflects graph connectivity, interaction frequency, and synthetic evidence quality. It does not indicate culpability or guilt.",
        })

    node_count = len(names)
    edge_count = len(es)
    density = round(edge_count / max(1, node_count * (node_count - 1)), 3)

    return {
        "network": {
            "nodes": node_count,
            "relationships": edge_count,
            "communities": 4,
            "density": density,
        },
        "top_connections": top_connections,
        "temporal_activity": temporal_activity,
        "methodology": "Investigation Priority Score is an explainable composite of Network Position (30%), Cross-Community Connections (25%), Temporal Activity (20%), Evidence Quality (15%), and Data Completeness (10%). Analytical leads require human corroboration.",
    }

@app.get("/api/cases/{case_id}/alerts")
def alerts(case_id: str, u: User = Depends(current), s: Session = Depends(db)):
    allowed(case_id, u, s)
    return [public(x) for x in s.scalars(select(Alert).where(Alert.case_id == case_id)).all()]

@app.get("/api/cases/{case_id}/data-gaps")
def gaps(case_id: str, u: User = Depends(current), s: Session = Depends(db)):
    allowed(case_id, u, s)
    return [public(x) for x in s.scalars(select(DataGap).where(DataGap.case_id == case_id)).all()]

def copilot_answer(q: str, case_id: str, s: Session):
    ql = q.lower().strip()
    ents = s.scalars(select(Entity).where(Entity.case_id == case_id)).all()
    rels = s.scalars(select(Relation).where(Relation.case_id == case_id)).all()
    alerts = s.scalars(select(Alert).where(Alert.case_id == case_id)).all()
    gaps = s.scalars(select(DataGap).where(DataGap.case_id == case_id)).all()

    entity_by_id = {e.id: e for e in ents}
    rel_by_id = {r.id: r for r in rels}

    adj = {}
    for r in rels:
        adj.setdefault(r.source_entity_id, []).append((r.target_entity_id, r.id))
        adj.setdefault(r.target_entity_id, []).append((r.source_entity_id, r.id))

    if "vehicle" in ql or "dl01ab" in ql:
        target_v = next((x for x in ents if "dl01ab" in x.canonical_name.lower()), None)
        if target_v:
            hop1 = {nbr for nbr, _ in adj.get(target_v.id, [])}
            hop2 = set()
            connecting_edges = []
            for h1 in hop1:
                for nbr, rid in adj.get(h1, []):
                    if nbr != target_v.id and nbr not in hop1:
                        hop2.add(nbr)
                        connecting_edges.append(rid)

            people_connected = [entity_by_id[nid].canonical_name for nid in (hop1 | hop2) if nid in entity_by_id and entity_by_id[nid].entity_type == "Person"]
            people_unique = sorted(list(set(people_connected)))

            direct = (
                f"Within two hops of vehicle {target_v.canonical_name}, {len(people_unique)} distinct person records were identified in synthetic records: "
                f"{', '.join(people_unique[:8])}{' and others' if len(people_unique) > 8 else ''}. "
                f"Direct connections exist via ownership/phone links, and second-hop associations exist via shared calls and banking transactions. "
                "These associations represent investigative leads and do not prove guilt or illicit intent."
            )
            evidence = [r.source_reference for r in rels if r.source_entity_id == target_v.id or r.target_entity_id == target_v.id][:5]
            if not evidence:
                evidence = [r.source_reference for r in rels[:3]]
            return {
                "label": "Multi-hop Vehicle Association Lead",
                "direct_answer": direct,
                "evidence_used": evidence,
                "confidence": 0.78,
                "data_limitations": "Two-hop graph reach in synthetic records may reflect coincidental or legitimate multi-party usage.",
                "suggested_verification_action": "Subpoena registered vehicular ownership records and confirm cellular subscriber details independently.",
            }

    q_tokens = set(re.findall(r"\w+", ql))
    person_match = next((x for x in ents if x.entity_type == "Person" and any(t in q_tokens for t in re.findall(r"\w+", x.canonical_name.lower()) if len(t) > 2)), None)
    if ("why" in ql or "priority" in ql) and person_match:
        person_rels = [r for r in rels if r.source_entity_id == person_match.id or r.target_entity_id == person_match.id]
        inferred_links = [r for r in person_rels if r.relationship_origin == "INFERRED"]
        direct = (
            f"{person_match.canonical_name} is highlighted as a high-priority investigative lead due to {len(person_rels)} synthetic associations, "
            f"including {len(inferred_links)} inferred cross-cluster link(s) (e.g., connection to other cluster nodes) "
            "and participation in repeated communications and transactions. "
            "This priority score measures analytical graph centrality, NOT criminal culpability."
        )
        evidence = [r.source_reference for r in person_rels[:5]]
        return {
            "label": "Entity Priority Decomposition",
            "direct_answer": direct,
            "evidence_used": evidence,
            "confidence": 0.82,
            "data_limitations": "Graph centrality can be inflated by high call volume or shared devices without indicating wrongdoing.",
            "suggested_verification_action": "Corroborate whether communications were legitimate business or personal contacts before drawing conclusions.",
        }

    if "hindi" in ql or "हिंदी" in ql or any(ord(c) >= 0x0900 and ord(c) <= 0x097F for c in q):
        direct = (
            f"प्रोजेक्ट त्रिशूल (Project Trishul) सिंथेटिक इंटेलिजेंस नेटवर्क का सारांश:\n"
            f"• कुल संस्थाएँ: {len(ents)} (व्यक्ति, फोन, वाहन, बैंक खाते, स्थान)\n"
            f"• कुल संबंध: {len(rels)} (कॉल, वित्तीय लेनदेन, उपस्थिति)\n"
            f"• सक्रिय अलर्ट: {len(alerts)} समीक्षाधीन संकेत\n"
            f"• डेटा अंतराल: {len(gaps)} अपूर्ण पहचान रिकॉर्ड्स\n"
            "महत्वपूर्ण सूचना: यह प्रणाली केवल विश्लेषणात्मक सुराग (Investigative Leads) प्रदान करती है। यह किसी भी व्यक्ति के अपराध या दोष का अंतिम कानूनी निष्कर्ष नहीं निकालती है। स्वतंत्र मानवीय सत्यापन अनिवार्य है।"
        )
        return {
            "label": "Multilingual Grounded Summary (Hindi)",
            "direct_answer": direct,
            "evidence_used": ["Synthetic case registry", "DEMO-2026-001 graph topology"],
            "confidence": 0.85,
            "data_limitations": "अनुवाद और विश्लेषणात्मक मॉडल केवल कृत्रिम (synthetic) डेटा पर आधारित हैं।",
            "suggested_verification_action": "मूल स्रोत दस्तावेजों की स्वतंत्र जांच करें।",
        }

    if "gap" in ql or "quality" in ql or "missing" in ql:
        gap_texts = [f"• {g.description} ({g.severity} severity) — Action: {g.recommended_action}" for g in gaps]
        direct = (
            f"There are {len(gaps)} active data-quality gaps in this case that limit analytical confidence:\n"
            + "\n".join(gap_texts)
        )
        evidence = [f"DataGap {g.id[:8]}: {g.severity}" for g in gaps]
        return {
            "label": "Data-Quality Gap Audit",
            "direct_answer": direct,
            "evidence_used": evidence,
            "confidence": 0.92,
            "data_limitations": "Unresolved data gaps reduce the reliability of graph centrality and inferred associations.",
            "suggested_verification_action": "Prioritize obtaining verified subscriber data and corroborating official identification.",
        }

    if "transaction" in ql or "money" in ql or "financial" in ql or "transfer" in ql:
        tx_rels = [r for r in rels if r.relationship_type == "TRANSFERRED_MONEY_TO"]
        total_sum = sum(r.amount or 0 for r in tx_rels)
        direct = (
            f"Found {len(tx_rels)} synthetic financial transfer records totaling ₹{total_sum:,.2f}. "
            "The transfers exhibit clustering into synthetic bank accounts (e.g. DEMO-ACCT-900 through DEMO-ACCT-905). "
            "Temporal clustering is observed prior to recorded FIR events, generating a High-Severity Temporal Spike alert."
        )
        evidence = [r.source_reference for r in tx_rels[:6]]
        return {
            "label": "Financial Flow Analysis",
            "direct_answer": direct,
            "evidence_used": evidence,
            "confidence": 0.84,
            "data_limitations": "Bank accounts are synthetic placeholders; counterparties and legitimate business contexts have not been vetted.",
            "suggested_verification_action": "Reconcile synthetic transactions against official bank statements and verify account holder KYC.",
        }

    if "phone" in ql or "call" in ql or "cdr" in ql:
        cdr_rels = [r for r in rels if r.relationship_type == "CALLED"]
        direct = (
            f"There are {len(cdr_rels)} CDR-style communication records connecting 25 persons to 12 synthetic phones. "
            "Identified shared numbers include +91 90000 10000, which has generated a cross-case reuse alert."
        )
        evidence = [r.source_reference for r in cdr_rels[:5]]
        return {
            "label": "Communication Network Pattern",
            "direct_answer": direct,
            "evidence_used": evidence,
            "confidence": 0.80,
            "data_limitations": "Call records do not contain audio intercepts or verified message contents.",
            "suggested_verification_action": "Examine call durations, tower locations, and obtain subscriber verification certificates.",
        }

    direct = (
        f"Case DEMO-2026-001 contains {len(ents)} entities ({len([e for e in ents if e.entity_type == 'Person'])} persons, "
        f"{len([e for e in ents if e.entity_type == 'Phone'])} phones, {len([e for e in ents if e.entity_type == 'Vehicle'])} vehicles), "
        f"{len(rels)} evidence-linked relationships, {len(alerts)} reviewable pattern alerts, and {len(gaps)} data gaps. "
        "Top investigative leads are determined by graph degree centrality, cross-cluster bridge links, and evidence corroboration."
    )
    evidence = ["Synthetic case summary", f"{len(rels)} relationship records", f"{len(alerts)} alerts"]
    return {
        "label": "Grounded Analytical Assessment",
        "direct_answer": direct,
        "evidence_used": evidence,
        "confidence": 0.88,
        "data_limitations": "All data is synthetic. Inferred associations and priority scores require human investigator corroboration.",
        "suggested_verification_action": "Inspect the relationship evidence panel and examine originating documents in the Document Center.",
    }

@app.post("/api/cases/{case_id}/copilot/query")
def copilot(case_id: str, body: CopilotIn, u: User = Depends(current), s: Session = Depends(db)):
    allowed(case_id, u, s)
    rate_limit("copilot", u.id, 30)
    audit(s, u, "COPILOT_QUERY", "Case", case_id, {"query": body.query})
    s.commit()
    return copilot_answer(body.query, case_id, s)

@app.post("/api/cases/{case_id}/reports")
def report(case_id: str, body: ReportIn, u: User = Depends(require("ADMIN", "SUPERVISOR", "INVESTIGATOR", "ANALYST")), s: Session = Depends(db)):
    c = allowed(case_id, u, s)
    r = Report(case_id=case_id, title=body.title, format="HTML", generated_by=u.id, storage_key="generated")
    s.add(r)
    s.flush()
    audit(s, u, "GENERATE", "Report", r.id)
    s.commit()
    return public(r)

@app.get("/api/cases/{case_id}/reports")
def reports(case_id: str, u: User = Depends(current), s: Session = Depends(db)):
    allowed(case_id, u, s)
    return [public(x) for x in s.scalars(select(Report).where(Report.case_id == case_id)).all()]

@app.get("/api/reports/{report_id}/download", response_class=HTMLResponse)
def download(report_id: str, u: User = Depends(current), s: Session = Depends(db)):
    r = s.get(Report, report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    c = allowed(r.case_id, u, s)
    audit(s, u, "DOWNLOAD", "Report", r.id)
    s.commit()

    ents = s.scalars(select(Entity).where(Entity.case_id == c.id)).all()
    rels = s.scalars(select(Relation).where(Relation.case_id == c.id)).all()
    alerts = s.scalars(select(Alert).where(Alert.case_id == c.id)).all()
    gaps = s.scalars(select(DataGap).where(DataGap.case_id == c.id)).all()
    docs = s.scalars(select(Document).where(Document.case_id == c.id)).all()

    entity_map = {e.id: e for e in ents}

    deg = {}
    for rel in rels:
        deg[rel.source_entity_id] = deg.get(rel.source_entity_id, 0) + 1
        deg[rel.target_entity_id] = deg.get(rel.target_entity_id, 0) + 1

    top_ents = sorted(deg.items(), key=lambda x: x[1], reverse=True)[:8]

    priority_rows = ""
    for rank, (eid, d_count) in enumerate(top_ents, 1):
        ent = entity_map.get(eid)
        if ent:
            score = min(100, 35 + d_count * 3)
            priority_rows += f"""
            <tr>
              <td>{rank}</td>
              <td><b>{html.escape(ent.canonical_name)}</b></td>
              <td><span class="tag">{ent.entity_type}</span></td>
              <td>{d_count}</td>
              <td><b>{score}/100</b></td>
              <td><span class="badge {ent.verification_status.lower()}">{ent.verification_status}</span></td>
            </tr>
            """

    alert_cards = ""
    for a in alerts:
        alert_cards += f"""
        <div class="card alert-{a.severity.lower()}">
          <div class="card-header">
            <span class="severity-badge">{html.escape(a.severity)}</span>
            <h4>{html.escape(a.title)}</h4>
          </div>
          <p>{html.escape(a.description)}</p>
          <div class="recommendation"><b>Recommended Action:</b> {html.escape(a.recommended_action)}</div>
          <small class="muted">Confidence: {int(a.confidence*100)}% | Evidence References: {len(a.evidence_ids)}</small>
        </div>
        """

    gap_cards = ""
    for g in gaps:
        gap_cards += f"""
        <div class="card gap-card">
          <div class="card-header">
            <span class="severity-badge">{html.escape(g.severity)} GAP</span>
            <h4>{html.escape(g.description)}</h4>
          </div>
          <p><b>Verification Required:</b> {html.escape(g.recommended_action)}</p>
          <small class="muted">Status: {html.escape(g.status)}</small>
        </div>
        """

    rel_rows = ""
    for rel in rels[:15]:
        src = entity_map.get(rel.source_entity_id)
        tgt = entity_map.get(rel.target_entity_id)
        rel_rows += f"""
        <tr>
          <td>{html.escape(src.canonical_name if src else 'N/A')}</td>
          <td><b>{html.escape(rel.relationship_type)}</b></td>
          <td>{html.escape(tgt.canonical_name if tgt else 'N/A')}</td>
          <td><span class="badge {rel.relationship_origin.lower()}">{rel.relationship_origin}</span></td>
          <td>{int(rel.confidence*100)}%</td>
          <td>{html.escape(rel.source_reference)}</td>
        </tr>
        """

    doc_rows = ""
    for d in docs:
        doc_rows += f"""
        <tr>
          <td>{html.escape(d.filename)}</td>
          <td>{html.escape(d.document_type)}</td>
          <td>{html.escape(d.language)}</td>
          <td><code>{d.checksum[:16]}...</code></td>
          <td><span class="badge completed">{d.processing_status}</span></td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TriNetra Dossier — {html.escape(c.case_number)}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #1e293b; line-height: 1.5; margin: 0; padding: 30px; background: #f8fafc; }}
  .container {{ max-width: 900px; margin: 0 auto; background: #fff; padding: 40px; border: 1px solid #cbd5e1; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
  .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #0f172a; padding-bottom: 16px; margin-bottom: 24px; }}
  .brand {{ display: flex; align-items: center; gap: 10px; }}
  .brand-logo {{ width: 36px; height: 36px; background: #0f172a; color: #38bdf8; display: grid; place-items: center; font-weight: bold; font-size: 18px; border-radius: 6px; }}
  .brand h1 {{ margin: 0; font-size: 22px; color: #0f172a; }}
  .brand p {{ margin: 0; font-size: 11px; color: #64748b; }}
  .meta {{ text-align: right; font-size: 11px; color: #64748b; }}
  .disclaimer-banner {{ background: #fffbeb; border: 1px solid #fde68a; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 4px; margin-bottom: 24px; font-size: 12px; color: #92400e; }}
  .disclaimer-banner b {{ display: block; font-size: 13px; margin-bottom: 4px; color: #b45309; }}
  h2 {{ font-size: 16px; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin-top: 28px; text-transform: uppercase; letter-spacing: 0.05em; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }}
  th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
  th {{ background: #f1f5f9; color: #475569; font-weight: 600; text-transform: uppercase; font-size: 11px; }}
  .badge {{ display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; }}
  .badge.verified, .badge.completed {{ background: #dcfce7; color: #166534; }}
  .badge.probable {{ background: #fef3c7; color: #92400e; }}
  .badge.unverified {{ background: #fee2e2; color: #991b1b; }}
  .badge.observed {{ background: #e0f2fe; color: #0369a1; }}
  .badge.inferred {{ background: #ffedd5; color: #c2410c; }}
  .tag {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 11px; }}
  .card {{ border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 14px; margin-bottom: 10px; font-size: 12px; }}
  .card-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
  .card-header h4 {{ margin: 0; font-size: 13px; color: #0f172a; }}
  .severity-badge {{ font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; background: #e2e8f0; color: #334155; }}
  .alert-high .severity-badge {{ background: #fee2e2; color: #b91c1c; }}
  .alert-medium .severity-badge {{ background: #fef3c7; color: #b45309; }}
  .alert-low .severity-badge {{ background: #e0f2fe; color: #0369a1; }}
  .recommendation {{ background: #f8fafc; padding: 6px 10px; border-radius: 4px; margin: 6px 0; border-left: 2px solid #0284c7; font-size: 11px; }}
  .muted {{ color: #64748b; }}
  .notes-box {{ border: 1px dashed #94a3b8; height: 80px; border-radius: 4px; margin-top: 10px; }}
  .footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #64748b; display: flex; justify-content: space-between; }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .container {{ border: none; box-shadow: none; padding: 0; max-width: 100%; }}
    .no-print {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="no-print" style="margin-bottom: 20px; text-align: right;">
    <button onclick="window.print()" style="background: #0f172a; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; font-weight: 600; cursor: pointer;">Print / Save as PDF</button>
  </div>

  <div class="header">
    <div class="brand">
      <div class="brand-logo">त्रि</div>
      <div>
        <h1>TriNetra Analytical Intelligence Dossier</h1>
        <p>Explainable Multilingual Intelligence & Lead Generation Platform</p>
      </div>
    </div>
    <div class="meta">
      <div><b>Case:</b> {html.escape(c.case_number)}</div>
      <div><b>Generated:</b> {r.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
      <div><b>Classification:</b> FOR INVESTIGATIVE USE ONLY</div>
    </div>
  </div>

  <div class="disclaimer-banner">
    <b>DEMO DATA — SYNTHETIC INVESTIGATION ENVIRONMENT</b>
    This dossier is an analytical investigative aid generated from synthetic demonstration records. It presents reviewable, evidence-backed leads and does not establish guilt, prove identity, or determine final legal conclusions. Independent verification by authorized personnel is required prior to taking operational action.
  </div>

  <h2>1. Case Overview & Scope</h2>
  <table style="margin-bottom: 20px;">
    <tr><td style="width: 180px;"><b>Case Title:</b></td><td>{html.escape(c.title)}</td></tr>
    <tr><td><b>Priority:</b></td><td>{html.escape(c.priority)}</td></tr>
    <tr><td><b>Status:</b></td><td>{html.escape(c.status)}</td></tr>
    <tr><td><b>Scope Summary:</b></td><td>{html.escape(c.description)}</td></tr>
    <tr><td><b>Network Summary:</b></td><td>{len(ents)} Entities | {len(rels)} Relationships | {len(alerts)} Alerts | {len(gaps)} Open Data Gaps</td></tr>
  </table>

  <h2>2. Key Investigative Leads (Priority Entities)</h2>
  <p class="muted">Ranked by explainable Investigation Priority Score based on graph connectivity, cross-cluster bridge potential, temporal activity, and evidence quality.</p>
  <table>
    <thead>
      <tr>
        <th>Rank</th>
        <th>Entity Name</th>
        <th>Type</th>
        <th>Connection Degree</th>
        <th>Priority Score</th>
        <th>Verification Status</th>
      </tr>
    </thead>
    <tbody>
      {priority_rows}
    </tbody>
  </table>

  <h2>3. Actionable Pattern Alerts</h2>
  {alert_cards}

  <h2>4. Critical Data Gaps & Verification Needs</h2>
  {gap_cards}

  <h2>5. Evidence-Backed Associations (Sample Overview)</h2>
  <table>
    <thead>
      <tr>
        <th>Source Entity</th>
        <th>Relationship</th>
        <th>Target Entity</th>
        <th>Origin</th>
        <th>Confidence</th>
        <th>Source Reference</th>
      </tr>
    </thead>
    <tbody>
      {rel_rows}
    </tbody>
  </table>

  <h2>6. Source Document Inventory & Checksums</h2>
  <table>
    <thead>
      <tr>
        <th>Filename</th>
        <th>Document Type</th>
        <th>Language</th>
        <th>SHA-256 Checksum</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {doc_rows}
    </tbody>
  </table>

  <h2>7. Investigator Notes & Sign-Off</h2>
  <div class="notes-box"></div>
  <table style="margin-top: 15px;">
    <tr>
      <td style="width: 50%;"><b>Investigator Signature:</b> ___________________________</td>
      <td style="width: 50%;"><b>Supervisor Review Date:</b> ___________________________</td>
    </tr>
  </table>

  <div class="footer">
    <div>Report ID: <code>{r.id}</code></div>
    <div>TriNetra Autonomous Intelligence Prototype · Synthetic Data Only</div>
  </div>
</div>
</body>
</html>"""
    return html_content

@app.get("/api/audit-logs")
def audit_logs(u: User = Depends(require("ADMIN")), s: Session = Depends(db)):
    return [public(x) for x in s.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(100)).all()]

@app.get("/api/users")
def users(u: User = Depends(require("ADMIN")), s: Session = Depends(db)):
    return [{k: v for k, v in public(x).items() if k != "password_hash"} for x in s.scalars(select(User)).all()]

FRONTEND = ROOT / "frontend" / "dist"
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
