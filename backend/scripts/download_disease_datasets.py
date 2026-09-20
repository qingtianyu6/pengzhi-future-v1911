from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile


PROJECT_DIR = Path(__file__).resolve().parents[2]
ROOT = PROJECT_DIR / "datasets" / "disease_images"
USER_AGENT = "PengzhiFuture-DiseaseDataset/1.0 (+public dataset downloader)"
CHUNK_SIZE = 1024 * 1024

DATASETS = {
    "IMG-T01": {
        "directory": "IMG-T01_plantvillage_tomato",
        "name": "PlantVillage tomato subset",
        "page": "https://huggingface.co/datasets/mohanty/PlantVillage",
        "doi": "10.3389/fpls.2016.01419",
        "license": "CC BY-SA 3.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/3.0/",
        "role": "controlled_background_pretraining",
    },
    "IMG-T02": {
        "directory": "IMG-T02_pakistan_tomato_field",
        "name": "Tomato Leaf Disease Classification Dataset in Pakistan",
        "page": "https://data.mendeley.com/datasets/3mbnb82mxd/2",
        "doi": "10.17632/3mbnb82mxd.2",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "role": "field_fine_tuning_validation_internal_test",
    },
    "IMG-T03": {
        "directory": "IMG-T03_tomato_external_test",
        "name": "Tomato leaf diseases",
        "page": "https://data.mendeley.com/datasets/93h9p62kg4/1",
        "doi": "10.17632/93h9p62kg4.1",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "role": "independent_external_test_four_shared_classes",
    },
}

PV_BASE = "https://huggingface.co/datasets/mohanty/PlantVillage/resolve/main"
PV_FILES = {
    "data.zip": f"{PV_BASE}/data.zip",
    "leaf-map.json": f"{PV_BASE}/leaf_grouping/leaf-map.json",
    "color_train.txt": f"{PV_BASE}/splits/color_train.txt",
    "color_test.txt": f"{PV_BASE}/splits/color_test.txt",
}
PV_CLASS_DIRS = {
    "Tomato___healthy",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
}
EXTERNAL_FOLDERS = {"Healthy", "Early Blight", "Late Blight", "Leaf Mold"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_json(url: str, accept: str = "application/json") -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path, expected_size: int | None = None,
                  expected_sha256: str | None = None) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        size_ok = expected_size is None or destination.stat().st_size == expected_size
        checksum = sha256_file(destination) if size_ok else None
        hash_ok = expected_sha256 is None or checksum == expected_sha256
        if size_ok and hash_ok:
            return {"status": "skipped_verified", "path": str(destination), "size": destination.stat().st_size,
                    "sha256": checksum or sha256_file(destination), "url": url}

    partial = destination.with_suffix(destination.suffix + ".part")
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": USER_AGENT}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=120) as response:
            if offset and getattr(response, "status", 200) != 206:
                partial.unlink(missing_ok=True)
                offset = 0
            mode = "ab" if offset else "wb"
            with partial.open(mode) as output:
                shutil.copyfileobj(response, output, CHUNK_SIZE)
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"status": "failed", "path": str(destination), "url": url,
                "http_status": getattr(exc, "code", None), "error": str(exc)}

    size = partial.stat().st_size
    checksum = sha256_file(partial)
    if expected_size is not None and size != expected_size:
        return {"status": "failed", "path": str(destination), "url": url, "size": size,
                "error": f"size mismatch: expected {expected_size}, got {size}"}
    if expected_sha256 and checksum != expected_sha256:
        return {"status": "failed", "path": str(destination), "url": url, "size": size,
                "sha256": checksum, "error": "SHA256 mismatch"}
    partial.replace(destination)
    return {"status": "downloaded", "path": str(destination), "url": url, "size": size,
            "sha256": checksum}


def safe_member_path(root: Path, member: str) -> Path:
    pure = PurePosixPath(member.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"unsafe archive member: {member}")
    target = (root / Path(*pure.parts)).resolve()
    if root.resolve() not in target.parents and target != root.resolve():
        raise ValueError(f"archive member escapes destination: {member}")
    return target


def extract_plantvillage(archive: Path, destination: Path) -> dict[str, Any]:
    extracted = skipped = 0
    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            parts = PurePosixPath(member.filename.replace("\\", "/")).parts
            is_color = any(parts[index:index + 2] == ("raw", "color") for index in range(len(parts) - 1))
            if not is_color or not any(class_dir in parts for class_dir in PV_CLASS_DIRS):
                continue
            target = safe_member_path(destination, member.filename)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if target.exists() and target.stat().st_size == member.file_size:
                skipped += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, CHUNK_SIZE)
            extracted += 1
    return {"status": "completed", "extracted": extracted, "skipped": skipped}


def mendeley_files(dataset_id: str, version: int, folder_id: str = "root") -> list[dict[str, Any]]:
    url = (f"https://data.mendeley.com/public-api/datasets/{dataset_id}/files"
           f"?folder_id={folder_id}&version={version}")
    return request_json(url, "application/vnd.mendeley-public-dataset.1+json")


def mendeley_folders(dataset_id: str, version: int) -> list[dict[str, Any]]:
    return request_json(f"https://data.mendeley.com/public-api/datasets/{dataset_id}/folders/{version}")


def initialize_metadata(dataset_key: str) -> tuple[Path, Path, Path]:
    config = DATASETS[dataset_key]
    dataset_dir = ROOT / config["directory"]
    raw_dir = dataset_dir / "raw"
    extracted_dir = dataset_dir / "extracted"
    metadata_dir = dataset_dir / "metadata"
    raw_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    source = {"dataset_id": dataset_key, **config, "retrieved_at": utc_now()}
    (metadata_dir / "source.json").write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
    (metadata_dir / "license.txt").write_text(
        f"{config['license']}\n{config['license_url']}\nSource: {config['page']}\n",
        encoding="utf-8",
    )
    return raw_dir, extracted_dir, metadata_dir


def save_report(metadata_dir: Path, report: dict[str, Any]) -> None:
    report["finished_at"] = utc_now()
    content_files = [path for path in metadata_dir.parent.rglob("*")
                     if path.is_file() and metadata_dir not in path.parents]
    report["file_count"] = len(content_files)
    report["total_bytes"] = sum(path.stat().st_size for path in content_files)
    (metadata_dir / "download_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    checksum_files = [path for path in (metadata_dir.parent / "raw").rglob("*") if path.is_file()]
    checksum_files.extend(path for path in metadata_dir.iterdir()
                          if path.is_file() and path.name in {"leaf-map.json", "color_train.txt", "color_test.txt"})
    checksum_lines = []
    for path in sorted(checksum_files):
        checksum_lines.append(f"{sha256_file(path)}  {path.relative_to(metadata_dir.parent).as_posix()}")
    (metadata_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + ("\n" if checksum_lines else ""), encoding="utf-8")


def download_plantvillage() -> dict[str, Any]:
    raw_dir, extracted_dir, metadata_dir = initialize_metadata("IMG-T01")
    report: dict[str, Any] = {"dataset_id": "IMG-T01", "started_at": utc_now(), "downloads": []}
    for filename, url in PV_FILES.items():
        target = raw_dir / filename if filename == "data.zip" else metadata_dir / filename
        result = download_file(url, target)
        report["downloads"].append(result)
        if result["status"] == "failed":
            save_report(metadata_dir, report)
            return report
    report["extraction"] = extract_plantvillage(raw_dir / "data.zip", extracted_dir)
    save_report(metadata_dir, report)
    return report


def download_pakistan() -> dict[str, Any]:
    raw_dir, extracted_dir, metadata_dir = initialize_metadata("IMG-T02")
    report: dict[str, Any] = {"dataset_id": "IMG-T02", "started_at": utc_now(), "downloads": []}
    try:
        files = mendeley_files("3mbnb82mxd", 2)
        for entry in files:
            details = entry["content_details"]
            result = download_file(details["download_url"], raw_dir / entry["filename"],
                                   int(details["size"]), details.get("sha256_hash"))
            report["downloads"].append(result)
            if result["status"] != "failed" and zipfile.is_zipfile(raw_dir / entry["filename"]):
                with zipfile.ZipFile(raw_dir / entry["filename"]) as zipped:
                    extracted = skipped = 0
                    for member in zipped.infolist():
                        target = safe_member_path(extracted_dir, member.filename)
                        if member.is_dir():
                            target.mkdir(parents=True, exist_ok=True)
                        elif target.exists() and target.stat().st_size == member.file_size:
                            skipped += 1
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with zipped.open(member) as source, target.open("wb") as output:
                                shutil.copyfileobj(source, output, CHUNK_SIZE)
                            extracted += 1
                    report["extraction"] = {"status": "completed", "extracted": extracted, "skipped": skipped}
    except (HTTPError, URLError, ValueError, zipfile.BadZipFile) as exc:
        report["downloads"].append({"status": "failed", "url": DATASETS["IMG-T02"]["page"],
                                    "http_status": getattr(exc, "code", None), "error": str(exc)})
    save_report(metadata_dir, report)
    return report


def download_external() -> dict[str, Any]:
    raw_dir, _extracted_dir, metadata_dir = initialize_metadata("IMG-T03")
    report: dict[str, Any] = {"dataset_id": "IMG-T03", "started_at": utc_now(), "downloads": []}
    try:
        folders = mendeley_folders("93h9p62kg4", 1)
        selected = [folder for folder in folders if folder["name"] in EXTERNAL_FOLDERS]
        tasks: list[tuple[str, dict[str, Any]]] = []
        for folder in selected:
            tasks.extend((folder["name"], entry) for entry in mendeley_files("93h9p62kg4", 1, folder["id"]))

        def fetch(task: tuple[str, dict[str, Any]]) -> dict[str, Any]:
            folder_name, entry = task
            details = entry["content_details"]
            result = download_file(details["download_url"], raw_dir / folder_name / entry["filename"],
                                   int(details["size"]), details.get("sha256_hash"))
            result["class_folder"] = folder_name
            return result

        workers = max(1, min(32, int(os.getenv("PENGZHI_DOWNLOAD_WORKERS", "8"))))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            report["downloads"].extend(executor.map(fetch, tasks))
        report["download_workers"] = workers
        report["selected_folders"] = [folder["name"] for folder in selected]
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        report["downloads"].append({"status": "failed", "url": DATASETS["IMG-T03"]["page"],
                                    "http_status": getattr(exc, "code", None), "error": str(exc)})
    save_report(metadata_dir, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Download official tomato disease datasets")
    parser.add_argument("--dataset", choices=["all", *DATASETS], default="all")
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    selected = list(DATASETS) if args.dataset == "all" else [args.dataset]
    functions = {"IMG-T01": download_plantvillage, "IMG-T02": download_pakistan, "IMG-T03": download_external}
    reports = [functions[key]() for key in selected]
    failed = [item for report in reports for item in report.get("downloads", []) if item["status"] == "failed"]
    print(json.dumps({"datasets": selected, "failed": len(failed), "reports": reports}, ensure_ascii=False, indent=2))
    return 1 if "IMG-T02" in selected and any(item.get("dataset_id") == "IMG-T02" and
               any(download["status"] == "failed" for download in item.get("downloads", [])) for item in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
