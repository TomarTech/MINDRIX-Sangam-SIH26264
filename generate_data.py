"""
generate_data.py - creates realistic sample data for the SIH26264 prototype.
Run once:  python generate_data.py
Creates: data/institutions.csv, data/complaints.csv, data/actions.csv
"""
import os
import random
from datetime import datetime, timedelta

import pandas as pd
from faker import Faker

# Same seed = exactly the same data on both laptops
random.seed(42)
Faker.seed(42)
fake = Faker("en_IN")

TODAY = datetime(2026, 10, 25)
os.makedirs("data", exist_ok=True)

# ---------------- 1. Reference lists ----------------
CITIES = {  # city: (state, AICTE region)
    "Jaipur": ("Rajasthan", "Northern"), "Kota": ("Rajasthan", "Northern"),
    "New Delhi": ("Delhi", "Northern"), "Lucknow": ("Uttar Pradesh", "Northern"),
    "Chandigarh": ("Chandigarh", "North-West"), "Ludhiana": ("Punjab", "North-West"),
    "Bhopal": ("Madhya Pradesh", "Central"), "Indore": ("Madhya Pradesh", "Central"),
    "Kolkata": ("West Bengal", "Eastern"), "Bhubaneswar": ("Odisha", "Eastern"),
    "Mumbai": ("Maharashtra", "Western"), "Pune": ("Maharashtra", "Western"),
    "Ahmedabad": ("Gujarat", "Western"), "Hyderabad": ("Telangana", "South-Central"),
    "Vijayawada": ("Andhra Pradesh", "South-Central"), "Chennai": ("Tamil Nadu", "Southern"),
    "Coimbatore": ("Tamil Nadu", "Southern"), "Bengaluru": ("Karnataka", "South-West"),
    "Kochi": ("Kerala", "South-West"),
}
NAME_START = ["Shri Ram", "Maharishi Dayanand", "Sardar Patel", "Rajiv Gandhi",
              "Swami Vivekananda", "Global", "Sri Venkateswara", "Arya", "Poornima",
              "Lakshmi Narain", "Guru Nanak", "Dr. Ambedkar", "Vidya Bharati",
              "Sanjivani", "Kalinga", "Saraswati", "Jagannath", "Modern", "Apex", "Royal"]
NAME_TYPE = ["Institute of Technology", "College of Engineering",
             "Institute of Engineering and Technology", "Institute of Management",
             "Polytechnic College", "College of Pharmacy", "Engineering College",
             "Institute of Technology and Science"]
BUREAUS = ["PGRC", "RB", "Approval Bureau", "Academic Bureau", "Finance Bureau"]
PREFIX = {"PGRC": "PG", "RB": "RB", "Approval Bureau": "AB",
          "Academic Bureau": "AC", "Finance Bureau": "FB"}
CATEGORIES = {  # category: SLA (days allowed to dispose)
    "Fee refund / excess fee charged": 30,
    "Withholding of original certificates": 15,
    "Faculty shortage / unqualified faculty": 45,
    "Inadequate infrastructure / labs": 60,
    "Running course without AICTE approval": 30,
    "Admission irregularities": 30,
    "Scholarship / stipend not paid": 30,
    "Harassment / ragging": 15,
}
STATUSES = ["Received", "Under Process", "Transferred", "Escalated", "Disposed"]
NEXT_ACTION = {"Received": "Issue notice to institution",
               "Under Process": "Examine institution's reply and decide",
               "Transferred": "Examine case in new Bureau/Cell",
               "Escalated": "Decision by senior officer pending",
               "Disposed": "-"}
OFFICERS = {b: [fake.name() for _ in range(4)] for b in BUREAUS}

# ---------------- 2. Institutions ----------------
institutions, used = [], set()
while len(institutions) < 250:
    city = random.choice(list(CITIES))
    name = f"{random.choice(NAME_START)} {random.choice(NAME_TYPE)}, {city}"
    if name in used:
        continue
    used.add(name)
    state, region = CITIES[city]
    institutions.append({"institution_id": f"1-{random.randint(1000000000, 9999999999)}",
                         "name": name, "city": city, "state": state, "region": region})

# ---------------- 3. Name variants (how different clerks write the same name) ----------------
SHORT = {"Institute": "Inst.", "Technology": "Tech.", "Engineering": "Engg.",
         "College": "Coll.", "Management": "Mgmt.", "Science": "Sci.",
         "and": "&", "Pharmacy": "Pharm."}
SPELL = {"Shri": "Shree", "Sri": "Shri", "Vivekananda": "Vivekanand",
         "Saraswati": "Saraswathi", "Jagannath": "Jagnnath", "Narain": "Narayan"}

def add_typo(text):
    words = text.split()
    i = max(range(len(words)), key=lambda k: len(words[k]))  # longest word
    w = words[i]
    p = random.randint(1, len(w) - 2)
    words[i] = w[:p] + w[p + 1:]  # drop one letter
    return " ".join(words)

def make_variant(full_name):
    main, city = full_name.split(", ")
    style = random.choice(["short", "acronym", "spelling", "typo", "upper"])
    if style == "short":
        new = " ".join(SHORT.get(w, w) for w in main.split())
    elif style == "acronym":
        new = "".join(w[0] for w in main.split()
                      if w.lower() not in ("of", "and", "the") and w[0].isalpha()).upper()
    elif style == "spelling":
        new = " ".join(SPELL.get(w, w) for w in main.split())
    elif style == "typo":
        new = add_typo(main)
    else:
        new = main.upper()
    if new == main:  # nothing changed -> add a typo instead
        new = add_typo(main)
    return f"{new}, {city}"

# ---------------- 4. Complaints + action history ----------------
complaints, actions = [], []
case_counter = 0

def add_case(inst, bureau, use_variant, hide_id, force_active=False):
    global case_counter
    case_counter += 1
    case_id = f"{PREFIX[bureau]}-2026-{case_counter:04d}"
    category = random.choice(list(CATEGORIES))
    sla = CATEGORIES[category]
    if force_active:
        received = TODAY - timedelta(days=random.randint(5, 60))
        status = random.choice(["Received", "Under Process"])
    else:
        received = TODAY - timedelta(days=random.randint(1, 300))
        status = random.choices(STATUSES, weights=[10, 30, 8, 7, 45])[0]
    officer = random.choice(OFFICERS[bureau])

    steps = []
    if status == "Transferred":
        other = random.choice([b for b in BUREAUS if b != bureau])
        steps.append((f"Received on transfer from {other}", "Matter falls under this Bureau"))
    else:
        steps.append(("Complaint received and registered", "Complaint diarised"))
    if status != "Received":
        steps.append(("Notice issued to institution", "Reply sought within 15 days"))
        steps.append(("Reply received from institution", "Under examination"))
    if status == "Escalated":
        steps.append(("Escalated to senior officer", "Delay beyond prescribed timeline"))
    if status == "Disposed":
        steps.append(("Complaint disposed", "Matter resolved, complainant informed"))

    t = received
    for n, (action, remark) in enumerate(steps, start=1):
        if n > 1:
            t = min(t + timedelta(days=random.randint(2, 12)), TODAY)
        actions.append({"case_id": case_id, "step": n, "timestamp": t.strftime("%Y-%m-%d"),
                        "bureau": bureau, "officer": officer,
                        "action": action, "remarks": remark})

    complaints.append({
        "case_id": case_id,
        "date_received": received.strftime("%Y-%m-%d"),
        "bureau": bureau,
        "category": category,
        "status": status,
        "assigned_officer": officer,
        "institution_id": "" if hide_id else inst["institution_id"],
        "institution_name": make_variant(inst["name"]) if use_variant else inst["name"],
        "city": inst["city"], "state": inst["state"], "region": inst["region"],
        "sla_days": sla,
        "due_date": (received + timedelta(days=sla)).strftime("%Y-%m-%d"),
        "last_action": steps[-1][0],
        "last_action_date": t.strftime("%Y-%m-%d"),
        "next_action": NEXT_ACTION[status],
        "true_institution_id": inst["institution_id"],  # hidden answer key, for testing only
    })

# Normal complaints: each institution's complaints go to its usual ("home") Bureau
home = {i["institution_id"]: random.choices(BUREAUS, weights=[50, 20, 15, 10, 5])[0]
        for i in institutions}
for _ in range(700):
    inst = random.choice(institutions)
    add_case(inst, home[inst["institution_id"]],
             use_variant=random.random() < 0.15, hide_id=random.random() < 0.10)

# PLANTED OVERLAPS: same institution, active in two Bureaus, written differently
for inst in random.sample(institutions, 25):
    b1 = home[inst["institution_id"]]
    b2 = "PGRC" if b1 == "RB" else "RB"
    add_case(inst, b1, use_variant=False, hide_id=False, force_active=True)
    add_case(inst, b2, use_variant=True, hide_id=random.random() < 0.6, force_active=True)

# ---------------- 5. Save ----------------
pd.DataFrame(institutions).to_csv("data/institutions.csv", index=False)
pd.DataFrame(complaints).to_csv("data/complaints.csv", index=False)
pd.DataFrame(actions).to_csv("data/actions.csv", index=False)
print(f"Done! {len(institutions)} institutions, {len(complaints)} complaints, "
      f"{len(actions)} action records saved in the 'data' folder.")