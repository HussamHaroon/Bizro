"""vision_agent — Bizro Vision Audit pipeline.

Receipt photo in → OCR (Qwen-VL-OCR vs Qwen3.5-OCR, decided by bake-off) →
schema.md §1 expense transaction + price-sanity flags + Urdu confirmation.

See vision-agent/notes.md for cited API research and design decisions D-V1..D-V7.
"""

__version__ = "0.1.0"

from vision_agent.pipeline import ReceiptRejected, process_receipt_image  # noqa: F401
