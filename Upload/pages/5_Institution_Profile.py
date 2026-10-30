import pandas as pd
import plotly.express as px
import streamlit as st

# Works on both laptops: uses A's shared files if present, otherwise falls back
try:
    from config import TODAY
except ImportError:
    from config import TODAY
try:
    from overlap import resolve          # A's engine: links cases with missing IDs
except ImportError:
    resolve = None

st.set_page_config(page_title="Institution Profile", page_icon="🏫", layout="wide")


@st.cache_data
def load_data():
    inst = pd.read_csv("data/institutions.csv", dtype={"institution_id": str})
    c = pd.read_csv("data/complaints.csv", parse_dates=["date_received", "due_date"],
                    dtype={"institution_id": str})
    a = pd.read_csv("data/actions.csv")
    c["institution_id"] = c["institution_id"].fillna("")
    # Link every case to an institution (by ID, or by A's name-matching engine)
    c["linked_id"] = c["institution_id"]
    c["matched_by"] = "AICTE ID"
    if resolve is not None:
        for i, r in c[c["institution_id"] == ""].iterrows():
            rid, _, score, method = resolve(r["institution_name"], r["city"], inst)
            if rid and score >= 70:
                c.at[i, "linked_id"] = rid
                c.at[i, "matched_by"] = f"Name match ({method}, {score:.0f}%)"
    return inst, c, a


inst, c, a = load_data()

st.title("🏫 Institution 360° Profile")
st.caption("One institution, every complaint, every Bureau/Cell, one complete history")

# ---------- Pick an institution (most complaints first) ----------
counts = c.groupby("linked_id").size()
inst["cases"] = inst["institution_id"].map(counts).fillna(0).astype(int)
inst_sorted = inst.sort_values("cases", ascending=False)
label = {r.institution_id: f"{r.name}  ({r.institution_id}) — {r.cases} cases"
         for r in inst_sorted.itertuples()}
sel = st.selectbox("Search institution by name or AICTE Permanent ID",
                   inst_sorted["institution_id"].tolist(), format_func=lambda x: label[x])

p = inst.set_index("institution_id").loc[sel]
cases = c[c["linked_id"] == sel]
active = cases[cases["status"] != "Disposed"]
overdue = active[active["due_date"] < TODAY]

# ---------- Profile card ----------
with st.container(border=True):
    col1, col2 = st.columns(2)
    col1.markdown(f"### {p['name']}")
    col1.markdown(f"**AICTE Permanent ID:** {sel}  \n"
                  f"**Address:** {p.get('address', p['city'] + ', ' + p['state'])}")
    col2.markdown(f"**Type:** {p.get('institution_type', '—')}  \n"
                  f"**Established:** {p.get('established', '—')}  \n"
                  f"**City / State:** {p['city']}, {p['state']}  \n"
                  f"**AICTE Region:** {p['region']}")

# ---------- Key numbers ----------
k = st.columns(5)
k[0].metric("Total complaints", len(cases))
k[1].metric("Active", len(active))
k[2].metric("Disposed", (cases["status"] == "Disposed").sum())
k[3].metric("🔴 Beyond SLA", len(overdue))
k[4].metric("Bureaus with active cases", active["bureau"].nunique())

# ---------- Overlap warning ----------
if active["bureau"].nunique() > 1:
    st.error(f"⚠️ **Potential Overlapping Cases – Coordination Required.** This institution has "
             f"active cases in: **{', '.join(sorted(active['bureau'].unique()))}**")
elif len(active) > 0:
    st.success(f"✅ All active cases are handled by a single Bureau/Cell "
               f"({active['bureau'].iloc[0]}). No overlap.")

if cases.empty:
    st.info("No complaints recorded for this institution.")
    st.stop()

# ---------- Institution-wise case status ----------
st.subheader("📊 Case status by Bureau/Cell")
st.dataframe(pd.crosstab(cases["bureau"], cases["status"]), use_container_width=True)

# ---------- All cases ----------
st.subheader("📁 All complaints against this institution")
show = ["case_id", "date_received", "bureau", "category", "status", "assigned_officer",
        "last_action", "next_action", "due_date", "institution_name", "matched_by"]
st.dataframe(cases[show].sort_values("date_received", ascending=False),
             hide_index=True, use_container_width=True)
st.caption("'institution_name' shows how each Bureau recorded the name. "
           "'matched_by' shows how the system linked it to this institution.")

# ---------- Combined timeline ----------
st.subheader("🕒 Complete history across all Bureaus/Cells")
acts = a[a["case_id"].isin(cases["case_id"])].copy()
acts["when"] = pd.to_datetime(acts["timestamp"], format="mixed")
fig = px.scatter(acts, x="when", y="case_id", color="bureau",
                 hover_data=["action", "officer", "remarks"],
                 title="Every action on every case of this institution")
fig.update_traces(marker_size=12)
st.plotly_chart(fig, use_container_width=True)

for _, h in acts.sort_values("when", ascending=False).iterrows():
    st.markdown(f"**{h['timestamp']}** · `{h['case_id']}` · {h['bureau']} · {h['officer']}  \n"
                f"➡️ {h['action']} — *{h['remarks']}*")