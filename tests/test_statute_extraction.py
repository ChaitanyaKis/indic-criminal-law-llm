"""Tests for the statute/citation extractor.

Covers real phrasings seen in the Arnesh Kumar v. State of Bihar judgment
plus a handful of synthetic edge cases (ranges, sub-sections, false
positives). The extractor returns structured dicts; tests compare on
``(act, section)`` tuples to ignore raw-string variance.
"""

from src.extractors.statutes import extract_statutes


def _keys(text: str) -> list[tuple[str, str]]:
    return [(r["act"], r["section"]) for r in extract_statutes(text)]


# ---- Arnesh Kumar specific phrasings ------------------------------------


def test_arnesh_498a_hyphenated_ipc_long_form():
    text = "Section 498-A of the Indian Penal Code, 1860 (hereinafter called as IPC)"
    assert ("IPC", "498A") in _keys(text)


def test_arnesh_crpc_dot_variants():
    text = (
        "Section 41 Cr.PC, and Section 41A Cr.PC, and Section 57, Cr.PC, "
        "and Section 167 Cr.PC"
    )
    keys = _keys(text)
    assert ("CrPC", "41") in keys
    assert ("CrPC", "41A") in keys
    assert ("CrPC", "57") in keys
    assert ("CrPC", "167") in keys


def test_arnesh_article_22_sub_2():
    text = "the constitutional right under Article 22(2) of the Constitution of India"
    result = extract_statutes(text)
    assert any(
        r["act"] == "Constitution" and r["section"] == "Article 22(2)"
        for r in result
    )


def test_arnesh_dowry_prohibition_act():
    text = "Section 4 of the Dowry Prohibition Act, 1961"
    assert ("Dowry Prohibition Act", "4") in _keys(text)


def test_arnesh_41_1_b_subsection():
    text = "Section 41(1)(b), Cr.PC which is relevant for the purpose"
    assert ("CrPC", "41(1)(b)") in _keys(text)


# ---- Section list / sub-section / range edge cases ----------------------


def test_sections_list_and():
    keys = _keys("Sections 302 and 304 IPC")
    assert ("IPC", "302") in keys
    assert ("IPC", "304") in keys


def test_sections_comma_and():
    keys = _keys("Sections 302, 304 and 306 of the Indian Penal Code")
    assert ("IPC", "302") in keys
    assert ("IPC", "304") in keys
    assert ("IPC", "306") in keys


def test_section_167_2_crpc_dotted():
    assert ("CrPC", "167(2)") in _keys("Section 167(2) Cr.P.C.")


def test_articles_list_constitution():
    keys = _keys("Articles 14, 19 and 21 of the Constitution")
    assert ("Constitution", "Article 14") in keys
    assert ("Constitution", "Article 19") in keys
    assert ("Constitution", "Article 21") in keys


def test_range_to():
    keys = _keys("Sections 302 to 304 IPC")
    assert ("IPC", "302") in keys
    assert ("IPC", "303") in keys
    assert ("IPC", "304") in keys


def test_range_hyphen():
    keys = _keys("Sections 302-304 IPC")
    assert ("IPC", "302") in keys
    assert ("IPC", "303") in keys
    assert ("IPC", "304") in keys


def test_reverse_direction():
    # "IPC Section 302" — act before section
    assert ("IPC", "302") in _keys("The charge under IPC Section 302 is made out.")


def test_dedup_same_citation_twice():
    text = "Section 302 IPC is discussed. Later, Section 302 of the Indian Penal Code."
    result = extract_statutes(text)
    ipc_302 = [r for r in result if r["act"] == "IPC" and r["section"] == "302"]
    assert len(ipc_302) == 1


def test_order_by_first_appearance():
    text = "Section 302 IPC is the offence; Section 41 Cr.PC governs arrest."
    result = extract_statutes(text)
    assert (result[0]["act"], result[0]["section"]) == ("IPC", "302")
    assert (result[1]["act"], result[1]["section"]) == ("CrPC", "41")


def test_bnss_not_bns_prefix_collision():
    # "BNSS" must not be classified as BNS.
    keys = _keys("Section 35 of the BNSS")
    assert ("BNSS", "35") in keys
    assert not any(act == "BNS" for act, _ in keys)


# ---- False positives that should be rejected ----------------------------


def test_no_match_section_of_this_judgment():
    # "this judgment" is not an act name.
    assert _keys("As noted in Section 2 of this judgment, the appellant...") == []


def test_no_match_date():
    assert _keys("The judgment was pronounced on 2 July 2014.") == []


def test_no_match_bare_numbers():
    assert _keys("The Court referenced 41 prior decisions and 167 cases.") == []


def test_no_match_generic_code():
    # "the Code" alone is not specific enough to attribute.
    assert _keys("The requirements of Section 41 of the Code are not met.") == []
