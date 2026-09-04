"""SQLAlchemy models — server/schema.md §2 is law.

Dev default is SQLite via DATABASE_URL; DDL stays Postgres-compatible:
- TIMESTAMPTZ  → DateTime(timezone=True)
- JSONB        → JSON().variant(JSONB) — JSON on SQLite, JSONB on Postgres
- UUID         → sa.Uuid (CHAR(32) on SQLite, native UUID on Postgres)

Do not rename columns/tables here without flagging the Orchestrator: three
other agents build against schema.md.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    create_engine,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import JSON

from .config import REPO_ROOT, get_settings

JSONVariant = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_new_id)
    wa_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class MerchantSettings(Base):
    """Per-merchant settings (schema.md §8, ruling D4-2): each merchant IS an
    account, so settings persist server-side and follow the user across
    browsers/devices. One row per merchant, created on first PUT. A missing
    row means implied defaults (language 'mixed', numeral_style mirroring the
    NUMERAL_STYLE env) — the API returns those as 200, never 404."""

    __tablename__ = "merchant_settings"
    __table_args__ = (
        CheckConstraint("language IN ('ur','en','mixed')", name="ck_settings_language"),
        CheckConstraint(
            "numeral_style IN ('western','urdu')", name="ck_settings_numeral_style"
        ),
    )

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("merchants.id"), primary_key=True
    )
    language: Mapped[str] = mapped_column(Text, nullable=False, default="mixed")
    numeral_style: Mapped[str] = mapped_column(Text, nullable=False, default="western")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class MediaBlob(Base):
    """Raw audit trail — bytes live under media/ (gitignored), never deleted."""

    __tablename__ = "media_blobs"
    __table_args__ = (
        CheckConstraint("kind IN ('voice','image')", name="ck_media_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_new_id)
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchants.id"))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        # schema.md §2: UNIQUE (merchant_id, lower(name)) — functional index
        Index(
            "uq_customers_merchant_lower_name",
            "merchant_id",
            text("lower(name)"),
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_new_id)
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchants.id"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('sale','expense','udhar_given','udhar_settlement')",
            name="ck_tx_kind",
        ),
        CheckConstraint("amount_pkd > 0", name="ck_tx_amount_positive"),
        CheckConstraint(
            "source_type IN ('voice','photo','manual')", name="ck_tx_source_type"
        ),
        # schema.md §2: (merchant_id, occurred_at DESC)
        Index(
            "idx_tx_merchant_time",
            "merchant_id",
            text("occurred_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_new_id)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("merchants.id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    # Wire-key fix: the API/wire field is amount_pkr ("PKD" is not a currency);
    # the PHYSICAL column keeps its legacy name — the Neon DB already holds data.
    amount_pkr: Mapped[float] = mapped_column("amount_pkd", nullable=False)  # NUMERIC(12,2)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="PKR")
    description: Mapped[str | None] = mapped_column(Text)
    item_lines: Mapped[list | None] = mapped_column(JSONVariant)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # --- audit trail (design.md §7.2): provenance is immutable after insert ---
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_blobs.id"))
    source_model: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(nullable=True)  # NUMERIC(4,3)
    raw_model_output: Mapped[dict | None] = mapped_column(JSONVariant)
    flag: Mapped[str] = mapped_column(Text, nullable=False, default="none")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    # PATCH keeps original values alongside (schema.md §4): full pre-edit
    # snapshot stored on FIRST edit only (subsequent edits don't overwrite it);
    # provenance columns above are never modified by PATCH.
    # NOTE: additive nullable column beyond the schema.md v0.1 DDL, filed with
    # the Orchestrator for v0.2 (see STATUS.agent.md) — no consumer migration.
    original_values: Mapped[dict | None] = mapped_column(JSONVariant)


class OutboundMessage(Base):
    """What we sent, for the audit trail (schema.md §2)."""

    __tablename__ = "outbound_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_new_id)
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchants.id"))
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id"))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    media_path: Mapped[str | None] = mapped_column(Text)
    # §7.1 (additive, flagged to the Orchestrator): structured extras for the
    # send — button messages store {"buttons": [...]} (Graph API reply-button
    # wire shape) so the one-tap flow is auditable. kind stays
    # 'confirmation_text'; null on every pre-§7.1 row. No consumer migration.
    payload: Mapped[dict | None] = mapped_column(JSONVariant)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class CreditReport(Base):
    __tablename__ = "credit_reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_new_id)
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchants.id"))
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    report_json: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    narrative_ur: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class ProcessedMessage(Base):
    """Webhook idempotency table (schema.md §6.8, finding F-5): the webhook
    inserts-or-ignores the wamid BEFORE dispatching; a Meta redelivery hits the
    primary key and is acknowledged without re-processing, so one message can
    never double-create a transaction. Additive — no consumer migration."""

    __tablename__ = "processed_messages"

    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


# --- engine / session -------------------------------------------------------


def _database_url() -> str:
    """Anchor the default SQLite file to the repo root so the DB location is
    stable regardless of the cwd uvicorn/scripts were started from."""
    url = get_settings().database_url
    prefix = "sqlite:///./"
    if url.startswith(prefix):
        url = f"sqlite:///{(REPO_ROOT / url[len(prefix):]).as_posix()}"
    return url


engine = create_engine(
    _database_url(),
    connect_args={"check_same_thread": False} if _database_url().startswith("sqlite") else {},
)

if _database_url().startswith("sqlite"):
    # SQLite + timezone-aware datetimes: always store/compare in UTC.
    @event.listens_for(engine, "connect")
    def _set_sqlite_utc(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables if missing and ensure the media dir exists."""
    get_settings().media_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _ensure_additive_columns()


def _ensure_additive_columns() -> None:
    """create_all() never ALTERs an existing table, so additive columns added
    after a DB was first created must be back-filled here (SQLite dev DBs;
    Postgres deployments run a real migration). Currently: §7.1's
    outbound_messages.payload."""
    from sqlalchemy import inspect, text as sa_text

    inspector = inspect(engine)
    if not inspector.has_table("outbound_messages"):
        return
    columns = {c["name"] for c in inspector.get_columns("outbound_messages")}
    with engine.begin() as conn:
        if "payload" not in columns:
            conn.execute(sa_text("ALTER TABLE outbound_messages ADD COLUMN payload JSON"))


def db_session() -> Session:
    return SessionLocal()
