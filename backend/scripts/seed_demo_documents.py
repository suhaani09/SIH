"""Seed synthetic PDFs from data/synthetic/output/ into document storage and
link them to the demo application version (appv-demo-0042-v1).

This script is IDEMPOTENT – it checks for existing Document records before
inserting and skips any file already present in content-addressed storage.

All files are SYNTHETIC.  Footer watermark: SYNTHETIC DOCUMENT — FOR DEMONSTRATION ONLY.

Usage (from the repo root or from backend/):
    python backend/scripts/seed_demo_documents.py
"""
import os
import sys
import hashlib
import shutil
from pathlib import Path
from datetime import datetime, timezone

# ── Path bootstrap ──────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent          # backend/scripts/
_BACKEND_DIR = _SCRIPT_DIR.parent                       # backend/
_REPO_ROOT   = _BACKEND_DIR.parent                      # repo root

sys.path.insert(0, str(_BACKEND_DIR))
os.chdir(str(_BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal, engine, Base
from app.models import ApplicationVersion, Document, ScanStatus
from app.config import get_settings

Base.metadata.create_all(bind=engine)
settings = get_settings()

# ── Helpers ─────────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _storage_dest(sha256: str) -> Path:
    root = Path(settings.STORAGE_ROOT)
    return root / sha256[:2] / sha256[2:4] / sha256


def store_pdf(src: Path) -> dict:
    """Content-address a PDF and return metadata dict."""
    sha = _sha256(src)
    dest = _storage_dest(sha)
    key = f"{sha[:2]}/{sha[2:4]}/{sha}"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"    Stored  {src.name} -> {key}")
    else:
        print(f"    Already {src.name} -> {key} (skipped copy)")
    return {"sha256": sha, "storage_key": key}


# ── Document definitions ─────────────────────────────────────────────────────
# Ordered list that matches the evidence doc_name values used in api.js fallback
# and in the verification engine's findings.

SYNTHETIC_PDF_DIR = _REPO_ROOT / "data" / "synthetic" / "output"

DOCUMENTS = [
    {"filename": "01_APPLICATION_FORM.pdf",  "doc_type": "APPLICATION_FORM"},
    {"filename": "02_FACULTY_LIST.pdf",       "doc_type": "FACULTY_LIST"},
    {"filename": "03_FINANCIAL_STATEMENT.pdf","doc_type": "FINANCIAL_STATEMENT"},
    {"filename": "04_LAND_DEED.pdf",          "doc_type": "LAND_DEED"},
    {"filename": "05_BUILDING_PLAN.pdf",      "doc_type": "BUILDING_PLAN"},
    {"filename": "06_FACULTY_AFFIDAVIT.pdf",  "doc_type": "FACULTY_AFFIDAVIT"},
]

VERSION_ID = "appv-demo-0042-v1"
ACTOR_ID   = "user-inst-admin-001"   # institution admin who uploaded

# ── Seed ────────────────────────────────────────────────────────────────────

db = SessionLocal()

version = db.query(ApplicationVersion).filter(
    ApplicationVersion.id == VERSION_ID
).first()

if not version:
    print(f"ERROR: ApplicationVersion '{VERSION_ID}' not found. Run seed_db.py first.")
    db.close()
    sys.exit(1)

print(f"Seeding demo documents into version {VERSION_ID} …")

created = 0
skipped = 0

for doc_def in DOCUMENTS:
    src = SYNTHETIC_PDF_DIR / doc_def["filename"]
    if not src.exists():
        print(f"  WARNING: source PDF missing: {src}")
        continue

    # Skip if a Document record with the same original_name already exists
    existing = db.query(Document).filter(
        Document.version_id == VERSION_ID,
        Document.original_name == doc_def["filename"],
    ).first()
    if existing:
        print(f"  Skipping {doc_def['filename']} – record already exists (id={existing.id})")
        skipped += 1
        continue

    # Store file (idempotent)
    print(f"  Processing {doc_def['filename']} …")
    stored = store_pdf(src)

    doc = Document(
        version_id=VERSION_ID,
        doc_type=doc_def["doc_type"],
        original_name=doc_def["filename"],
        mime="application/pdf",
        sha256=stored["sha256"],
        storage_key=stored["storage_key"],
        page_count=1,       # Synthetic PDFs are single-page
        scan_status=ScanStatus.DONE,  # Pre-scanned synthetic content
    )
    db.add(doc)
    db.flush()
    print(f"    DB record created: id={doc.id}")
    created += 1

db.commit()
db.close()

print(f"\nDone – {created} document(s) created, {skipped} skipped.")
print("Run the app and navigate to the dashboard to see real PDFs in the evidence viewer.")
