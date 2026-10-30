import pytest

from validator.loader import load_receipts
from validator.normaliser import normalise, normalise_receipt


@pytest.mark.parametrize("raw, clean", [
    ("  Draft   IPA ", "Draft IPA"),
    ("Café\tcon\nleche", "Café con leche"),
    ("ＵＳＢ－Ｃ ケーブル　２ｍ", "USB-C ケーブル 2m"),      # full-width forms and the ideographic space (NFKC)
    ("ｶﾞｲﾄﾞ", "ガイド"),                                  # half-width katakana
    ("Zero​width\x00 bell\x07", "Zerowidth bell"),  # format and control characters removed
    ("ﬁle", "file"),                                     # ligature
    ("", ""),
])
def test_normalise(raw, clean):
    assert normalise(raw) == clean
    assert normalise(clean) == clean  # idempotent


def test_normalise_receipt_copies_and_keeps_the_original():
    r = {"receipt_id": "X", "line_items": [{"line_id": "X-L1", "description_raw": " a　b "}]}
    out = normalise_receipt(r)
    assert out["line_items"][0] == {"line_id": "X-L1", "description_raw": " a　b ", "description_norm": "a b"}
    assert r["line_items"][0] == {"line_id": "X-L1", "description_raw": " a　b "}


def test_dataset_text_is_already_clean():
    assert all(normalise(li["description_raw"]) == li["description_raw"] for r in load_receipts() for li in r["line_items"])
