"""Seed the database with synthetic demo data for the SIH26261 demonstration.

Creates:
- Institutions (Sunrise Institute of Technology, Demo City)
- Users (officer, institution admin, senior reviewer, curator, auditor)
- Rulebook with all 6 rules
- A demo application with version 1

All data is SYNTHETIC. Footer watermark: SYNTHETIC DOCUMENT — FOR DEMONSTRATION ONLY.
"""
import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# Allow running from backend/ directory

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(str(Path(__file__).parent.parent))

# Load .env
from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal, engine, Base
from app.models import (
    User, Institution, Application, ApplicationVersion,
    Rulebook, RulebookVersion, Rule,
)
from app.auth import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()

print("Seeding database...")

# ─── Institution ──────────────────────────────────────────────────────────────

institution = Institution(
    id="inst-sunrise-001",
    name="Sunrise Institute of Technology, Demo City",
    aicte_id_text="AICTE-DEMO-12345",
    state="Demo State",
    type="Private",
)
existing = db.query(Institution).filter(Institution.id == institution.id).first()
if not existing:
    db.add(institution)
    db.flush()
    print(f"  Created institution: {institution.name}")
else:
    institution = existing
    print(f"  Institution already exists: {institution.name}")

# ─── Users ────────────────────────────────────────────────────────────────────

users_data = [
    {
        "id": "user-inst-admin-001",
        "officer_id": "INST-ADMIN-01",
        "name": "Sunita Sharma (Synthetic)",
        "email": "admin@sunrise-demo.example",
        "password": "demo1234",
        "role": "INSTITUTION_ADMIN",
        "institution_id": institution.id,
    },
    {
        "id": "user-officer-001",
        "officer_id": "OFFICER-001",
        "name": "R. Rao (Scrutiny Officer)",
        "email": "rao@aicte-demo.example",
        "password": "demo1234",
        "role": "SCRUTINY_OFFICER",
        "institution_id": None,
    },
    {
        "id": "user-officer-002",
        "officer_id": "OFFICER-002",
        "name": "V. Sharma (Scrutiny Officer)",
        "email": "sharma@aicte-demo.example",
        "password": "demo1234",
        "role": "SCRUTINY_OFFICER",
        "institution_id": None,
    },
    {
        "id": "user-senior-001",
        "officer_id": "SUPERVISOR-001",
        "name": "P. Kumar (Supervisor / Senior Reviewer)",
        "email": "kumar@aicte-demo.example",
        "password": "demo1234",
        "role": "SENIOR_REVIEWER",
        "institution_id": None,
    },
    {
        "id": "user-admin-001",
        "officer_id": "ADMIN-001",
        "name": "System Administrator",
        "email": "admin@aicte-gov.example",
        "password": "demo1234",
        "role": "SYSTEM_ADMIN",
        "institution_id": None,
    },
    {
        "id": "user-curator-001",
        "officer_id": "CURATOR-001",
        "name": "A. Singh (Rulebook Curator)",
        "email": "singh@aicte-demo.example",
        "password": "demo1234",
        "role": "CURATOR",
        "institution_id": None,
    },
    {
        "id": "user-auditor-001",
        "officer_id": "AUDITOR-001",
        "name": "System Auditor",
        "email": "auditor@aicte-demo.example",
        "password": "demo1234",
        "role": "AUDITOR",
        "institution_id": None,
    },
]

for ud in users_data:
    existing = db.query(User).filter(User.id == ud["id"]).first()
    if not existing:
        user = User(
            id=ud["id"],
            officer_id=ud.get("officer_id"),
            name=ud["name"],
            email=ud["email"],
            password_hash=hash_password(ud["password"]),
            role=ud["role"],
            institution_id=ud.get("institution_id"),
            active=True,
        )
        db.add(user)
        print(f"  Created user: {ud['name']} ({ud['role']}) [ID: {ud.get('officer_id')}]")
    else:
        existing.officer_id = ud.get("officer_id")
        existing.active = True
        print(f"  Updated existing user: {ud['name']} [ID: {ud.get('officer_id')}]")

db.flush()

# ─── Rulebook ────────────────────────────────────────────────────────────────

rulebook = db.query(Rulebook).filter(Rulebook.id == "rb-demo-2026-27").first()
if not rulebook:
    rulebook = Rulebook(
        id="rb-demo-2026-27",
        name="AICTE Approval Process Handbook 2024-27 (Demo)",
        authority="AICTE",
        academic_year="2026-27",
        source_document="APH 2024-27 (official source: aicte.gov.in — verify thresholds before production use)",
    )
    db.add(rulebook)
    db.flush()
    print("  Created rulebook")

rb_version = db.query(RulebookVersion).filter(RulebookVersion.id == "rbv-demo-0.3").first()
if not rb_version:
    rb_version = RulebookVersion(
        id="rbv-demo-0.3",
        rulebook_id=rulebook.id,
        version_label="DEMO-RB-0.3",
        status="PUBLISHED",
        approved_by="user-curator-001",
        published_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    db.add(rb_version)
    db.flush()
    print("  Created rulebook version DEMO-RB-0.3")

# Load YAML rules
import yaml
rules_dir = Path(__file__).parent.parent.parent / "rulebooks" / "2026-27"
yaml_files = sorted(rules_dir.glob("*.yaml"))
print(f"  Loading {len(yaml_files)} rules from {rules_dir}")

for yaml_file in yaml_files:
    with open(yaml_file, "r", encoding="utf-8") as f:
        rule_def = yaml.safe_load(f)

    rule_key = rule_def["rule_key"]
    existing_rule = db.query(Rule).filter(
        Rule.rulebook_version_id == rb_version.id,
        Rule.rule_key == rule_key,
    ).first()

    if not existing_rule:
        rule = Rule(
            rulebook_version_id=rb_version.id,
            rule_key=rule_key,
            title=rule_def["title"],
            clause_ref=rule_def.get("clause_ref"),
            source_page=rule_def.get("source_page"),
            severity=rule_def["severity"],
            applicability=rule_def.get("applicability"),
            definition=rule_def,
            verified=rule_def.get("verified", False),
        )
        db.add(rule)
        print(f"    Added rule: {rule_key}")
    else:
        print(f"    Rule already exists: {rule_key}")

# ─── Demo application ─────────────────────────────────────────────────────────

app_obj = db.query(Application).filter(Application.id == "app-demo-0042").first()
if not app_obj:
    app_obj = Application(
        id="app-demo-0042",
        institution_id=institution.id,
        academic_year="2026-27",
        program_type="UG Engineering",
        category="Extension of Approval",
        current_version_no=1,
        status="SUBMITTED",
    )
    db.add(app_obj)
    db.flush()

    version = ApplicationVersion(
        id="appv-demo-0042-v1",
        application_id=app_obj.id,
        version_no=1,
        submitted_by="user-inst-admin-001",
        submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
        rulebook_version_id=rb_version.id,

        status="SUBMITTED",
    )
    db.add(version)
    print("  Created demo application APP-2026-0042 v1")
else:
    print("  Demo application already exists")

db.commit()

# ─── Seed Demo Synthetic Documents into Storage & DB ─────────────────────────
try:
    from app.models import Document, ScanStatus
    from app.config import get_settings
    settings = get_settings()
    root = Path(settings.STORAGE_ROOT)
    synthetic_dir = Path(__file__).parent.parent.parent / "data" / "synthetic" / "output"

    docs_def = [
        {"filename": "01_APPLICATION_FORM.pdf",  "doc_type": "APPLICATION_FORM"},
        {"filename": "02_FACULTY_LIST.pdf",       "doc_type": "FACULTY_LIST"},
        {"filename": "03_FINANCIAL_STATEMENT.pdf","doc_type": "FINANCIAL_STATEMENT"},
        {"filename": "04_LAND_DEED.pdf",          "doc_type": "LAND_DEED"},
        {"filename": "05_BUILDING_PLAN.pdf",      "doc_type": "BUILDING_PLAN"},
        {"filename": "06_FACULTY_AFFIDAVIT.pdf",  "doc_type": "FACULTY_AFFIDAVIT"},
    ]
    for d_def in docs_def:
        src = synthetic_dir / d_def["filename"]
        if src.exists():
            with open(src, "rb") as f:
                content = f.read()
            sha = hashlib.sha256(content).hexdigest()
            dest = root / sha[:2] / sha[2:4] / sha
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(content)
            key = f"{sha[:2]}/{sha[2:4]}/{sha}"
            existing_doc = db.query(Document).filter(
                Document.version_id == "appv-demo-0042-v1",
                Document.original_name == d_def["filename"],
            ).first()
            if not existing_doc:
                db_doc = Document(
                    version_id="appv-demo-0042-v1",
                    doc_type=d_def["doc_type"],
                    original_name=d_def["filename"],
                    mime="application/pdf",
                    sha256=sha,
                    storage_key=key,
                    page_count=1,
                    scan_status=ScanStatus.DONE,
                )
                db.add(db_doc)
    db.commit()
    print("  Demo PDF documents verified/seeded into storage.")
except Exception as e:
    print(f"  Note: Demo documents check skipped ({e})")

print("\nSeed complete!")
print("\nDemo users (password: demo1234):")
for ud in users_data:
    print(f"  {ud['email']:40s}  role: {ud['role']}")
print("\nRulebook: DEMO-RB-0.3 (status: PUBLISHED, all thresholds ILLUSTRATIVE)")
