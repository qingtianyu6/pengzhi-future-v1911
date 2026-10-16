"""Create the submission ZIP without local secrets, databases, or dependencies."""

from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "棚智未来_提交源码.zip"
PREFIX = "棚智未来_提交源码"
ROOT_FILES = (
    ".dockerignore", ".gitignore", "Caddyfile", "Dockerfile", "docker-compose.yml",
    "README.md", "QUICK_START.md", "version.json", "setup.ps1", "start_all.ps1",
    "start_backend.ps1", "start_frontend.ps1", "start_production.ps1", "stop_all.ps1",
    "verify_release.ps1", "网站入口.cmd", "网站入口.ps1", "提交使用说明.md", "打包源码.py",
)
EXTRA_FILES = (
    "backend/.env.example", "backend/requirements.txt", "backend/run.py",
    "frontend/.env.production", "frontend/eslint.config.js", "frontend/index.html",
    "frontend/package-lock.json", "frontend/package.json", "frontend/tsconfig.app.json",
    "frontend/tsconfig.json", "frontend/tsconfig.node.json", "frontend/vite.config.ts",
)
DIRECTORIES = (
    "backend/app", "backend/config", "backend/knowledge_base", "backend/scripts",
    "backend/tests", "frontend/src", "frontend/public", "frontend/dist",
)
BLOCKED_PARTS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mplconfig", ".run", "uploads", "dist-cache",
}
BLOCKED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".log", ".pyc", ".pyo", ".mp4", ".webm"}


def allowed(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in BLOCKED_PARTS for part in relative.parts):
        return False
    if path.name.startswith("~$") or path.name == ".env":
        return False
    if path.suffix.lower() in BLOCKED_SUFFIXES:
        return False
    return True


def paths() -> list[Path]:
    result = [ROOT / name for name in ROOT_FILES + EXTRA_FILES]
    for name in DIRECTORIES:
        directory = ROOT / name
        if not directory.is_dir():
            raise FileNotFoundError(f"必需目录缺失：{directory}")
        result.extend(path for path in directory.rglob("*") if path.is_file() and allowed(path))
    missing = [path for path in result if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"必需文件缺失：{missing[0]}")
    return sorted(set(result), key=lambda path: path.relative_to(ROOT).as_posix())


def main() -> None:
    files = paths()
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zip_file:
        for file in files:
            zip_file.write(file, f"{PREFIX}/{file.relative_to(ROOT).as_posix()}")
    with ZipFile(ARCHIVE) as zip_file:
        failed = zip_file.testzip()
        if failed:
            raise RuntimeError(f"ZIP 校验失败：{failed}")
        names = zip_file.namelist()
        if len(names) != len(files):
            raise RuntimeError("ZIP 文件数量与源文件不一致。")
        if any("/.env" in name and not name.endswith(".env.example") and not name.endswith(".env.production") for name in names):
            raise RuntimeError("ZIP 中发现不应提交的环境配置文件。")
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    print(f"文件数：{len(files)}")
    print(f"压缩包：{ARCHIVE}")
    print(f"大小：{ARCHIVE.stat().st_size / 1_000_000:.1f} MB")
    print(f"SHA-256：{digest}")


if __name__ == "__main__":
    main()
