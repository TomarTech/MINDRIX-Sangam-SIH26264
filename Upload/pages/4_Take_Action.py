import os

import pandas as pd
import streamlit as st

from store import DOCS, add_action, save_document

st.set_page_config(page_title="Take Action", page_icon="🛠️", layout="wide")

@st.cache_data
def load_data():
    c = pd.read_csv("data/complaints.csv", dtype={"institution_id": str})
    a = pd.read_csv("data/actions.csv")
    if "document" not in a.columns:
        a["document"] = ""
    a["document"] = a["document"].fillna("")
    return c, a

c, a = load_data()
BUREAUS = sorted(c["bureau"].unique())

st.title("🛠️ Take Action on a Case")
st.caption("Record actions, transfer, escalate or dispose a case. Every action is saved "
           "permanently with officer, date, time, remarks and supporting documents.")

if "last_msg" in st.session_state:
    st.success(st.session_state.pop("last_msg"))

# ---------- Pick a case ----------
active = c[c["status"] != "Disposed"]
names = dict(zip(active["case_id"], active["institution_name"]))
case_id = st.selectbox("Select an active case (type to search)", active["case_id"].tolist(),
                       format_func=lambda x: f"{x} — {names[x]}")
row = c[c["case_id"] == case_id].iloc[0]

# ---------- Case summary ----------
with st.container(border=True):
    s1, s2, s3 = st.columns(3)
    s1.markdown(f"**Institution:** {row['institution_name']}  \n"
                f"**AICTE ID:** {row['institution_id'] if pd.notna(row['institution_id']) else '— not recorded —'}  \n"
                f"**Category:** {row['category']}")
    s2.markdown(f"**Bureau/Cell:** {row['bureau']}  \n"
                f"**Assigned officer:** {row['assigned_officer']}  \n"
                f"**Status:** {row['status']}")
    s3.markdown(f"**Received:** {row['date_received']}  \n"
                f"**Due date:** {row['due_date']}  \n"
                f"**Complainant:** {row['complainant_name']} ({row['complainant_type']})")
    st.markdown(f"**Complaint:** *{row['description']}*")

left, right = st.columns([1, 1])

# ---------- Action history ----------
with left:
    st.subheader("🕒 Action history")
    for _, h in a[a["case_id"] == case_id].sort_values("step").iterrows():
        st.markdown(f"**{h['timestamp']}** · {h['bureau']} · {h['officer']}  \n"
                    f"➡️ {h['action']} — *{h['remarks']}*")
        if h["document"]:
            path = os.path.join(DOCS, h["document"])
            if os.path.exists(path):
                with open(path, "rb") as f:
                    st.download_button(f"📎 {h['document']}", f.read(), h["document"],
                                       key=f"doc_{h['case_id']}_{h['step']}")

# ---------- Action form ----------
with right:
    st.subheader("➕ Record a new action")
    officers = sorted(c.loc[c["bureau"] == row["bureau"], "assigned_officer"].unique())
    with st.form("action_form", clear_on_submit=True):
        action_type = st.radio("Type of action", ["📝 Record action / note",
                                                  "🔁 Transfer to another Bureau/Cell",
                                                  "⬆️ Escalate to senior officer",
                                                  "✅ Dispose / close case"])
        officer = st.selectbox("Action taken by", officers)
        remarks = st.text_area("Remarks *")
        next_act = st.text_input("Next action required", value=str(row["next_action"]))
        target = st.selectbox("Transfer to (used only for transfer)",
                              [b for b in BUREAUS if b != row["bureau"]])
        doc = st.file_uploader("Attach supporting document (optional)",
                               type=["pdf", "png", "jpg", "jpeg", "docx"])
        submitted = st.form_submit_button("💾 Save action", type="primary")

    if submitted:
        if not remarks.strip():
            st.error("Please enter remarks before saving.")
        else:
            doc_name = save_document(case_id, doc) if doc else ""
            if action_type.startswith("📝"):
                add_action(case_id, "Action recorded", remarks, officer,
                           new_status="Under Process" if row["status"] == "Received" else None,
                           next_action=next_act, document=doc_name)
            elif action_type.startswith("🔁"):
                new_officer = c.loc[c["bureau"] == target, "assigned_officer"].mode()[0]
                add_action(case_id, f"Transferred from {row['bureau']} to {target}", remarks,
                           officer, new_status="Transferred", new_bureau=target,
                           assign_to=new_officer, next_action="Examine case in new Bureau/Cell",
                           document=doc_name)
            elif action_type.startswith("⬆️"):
                add_action(case_id, "Escalated to senior officer", remarks, officer,
                           new_status="Escalated", next_action="Decision by senior officer pending",
                           document=doc_name)
            else:
                add_action(case_id, "Complaint disposed", remarks, officer,
                           new_status="Disposed", next_action="-", document=doc_name)
            st.session_state.last_msg = f"✅ Action saved for {case_id}."
            st.rerun()