import datetime as dt
from sqlalchemy import (Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, scoped_session

Base = declarative_base()
now = lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(16), nullable=False, default="analyst")  # admin | analyst
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=now)

class Case(Base):
    __tablename__ = "cases"
    id = Column(Integer, primary_key=True)
    case_code = Column(String(32), unique=True)
    title = Column(String(200), nullable=False)
    status = Column(String(16), default="open")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=now)
    evidence = relationship("Evidence", back_populates="case")

class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    original_name = Column(String(255))
    original_path = Column(String(500), nullable=False)   # server-side random name, never user-supplied
    sha256 = Column(String(64), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    fmt = Column(String(16))
    width = Column(Integer); height = Column(Integer)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    uploaded_at = Column(DateTime, default=now)
    case = relationship("Case", back_populates="evidence")
    __table_args__ = (UniqueConstraint("case_id", "sha256", name="uq_case_sha"),)

class ModelVersion(Base):
    __tablename__ = "model_versions"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True)
    algo = Column(String(32))
    trained_at = Column(String(40)); seed = Column(Integer)
    metrics_json = Column(Text); path = Column(String(500))

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=False)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=True)
    params = Column(Text)
    result_json = Column(Text)
    started_at = Column(DateTime, default=now)
    created_by = Column(Integer, ForeignKey("users.id"))

class DetectionResult(Base):
    __tablename__ = "detection_results"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False)
    method = Column(String(16))  # stats | ml
    name = Column(String(64)); score = Column(Float, nullable=True); level = Column(String(16))

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    run_ids = Column(Text)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=True)
    pdf_path = Column(String(500)); pdf_sha256 = Column(String(64)); content_sha256 = Column(String(64))
    created_at = Column(DateTime, default=now); created_by = Column(Integer, ForeignKey("users.id"))

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True); case_id = Column(Integer, nullable=True); evidence_id = Column(Integer, nullable=True)
    action = Column(String(64), nullable=False); detail = Column(Text, default="{}")
    timestamp = Column(DateTime, default=now)

class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"
    id = Column(Integer, primary_key=True)
    config_json = Column(Text); result_json = Column(Text)
    seed = Column(Integer); started_at = Column(DateTime, default=now); created_by = Column(Integer)

import contextlib
from sqlalchemy import text

@contextlib.contextmanager
def startup_lock(engine):
    """Serialise first-boot work (create tables, seed rows) across gunicorn workers. PostgreSQL advisory lock; no-op on SQLite."""
    if engine.dialect.name != "postgresql":
        yield; return
    conn = engine.connect()
    try:
        conn.execute(text("SELECT pg_advisory_lock(727274)"))
        yield
    finally:
        try:
            conn.execute(text("SELECT pg_advisory_unlock(727274)"))
        finally:
            conn.close()

def make_session(uri):
    engine = create_engine(uri, future=True)
    with startup_lock(engine):
        Base.metadata.create_all(engine)
    return engine, scoped_session(sessionmaker(bind=engine, expire_on_commit=False))
