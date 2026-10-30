import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="AICTE Complaint Monitor", page_icon="🏛️", layout="wide")

from config import TODAY

@st.cache_data
def load_data():
    df = pd.read_csv("data/complaints.csv", parse_dates=["date_received", "due_date"])
    return df

c = load_data()
active = c[c["status"] != "Disposed"]
overdue = active[active["due_date"] < TODAY]

# ---------- Header ----------
st.title("🏛️ AICTE Complaint Tracker - Team MINDRIX")
st.caption("Single source of truth for institution-related complaints across RB, PGRC "
           "and other Bureaus/Cells")

# ---------- KPI cards ----------
k = st.columns(6)
k[0].metric("Total cases", len(c))
k[1].metric("Pending (not started)", (c["status"] == "Received").sum())
k[2].metric("Under process", (c["status"] == "Under Process").sum())
k[3].metric("Transferred / Escalated", c["status"].isin(["Transferred", "Escalated"]).sum())
k[4].metric("Disposed", (c["status"] == "Disposed").sum())
k[5].metric("⚠️ Beyond SLA", len(overdue))

st.divider()

# ---------- Charts row 1 ----------
left, right = st.columns(2)

workload = active.groupby(["bureau", "status"]).size().reset_index(name="cases")
fig1 = px.bar(workload, x="bureau", y="cases", color="status",
              title="Active workload by Bureau/Cell")
left.plotly_chart(fig1, use_container_width=True)

fig2 = px.pie(c, names="status", hole=0, title="All cases by status")
right.plotly_chart(fig2, use_container_width=True)

# ---------- Charts row 2 ----------
left2, right2 = st.columns(2)

region = c.groupby("region").size().reset_index(name="cases")
fig3 = px.bar(region, x="region", y="cases", title="Region-wise complaints")
left2.plotly_chart(fig3, use_container_width=True)

monthly = (c.groupby(c["date_received"].dt.to_period("M").astype(str))
             .size().reset_index(name="cases"))
fig4 = px.line(monthly, x="date_received", y="cases", markers=True,
               title="Complaints received per month")
right2.plotly_chart(fig4, use_container_width=True)
