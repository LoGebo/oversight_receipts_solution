"""Normaliser (component 1): deterministic cleaning of line-item text before the classifier sees it.

normalise(): Unicode NFKC (full-width letters and digits, ligatures and compatibility forms become
their plain forms), control and format characters removed (tabs and newlines become spaces),
whitespace collapsed, ends stripped. Idempotent.
normalise_receipt() adds `description_norm` to each line, which the classifier reads; `description_raw` is
never changed: the report quotes it as printed, and the classifier's injection tripwire reads it.
Translation is the classifier's: the model returns `description_en` for every line in the same call
that classifies it (English text is copied unchanged), and the report shows it next to the original.
"""
import unicodedata


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(" " if ch.isspace() else ch for ch in text
                   if ch.isspace() or unicodedata.category(ch) not in ("Cc", "Cf"))
    return " ".join(text.split())


def normalise_receipt(receipt: dict) -> dict:
    """A copy of the receipt whose lines also carry `description_norm`; the input is not changed."""
    return {**receipt, "line_items": [{**li, "description_norm": normalise(li["description_raw"])}
                                      for li in receipt["line_items"]]}
