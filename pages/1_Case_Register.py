import pandas as pd
import streamlit as st

st.set_page_config(page_title="Case Register", page_icon="📋", layout="wide")
from config import TODAY

@st.cache_data
def load_data():
    c = pd.read_csv("data/complaints.csv",
                    parse_dates=["date_received", "due_date", "last_action_date"],
                    dtype={"institution_id": str})
    a = pd.read_csv("data/actions.csv")
    c["institution_id"] = c["institution_id"].fillna("")
    # SLA status for every case
    def sla(row):
        if row["status"] == "Disposed":
            return "✅ Disposed"
        if row["due_date"] < TODAY:
            return "🔴 Overdue"
        return "🟢 On track"
    c["sla_status"] = c.apply(sla, axis=1)
    return c, a

c, a = load_data()

st.title("📋 Case Register")
st.caption("Search and track every institution-related complaint across all Bureaus/Cells")

# ---------- Filters (in the sidebar) ----------
st.sidebar.header("🔍 Search & Filters")
search = st.sidebar.text_input("Case ID, Institution name or AICTE ID")
bureaus = st.sidebar.multiselect("Bureau/Cell", sorted(c["bureau"].unique()))
regions = st.sidebar.multiselect("Region", sorted(c["region"].unique()))
categories = st.sidebar.multiselect("Complaint category", sorted(c["category"].unique()))
statuses = st.sidebar.multiselect("Status", sorted(c["status"].unique()))
dates = st.sidebar.date_input("Received between",
                              value=(c["date_received"].min().date(), TODAY.date()))

# ---------- Apply filters ----------
f = c.copy()
if search:
    s = search.lower()
    f = f[f["case_id"].str.lower().str.contains(s, regex=False)
          | f["institution_name"].str.lower().str.contains(s, regex=False)
          | f["institution_id"].str.lower().str.contains(s, regex=False)]
if bureaus:
    f = f[f["bureau"].isin(bureaus)]
if regions:
    f = f[f["region"].isin(regions)]
if categories:
    f = f[f["category"].isin(categories)]
if statuses:
    f = f[f["status"].isin(statuses)]
if len(dates) == 2:
    f = f[(f["date_received"].dt.date >= dates[0]) & (f["date_received"].dt.date <= dates[1])]

# ---------- Results table ----------
st.write(f"**{len(f)} cases found**")
show_cols = ["case_id", "date_received", "institution_name", "institution_id", "region",
             "bureau", "category", "status", "sla_status", "assigned_officer",
             "last_action", "next_action", "due_date"]
st.dataframe(f[show_cols].sort_values("date_received", ascending=False),
             use_container_width=True, hide_index=True)

st.download_button("⬇️ Download these cases (CSV)", f[show_cols].to_csv(index=False),
                   "aicte_cases.csv", "text/csv")

st.divider()

# ---------- Case details + action history ----------
st.subheader("🔎 Case details & action history")
if len(f) == 0:
    st.info("No cases match your filters.")
else:
    case_id = st.selectbox("Select a case", f["case_id"])
    row = c[c["case_id"] == case_id].iloc[0]

    col1, col2, col3 = st.columns(3)
    col1.markdown(f"**Institution:** {row['institution_name']}  \n"
                  f"**AICTE ID:** {row['institution_id'] or '— not recorded —'}  \n"
                  f"**Region:** {row['region']} ({row['city']})")
    col2.markdown(f"**Bureau/Cell:** {row['bureau']}  \n"
                  f"**Officer:** {row['assigned_officer']}  \n"
                  f"**Category:** {row['category']}")
    col3.markdown(f"**Status:** {row['status']}  \n"
                  f"**SLA:** {row['sla_status']}  \n"
                  f"**Due date:** {row['due_date'].date()}")

    st.markdown("#### 🕒 Action history")
    history = a[a["case_id"] == case_id].sort_values("step")
    for _, h in history.iterrows():
        st.markdown(f"**{h['timestamp']}** · {h['bureau']} · {h['officer']}  \n"
                    f"➡️ {h['action']} — *{h['remarks']}*")