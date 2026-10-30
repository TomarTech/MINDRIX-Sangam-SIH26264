import pandas as pd
import streamlit as st

from overlap import find_overlaps

st.set_page_config(page_title="Alerts", page_icon="🔔", layout="wide")
from config import TODAY

@st.cache_data
def load_data():
    c = pd.read_csv("data/complaints.csv",
                    parse_dates=["date_received", "due_date", "last_action_date"],
                    dtype={"institution_id": str})
    inst = pd.read_csv("data/institutions.csv", dtype={"institution_id": str})
    return c, find_overlaps(c, inst)

c, overlaps = load_data()

st.title("🔔 Alerts & Notifications")
st.caption("Timeline (SLA) alerts, overdue cases, escalations, pending reminders and overlap alerts")

# ---------- Which Bureau is looking? ----------
bureau = st.selectbox("View alerts for", ["All Bureaus/Cells"] + sorted(c["bureau"].unique()))

active = c[c["status"] != "Disposed"].copy()
if bureau != "All Bureaus/Cells":
    active = active[active["bureau"] == bureau]
    overlaps = overlaps[(overlaps["bureau_a"] == bureau) | (overlaps["bureau_b"] == bureau)]

active["days_left"] = (active["due_date"] - TODAY).dt.days
active["days_since_last_action"] = (TODAY - active["last_action_date"]).dt.days

approaching = active[(active["days_left"] >= 0) & (active["days_left"] <= 7)].sort_values("days_left")
overdue = active[active["days_left"] < 0].sort_values("days_left")
overdue = overdue.assign(days_overdue=-overdue["days_left"])
escalated = active[active["status"] == "Escalated"]
stale = active[(active["days_since_last_action"] >= 15) & (active["days_left"] >= 0)]

# ---------- Summary ----------
k = st.columns(5)
k[0].metric("⏰ Due within 7 days", len(approaching))
k[1].metric("🔴 Overdue (beyond SLA)", len(overdue))
k[2].metric("⬆️ Escalated", len(escalated))
k[3].metric("💤 No action for 15+ days", len(stale))
k[4].metric("⚠️ Overlap alerts", overlaps["institution_id"].nunique())

st.divider()

cols = ["case_id", "institution_name", "bureau", "category", "status",
        "assigned_officer", "last_action", "last_action_date", "due_date"]

def reminder_button(df, label, key):
    if st.button(f"📧 {label}", key=key, disabled=df.empty):
        st.success(f"Reminder sent to {df['assigned_officer'].nunique()} officer(s) "
                   f"for {len(df)} case(s). (Simulated in prototype)")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["⏰ Approaching deadline", "🔴 Overdue",
                                        "⬆️ Escalated", "💤 Pending reminders",
                                        "⚠️ Overlaps"])

with tab1:
    st.write("Active cases whose prescribed timeline ends within the next 7 days.")
    st.dataframe(approaching[["days_left"] + cols], hide_index=True, use_container_width=True)
    reminder_button(approaching, "Send deadline reminders", "r1")

with tab2:
    st.write("Active cases already beyond the prescribed timeline (most overdue first).")
    st.dataframe(overdue.sort_values("days_overdue", ascending=False)[["days_overdue"] + cols],
                 hide_index=True, use_container_width=True)
    reminder_button(overdue, "Send overdue reminders", "r2")

with tab3:
    st.write("Cases escalated to a senior officer.")
    st.dataframe(escalated[cols], hide_index=True, use_container_width=True)

with tab4:
    st.write("Active cases where no action has been recorded for 15 days or more.")
    st.dataframe(stale.sort_values("days_since_last_action", ascending=False)
                 [["days_since_last_action"] + cols], hide_index=True, use_container_width=True)
    reminder_button(stale, "Send pending-case reminders", "r4")

with tab5:
    st.write(f"**{overlaps['institution_id'].nunique()} institution(s)** have active cases in "
             f"more than one Bureau/Cell.")
    st.page_link("pages/2_Overlap_Alerts.py", label="Open Overlap Alerts →", icon="⚠️")