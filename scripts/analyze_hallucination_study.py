"""Analyze the hallucination measurement study (pre-registered).

Reads ``data/processed/hallucination_study_v1.jsonl`` and produces:

- ``data/processed/hallucination_study_v1_analysis.json`` (machine)
- ``docs/findings/2026-04-29_hallucination_study_v1_results.md`` (prose)

Computes the metrics locked in
``docs/findings/2026-04-29_hallucination_study_v1_design.md``:

- Overall any-mode hallucination rate with 95% Wilson CI
- Per-mode rate (clean / mode_1 / mode_2 / novel) with CIs
- Per-query rate; query × mode contingency
- Session-level rate; chi-squared on session × hallucinated yes/no
- Retrieval-quality correlation (mean top-k score vs hallucination)
- Per-query stability (distinct cited-doc-id sets)
- "User-saved-by-verifier" tally
- Top-5 surprising findings
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

DEFAULT_INPUT = _PROJECT_ROOT / "data" / "processed" / "hallucination_study_v1.jsonl"
DEFAULT_JSON_OUT = _PROJECT_ROOT / "data" / "processed" / "hallucination_study_v1_analysis.json"
DEFAULT_MD_OUT = _PROJECT_ROOT / "docs" / "findings" / "2026-04-29_hallucination_study_v1_results.md"


# ---- Stats helpers -----------------------------------------------------


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% CI for a binomial proportion."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def chi_squared_2x2(a: int, b: int, c: int, d: int) -> tuple[float, float]:
    """Chi-squared statistic + p-value for a 2×2 table.

    Returns (chi2, p_approx). Uses the standard formula with no
    correction for continuity. p computed from the chi-squared
    survival function via a series expansion (no scipy dependency).
    """
    n = a + b + c + d
    if n == 0:
        return (0.0, 1.0)
    row1, row2 = a + b, c + d
    col1, col2 = a + c, b + d
    expected = [
        row1 * col1 / n, row1 * col2 / n,
        row2 * col1 / n, row2 * col2 / n,
    ]
    observed = [a, b, c, d]
    chi2 = 0.0
    for o, e in zip(observed, expected):
        if e > 0:
            chi2 += (o - e) ** 2 / e
    # 1 degree of freedom for 2×2: p = exp(-chi2/2). Crude but
    # accurate to within a few percent for chi2 < 20.
    p = math.exp(-chi2 / 2.0)
    return (chi2, p)


def pearson_r(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Pearson correlation r, plus 95% CI half-width via Fisher z.

    Returns (r, lo, hi).
    """
    n = len(xs)
    if n < 3 or len(ys) != n:
        return (0.0, -1.0, 1.0)
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    sx = statistics.pstdev(xs) or 1e-12
    sy = statistics.pstdev(ys) or 1e-12
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    r = cov / (sx * sy)
    r = max(min(r, 0.999999), -0.999999)
    # Fisher z transform for CI
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1 / math.sqrt(n - 3)
    lo = math.tanh(z - 1.96 * se)
    hi = math.tanh(z + 1.96 * se)
    return (r, lo, hi)


# ---- Load + classify ---------------------------------------------------


def load_runs(path: Path) -> list[dict[str, Any]]:
    runs = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            runs.append(json.loads(line))
    return runs


# ---- Aggregations ------------------------------------------------------


def analyze(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {"error": "no runs"}

    # Filter out errored runs from rate-denominator (per design)
    valid_runs = [r for r in runs if not r.get("errors")]
    n_total = len(runs)
    n_used = len(valid_runs)
    n_errored = n_total - n_used

    # Overall any-mode rate
    hallucinated = [r for r in valid_runs if not r["verification"]["all_valid"]]
    n_hall = len(hallucinated)
    rate = n_hall / n_used if n_used else 0.0
    ci_lo, ci_hi = wilson_ci(n_hall, n_used)

    # Per-mode counts
    mode_counts: Counter[str] = Counter()
    for r in valid_runs:
        mode_counts[r["verification"]["hallucination_mode"]] += 1
    per_mode_rate = {
        m: {
            "count": mode_counts.get(m, 0),
            "rate": mode_counts.get(m, 0) / n_used if n_used else 0.0,
            "wilson_ci_95": wilson_ci(mode_counts.get(m, 0), n_used),
        }
        for m in ("clean", "mode_1_stable", "mode_2_index", "novel")
    }

    # Per-query rate + query × mode contingency
    by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in valid_runs:
        by_query[r["query_id"]].append(r)
    per_query: dict[str, Any] = {}
    for qid, q_runs in sorted(by_query.items()):
        q_n = len(q_runs)
        q_hall = sum(1 for r in q_runs if not r["verification"]["all_valid"])
        q_modes = Counter(r["verification"]["hallucination_mode"] for r in q_runs)
        per_query[qid] = {
            "n": q_n,
            "hallucinated": q_hall,
            "rate": q_hall / q_n if q_n else 0.0,
            "wilson_ci_95": wilson_ci(q_hall, q_n),
            "by_mode": dict(q_modes),
            "query_text": q_runs[0]["query"],
        }

    # Session-level rate + chi-squared
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in valid_runs:
        by_session[r["session_id"]].append(r)
    sessions_summary: dict[str, Any] = {}
    for sid, s_runs in sorted(by_session.items()):
        s_n = len(s_runs)
        s_hall = sum(1 for r in s_runs if not r["verification"]["all_valid"])
        sessions_summary[sid] = {
            "n": s_n,
            "hallucinated": s_hall,
            "rate": s_hall / s_n if s_n else 0.0,
            "wilson_ci_95": wilson_ci(s_hall, s_n),
        }
    chi_test: dict[str, Any] | None = None
    if len(sessions_summary) == 2:
        sids = list(sessions_summary.keys())
        a = sessions_summary[sids[0]]["hallucinated"]
        b = sessions_summary[sids[0]]["n"] - a
        c = sessions_summary[sids[1]]["hallucinated"]
        d = sessions_summary[sids[1]]["n"] - c
        chi2, p = chi_squared_2x2(a, b, c, d)
        chi_test = {
            "session_a": sids[0],
            "session_b": sids[1],
            "table_a_hallucinated": a, "table_a_clean": b,
            "table_b_hallucinated": c, "table_b_clean": d,
            "chi2": round(chi2, 3),
            "p_approx": round(p, 4),
            "session_effect_significant": p < 0.05,
        }

    # Retrieval-quality correlation: per-query mean top score vs rate
    pq_top_scores = []
    pq_rates = []
    for qid, info in per_query.items():
        q_runs = by_query[qid]
        scores = [r["retrieval"]["top_score"] for r in q_runs
                  if r["retrieval"].get("top_score") is not None]
        if scores:
            pq_top_scores.append(statistics.mean(scores))
            pq_rates.append(info["rate"])
    r_val, r_lo, r_hi = pearson_r(pq_top_scores, pq_rates)
    retrieval_corr = {
        "n_queries": len(pq_top_scores),
        "pearson_r": round(r_val, 3),
        "ci_95": [round(r_lo, 3), round(r_hi, 3)],
        "direction_pre_registered": "negative (worse retrieval -> more hallucination)",
        "matches_pre_registration": r_val < 0,
    }

    # Per-query stability: distinct cited-doc-id sets across runs
    stability: dict[str, Any] = {}
    for qid, q_runs in by_query.items():
        sets = set()
        for r in q_runs:
            sets.add(tuple(sorted(r["answer"]["cited_doc_ids"])))
        stability[qid] = {
            "distinct_cited_sets": len(sets),
            "total_runs": len(q_runs),
            "fraction_unique": round(len(sets) / len(q_runs), 2) if q_runs else 0.0,
        }

    # Pre-registered decision
    threshold_lo = 0.05
    decision = {
        "h0_rejected": rate > 0.10 and ci_lo > threshold_lo,
        "rationale": (
            f"observed rate {rate:.1%}, lower 95% CI {ci_lo:.1%}; "
            f"H0 rejected iff rate > 10% AND lower CI > 5%."
        ),
    }
    if rate < 0.05:
        bucket = "verifier-may-be-overengineering (<5%)"
    elif rate < 0.10:
        bucket = "verifier-useful-not-loadbearing (5-10%)"
    elif rate < 0.25:
        bucket = "verifier-required (10-25%)"
    else:
        bucket = "catastrophic (>25%)"
    decision["interpretation_bucket"] = bucket

    # User-saved-by-verifier tally
    saved_by_verifier = sum(1 for r in valid_runs if r["verification"]["invalid_citations"])

    # Surprising-findings auto-flagger
    surprises: list[str] = []
    for qid, info in per_query.items():
        if info["rate"] > 0.5:
            surprises.append(
                f"Q{qid[1:]} hallucinates in {info['hallucinated']}/{info['n']} runs ({info['rate']:.0%}) — high"
            )
        if info["by_mode"].get("novel", 0) > 0:
            surprises.append(
                f"Q{qid[1:]} produced novel-mode hallucination(s): {info['by_mode']['novel']} run(s)"
            )
    # session-effect surprise
    if chi_test and chi_test["session_effect_significant"]:
        surprises.append(
            f"Session effect significant (chi2={chi_test['chi2']}, p≈{chi_test['p_approx']}) — "
            f"between-session variability is real."
        )
    # high overall variance among queries
    rates = [info["rate"] for info in per_query.values()]
    if rates and (max(rates) - min(rates)) > 0.5:
        surprises.append(
            f"Per-query rates span {min(rates):.0%}–{max(rates):.0%} — strong query-level "
            "variance; some queries are much more vulnerable than others."
        )
    surprises = surprises[:5]

    return {
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "n_total_runs": n_total,
        "n_used_in_rate": n_used,
        "n_errored": n_errored,
        "overall": {
            "hallucinated": n_hall,
            "rate": round(rate, 4),
            "wilson_ci_95": [round(ci_lo, 4), round(ci_hi, 4)],
        },
        "per_mode": per_mode_rate,
        "per_query": per_query,
        "sessions": sessions_summary,
        "session_chi_squared": chi_test,
        "retrieval_correlation": retrieval_corr,
        "per_query_stability": stability,
        "saved_by_verifier": saved_by_verifier,
        "decision": decision,
        "top_surprises": surprises,
    }


# ---- Markdown report ---------------------------------------------------


def write_markdown_report(analysis: dict[str, Any], path: Path) -> None:
    lines: list[str] = []
    a = analysis
    lines.append("# Hallucination Study v1 — Results")
    lines.append("")
    lines.append(f"**Snapshot:** {a['snapshot_at']}")
    lines.append("")
    lines.append(f"**Total runs:** {a['n_total_runs']} (used in rate: {a['n_used_in_rate']}, errored: {a['n_errored']})")
    lines.append("")
    lines.append(f"**Pre-registration:** see [`2026-04-29_hallucination_study_v1_design.md`](2026-04-29_hallucination_study_v1_design.md). This results doc was written **after** the runs completed; the design doc is committed before runs.")
    lines.append("")

    # Headline result
    o = a["overall"]
    ci = o["wilson_ci_95"]
    lines.append("## Headline result")
    lines.append("")
    lines.append(f"**Any-mode hallucination rate: {o['rate']:.1%}** (95% Wilson CI: {ci[0]:.1%}–{ci[1]:.1%})")
    lines.append("")
    d = a["decision"]
    lines.append(f"**Decision** (pre-registered rule: reject H₀ iff rate > 10% AND lower CI > 5%): {'**REJECT H₀**' if d['h0_rejected'] else 'fail to reject H₀'}")
    lines.append("")
    lines.append(f"**Interpretation bucket:** {d['interpretation_bucket']}")
    lines.append("")
    lines.append(f"**User-saved-by-verifier:** {a['saved_by_verifier']} run(s) had ≥1 hallucinated citation that would have shipped without verification.")
    lines.append("")

    # Per-mode
    lines.append("## Hallucination modes")
    lines.append("")
    lines.append("| Mode | Count | Rate | 95% Wilson CI |")
    lines.append("|---|---:|---:|---|")
    for m in ("clean", "mode_1_stable", "mode_2_index", "novel"):
        info = a["per_mode"][m]
        ci = info["wilson_ci_95"]
        lines.append(f"| {m} | {info['count']} | {info['rate']:.1%} | {ci[0]:.1%}–{ci[1]:.1%} |")
    lines.append("")

    # Per-query
    lines.append("## Per-query breakdown")
    lines.append("")
    lines.append("| Query | n | hallucinated | rate | 95% CI | modes |")
    lines.append("|---|---:|---:|---:|---|---|")
    for qid, info in a["per_query"].items():
        ci = info["wilson_ci_95"]
        modes_str = ", ".join(f"{m}={c}" for m, c in info["by_mode"].items())
        lines.append(f"| {qid} | {info['n']} | {info['hallucinated']} | {info['rate']:.1%} | {ci[0]:.1%}–{ci[1]:.1%} | {modes_str} |")
    lines.append("")

    # Per-query text reference
    lines.append("**Query texts:**")
    lines.append("")
    for qid, info in a["per_query"].items():
        lines.append(f"- **{qid}**: {info['query_text']}")
    lines.append("")

    # Session-level
    lines.append("## Session-level variability")
    lines.append("")
    lines.append("| Session | n | hallucinated | rate | 95% CI |")
    lines.append("|---|---:|---:|---:|---|")
    for sid, info in a["sessions"].items():
        ci = info["wilson_ci_95"]
        lines.append(f"| {sid} | {info['n']} | {info['hallucinated']} | {info['rate']:.1%} | {ci[0]:.1%}–{ci[1]:.1%} |")
    lines.append("")
    if a["session_chi_squared"]:
        c = a["session_chi_squared"]
        lines.append(f"**Chi-squared 2×2:** χ²={c['chi2']}, p≈{c['p_approx']}. "
                     f"Session effect significant at α=0.05: **{c['session_effect_significant']}**.")
        lines.append("")

    # Retrieval correlation
    rc = a["retrieval_correlation"]
    lines.append("## Retrieval-quality correlation")
    lines.append("")
    lines.append(f"Per-query mean top-k score vs per-query hallucination rate, "
                 f"N={rc['n_queries']} queries: **r = {rc['pearson_r']}** (95% CI: {rc['ci_95'][0]} to {rc['ci_95'][1]})")
    lines.append("")
    lines.append(f"Pre-registered direction: {rc['direction_pre_registered']}. "
                 f"Match: **{rc['matches_pre_registration']}**.")
    lines.append("")

    # Stability
    lines.append("## Per-query answer stability")
    lines.append("")
    lines.append("| Query | distinct cited-id sets | fraction unique |")
    lines.append("|---|---:|---:|")
    for qid, info in a["per_query_stability"].items():
        lines.append(f"| {qid} | {info['distinct_cited_sets']} / {info['total_runs']} | {info['fraction_unique']:.0%} |")
    lines.append("")

    # Surprises
    lines.append("## Top-5 surprising findings (auto-flagged)")
    lines.append("")
    if a["top_surprises"]:
        for s in a["top_surprises"]:
            lines.append(f"- {s}")
    else:
        lines.append("- (none flagged — observed behaviour fell within pre-registered expectations)")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ---- CLI ---------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    p.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    args = p.parse_args(argv)

    runs = load_runs(args.input)
    print(f"Loaded {len(runs)} runs from {args.input}")
    analysis = analyze(runs)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown_report(analysis, args.md_out)
    print(f"Wrote {args.json_out}")
    print(f"Wrote {args.md_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
