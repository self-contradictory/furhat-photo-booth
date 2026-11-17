"""Export the sessions table from D1 to an SPSS .sav file (and a CSV copy).

Run from the repository root with the `hri` conda env:
    python scripts/export_spss.py                 # production database (--remote)
    python scripts/export_spss.py --local         # the local dev database
Output: analysis/data/sessions.sav and analysis/data/sessions.csv

Group photos are flagged by hand: list them in analysis/group_photos.csv
(one column `id`, one row per photo with more than one person). They get
group_photo = 1 and are kept in the file so the report can count them;
filter on group_photo = 0 for the analysis.
"""
import argparse
import json
import os
import subprocess

import pandas as pd
import pyreadstat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
OUT_DIR = os.path.join(ROOT, "analysis", "data")
GROUP_FILE = os.path.join(ROOT, "analysis", "group_photos.csv")
CONDITIONS = ["passive", "inviting", "complimenting", "playful"]


def fetch_rows(local):
    cmd = ["npx", "wrangler", "d1", "execute", "DB", "--json",
           "--local" if local else "--remote",
           "--command", "SELECT * FROM sessions ORDER BY captured_at"]
    out = subprocess.run(cmd, cwd=WEB, check=True, capture_output=True, text=True).stdout
    return json.loads(out)[0]["results"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--local", action="store_true", help="read the local dev database instead of production")
    args = parser.parse_args()

    with open(os.path.join(WEB, "src", "survey.json")) as f:
        survey = json.load(f)
    items = [i for s in survey["sections"] for i in s["items"]]

    rows = []
    for r in fetch_rows(args.local):
        if r["condition"] == "check":  # left over from a failed --check run
            continue
        answers = json.loads(r["answers"]) if r["answers"] else {}
        row = {
            "id": r["id"],
            "condition": CONDITIONS.index(r["condition"]) + 1 if r["condition"] in CONDITIONS else None,
            "captured_at": r["captured_at"] or "",
            "submitted": 1 if r["submitted_at"] else 0,
            "has_photo": 1 if r["photo_key"] else 0,
            "survey_version": r["survey_version"],
        }
        for item in items:
            row[item["id"]] = answers.get(item["id"], "" if item["type"] == "text" else None)
        rows.append(row)
    df = pd.DataFrame(rows)

    groups = set(pd.read_csv(GROUP_FILE)["id"]) if os.path.exists(GROUP_FILE) else set()
    df["group_photo"] = df["id"].isin(groups).astype(int)

    # Scale scores: the mean of each item group, after flipping reverse-coded items.
    scales = {}
    for item in items:
        if item["type"] == "scale" and item.get("group"):
            col = df[item["id"]].astype(float)
            if item.get("reverse"):
                col = item["min"] + item["max"] - col
            scales.setdefault(item["group"], []).append(col)
    for group, cols in scales.items():
        df[f"{group}_score"] = pd.concat(cols, axis=1).mean(axis=1, skipna=False)

    labels = {"condition": "Robot behaviour condition", "group_photo": "More than one person in the photo",
              "submitted": "Survey submitted", "has_photo": "Photo uploaded"}
    value_labels = {"condition": {i + 1: c for i, c in enumerate(CONDITIONS)},
                    "group_photo": {0: "single", 1: "group"}}
    for item in items:
        labels[item["id"]] = item.get("text") or f"{item['minLabel']} - {item['maxLabel']}"
        if item["type"] == "choice":
            value_labels[item["id"]] = {o["value"]: o["label"] for o in item["options"]}
        elif item["type"] == "scale":
            value_labels[item["id"]] = {item["min"]: item["minLabel"], item["max"]: item["maxLabel"]}
    for group in scales:
        labels[f"{group}_score"] = f"{group} scale mean"

    os.makedirs(OUT_DIR, exist_ok=True)
    df.to_csv(os.path.join(OUT_DIR, "sessions.csv"), index=False)
    pyreadstat.write_sav(df, os.path.join(OUT_DIR, "sessions.sav"),
                         column_labels=labels, variable_value_labels=value_labels)
    print(f"{len(df)} sessions ({int(df['submitted'].sum())} with surveys, "
          f"{int(df['group_photo'].sum())} group photos) -> {OUT_DIR}")


if __name__ == "__main__":
    main()
