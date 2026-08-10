"""SQLAlchemy 2.0 models + SQLite engine factory for Phase 2 persistence.

Types are kept Postgres-portable (erd.md): a migration is a driver swap.
The *engine* still computes from in-memory loader dataclasses — the seeded
tables exist for persistence, the health band-count, and reseed idempotency,
not as an alternate compute path. See seed.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── Seeded tables (read-only at runtime) ────────────────────────────────


class Nutrient(Base):
    __tablename__ = "nutrients"
    nutrient_code: Mapped[str] = mapped_column(String, primary_key=True)
    nutrient_ko: Mapped[str] = mapped_column(String)
    group_name: Mapped[str] = mapped_column(String)
    target_unit: Mapped[str] = mapped_column(String)
    ul_unit: Mapped[str] = mapped_column(String)
    synonyms_ko_label: Mapped[str] = mapped_column(String, default="")
    has_rni: Mapped[bool] = mapped_column(Boolean, default=False)
    has_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    has_ul: Mapped[bool] = mapped_column(Boolean, default=False)


class KdriBand(Base):
    __tablename__ = "kdri_bands"
    __table_args__ = (
        UniqueConstraint("nutrient_code", "sex", "age_min", "age_max"),
        CheckConstraint("sex IN ('M','F')"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nutrient_code: Mapped[str] = mapped_column(ForeignKey("nutrients.nutrient_code"))
    sex: Mapped[str] = mapped_column(String)
    age_min: Mapped[int] = mapped_column(Integer)
    age_max: Mapped[int] = mapped_column(Integer)
    ri_base: Mapped[float] = mapped_column(Float)
    ul_limit: Mapped[float | None] = mapped_column(Float, nullable=True)


class NutrientLimit(Base):
    __tablename__ = "nutrient_limits"
    __table_args__ = (
        CheckConstraint("ul_basis IN ('total_intake','supplemental_only')"),
        CheckConstraint("length(trim(source)) > 0"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nutrient_code: Mapped[str] = mapped_column(ForeignKey("nutrients.nutrient_code"))
    applies_to_form: Mapped[str | None] = mapped_column(String, nullable=True)
    age_min: Mapped[int] = mapped_column(Integer)
    age_max: Mapped[int] = mapped_column(Integer)
    sex: Mapped[str] = mapped_column(String)
    ul_value: Mapped[float] = mapped_column(Float)
    ul_unit: Mapped[str] = mapped_column(String)
    ul_basis: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)


class NutrientForm(Base):
    __tablename__ = "nutrient_forms"
    __table_args__ = (
        UniqueConstraint("nutrient_code", "name_ko"),
        CheckConstraint("length(trim(source)) > 0"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nutrient_code: Mapped[str] = mapped_column(ForeignKey("nutrients.nutrient_code"))
    name_ko: Mapped[str] = mapped_column(String)
    elemental_pct: Mapped[float] = mapped_column(Float)
    target_factor: Mapped[float] = mapped_column(Float, default=1.0)
    ul_factor: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String)


class NutrientTiming(Base):
    # Modelled per erd.md; no seed source in Phase 2, left empty.
    __tablename__ = "nutrient_timing"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nutrient_code: Mapped[str] = mapped_column(ForeignKey("nutrients.nutrient_code"))
    taken_when: Mapped[str | None] = mapped_column(String, nullable=True)
    with_food: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    split_dose_above: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale_ko: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)


class Interaction(Base):
    __tablename__ = "interactions"
    __table_args__ = (
        CheckConstraint("severity IN ('low','medium','high','critical')"),
        CheckConstraint("length(trim(source)) > 0"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nutrient_code: Mapped[str] = mapped_column(ForeignKey("nutrients.nutrient_code"))
    drug_class: Mapped[str] = mapped_column(String)
    drug_examples_ko: Mapped[str | None] = mapped_column(String, nullable=True)
    effect: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)


class EnergyRatio(Base):
    __tablename__ = "energy_ratios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    macronutrient: Mapped[str] = mapped_column(String)
    age_min: Mapped[int] = mapped_column(Integer)
    age_max: Mapped[int] = mapped_column(Integer)
    pct_min: Mapped[float] = mapped_column(Float)
    pct_max: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String)
    changed_2025: Mapped[str | None] = mapped_column(String, nullable=True)


# ── Runtime tables (user-owned) ─────────────────────────────────────────


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class MagicLink(Base):
    __tablename__ = "magic_links"
    token: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("user_id", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Anonymous reports have user_id NULL and are bound to session_key (sid).
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    session_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )
    profile_json: Mapped[dict] = mapped_column(JSON)
    result_json: Mapped[list] = mapped_column(JSON)
    trace_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (CheckConstraint("role IN ('user','assistant')"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


# ── engine factory ──────────────────────────────────────────────────────


def make_engine(db_url: str = "sqlite:///kdri.db") -> Engine:
    """Create an engine with SQLite FK enforcement (SE-07).

    For an in-memory URL a StaticPool keeps one shared connection so the
    schema survives across sessions in a test.
    """
    kwargs: dict = {}
    if db_url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in db_url or db_url in ("sqlite://",):
            kwargs["poolclass"] = StaticPool
    engine = create_engine(db_url, **kwargs)
    if engine.url.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_conn, _rec):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
