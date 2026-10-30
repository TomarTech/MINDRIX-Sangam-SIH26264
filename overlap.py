"""
overlap.py - Cross-Bureau overlap detection engine for SIH26264.
Step 1: link every active case to an institution in the AICTE master list
        (by AICTE ID, or by name matching when the ID is missing).
Step 2: same institution + different Bureaus/Cells = overlap.
"""
import re

import pandas as pd
from rapidfuzz import fuzz

EXPAND = {
    "inst": "institute", "tech": "technology", "engg": "engineering",
    "coll": "college", "mgmt": "management", "sci": "science",
    "pharm": "pharmacy", "shree": "shri", "sri": "shri",
}
DROP = {"of", "the", "and"}

ALERT_LEVEL = 85     # 85+  -> red alert
POSSIBLE_LEVEL = 70  # 70-84 -> possible match


def clean_words(name):
    main = str(name).rsplit(",", 1)[0].lower()
    main = main.replace("&", " and ")
    main = re.sub(r"[^a-z ]", " ", main)
    return [EXPAND.get(w, w) for w in main.split()]


def normalize(name):
    return " ".join(w for w in clean_words(name) if w not in DROP)


def acronym(name):
    return "".join(w[0] for w in clean_words(name) if w not in DROP)


def is_acronym_of(short_name, full_name):
    words = clean_words(short_name)
    return len(words) == 1 and 2 <= len(words[0]) <= 7 and words[0] == acronym(full_name)


def resolve(name, city, institutions):
    """Find the best-matching institution in the AICTE master list (same city).
    Returns (institution_id, official_name, score, method)."""
    best = (None, None, 0, "")
    for r in institutions[institutions["city"] == city].itertuples():
        if is_acronym_of(name, r.name):
            score, method = 95, "acronym match"
        else:
            score, method = fuzz.token_sort_ratio(normalize(name), normalize(r.name)), "name similarity"
        if score > best[2]:
            best = (r.institution_id, r.name, score, method)
    return best


def find_overlaps(df, institutions):
    """Return all cross-Bureau overlaps among ACTIVE cases."""
    df = df.copy()
    df["institution_id"] = df["institution_id"].fillna("").astype(str)
    active = df[df["status"] != "Disposed"].copy()
    official_name = dict(zip(institutions["institution_id"], institutions["name"]))

    # ---- Step 1: link each case to an institution ----
    resolved, scores, notes = [], [], []
    for r in active.itertuples():
        if r.institution_id:
            resolved.append(r.institution_id)
            scores.append(100)
            notes.append(f"{r.case_id}: AICTE ID recorded")
        else:
            inst_id, off_name, score, method = resolve(r.institution_name, r.city, institutions)
            resolved.append(inst_id if score >= POSSIBLE_LEVEL else None)
            scores.append(score)
            notes.append(f"{r.case_id}: '{r.institution_name}' matched to '{off_name}' "
                         f"({method}, {score:.0f}%)")
    active["resolved_id"] = resolved
    active["match_score"] = scores
    active["match_note"] = notes

    # ---- Step 2: same institution in different Bureaus = overlap ----
    results = []
    for inst_id, group in active.dropna(subset=["resolved_id"]).groupby("resolved_id"):
        if group["bureau"].nunique() < 2:
            continue
        cases = group.to_dict("records")
        for i in range(len(cases)):
            for j in range(i + 1, len(cases)):
                a, b = cases[i], cases[j]
                if a["bureau"] == b["bureau"]:
                    continue
                score = min(a["match_score"], b["match_score"])
                if a["institution_id"] and b["institution_id"]:
                    reasons = "Same AICTE Permanent ID in both cases"
                else:
                    reasons = " • ".join(c["match_note"] for c in (a, b)
                                         if not c["institution_id"])
                results.append({
                    "institution_id": inst_id,
                    "institution": official_name.get(inst_id, ""),
                    "case_a": a["case_id"], "bureau_a": a["bureau"], "name_a": a["institution_name"],
                    "case_b": b["case_id"], "bureau_b": b["bureau"], "name_b": b["institution_name"],
                    "confidence": round(score),
                    "level": "🔴 Overlap – Coordination Required" if score >= ALERT_LEVEL
                             else "🟠 Possible match – verify",
                    "reasons": reasons,
                })

    columns = ["institution_id", "institution", "case_a", "bureau_a", "name_a",
               "case_b", "bureau_b", "name_b", "confidence", "level", "reasons"]
    if not results:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(results)[columns].sort_values("confidence", ascending=False).reset_index(drop=True)

# =====================================================================
#  NEW: checks for a new complaint + duplicate detection
# =====================================================================

def link_active_cases(df, institutions):
    """Link every ACTIVE case to an institution (by ID, or by name matching)."""
    df = df.copy()
    df["institution_id"] = df["institution_id"].fillna("").astype(str)
    active = df[df["status"] != "Disposed"].copy()
    ids, scores = [], []
    for r in active.itertuples():
        if r.institution_id:
            ids.append(r.institution_id)
            scores.append(100)
        else:
            inst_id, _, score, _ = resolve(r.institution_name, r.city, institutions)
            ids.append(inst_id if score >= POSSIBLE_LEVEL else None)
            scores.append(score)
    active["resolved_id"] = ids
    active["match_score"] = scores
    return active


def text_similarity(a, b):
    """How similar two complaint descriptions are (0-100)."""
    return fuzz.token_set_ratio(str(a).lower(), str(b).lower())


def check_new_complaint(new, df, institutions):
    """Instant check for a complaint BEFORE it is registered.
    Returns the matched institution + overlapping cases + possible duplicates."""
    known_ids = set(institutions["institution_id"])
    if new["institution_id"] and new["institution_id"] in known_ids:
        inst_id = new["institution_id"]
        official = institutions.loc[institutions["institution_id"] == inst_id, "name"].iloc[0]
        score, method = 100, "AICTE ID"
    else:
        inst_id, official, score, method = resolve(new["institution_name"], new["city"], institutions)

    result = {"institution_id": inst_id if score >= POSSIBLE_LEVEL else None,
              "official_name": official, "score": score, "method": method,
              "overlaps": pd.DataFrame(), "duplicates": pd.DataFrame()}
    if result["institution_id"] is None:
        return result

    active = link_active_cases(df, institutions)
    same_college = active[active["resolved_id"] == inst_id]

    # Overlap = same college, active in a DIFFERENT Bureau
    result["overlaps"] = same_college[same_college["bureau"] != new["bureau"]]

    # Duplicate = same college, SAME Bureau, and same person / similar text / same category
    same_bureau = same_college[same_college["bureau"] == new["bureau"]].copy()
    if not same_bureau.empty:
        same_bureau["same_complainant"] = (
            same_bureau["complainant_name"].astype(str).str.lower().str.strip()
            == new["complainant_name"].lower().strip())
        same_bureau["text_similarity"] = same_bureau["description"].apply(
            lambda d: text_similarity(d, new["description"]))
        result["duplicates"] = same_bureau[same_bureau["same_complainant"]
                                           | (same_bureau["text_similarity"] >= 60)
                                           | (same_bureau["category"] == new["category"])]
    return result


def find_duplicates(df, institutions, days=60):
    """Possible duplicate complaints already in the system:
    same college + same Bureau + within `days` + (same complainant OR very similar text)."""
    active = link_active_cases(df, institutions).dropna(subset=["resolved_id"])
    active["date_received"] = pd.to_datetime(active["date_received"])
    official = dict(zip(institutions["institution_id"], institutions["name"]))
    rows = []
    for (inst_id, bureau), g in active.groupby(["resolved_id", "bureau"]):
        cases = g.to_dict("records")
        for i in range(len(cases)):
            for j in range(i + 1, len(cases)):
                a, b = cases[i], cases[j]
                gap = abs((a["date_received"] - b["date_received"]).days)
                if gap > days:
                    continue
                same_person = str(a["complainant_name"]).lower() == str(b["complainant_name"]).lower()
                sim = text_similarity(a["description"], b["description"])
                if same_person or sim >= 70:
                    reasons = []
                    if same_person:
                        reasons.append(f"Same complainant ({a['complainant_name']})")
                    reasons.append(f"Description similarity {sim:.0f}%")
                    reasons.append(f"Filed {gap} days apart")
                    rows.append({"institution": official.get(inst_id, ""), "bureau": bureau,
                                 "case_a": a["case_id"], "case_b": b["case_id"],
                                 "reasons": " • ".join(reasons)})
    return pd.DataFrame(rows, columns=["institution", "bureau", "case_a", "case_b", "reasons"])