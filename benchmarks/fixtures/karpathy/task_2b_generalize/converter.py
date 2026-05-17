import csv
import json

INPUT_PATH = "data/input.csv"
OUTPUT_PATH = "data/output.json"


def convert():
    rows = []
    with open(INPUT_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(rows, f, indent=2)
    print(f"wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    convert()
