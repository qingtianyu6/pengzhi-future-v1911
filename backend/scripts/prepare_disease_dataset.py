from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.disease.config import CLASS_CONFIG_PATH, CLASS_NAMES, DATASET_ROOT, PROCESSED_DIR, RANDOM_SEED


INVENTORY_PATH = DATASET_ROOT / "audit" / "image_inventory.csv"
FIELDS = ["path", "dataset_id", "class_name", "group_id", "source_split", "stage", "sha256"]


def read_rows() -> list[dict[str, str]]:
    with INVENTORY_PATH.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def group_key(row: dict[str, str]) -> str:
    if row["dataset_id"] == "IMG-T01" and row.get("leaf_id"):
        return f"IMG-T01:leaf:{row['leaf_id']}"
    return f"{row['dataset_id']}:{row['phash_group']}"


def write_manifest(name: str, rows: list[dict[str, Any]]) -> str:
    path = PROCESSED_DIR / name
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def choose_groups(groups: list[list[dict[str, str]]], maximum: int, rng: random.Random) -> list[dict[str, str]]:
    shuffled = sorted(groups, key=lambda group: group_key(group[0]))
    rng.shuffle(shuffled)
    selected: list[dict[str, str]] = []
    for group in shuffled:
        if len(selected) >= maximum:
            break
        room = maximum - len(selected)
        selected.extend(sorted(group, key=lambda row: row["path"])[:room])
    return selected


def split_groups(groups: list[list[dict[str, str]]], rng: random.Random) -> dict[str, list[dict[str, str]]]:
    groups = sorted(groups, key=lambda group: group_key(group[0]))
    rng.shuffle(groups)
    total = sum(len(group) for group in groups)
    targets = {"train": total * 0.70, "validation": total * 0.15, "internal_test": total * 0.15}
    result: dict[str, list[dict[str, str]]] = {key: [] for key in targets}
    counts = Counter()
    for group in sorted(groups, key=lambda item: (-len(item), group_key(item[0]))):
        split = max(targets, key=lambda key: targets[key] - counts[key])
        result[split].extend(sorted(group, key=lambda row: row["path"]))
        counts[split] += len(group)
    return result


def main() -> int:
    if not INVENTORY_PATH.exists():
        raise FileNotFoundError("Run audit_disease_datasets.py first")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    rows = [row for row in read_rows() if not row["excluded_reason"] and row["class_name"] in CLASS_NAMES]
    grouped: dict[tuple[str, str], dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[(row["dataset_id"], row["class_name"])][group_key(row)].append(row)

    rng = random.Random(RANDOM_SEED)
    train: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    internal_test: list[dict[str, Any]] = []
    external_test: list[dict[str, Any]] = []
    for class_name in CLASS_NAMES:
        pv_rows = choose_groups(list(grouped[("IMG-T01", class_name)].values()), 1000, rng)
        train.extend({**row, "group_id": group_key(row), "source_split": "pretrain",
                      "stage": "plantvillage_pretrain"} for row in pv_rows)
        splits = split_groups(list(grouped[("IMG-T02", class_name)].values()), rng)
        train.extend({**row, "group_id": group_key(row), "source_split": "train",
                      "stage": "field_fine_tune"} for row in splits["train"])
        validation.extend({**row, "group_id": group_key(row), "source_split": "validation",
                           "stage": "field_validation"} for row in splits["validation"])
        internal_test.extend({**row, "group_id": group_key(row), "source_split": "internal_test",
                              "stage": "field_internal_test"} for row in splits["internal_test"])

    for class_name in ("healthy", "early_blight", "late_blight", "leaf_mold"):
        for group in grouped[("IMG-T03", class_name)].values():
            external_test.extend({**row, "group_id": group_key(row), "source_split": "external_test",
                                  "stage": "independent_external_test"} for row in group)

    manifests = {
        "train_manifest.csv": train, "validation_manifest.csv": validation,
        "internal_test_manifest.csv": internal_test, "external_test_manifest.csv": external_test,
    }
    hashes = {name: write_manifest(name, sorted(items, key=lambda row: (row["stage"], row["class_name"], row["path"])))
              for name, items in manifests.items()}
    class_config = json.loads(CLASS_CONFIG_PATH.read_text(encoding="utf-8"))
    (PROCESSED_DIR / "class_names.json").write_text(json.dumps(class_config, ensure_ascii=False, indent=2), encoding="utf-8")
    group_sets = {
        split: {row["group_id"] for row in items if row["dataset_id"] == "IMG-T02"}
        for split, items in (("train", train), ("validation", validation), ("internal_test", internal_test))
    }
    leakage = sorted((group_sets["train"] & group_sets["validation"]) |
                     (group_sets["train"] & group_sets["internal_test"]) |
                     (group_sets["validation"] & group_sets["internal_test"]))
    summary = {
        "random_seed": RANDOM_SEED, "class_order": list(CLASS_NAMES), "manifest_sha256": hashes,
        "counts": {name.removesuffix("_manifest.csv"): len(items) for name, items in manifests.items()},
        "by_dataset_class_split": {
            f"{dataset}:{class_name}:{split}": count
            for (dataset, class_name, split), count in sorted(Counter(
                (row["dataset_id"], row["class_name"], row["source_split"])
                for items in manifests.values() for row in items
            ).items())
        },
        "group_leakage": leakage, "external_used_for_selection": False,
    }
    (PROCESSED_DIR / "split_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if leakage else 0


if __name__ == "__main__":
    raise SystemExit(main())
