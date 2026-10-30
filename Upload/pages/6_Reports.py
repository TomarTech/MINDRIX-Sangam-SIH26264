import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from config import TODAY
except ImportError:
    from config import TODAY
try:
    from overlap import find_overlaps     # A's engine (present on A's laptop)
except ImportError:
    find_overlaps = None

st.set_page_config(page_title="Reports & Analytics", page_icon="📈", layout="wide")


@st.cache_data
def load_data():
    c = pd.read_csv("data/complaints.csv",
                    parse_dates=["date_received", "due_date", "last_action_date"],
                    dtype={"institution_id": str})
    inst = pd.read_csv("data/institutions.csv", dtype={"institution_id": str})
    ov = find_overlaps(c, inst) if find_overlaps else None
    return c, inst, ov


c, inst, ov = load_data()

st.title("📈 Reports & Analytics")
st.caption("Bureau-wise, region-wise and institution-wise reports, ageing analysis, "
           "disposal performance and overlap reports, all downloadable")

# ---------- Report period ----------
period = st.date_input("Report period (by date of receipt)",
                       value=(c["date_received"].min().date(), TODAY.date()))
if len(period) != 2:
    st.info("Select both a start and an end date.")
    st.stop()
f = c[(c["date_received"].dt.date >= period[0]) & (c["date_received"].dt.date <= period[1])]

# Helper columns
f = f.assign(
    Active=f["status"] != "Disposed",
    Disposed=f["status"] == "Disposed",
    Overdue=(f["status"] != "Disposed") & (f["due_date"] < TODAY),
)
disposed = f[f["Disposed"]]
active = f[f["Active"]]


def summary(df, key):
    """Total / active / disposed / beyond-SLA / disposal rate for each value of `key`."""
    out = (df.groupby(key)
             .agg(Total=("case_id", "count"), Active=("Active", "sum"),
                  Disposed=("Disposed", "sum"), Beyond_SLA=("Overdue", "sum"))
             .reset_index())
    out["Disposal rate %"] = (out["Disposed"] / out["Total"] * 100).round(1)
    return out.rename(columns={"Beyond_SLA": "Beyond SLA"}).sort_values("Total", ascending=False)


def download(df, name, key):
    st.download_button(f"⬇️ Download {name} (CSV)", df.to_csv(index=False),
                       f"{name.replace(' ', '_').lower()}.csv", "text/csv", key=key)


# ---------- Headline numbers ----------
days_to_dispose = (disposed["last_action_date"] - disposed["date_received"]).dt.days
within_sla = (disposed["last_action_date"] <= disposed["due_date"]).mean() * 100 if len(disposed) else 0

k = st.columns(5)
k[0].metric("Cases in period", len(f))
k[1].metric("Disposal rate", f"{(len(disposed) / len(f) * 100 if len(f) else 0):.1f}%")
k[2].metric("Avg. days to dispose", f"{days_to_dispose.mean():.0f}" if len(disposed) else "—")
k[3].metric("Disposed within SLA", f"{within_sla:.0f}%")
k[4].metric("Active cases beyond SLA", int(f["Overdue"].sum()))

st.divider()

tabs = st.tabs(["🏢 Bureau-wise", "🗺️ Region-wise", "🏫 Institution-wise",
                "⏳ Ageing analysis", "📅 Monthly / Quarterly", "⚠️ Overlapping cases"])

# ---------- 1. Bureau-wise ----------
with tabs[0]:
    rep = summary(f, "bureau")
    st.plotly_chart(px.bar(rep, x="bureau", y=["Active", "Disposed"], barmode="stack",
                           title="Workload and disposal by Bureau/Cell"),
                    use_container_width=True)
    st.dataframe(rep, hide_index=True, use_container_width=True)
    download(rep, "Bureau-wise report", "d1")

# ---------- 2. Region-wise ----------
with tabs[1]:
    rep = summary(f, "region")
    st.plotly_chart(px.bar(rep, x="region", y="Total", color="Disposal rate %",
                           title="Complaints and disposal rate by AICTE region"),
                    use_container_width=True)
    st.dataframe(rep, hide_index=True, use_container_width=True)
    download(rep, "Region-wise report", "d2")

# ---------- 3. Institution-wise ----------
with tabs[2]:
    with_id = f[f["institution_id"].notna() & (f["institution_id"] != "")]
    rep = summary(with_id, "institution_id")
    rep.insert(1, "Institution", rep["institution_id"].map(dict(zip(inst["institution_id"],
                                                                      inst["name"]))))
    top = rep.head(15)
    st.plotly_chart(px.bar(top, x="Total", y="Institution", orientation="h",
                           title="Top 15 institutions by number of complaints")
                    .update_layout(yaxis={"categoryorder": "total ascending"}),
                    use_container_width=True)
    st.dataframe(rep, hide_index=True, use_container_width=True)
    st.caption("Based on cases with a recorded AICTE Permanent ID. Open the Institution "
               "Profile page for the full history including name-matched cases.")
    download(rep, "Institution-wise report", "d3")

# ---------- 4. Ageing analysis ----------
with tabs[3]:
    act = active.assign(age_days=(TODAY - active["date_received"]).dt.days)
    act["Age bucket"] = pd.cut(act["age_days"], bins=[-1, 15, 30, 60, 90, 10000],
                               labels=["0–15 days", "16–30 days", "31–60 days",
                                       "61–90 days", "90+ days"])
    heat = pd.crosstab(act["bureau"], act["Age bucket"])
    st.plotly_chart(px.imshow(heat, text_auto=True, color_continuous_scale="Reds",
                              title="Pending cases by age: where are cases stuck?"),
                    use_container_width=True)
    st.dataframe(heat, use_container_width=True)
    st.caption("Darker cells mean more pending cases. The '90+ days' column needs urgent attention.")
    download(heat.reset_index(), "Ageing analysis", "d4")

# ---------- 5. Monthly / Quarterly ----------
with tabs[4]:
    freq = st.radio("Group by", ["Monthly", "Quarterly"], horizontal=True)
    code = "M" if freq == "Monthly" else "Q"
    received = f.groupby(f["date_received"].dt.to_period(code).astype(str)).size()
    closed = disposed.groupby(disposed["last_action_date"].dt.to_period(code).astype(str)).size()
    perf = (pd.DataFrame({"Received": received, "Disposed": closed})
              .fillna(0).astype(int).rename_axis("Period").reset_index())
    st.plotly_chart(px.bar(perf, x="Period", y=["Received", "Disposed"], barmode="group",
                           title=f"{freq} performance: complaints received vs disposed"),
                    use_container_width=True)
    st.dataframe(perf, hide_index=True, use_container_width=True)
    download(perf, f"{freq} performance report", "d5")

# ---------- 6. Overlapping cases ----------
with tabs[5]:
    if ov is None:
        st.info("The overlap report appears when the overlap engine (overlap.py) is present.")
    elif ov.empty:
        st.success("No overlapping cases at present.")
    else:
        pairs = ov.assign(**{"Bureau pair": ov.apply(
            lambda r: " ↔ ".join(sorted([r["bureau_a"], r["bureau_b"]])), axis=1)})
        by_pair = pairs.groupby("Bureau pair").agg(
            Overlaps=("case_a", "count"),
            Institutions=("institution_id", "nunique")).reset_index()
        o1, o2 = st.columns(2)
        o1.metric("Institutions with overlapping cases", ov["institution_id"].nunique())
        o2.metric("Overlapping case pairs", len(ov))
        st.plotly_chart(px.bar(by_pair, x="Bureau pair", y="Overlaps",
                               title="Which Bureaus overlap most often?"),
                        use_container_width=True)
        st.dataframe(ov[["institution", "case_a", "bureau_a", "case_b", "bureau_b",
                         "confidence", "level"]], hide_index=True, use_container_width=True)
        download(ov, "Overlapping cases report", "d6")