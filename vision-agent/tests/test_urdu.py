"""Urdu confirmation builders: numerals, flag-aware phrasing, polite rejects."""

from __future__ import annotations

from vision_agent.sanity import FlagDetail
from vision_agent.urdu import confirmation_ur, fmt_number, reject_reply_ur

ITEMS = [
    {"item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 350, "line_total": 700},
    {"item": "cheeni", "qty": 5, "unit": "kg", "unit_price": 180, "line_total": 900},
]


class TestNumerals:
    def test_western_default(self):
        assert fmt_number(2560) == "2,560"
        assert fmt_number(700.0) == "700"  # integral floats lose the .0
        assert fmt_number(3500.5) == "3,500.50"

    def test_urdu_style(self):
        assert fmt_number(2560, "urdu") == "۲,۵۶۰"
        assert fmt_number(350, "urdu") == "۳۵۰"


class TestConfirmation:
    def test_clean_expense(self):
        text = confirmation_ur("Al-Madina Kiryana Store", 2560, ITEMS, "none", [], "western")
        assert "خرچ درج ہو گیا" in text            # expense saved
        assert "Al-Madina Kiryana Store سے" in text  # supplier from
        assert "2,560 روپے" in text                 # total
        assert "کیا یہ درست ہے؟" in text            # the confirm ask
        assert "chai patti" in text                 # items are listed

    def test_low_confidence_asks_for_the_number(self):
        text = confirmation_ur(None, 700, ITEMS[:1], "low_confidence", [], "western")
        assert "تصویر صاف نہیں" in text             # the honest admission
        assert "دوبارہ بھیجیں" in text              # ask for a re-send
        assert "کیا یہ درست ہے؟" not in text        # no confirm ask when unparseable

    def test_price_anomaly_warning(self):
        detail = FlagDetail(
            kind="price_anomaly",
            message="unit price deviation",
            data={"item": "chai patti", "unit_price": 3500, "historical_median": 350,
                  "historical_prices": [350], "deviation_ratio": 9.0},
        )
        text = confirmation_ur("Al-Madina Kiryana Store", 8860, ITEMS, "price_anomaly", [detail], "western")
        assert "تنبیہ" in text                       # a warning exists
        assert "350" in text and "3,500" in text     # both prices shown
        assert "کیا یہ درست ہے؟" in text

    def test_total_mismatch_warning(self):
        detail = FlagDetail(
            kind="total_mismatch",
            message="sum mismatch",
            data={"stated_total": 800, "computed_total": 700},
        )
        text = confirmation_ur(None, 800, ITEMS[:1], "total_mismatch", [detail], "western")
        assert "حساب" in text and "700" in text and "800" in text

    def test_duplicate_warning(self):
        detail = FlagDetail(
            kind="duplicate_suspect",
            message="dup",
            data={"supplier": "X", "amount_pkd": 700, "minutes_apart": 20},
        )
        text = confirmation_ur(None, 700, ITEMS[:1], "duplicate_suspect", [detail], "western")
        assert "منٹ پہلے" in text and "۲۰" not in text  # western numerals by default

    def test_urdu_numerals_render_eastern(self):
        text = confirmation_ur(None, 700, ITEMS[:1], "none", [], "urdu")
        assert "۷۰۰" in text and "700" not in text


class TestRejectReplies:
    def test_not_a_receipt(self):
        text = reject_reply_ur("not_a_receipt")
        assert "receipt نہیں" in text
        assert "معاف کیجیے گا" in text  # polite

    def test_unreadable(self):
        text = reject_reply_ur("unreadable")
        assert "دوبارہ بھیجیں" in text
