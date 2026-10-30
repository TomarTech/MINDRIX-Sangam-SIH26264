"""
enrich_data.py - adds missing details to the EXISTING data (run once).
Adds: institution address/type/year, complainant details, complaint descriptions,
and 10 planted duplicate complaints (same complainant, same Bureau, reworded).
Does NOT change any existing values, so the overlap test results stay the same.
"""
import random

import pandas as pd
from faker import Faker

rng = random.Random(7)
fake = Faker("en_IN")
fake.seed_instance(7)
DATA_DATE = pd.Timestamp("2026-10-25")   # the date the original data was generated for

inst = pd.read_csv("data/institutions.csv", dtype=str)
c = pd.read_csv("data/complaints.csv", dtype={"institution_id": str})
a = pd.read_csv("data/actions.csv")

if "description" in c.columns:
    print("Data is already enriched - nothing to do.")
    raise SystemExit

# ---------------- 1. Institution details ----------------
def institution_type(name):
    n = name.lower()
    if "pharmacy" in n:
        return "Pharmacy"
    if "management" in n:
        return "Management"
    if "polytechnic" in n:
        return "Polytechnic (Diploma)"
    return "Engineering & Technology"

inst["institution_type"] = inst["name"].apply(institution_type)
inst["address"] = [f"{fake.building_number()}, {fake.street_name()}, {city}, {state} - "
                   f"{rng.randint(110001, 799999)}"
                   for city, state in zip(inst["city"], inst["state"])]
inst["established"] = [rng.randint(1985, 2018) for _ in range(len(inst))]

# ---------------- 2. Complainant + description ----------------
TEMPLATES = {
    "Fee refund / excess fee charged": [
        "I cancelled my admission at {i} but the fee has not been refunded even after many requests.",
        "{i} is charging fees higher than the approved fee structure and refusing to give receipts.",
    ],
    "Withholding of original certificates": [
        "{i} is not returning my original 10th and 12th certificates and is demanding full course fee.",
        "My original documents are being held by {i}; I need them urgently for another admission.",
    ],
    "Faculty shortage / unqualified faculty": [
        "Many subjects at {i} have no regular teachers; classes are taken by unqualified staff.",
        "{i} does not have the required number of qualified faculty as per AICTE norms.",
    ],
    "Inadequate infrastructure / labs": [
        "Laboratories at {i} lack basic equipment and practicals are not being conducted.",
        "{i} has no proper library, labs or classrooms as promised during admission.",
    ],
    "Running course without AICTE approval": [
        "{i} is running a course that does not appear in the AICTE approved list.",
        "I suspect {i} admitted students to a programme without valid AICTE approval.",
    ],
    "Admission irregularities": [
        "{i} gave admission to students outside the merit list and ignored the counselling process.",
        "Seats at {i} were allotted against capitation money instead of merit.",
    ],
    "Scholarship / stipend not paid": [
        "My scholarship amount for this year has not been credited by {i}.",
        "{i} has not released the stipend for months despite approval.",
    ],
    "Harassment / ragging": [
        "Junior students at {i} are facing ragging in the hostel and no action is being taken.",
        "I am facing harassment at {i} and the anti-ragging committee is not responding.",
    ],
}
COMPLAINANT_TYPES = ["Student", "Parent", "Faculty member", "Other stakeholder"]

c["complainant_name"] = [fake.name() for _ in range(len(c))]
c["complainant_type"] = rng.choices(COMPLAINANT_TYPES, weights=[60, 20, 15, 5], k=len(c))
c["description"] = [rng.choice(TEMPLATES[cat]).format(i=name)
                    for cat, name in zip(c["category"], c["institution_name"])]
c["true_duplicate_of"] = ""   # hidden answer key for duplicate detection

# ---------------- 3. Planted duplicates (same Bureau) ----------------
PREFIX = {"PGRC": "PG", "RB": "RB", "Approval Bureau": "AB",
          "Academic Bureau": "AC", "Finance Bureau": "FB"}
next_no = c["case_id"].str.split("-").str[-1].astype(int).max() + 1

new_cases, new_actions = [], []
for _, orig in c[c["status"] != "Disposed"].sample(10, random_state=7).iterrows():
    received = min(pd.Timestamp(orig["date_received"]) + pd.Timedelta(days=rng.randint(3, 20)),
                   DATA_DATE)
    other_text = [t for t in TEMPLATES[orig["category"]]
                  if t.format(i=orig["institution_name"]) != orig["description"]]
    dup = orig.copy()
    dup["case_id"] = f"{PREFIX[orig['bureau']]}-2026-{next_no:04d}"
    dup["date_received"] = received.strftime("%Y-%m-%d")
    dup["due_date"] = (received + pd.Timedelta(days=int(orig["sla_days"]))).strftime("%Y-%m-%d")
    dup["status"] = "Received"
    dup["last_action"] = "Complaint received and registered"
    dup["last_action_date"] = dup["date_received"]
    dup["next_action"] = "Issue notice to institution"
    dup["description"] = (other_text[0] if other_text else orig["description"]).format(
        i=orig["institution_name"]) + " Filing again as no response was received."
    dup["true_duplicate_of"] = orig["case_id"]
    new_cases.append(dup)
    new_actions.append({"case_id": dup["case_id"], "step": 1, "timestamp": dup["date_received"],
                        "bureau": orig["bureau"], "officer": orig["assigned_officer"],
                        "action": "Complaint received and registered",
                        "remarks": "Complaint diarised"})
    next_no += 1

c = pd.concat([c, pd.DataFrame(new_cases)], ignore_index=True)
a = pd.concat([a, pd.DataFrame(new_actions)], ignore_index=True)

# ---------------- 4. Save ----------------
inst.to_csv("data/institutions.csv", index=False)
c.to_csv("data/complaints.csv", index=False)
a.to_csv("data/actions.csv", index=False)
print(f"Enriched! {len(inst)} institutions now have address/type; "
      f"{len(c)} complaints now have complainant + description "
      f"(including {len(new_cases)} planted duplicates).")