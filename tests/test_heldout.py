"""Validates the held-out fixture itself (no network). Compares against dataset input descriptions only."""
import pytest

from validator.classifier import CATEGORIES
from validator.evaluation import heldout
from validator.evaluation.heldout import load
from validator.loader import load_receipts
from validator.rules.documentation import EXTENSIONS
from validator.rules.gifts import RECIPIENT_KINDS

RECEIPTS, EXPECTED = load()
ENGINE_CATEGORIES = set(CATEGORIES) | set(EXTENSIONS)  # labels use the engine's refinements of `other`
LINES = [li for r in RECEIPTS for li in r["line_items"]]


def test_ids_unique_and_labels_cover_every_line():
    rids = [r["receipt_id"] for r in RECEIPTS]
    lids = [li["line_id"] for li in LINES]
    assert len(set(rids)) == len(rids) and len(set(lids)) == len(lids)
    assert all(li["line_id"].startswith(r["receipt_id"] + "-L") for r in RECEIPTS for li in r["line_items"])
    assert set(EXPECTED) == set(lids) and all(EXPECTED[lid]["receipt_id"] == lid.rsplit("-L", 1)[0] for lid in lids)


def test_input_shape_matches_the_dataset():
    ref = load_receipts()[0]
    for r in RECEIPTS:
        assert r.keys() == ref.keys() and r["receipt_id"].startswith("HO-")
        assert all(li.keys() == ref["line_items"][0].keys() for li in r["line_items"])
        assert abs(r["total_amount"] - sum(li["amount"] for li in r["line_items"])) < 0.01


def test_labels_are_valid():
    for e in EXPECTED.values():
        assert e.keys() == {"receipt_id", "line_id", "category", "acceptable_alternatives", "genuinely_ambiguous", "gift_recipient"}
        assert e["category"] in ENGINE_CATEGORIES and set(e["acceptable_alternatives"]) <= ENGINE_CATEGORIES
        assert e["category"] not in e["acceptable_alternatives"] and isinstance(e["genuinely_ambiguous"], bool)
        g = e["gift_recipient"]
        assert g is None or (g.keys() == {"kind", "name"} and g["kind"] in RECIPIENT_KINDS)
    assert sum(e["genuinely_ambiguous"] for e in EXPECTED.values()) >= 10
    assert {g["kind"] for e in EXPECTED.values() if (g := e["gift_recipient"])} == set(RECIPIENT_KINDS)


def test_all_six_languages_present():
    assert {li["language"] for li in LINES} == {"en", "es", "fr", "de", "pt", "ja"}


def test_no_description_reused_from_the_dataset():
    seen = {li["description_raw"].strip().lower() for r in load_receipts() for li in r["line_items"]}
    assert not [li["description_raw"] for li in LINES if li["description_raw"].strip().lower() in seen]


class _Down:
    @property
    def messages(self):
        raise RuntimeError("API down")


def test_refuses_to_overwrite_a_record_without_force(tmp_path, monkeypatch):
    out = tmp_path / "run_record.json"
    out.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(heldout, "OUT", out)
    with pytest.raises(SystemExit, match="--force"):
        heldout.main([], client=_Down())
    assert out.read_text(encoding="utf-8") == "{}"


def test_any_failure_exits_non_zero_and_writes_no_record(tmp_path, monkeypatch):
    monkeypatch.setattr(heldout, "OUT", tmp_path / "run_record.json")
    monkeypatch.setattr(heldout, "CACHE", tmp_path / "cache")
    with pytest.raises(SystemExit, match="classifier failed") as e:
        heldout.main(["--force"], client=_Down())
    assert e.value.code != 0 and not (tmp_path / "run_record.json").exists()


def test_provider_and_model_flags_reach_the_classifier(tmp_path, monkeypatch):
    seen = {}

    def fake_classify(_receipts, **kw):
        seen.update(kw)
        raise SystemExit("stop")
    monkeypatch.setattr(heldout, "OUT", tmp_path / "run_record.json")
    monkeypatch.setattr(heldout, "classify", fake_classify)
    with pytest.raises(SystemExit):
        heldout.main(["--provider", "openrouter", "--model", "x/y"])
    assert seen["provider"] == "openrouter" and seen["model"] == "x/y"
