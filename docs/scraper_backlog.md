# Scraper Backlog

Known gaps and remediation items for the Indian Kanoon scraping
pipeline (``src/scrapers/``). Items here are *not* blockers for the
current iteration but need to be worked through before any claims
about corpus completeness.

---

## Historical JJ Act false negatives

The criminal filter previously did not recognize the Juvenile Justice
Act as a criminal statute, so JJ Act cases encountered during scraping
were filtered out and not saved. After the filter fix (this commit),
JJ Act cases are correctly classified going forward, but historical
JJ Act cases the scraper already saw are lost — we have their doc_ids
in the ``filtered_out`` bucket of the state file, but not their
judgment text, because they were rejected before disk write.

To recover them would require either:

(a) **Re-running the scraper from scratch** with the fixed filter
    (cost: ~48 hours of scraping time at the current 3-second rate
    limit, plus the blast radius of re-hitting Indian Kanoon for docs
    we already have).

(b) **A targeted JJ Act search on Indian Kanoon** using its built-in
    statute filter to pull only JJ Act SC cases and feed them through
    the parser. Much cheaper — estimated <2 hours for the full JJ Act
    SC case backlog. Cleanly re-uses ``IndianKanoonScraper`` with a
    custom ``search_by_year`` variant that adds
    ``statute:Juvenile Justice Act`` to the ``formInput``.

Option (b) is cheaper and cleaner. **Parked as Week 2+ task.** The
downstream impact is that the current corpus under-represents
juvenile-law cases — relevant especially for age-related sentencing
questions (e.g. the "15-year-old attempt to murder" smoke question
that surfaced this gap in the first place).

### Remediation plan sketch (for option b)

1. Add ``search_by_act()`` method to ``IndianKanoonScraper`` that
   emits ``formInput=doctypes:supremecourt+statute:<act>`` per year.
2. Run for ``Juvenile Justice Act`` across 2015-2024.
3. Pipe through the filter and normal save pipeline. Idempotent — the
   state file's ``docs`` dict dedups by doc_id, so already-saved JJ
   Act cases (if any slipped through) won't double-save.
4. Extend the same mechanism to any other single-statute backfills
   the corpus inventory surfaces as gaps.

---

## Title-scrape gap (informational)

Indian Kanoon strips case-style markers (``Crl.A.``, ``SLP (Crl)``)
from the ``<title>`` tag on judgment pages. Fixed in this commit by
looking at the first 2000 chars of the judgment body, where the court
itself prints the case style. No re-scrape needed — the fix applies
retroactively via ``scripts/rescore_filter.py``.
