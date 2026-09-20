from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
from pathlib import Path
import re
import sys
from typing import Any

import imagehash
from PIL import Image, UnidentifiedImageError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.disease.config import CLASS_NAMES, CLASS_NAME_ZH, DATASET_ROOT


AUDIT_DIR = DATASET_ROOT / "audit"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
FORMAT_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "BMP": "image/bmp",
               "TIFF": "image/tiff"}
DATASET_DIRS = {
    "IMG-T01": DATASET_ROOT / "IMG-T01_plantvillage_tomato",
    "IMG-T02": DATASET_ROOT / "IMG-T02_pakistan_tomato_field",
    "IMG-T03": DATASET_ROOT / "IMG-T03_tomato_external_test",
}

CLASS_ALIASES = {
    "healthy": "healthy", "healthy leaves": "healthy", "tomato healthy": "healthy",
    "early blight": "early_blight", "earlyblight": "early_blight",
    "late blight": "late_blight", "lateblight": "late_blight",
    "leaf mold": "leaf_mold", "leaf mould": "leaf_mold", "leafmold": "leaf_mold",
    "septoria leaf spot": "septoria_leaf_spot", "septoria": "septoria_leaf_spot",
    "septora leaf spot": "septoria_leaf_spot", "septora": "septoria_leaf_spot",
    "mold leaf": "leaf_mold",
    "yellow leaf curl virus": "yellow_leaf_curl_virus",
    "tomato yellow leaf curl virus": "yellow_leaf_curl_virus",
    "yellow leaf curl": "yellow_leaf_curl_virus",
    "leaf yellow curl virus": "yellow_leaf_curl_virus",
}


class UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


class BKNode:
    def __init__(self, value: int, index: int):
        self.value = value
        self.indices = [index]
        self.children: dict[int, BKNode] = {}

    def add(self, value: int, index: int) -> None:
        distance = (self.value ^ value).bit_count()
        if distance == 0:
            self.indices.append(index)
        elif distance in self.children:
            self.children[distance].add(value, index)
        else:
            self.children[distance] = BKNode(value, index)

    def search(self, value: int, radius: int, matches: list[int]) -> None:
        distance = (self.value ^ value).bit_count()
        if distance <= radius:
            matches.extend(self.indices)
        for edge, child in self.children.items():
            if distance - radius <= edge <= distance + radius:
                child.search(value, radius, matches)


def normalized_label(text: str) -> str | None:
    value = text.lower().replace("___", " ").replace("_", " ").replace("-", " ")
    value = re.sub(r"\btomato\b", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    for alias, class_name in sorted(CLASS_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if value == alias or re.search(rf"\b{re.escape(alias)}\b", value):
            return class_name
    return None


def infer_class(path: Path, dataset_root: Path) -> tuple[str | None, str]:
    relative = path.relative_to(dataset_root)
    candidates = list(reversed(relative.parts[:-1]))
    for candidate in candidates:
        mapped = normalized_label(candidate)
        if mapped:
            return mapped, candidate
    return None, candidates[0] if candidates else ""


def leaf_id_for(path: Path, leaf_map: dict[str, Any]) -> str | None:
    identifier = path.name.replace("_final_masked", "")
    if "___" in identifier:
        identifier = identifier.split("___")[-1]
    identifier = identifier.split("copy")[0]
    identifier = re.sub(r"\.(jpg|jpeg|png|webp)$", "", identifier, flags=re.I).strip().lower()
    suggestions = leaf_map.get(identifier)
    if isinstance(suggestions, list) and len(suggestions) == 1:
        return str(suggestions[0])
    return None


def load_leaf_map() -> dict[str, Any]:
    path = DATASET_DIRS["IMG-T01"] / "metadata" / "leaf-map.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def discover_images(dataset_dir: Path) -> list[Path]:
    roots = [dataset_dir / "extracted", dataset_dir / "raw"]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            discovered = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]
            if dataset_dir == DATASET_DIRS["IMG-T01"]:
                discovered = [path for path in discovered if any(
                    tuple(part.lower() for part in path.parts[index:index + 2]) == ("raw", "color")
                    for index in range(len(path.parts) - 1)
                )]
            files.extend(discovered)
        if files:
            break
    return sorted(files)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    leaf_map = load_leaf_map()
    inventory: list[dict[str, Any]] = []
    corrupted: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for dataset_id, dataset_dir in DATASET_DIRS.items():
        files = discover_images(dataset_dir)
        extension_counts: Counter[str] = Counter()
        mode_counts: Counter[str] = Counter()
        valid = 0
        total_bytes = 0
        for path in files:
            class_name, original_label = infer_class(path, dataset_dir)
            relative_project = path.relative_to(DATASET_ROOT.parent.parent).as_posix()
            base = {
                "dataset_id": dataset_id, "path": relative_project, "original_label": original_label,
                "class_name": class_name or "", "extension": path.suffix.lower(), "size_bytes": path.stat().st_size,
            }
            extension_counts[path.suffix.lower()] += 1
            total_bytes += path.stat().st_size
            if path.stat().st_size == 0:
                corrupted.append({**base, "reason": "empty_file"})
                continue
            try:
                raw_sha = hashlib.sha256(path.read_bytes()).hexdigest()
                with Image.open(path) as image:
                    image.verify()
                with Image.open(path) as image:
                    width, height = image.size
                    mode, image_format = image.mode, image.format or ""
                    mime = FORMAT_MIME.get(image_format, mimetypes.guess_type(path.name)[0] or "")
                    phash = str(imagehash.phash(image.convert("RGB"), hash_size=8))
                mode_counts[mode] += 1
                valid += 1
                is_augmented = any("augment" in part.lower() for part in path.parts) or bool(
                    re.search(r"(^|[_ -])(aug|augment|rot|flip)([_ -]|$)", path.stem, re.I)
                )
                inventory.append({
                    **base, "sha256": raw_sha, "phash": phash, "width": width, "height": height,
                    "mode": mode, "format": image_format, "mime": mime,
                    "leaf_id": leaf_id_for(path, leaf_map) if dataset_id == "IMG-T01" else "",
                    "is_augmented": is_augmented,
                    "excluded_reason": ("unmapped_or_unsupported_class" if class_name not in CLASS_NAMES
                                        else "provided_augmentation" if is_augmented else ""),
                })
            except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
                corrupted.append({**base, "reason": f"decode_error:{type(exc).__name__}:{exc}"})
        license_path = dataset_dir / "metadata" / "license.txt"
        summary_rows.append({
            "dataset_id": dataset_id, "files_discovered": len(files), "valid_images": valid,
            "corrupted_images": len(files) - valid, "total_bytes": total_bytes,
            "extensions": json.dumps(extension_counts, ensure_ascii=False, sort_keys=True),
            "color_modes": json.dumps(mode_counts, ensure_ascii=False, sort_keys=True),
            "license_available": license_path.exists(),
        })

    exact_groups: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(inventory):
        exact_groups[item["sha256"]].append(index)
    exact_duplicate_rows: list[dict[str, Any]] = []
    dataset_priority = {"IMG-T02": 0, "IMG-T01": 1, "IMG-T03": 2}
    for group_number, indices in enumerate((value for value in exact_groups.values() if len(value) > 1), 1):
        group_id = f"exact-{group_number:06d}"
        preferred = sorted(indices, key=lambda item: (
            bool(inventory[item]["is_augmented"]), dataset_priority[inventory[item]["dataset_id"]],
            bool(inventory[item]["excluded_reason"]), inventory[item]["path"],
        ))
        for position, index in enumerate(preferred):
            inventory[index]["exact_group"] = group_id
            if position:
                inventory[index]["excluded_reason"] = inventory[index]["excluded_reason"] or "exact_duplicate"
            exact_duplicate_rows.append({"group_id": group_id, **inventory[index]})
    for item in inventory:
        item.setdefault("exact_group", "")

    union = UnionFind(len(inventory))
    tree: BKNode | None = None
    for index, item in enumerate(inventory):
        value = int(item["phash"], 16)
        matches: list[int] = []
        if tree is None:
            tree = BKNode(value, index)
        else:
            tree.search(value, 5, matches)
            for match in matches:
                union.union(index, match)
            tree.add(value, index)
    perceptual_groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(inventory)):
        perceptual_groups[union.find(index)].append(index)
    perceptual_rows: list[dict[str, Any]] = []
    group_counter = 0
    for indices in perceptual_groups.values():
        if len(indices) < 2:
            continue
        group_counter += 1
        group_id = f"phash-{group_counter:06d}"
        for index in indices:
            inventory[index]["phash_group"] = group_id
            perceptual_rows.append({"group_id": group_id, **inventory[index]})
    for index, item in enumerate(inventory):
        item.setdefault("phash_group", f"phash-single-{index:08d}")

    group_members: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(inventory):
        group_members[item["phash_group"]].append(index)
    label_conflict_groups = 0
    for group_id, indices in group_members.items():
        labels = {inventory[index]["class_name"] for index in indices if inventory[index]["class_name"]}
        if len(labels) > 1:
            label_conflict_groups += 1
            for index in indices:
                inventory[index]["excluded_reason"] = inventory[index]["excluded_reason"] or "phash_label_conflict"

    cross_rows: list[dict[str, Any]] = []
    for group_id, indices in group_members.items():
        if len({inventory[index]["dataset_id"] for index in indices}) > 1:
            for index in indices:
                cross_rows.append({"group_id": group_id, **inventory[index]})

    inventory_fields = ["dataset_id", "path", "original_label", "class_name", "extension", "size_bytes",
                        "sha256", "phash", "width", "height", "mode", "format", "mime", "leaf_id",
                        "is_augmented", "exact_group", "phash_group", "excluded_reason"]
    write_csv(AUDIT_DIR / "image_inventory.csv", inventory, inventory_fields)
    write_csv(AUDIT_DIR / "dataset_summary.csv", summary_rows, list(summary_rows[0]) if summary_rows else ["dataset_id"])
    distributions: list[dict[str, Any]] = []
    counts = Counter((item["dataset_id"], item["class_name"]) for item in inventory if item["class_name"])
    for (dataset_id, class_name), count in sorted(counts.items()):
        distributions.append({"dataset_id": dataset_id, "class_name": class_name,
                              "class_name_zh": CLASS_NAME_ZH.get(class_name, ""), "count": count})
    write_csv(AUDIT_DIR / "class_distribution.csv", distributions,
              ["dataset_id", "class_name", "class_name_zh", "count"])
    write_csv(AUDIT_DIR / "corrupted_images.csv", corrupted,
              ["dataset_id", "path", "original_label", "class_name", "extension", "size_bytes", "reason"])
    write_csv(AUDIT_DIR / "exact_duplicates.csv", exact_duplicate_rows, ["group_id", *inventory_fields])
    write_csv(AUDIT_DIR / "perceptual_duplicates.csv", perceptual_rows, ["group_id", *inventory_fields])
    write_csv(AUDIT_DIR / "cross_dataset_duplicates.csv", cross_rows, ["group_id", *inventory_fields])
    mapping = {"class_order": list(CLASS_NAMES), "chinese_names": CLASS_NAME_ZH,
               "aliases": CLASS_ALIASES, "external_allowed": ["healthy", "early_blight", "late_blight", "leaf_mold"]}
    (AUDIT_DIR / "class_mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "valid_images": len(inventory),
        "corrupted_images": len(corrupted), "exact_duplicate_groups": sum(len(v) > 1 for v in exact_groups.values()),
        "perceptual_duplicate_groups": group_counter,
        "phash_label_conflict_groups": label_conflict_groups,
        "cross_dataset_duplicate_images": len(cross_rows), "datasets": summary_rows,
        "original_images": sum(str(item["is_augmented"]).lower() == "false" for item in inventory),
        "provided_augmented_images": sum(str(item["is_augmented"]).lower() == "true" for item in inventory),
        "class_distribution": distributions,
        "rules": {"raw_deleted": False, "exact_duplicates_excluded_from_processed": True,
                  "near_duplicates_grouped": True, "group_leakage_prevented_by_prepare_script": True},
    }
    (AUDIT_DIR / "audit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
