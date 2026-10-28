"""
Build MedAI.zip (next to the MedAI folder) containing source, configuration templates, scripts,
documentation and tests — and nothing private.

    backend\\.venv\\Scripts\\python scripts\\package.py

Excluded: node_modules, virtual environments, caches, build output, .env files, databases,
uploaded images, model weights/checkpoints/datasets, and the local ai/model_config.json
(the shipped ai/model_config.default.json keeps the model disabled until weights are fetched).
"""
import fnmatch
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "MedAI.zip"

EXCLUDED_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", ".git", "backups",
                 "storage", "weights", "checkpoints", "data", "runs", ".vite", ".idea", ".vscode"}
EXCLUDED_FILES = ["*.pyc", "*.db", "*.sqlite*", "*.pt", "*.pth", "*.ckpt", "*.safetensors", "*.tsbuildinfo",
                  "*.dcm", "*.dicom", "*.log", "*.zip", ".DS_Store", "Thumbs.db"]
EXCLUDED_PATHS = {"ai/model_config.json"}
# Placeholder JWT secrets used only by the test-suite are allowed; anything else that looks like a key is not.
SECRET_PATTERN = re.compile(r"JWT_SECRET_KEY\s*=\s*['\"]?([A-Za-z0-9_\-]{32,})")


def included(rel: Path) -> bool:
    parts = rel.parts
    if any(p in EXCLUDED_DIRS for p in parts[:-1]):
        return False
    name = parts[-1]
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return False
    if rel.as_posix() in EXCLUDED_PATHS:
        return False
    return not any(fnmatch.fnmatch(name, pat) for pat in EXCLUDED_FILES)


def main() -> int:
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and included(p.relative_to(ROOT)))
    problems = []
    for p in files:
        if p.suffix in {".py", ".ts", ".tsx", ".json", ".md", ".ps1", ".yml", ".ini", ".example", ".txt"}:
            for m in SECRET_PATTERN.finditer(p.read_text(encoding="utf-8", errors="ignore")):
                problems.append(f"{p.relative_to(ROOT)}: possible secret {m.group(1)[:6]}...")
    if problems:
        print("Refusing to package, possible secrets found:\n  " + "\n  ".join(problems))
        return 1

    OUT.unlink(missing_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in files:
            zf.write(p, Path("MedAI") / p.relative_to(ROOT))
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB, {len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
