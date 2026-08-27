"""Deterministic demo-history seeder — months of realistic karyana activity.

Creates one merchant + customers + ~90 days of transactions (mix of voice/photo
sources, confidences, a few flags, udhar given + settled). Deterministic: fixed RNG
seed (bizro-testability). Used by tests AND by scripts/seed_demo.py for the
dashboard/report demo.
"""

from __future__ import annotations

import pathlib
import random
import uuid
from datetime import datetime, timedelta, timezone

from .db_view import Base, Customer, MediaBlob, Merchant, Transaction, get_sessionmaker

RNG_SEED = 20260821
CUSTOMERS = ["Ahmad", "Bilal", "Kamran", "Nasir", "Sana"]
ITEMS = [
    ("chai patti", 350, "packet"),
    ("cheeni", 180, "kg"),
    ("dal", 260, "kg"),
    ("cooking oil", 720, "litre"),
    ("atta", 190, "bag"),
]


def _demo_voice_bytes(seconds: float = 0.3) -> bytes:
    """Tiny valid WAV of silence — real file, clearly synthetic (audit drill-down fix)."""
    import io
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(struct.pack("<h", 0) * int(8000 * seconds))
    return buf.getvalue()


def _demo_receipt_png() -> bytes:
    """64×64 cream PNG with 'MOCK' — real image file, unmistakably demo data."""
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (64, 64), (247, 242, 231))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 63, 63], outline=(166, 51, 43))
    d.text((10, 26), "MOCK", fill=(166, 51, 43))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _media_root_for(db_url: str) -> pathlib.Path:
    """SQLite → media/ next to the DB file (tests self-clean); other URLs → repo media/."""
    if db_url.startswith("sqlite:///") and db_url != "sqlite:///:memory:":
        db_file = pathlib.Path(db_url[len("sqlite:///"):]).parent
        return db_file / "media"
    return pathlib.Path("media").resolve()


def seed_demo(db_url: str, merchant_name: str = "Al-Madina Kiryana Store",
              days: int = 90, create_tables: bool = True) -> str:
    """create_tables=True builds THIS package's minimal mirrored tables — for
    standalone/test DBs only. Against the real server DB pass False and let the
    server's own models own the DDL (prevents minimal-table pollution — the
    seeder must never define the shared schema, schema.md is server-owned)."""
    from sqlalchemy import create_engine

    rng = random.Random(RNG_SEED)
    engine = create_engine(db_url)
    if create_tables:
        Base.metadata.create_all(engine)
    Session = get_sessionmaker(db_url)
    now = datetime.now(timezone.utc)

    with Session() as s:
        import hashlib

        media_root = _media_root_for(db_url)

        def _blob(kind: str, data: bytes, when: datetime) -> uuid.UUID:
            """Real file on disk + media_blobs row → audit drill-down resolves (§6.3 mock-marked)."""
            mid_ = uuid.uuid4()
            sub = media_root / f"{when.year:04d}" / f"{when.month:02d}"
            sub.mkdir(parents=True, exist_ok=True)
            ext = "wav" if kind == "voice" else "png"
            path = sub / f"{mid_}.{ext}"
            path.write_bytes(data)
            s.add(MediaBlob(
                id=mid_, merchant_id=m.id, kind=kind,
                mime_type="audio/wav" if kind == "voice" else "image/png",
                storage_path=str(path.resolve()),
                sha256=hashlib.sha256(data).hexdigest(), created_at=when,
            ))
            return mid_

        m = Merchant(id=uuid.uuid4(), wa_id="923009999888", display_name=merchant_name,
                     created_at=now)
        s.add(m)
        cust_ids = {}
        for name in CUSTOMERS:
            c = Customer(id=uuid.uuid4(), merchant_id=m.id, name=name, created_at=now)
            s.add(c)
            cust_ids[name] = c.id

        def add_tx(day_offset, kind, amount, source, conf, flag="none", status="confirmed",
                   desc="", customer=None):
            when = now - timedelta(days=day_offset, hours=rng.randint(0, 12))
            media_id = None
            raw_out = None
            if source != "manual":
                data = _demo_voice_bytes() if source == "voice" else _demo_receipt_png()
                media_id = _blob("voice" if source == "voice" else "image", data, when)
                raw_out = {"mock": True, "note": "seeded demo history (schema.md §6.3)"}
            s.add(Transaction(
                id=uuid.uuid4(), merchant_id=m.id,
                customer_id=cust_ids.get(customer),
                kind=kind, amount_pkd=round(amount, 2), description=desc,
                occurred_at=when,
                source_type=source,
                source_media_id=media_id,
                source_model={"voice": "qwen3.5-omni-plus", "photo": "qwen-vl-ocr"}.get(source),
                confidence=conf if source != "manual" else None,
                raw_model_output=raw_out,
                flag=flag, status=status,
                created_at=when, updated_at=when,
            ))

        for day in range(days, 0, -1):
            # 5-6 entries/week: sales every ~1.2 days, udhar ~weekly, receipts ~weekly
            if day % 2 == 0:
                add_tx(day, "sale", rng.uniform(800, 4500), "voice",
                       rng.uniform(0.86, 0.98), desc="cash sale")
            if day % 7 == 3:
                add_tx(day, "udhar_given", rng.uniform(500, 5000), "voice",
                       rng.uniform(0.82, 0.96), customer=rng.choice(CUSTOMERS),
                       desc="udhar given")
            if day % 7 == 5:
                add_tx(day, "udhar_settlement", rng.uniform(300, 3000), "voice",
                       rng.uniform(0.88, 0.97), customer=rng.choice(CUSTOMERS),
                       desc="udhar received")
            if day % 6 == 0:
                item, price, unit = rng.choice(ITEMS)
                qty = rng.randint(1, 4)
                flag = "price_anomaly" if day % 30 == 0 else "none"
                conf = rng.uniform(0.78, 0.95)
                if flag != "none":
                    conf = rng.uniform(0.5, 0.7)
                add_tx(day, "expense", qty * price, "photo", conf, flag=flag,
                       status="pending" if flag != "none" else "confirmed",
                       desc=f"supplier: {item} {qty} {unit}")
        s.commit()
        return str(m.id)
