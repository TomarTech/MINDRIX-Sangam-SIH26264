import pandas as pd
import streamlit as st

from overlap import check_new_complaint
from store import add_complaint

st.set_page_config(page_title="New Complaint", page_icon="📥", layout="wide")

@st.cache_data
def load_data():
    c = pd.read_csv("data/complaints.csv", dtype={"institution_id": str})
    inst = pd.read_csv("data/institutions.csv", dtype={"institution_id": str})
    return c, inst

c, inst = load_data()
SLA = c.groupby("category")["sla_days"].first().to_dict()
BUREAUS = sorted(c["bureau"].unique())
CITIES = sorted(inst["city"].unique())

st.title("📥 Register New Complaint")
st.caption("Every new complaint is checked instantly against ALL Bureaus/Cells "
           "for overlapping and duplicate cases, before it is registered.")

if "registered" in st.session_state:
    st.success(st.session_state.pop("registered"))

# ---------- Complaint form ----------
with st.form("new_complaint"):
    col1, col2 = st.columns(2)
    bureau = col1.selectbox("Receiving Bureau/Cell", BUREAUS,
                            index=BUREAUS.index("PGRC") if "PGRC" in BUREAUS else 0)
    category = col2.selectbox("Complaint category", sorted(SLA))
    name = col1.text_input("Institution name (as written in the complaint) *")
    inst_id = col2.text_input("AICTE Permanent ID (if known)")
    city = col1.selectbox("City", CITIES)
    ctype = col2.selectbox("Complainant type",
                           ["Student", "Parent", "Faculty member", "Other stakeholder"])
    complainant = col1.text_input("Complainant name *")
    description = st.text_area("Complaint description *")
    check = st.form_submit_button("🔍 Check for overlaps & duplicates", type="primary")

if check:
    if not (name.strip() and complainant.strip() and description.strip()):
        st.error("Please fill all fields marked *.")
    else:
        st.session_state.pending = {
            "bureau": bureau, "category": category, "institution_name": name.strip(),
            "institution_id": inst_id.strip(), "city": city, "complainant_name": complainant.strip(),
            "complainant_type": ctype, "description": description.strip(),
        }

# ---------- Instant check result ----------
if "pending" in st.session_state:
    new = st.session_state.pending
    res = check_new_complaint(new, c, inst)
    st.divider()
    st.subheader("🔎 Instant check result")

    if res["institution_id"] is None:
        st.warning(f"Could not confidently match **'{new['institution_name']}'** to an AICTE "
                   f"institution in {new['city']} (best guess: {res['official_name']}, "
                   f"{res['score']:.0f}%). Please check the name or enter the AICTE ID.")
    else:
        st.info(f"🔗 Matched to **{res['official_name']}** (AICTE ID {res['institution_id']}) — "
                f"{res['method']}, **{res['score']:.0f}%** confidence")

    cols = ["case_id", "bureau", "status", "category", "assigned_officer",
            "date_received", "institution_name"]

    if not res["overlaps"].empty:
        ov = res["overlaps"]
        st.error(f"### ⚠️ Potential Overlapping Cases – Coordination Required\n"
                 f"This institution already has **{len(ov)} active case(s)** in: "
                 f"**{', '.join(sorted(ov['bureau'].unique()))}**")
        st.dataframe(ov[cols], hide_index=True, use_container_width=True)

    if not res["duplicates"].empty:
        dup = res["duplicates"]
        st.warning(f"### 🔁 Possible duplicate complaint\n"
                   f"{len(dup)} active case(s) in **{new['bureau']}** for the same institution "
                   f"look similar (same complainant, similar description or same category).")
        st.dataframe(dup[cols + ["complainant_name", "same_complainant", "text_similarity"]],
                     hide_index=True, use_container_width=True)

    if res["institution_id"] and res["overlaps"].empty and res["duplicates"].empty:
        st.success("✅ No overlapping or duplicate cases found. Safe to register.")

    b1, b2 = st.columns(2)
    if b1.button("✅ Register complaint", type="primary"):
        place = inst[inst["city"] == new["city"]].iloc[0]
        officer = c.loc[c["bureau"] == new["bureau"], "assigned_officer"].mode()[0]
        rec = {**new, "state": place["state"], "region": place["region"],
               "sla_days": SLA[new["category"]], "assigned_officer": officer,
               "true_institution_id": res["institution_id"] or ""}
        case_id = add_complaint(rec)
        note = " ⚠️ It now appears on the Overlap Alerts page." if not res["overlaps"].empty else ""
        st.session_state.registered = f"✅ Complaint registered as **{case_id}**, assigned to {officer}.{note}"
        del st.session_state.pending
        st.rerun()
    if b2.button("✖ Cancel"):
        del st.session_state.pending
        st.rerun()