import pandas as pd
from overlap import find_overlaps

pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 45)

df = pd.read_csv("data/complaints.csv", dtype={"institution_id": str})
inst = pd.read_csv("data/institutions.csv", dtype={"institution_id": str})
found = find_overlaps(df, inst)

print(found[["case_a", "bureau_a", "name_a", "case_b", "bureau_b", "name_b",
             "confidence"]].to_string())

# ---- Accuracy check using the hidden answer key (true_institution_id) ----
true_id = dict(zip(df["case_id"], df["true_institution_id"]))

# All REAL overlaps: active cases, same true institution, different Bureaus
active = df[df["status"] != "Disposed"]
real_pairs = set()
for _, g in active.groupby("true_institution_id"):
    cases = g.to_dict("records")
    for i in range(len(cases)):
        for j in range(i + 1, len(cases)):
            if cases[i]["bureau"] != cases[j]["bureau"]:
                real_pairs.add(tuple(sorted([cases[i]["case_id"], cases[j]["case_id"]])))

found_pairs = {tuple(sorted([r.case_a, r.case_b])) for r in found.itertuples()}
caught = real_pairs & found_pairs
false_alarms = [p for p in found_pairs if true_id[p[0]] != true_id[p[1]]]

print("\n========== ENGINE ACCURACY ==========")
print(f"Real overlaps hidden in data : {len(real_pairs)}")
print(f"Caught by our engine         : {len(caught)}")
print(f"Missed                       : {len(real_pairs - found_pairs)}")
print(f"False alarms                 : {len(false_alarms)}")
for p in real_pairs - found_pairs:
    names = df.set_index("case_id").loc[list(p), "institution_name"].tolist()
    print("  MISSED:", p, names)