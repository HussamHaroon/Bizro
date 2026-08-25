"""Read-only mirrored ORM layer over the shared schema (schema.md §2).

Mirrors only what report generation needs. Read-only by convention: nothing in this
module issues writes except CreditReport persistence in report.py (its own table).
Drift control: schema.md is the contract; qa-agent cross-checks column names.
"""

from __future__ import annotations

import os
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, Uuid, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[str] = mapped_column(Uuid, primary_key=True)
    wa_id: Mapped[str | None] = mapped_column(String)
    display_name: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(Uuid, primary_key=True)
    merchant_id: Mapped[str | None] = mapped_column(Uuid, ForeignKey("merchants.id"))
    name: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[str] = mapped_column(Uuid, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(Uuid, ForeignKey("merchants.id"))
    customer_id: Mapped[str | None] = mapped_column(Uuid, ForeignKey("customers.id"))
    kind: Mapped[str] = mapped_column(String)
    amount_pkd: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String, default="PKR")
    description: Mapped[str | None] = mapped_column(Text)
    item_lines: Mapped[dict | None] = mapped_column(__import__("sqlalchemy").JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str] = mapped_column(String)
    source_media_id: Mapped[str | None] = mapped_column(Uuid)
    source_model: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    flag: Mapped[str] = mapped_column(String, default="none")
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreditReport(Base):
    __tablename__ = "credit_reports"
    id: Mapped[str] = mapped_column(Uuid, primary_key=True)
    merchant_id: Mapped[str | None] = mapped_column(Uuid, ForeignKey("merchants.id"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    model: Mapped[str | None] = mapped_column(String)
    report_json: Mapped[dict] = mapped_column(__import__("sqlalchemy").JSON)
    narrative_ur: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def get_sessionmaker(db_url: str | None = None) -> sessionmaker:
    url = db_url or os.environ.get("DATABASE_URL", "sqlite:///./bizro.db")
    # check_same_thread=False: report generation may run on a FastAPI worker thread.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    return sessionmaker(bind=engine, expire_on_commit=False)
