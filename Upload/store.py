"""
store.py - every write to the data files goes through here.
After each save, st.cache_data.clear() makes every page show the new data instantly.
"""
import os
from datetime import datetime

import pandas as pd
import streamlit as st

DATA = "data"
DOCS = os.path.join(DATA, "documents")
LINKS_FILE = os.path.join(DATA, "links.csv")


def add_action(case_id, action, remarks, officer, new_status=None, new_bureau=None,
               assign_to=None, next_action=None, document=""):
    """Add one action to a case's history and update the case itself."""
    c = pd.read_csv(f"{DATA}/complaints.csv", dtype={"institution_id": str})
    a = pd.read_csv(f"{DATA}/actions.csv")
    now = datetime.now()

    i = c.index[c["case_id"] == case_id][0]
    bureau = new_bureau or c.at[i, "bureau"]
    step = int(a.loc[a["case_id"] == case_id, "step"].max()) + 1 \
        if (a["case_id"] == case_id).any() else 1

    a = pd.concat([a, pd.DataFrame([{
        "case_id": case_id, "step": step, "timestamp": now.strftime("%Y-%m-%d %H:%M"),
        "bureau": bureau, "officer": officer, "action": action,
        "remarks": remarks, "document": document,
    }])], ignore_index=True)

    if new_status:
        c.at[i, "status"] = new_status
    if new_bureau:
        c.at[i, "bureau"] = new_bureau
    if assign_to:
        c.at[i, "assigned_officer"] = assign_to
    if next_action is not None:
        c.at[i, "next_action"] = next_action
    c.at[i, "last_action"] = action
    c.at[i, "last_action_date"] = now.strftime("%Y-%m-%d")

    c.to_csv(f"{DATA}/complaints.csv", index=False)
    a.to_csv(f"{DATA}/actions.csv", index=False)
    st.cache_data.clear()   # every page reloads fresh data


def save_document(case_id, uploaded_file):
    """Save an uploaded file to data/documents and return its stored name."""
    os.makedirs(DOCS, exist_ok=True)
    name = f"{case_id}_{uploaded_file.name}"
    with open(os.path.join(DOCS, name), "wb") as f:
        f.write(uploaded_file.getbuffer())
    return name


def load_links():
    if os.path.exists(LINKS_FILE):
        return pd.read_csv(LINKS_FILE, dtype=str)
    return pd.DataFrame(columns=["institution_id", "case_ids", "linked_by", "linked_on", "note"])


def link_cases(institution_id, case_ids, linked_by, note):
    """Permanently link related cases and record it in each case's history."""
    links = load_links()
    links = pd.concat([links, pd.DataFrame([{
        "institution_id": institution_id, "case_ids": "; ".join(case_ids),
        "linked_by": linked_by, "linked_on": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note": note,
    }])], ignore_index=True)
    links.to_csv(LINKS_FILE, index=False)
    for cid in case_ids:
        others = ", ".join(x for x in case_ids if x != cid)
        add_action(cid, f"Linked with {others} for cross-Bureau coordination", note, linked_by)

PREFIX = {"PGRC": "PG", "RB": "RB", "Approval Bureau": "AB",
          "Academic Bureau": "AC", "Finance Bureau": "FB"}


def add_complaint(rec):
    """Register a new complaint. Returns its new case ID."""
    c = pd.read_csv(f"{DATA}/complaints.csv", dtype={"institution_id": str})
    a = pd.read_csv(f"{DATA}/actions.csv")
    now = datetime.now()
    next_no = c["case_id"].str.split("-").str[-1].astype(int).max() + 1
    case_id = f"{PREFIX.get(rec['bureau'], 'XX')}-{now.year}-{next_no:04d}"

    row = {col: "" for col in c.columns}
    row.update(rec)
    row.update({
        "case_id": case_id,
        "date_received": now.strftime("%Y-%m-%d"),
        "status": "Received",
        "due_date": (now + pd.Timedelta(days=int(rec["sla_days"]))).strftime("%Y-%m-%d"),
        "last_action": "Complaint received and registered",
        "last_action_date": now.strftime("%Y-%m-%d"),
        "next_action": "Issue notice to institution",
    })
    c = pd.concat([c, pd.DataFrame([row])], ignore_index=True)
    a = pd.concat([a, pd.DataFrame([{
        "case_id": case_id, "step": 1, "timestamp": now.strftime("%Y-%m-%d %H:%M"),
        "bureau": rec["bureau"], "officer": rec["assigned_officer"],
        "action": "Complaint received and registered", "remarks": "Registered via dashboard",
        "document": "",
    }])], ignore_index=True)
    c.to_csv(f"{DATA}/complaints.csv", index=False)
    a.to_csv(f"{DATA}/actions.csv", index=False)
    st.cache_data.clear()
    return case_id
