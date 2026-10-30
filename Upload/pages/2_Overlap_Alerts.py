import pandas as pd
import streamlit as st

from overlap import find_overlaps
from store import link_cases, load_links

st.set_page_config(page_title="Overlap Alerts", page_icon="⚠️", layout="wide")

@st.cache_data
def load_data():
    c = pd.read_csv("data/complaints.csv", dtype={"institution_id": str})
    inst = pd.read_csv("data/institutions.csv", dtype={"institution_id": str})
    return c, find_overlaps(c, inst)

c, overlaps = load_data()
links = load_links()
linked_ids = set(links["institution_id"])

st.title("⚠️ Cross-Bureau Overlap Alerts")
st.caption("Institutions with active cases in more than one Bureau/Cell, detected automatically "
           "even when the institution name is written differently or the AICTE ID is missing.")

pending = overlaps[~overlaps["institution_id"].isin(linked_ids)]
k = st.columns(4)
k[0].metric("Institutions needing coordination", pending["institution_id"].nunique())
k[1].metric("🔴 High-confidence overlaps", (pending["confidence"] >= 85).sum())
k[2].metric("🟠 Possible matches to verify", (pending["confidence"] < 85).sum())
k[3].metric("🔗 Linked & coordinated", len(linked_ids))

level = st.radio("Show", ["All", "🔴 High confidence only", "🟠 Possible matches only"],
                 horizontal=True)
if level == "🔴 High confidence only":
    pending = pending[pending["confidence"] >= 85]
elif level == "🟠 Possible matches only":
    pending = pending[pending["confidence"] < 85]

st.divider()

case_cols = ["case_id", "bureau", "institution_name", "institution_id",
             "status", "assigned_officer", "date_received", "category"]

for inst_id, g in pending.groupby("institution_id", sort=False):
    case_ids = sorted(set(g["case_a"]) | set(g["case_b"]))
    cases = c[c["case_id"].isin(case_ids)][case_cols]
    conf = int(g["confidence"].max())

    with st.container(border=True):
        st.markdown(f"#### {g['level'].iloc[0]}")
        st.markdown(f"**Institution:** {g['institution'].iloc[0]}  \n"
                    f"**AICTE Permanent ID:** {inst_id}  \n"
                    f"**Bureaus/Cells involved:** {', '.join(sorted(cases['bureau'].unique()))}")
        st.progress(conf, text=f"Match confidence: {conf}%")
        st.dataframe(cases, hide_index=True, use_container_width=True)

        with st.expander("🧠 Why did the system flag this?"):
            for reason in sorted(set(" • ".join(g["reasons"]).split(" • "))):
                st.write("•", reason)

        col1, col2 = st.columns([2, 1])
        linker = col1.text_input("Linked by (officer name)", value="RB Officer",
                                 key=f"by_{inst_id}")
        if col2.button("🔗 Link cases & mark for coordination", key=f"link_{inst_id}"):
            link_cases(inst_id, case_ids, linker, "Cross-Bureau overlap confirmed by officer")
            st.rerun()

if pending.empty:
    st.success("No pending overlaps. All Bureaus are coordinated. 🎉")

if not links.empty:
    st.divider()
    st.subheader("🔗 Linked case groups")
    st.dataframe(links, hide_index=True, use_container_width=True)