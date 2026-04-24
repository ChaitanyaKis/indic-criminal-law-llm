"""Tests for the criminal-case filter.

Covers:
- JJ Act variant detection (BUG 1)
- High-confidence promotion from full_text header / case_number (BUG 2)
- Confidence-tier logic for single-signal edge cases
- Regression on a real corpus doc (Jage Ram or Arnesh Kumar)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.scrapers.criminal_filter import is_criminal


# ---- Helpers -----------------------------------------------------------


def _judgment(**kwargs) -> dict:
    """Build a minimal judgment dict with the fields the filter reads."""
    rec = {
        "doc_id": kwargs.get("doc_id", "synthetic_001"),
        "title": kwargs.get("title", "Plaintiff vs Defendant on 1 January, 2020"),
        "full_text": kwargs.get("full_text", "Some body text without any criminal markers."),
        "statutes_cited": kwargs.get("statutes_cited", []),
    }
    if "case_number" in kwargs:
        rec["case_number"] = kwargs["case_number"]
    return rec


# ---- BUG 1 — JJ Act variants ------------------------------------------


@pytest.mark.parametrize("variant", [
    "Juvenile Justice Act",
    "JJ Act",
    "Juvenile Justice (Care and Protection of Children) Act",
    "Juvenile Justice (Care and Protection of Children) Act, 2015",
    "Juvenile Justice (Care and Protection of Children) Act, 2000",
])
def test_jj_act_variants_detected(variant: str):
    # Bare-title doc (no case-style markers anywhere) + a JJ-Act reference
    # in the body should be classified criminal. Because the filter has
    # exactly one signal (act match), confidence is "medium" — that's
    # correct for JJ-only cases without case-style markers. The core
    # assertion is kept=True (not filtered out).
    rec = _judgment(
        title="X vs State on 1 January, 2020",
        full_text=f"The appellant argued that the {variant} applies here.",
    )
    kept, confidence = is_criminal(rec)
    assert kept is True, f"JJ variant {variant!r} was filtered out"
    assert confidence in ("medium", "high")


# ---- BUG 2 — high-conf from body / case_number ------------------------


def test_high_confidence_from_full_text_header():
    # Title is plain ("X vs State") but the judgment body starts with
    # the typical SC header. Pre-fix, this would have been medium; post-
    # fix, both signals hit → high.
    body = (
        "REPORTABLE\n"
        "IN THE SUPREME COURT OF INDIA\n"
        "CRIMINAL APPELLATE JURISDICTION\n"
        "CRIMINAL APPEAL NO. 1277 OF 2014\n"
        "ARNESH KUMAR ..... APPELLANT\n"
        "VERSUS\n"
        "STATE OF BIHAR & ANR. .... RESPONDENTS\n"
        "The petitioner apprehends his arrest in a case under Section 498-A of the IPC."
    )
    rec = _judgment(
        title="Arnesh Kumar vs State Of Bihar & Anr on 2 July, 2014",
        full_text=body,
        statutes_cited=[{"act": "IPC", "section": "498A", "raw": "Section 498-A of the IPC"}],
    )
    kept, confidence = is_criminal(rec)
    assert kept is True
    assert confidence == "high"


def test_high_confidence_from_case_number():
    # Title and body both bland, but the parsed case_number contains the
    # marker. Pre-fix: medium. Post-fix: high.
    rec = _judgment(
        title="A vs State on 5 May, 2020",
        case_number="Crl.A. 123/2020",
        full_text="The appellant was convicted under Section 302 IPC.",
        statutes_cited=[{"act": "IPC", "section": "302", "raw": "Section 302 IPC"}],
    )
    kept, confidence = is_criminal(rec)
    assert kept is True
    assert confidence == "high"


# ---- Confidence-tier coverage -----------------------------------------


def test_medium_when_only_acts():
    # IPC in statutes but no case-style marker anywhere → medium.
    rec = _judgment(
        title="Civil suit vs company on 1 January, 2020",
        full_text=(
            "In this civil defamation case, the plaintiff relies on the "
            "Section 499 IPC definition of defamation for context but the "
            "cause of action is entirely civil."
        ),
        statutes_cited=[{"act": "IPC", "section": "499", "raw": "Section 499 IPC"}],
    )
    kept, confidence = is_criminal(rec)
    assert kept is True
    assert confidence == "medium"


def test_medium_when_only_case_style():
    # Case-style marker present (body header), but NO criminal-act
    # citation. Unusual but possible — e.g. procedural orders referring
    # to a parallel criminal proceeding. Should be medium, not high.
    rec = _judgment(
        title="X vs Y on 1 January, 2020",
        full_text=(
            "IN THE SUPREME COURT OF INDIA\n"
            "CRIMINAL APPELLATE JURISDICTION\n"
            "CRIMINAL APPEAL NO. 50 OF 2021\n"
            "The parties had resolved the underlying dispute and the matter "
            "was withdrawn. No substantive order is required."
        ),
        statutes_cited=[],  # no criminal acts
    )
    kept, confidence = is_criminal(rec)
    assert kept is True
    assert confidence == "medium"


# ---- Regression on real corpus ---------------------------------------


def test_regression_jage_ram_or_arnesh_is_high_now():
    """Pre-fix, both Jage Ram and Arnesh Kumar landed as ``medium`` because
    IK strips case-style markers from the page <title>. Post-fix, the
    body-header check finds "CRIMINAL APPELLATE JURISDICTION" and both
    signals hit. This is the bug-fix validation tied to real data.

    Skipped gracefully if neither judgment is on disk (data/raw is
    gitignored, so CI runs without them)."""
    project_root = Path(__file__).resolve().parent.parent
    candidates = [
        project_root / "data" / "raw" / "supreme_court" / "2015" / "115651329.json",
        project_root / "data" / "raw" / "2982624.json",  # Arnesh Kumar
    ]
    rec: dict | None = None
    chosen: Path | None = None
    for c in candidates:
        if c.exists():
            chosen = c
            rec = json.loads(c.read_text(encoding="utf-8"))
            break
    if rec is None:
        pytest.skip("No real-corpus regression doc on disk")
    kept, confidence = is_criminal(rec)
    assert kept is True, f"{chosen} filtered out"
    assert confidence == "high", (
        f"{chosen} was classified {confidence!r}, expected 'high' after fix"
    )
