"""Tests for authenticated Document PDF retrieval endpoint, access control, and storage safety."""
import os
import shutil
import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import User, Application, ApplicationVersion, Document, Institution, ScanStatus
from app.auth import hash_password, create_access_token
from app.config import get_settings


@pytest.fixture(scope="module")
def pdf_test_env():
    """Setup database records, storage files, and test users for PDF retrieval tests."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    settings = get_settings()
    storage_root = Path(settings.STORAGE_ROOT)
    storage_root.mkdir(parents=True, exist_ok=True)

    # 1. Institutions
    inst_a = db.query(Institution).filter(Institution.id == "inst-pdf-test-a").first()
    if not inst_a:
        inst_a = Institution(id="inst-pdf-test-a", name="PDF Test College A")
        db.add(inst_a)

    inst_b = db.query(Institution).filter(Institution.id == "inst-pdf-test-b").first()
    if not inst_b:
        inst_b = Institution(id="inst-pdf-test-b", name="PDF Test College B")
        db.add(inst_b)

    # 2. Users
    # Scrutiny Officer 1
    u_off1 = db.query(User).filter(User.id == "pdf-user-off1").first()
    if not u_off1:
        u_off1 = User(
            id="pdf-user-off1",
            officer_id="PDF-OFF-01",
            name="Officer Alpha",
            email="off1@pdf-test.example",
            password_hash=hash_password("Pass1234!"),
            role="SCRUTINY_OFFICER",
            active=True,
        )
        db.add(u_off1)

    # Scrutiny Officer 2
    u_off2 = db.query(User).filter(User.id == "pdf-user-off2").first()
    if not u_off2:
        u_off2 = User(
            id="pdf-user-off2",
            officer_id="PDF-OFF-02",
            name="Officer Beta",
            email="off2@pdf-test.example",
            password_hash=hash_password("Pass1234!"),
            role="SCRUTINY_OFFICER",
            active=True,
        )
        db.add(u_off2)

    # Supervisor / Senior Reviewer
    u_sup = db.query(User).filter(User.id == "pdf-user-sup").first()
    if not u_sup:
        u_sup = User(
            id="pdf-user-sup",
            officer_id="PDF-SUP-01",
            name="Supervisor Alpha",
            email="sup@pdf-test.example",
            password_hash=hash_password("Pass1234!"),
            role="SENIOR_REVIEWER",
            active=True,
        )
        db.add(u_sup)

    # Institution Admin for College A
    u_inst_a = db.query(User).filter(User.id == "pdf-user-insta").first()
    if not u_inst_a:
        u_inst_a = User(
            id="pdf-user-insta",
            officer_id="PDF-INST-A",
            name="Admin Inst A",
            email="admin@inst-a.example",
            password_hash=hash_password("Pass1234!"),
            role="INSTITUTION_ADMIN",
            institution_id="inst-pdf-test-a",
            active=True,
        )
        db.add(u_inst_a)

    # Institution Admin for College B
    u_inst_b = db.query(User).filter(User.id == "pdf-user-instb").first()
    if not u_inst_b:
        u_inst_b = User(
            id="pdf-user-instb",
            officer_id="PDF-INST-B",
            name="Admin Inst B",
            email="admin@inst-b.example",
            password_hash=hash_password("Pass1234!"),
            role="INSTITUTION_ADMIN",
            institution_id="inst-pdf-test-b",
            active=True,
        )
        db.add(u_inst_b)

    db.flush()

    # 3. Application A (assigned to Officer 1)
    app_a = db.query(Application).filter(Application.id == "app-pdf-a").first()
    if not app_a:
        app_a = Application(
            id="app-pdf-a",
            institution_id="inst-pdf-test-a",
            assigned_officer_id="pdf-user-off1",
            academic_year="2026-27",
            program_type="UG Engineering",
            category="Extension of Approval",
            status="UNDER_REVIEW",
        )
        db.add(app_a)
        db.flush()

        ver_a = ApplicationVersion(
            id="appv-pdf-a-v1",
            application_id="app-pdf-a",
            version_no=1,
            status="UNDER_REVIEW",
        )
        db.add(ver_a)
        db.flush()

    # 4. Application B (assigned to Officer 2)
    app_b = db.query(Application).filter(Application.id == "app-pdf-b").first()
    if not app_b:
        app_b = Application(
            id="app-pdf-b",
            institution_id="inst-pdf-test-b",
            assigned_officer_id="pdf-user-off2",
            academic_year="2026-27",
            program_type="UG Engineering",
            category="Extension of Approval",
            status="UNDER_REVIEW",
        )
        db.add(app_b)
        db.flush()

        ver_b = ApplicationVersion(
            id="appv-pdf-b-v1",
            application_id="app-pdf-b",
            version_no=1,
            status="UNDER_REVIEW",
        )
        db.add(ver_b)
        db.flush()

    # 5. Create real dummy PDF files in storage for tests
    # Document 1 (belongs to App A)
    pdf_content_a = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
    sha_a = hashlib.sha256(pdf_content_a).hexdigest()
    storage_key_a = f"{sha_a[:2]}/{sha_a[2:4]}/{sha_a}"
    file_path_a = storage_root / sha_a[:2] / sha_a[2:4] / sha_a
    file_path_a.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path_a, "wb") as f:
        f.write(pdf_content_a)

    doc_a = db.query(Document).filter(Document.id == "doc-pdf-valid-a").first()
    if not doc_a:
        doc_a = Document(
            id="doc-pdf-valid-a",
            version_id="appv-pdf-a-v1",
            doc_type="APPLICATION_FORM",
            original_name="01_APPLICATION_FORM.pdf",
            mime="application/pdf",
            sha256=sha_a,
            storage_key=storage_key_a,
            page_count=1,
            scan_status=ScanStatus.DONE,
        )
        db.add(doc_a)

    # Document 2 (belongs to App B)
    pdf_content_b = b"%PDF-1.4\n2 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
    sha_b = hashlib.sha256(pdf_content_b).hexdigest()
    storage_key_b = f"{sha_b[:2]}/{sha_b[2:4]}/{sha_b}"
    file_path_b = storage_root / sha_b[:2] / sha_b[2:4] / sha_b
    file_path_b.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path_b, "wb") as f:
        f.write(pdf_content_b)

    doc_b = db.query(Document).filter(Document.id == "doc-pdf-valid-b").first()
    if not doc_b:
        doc_b = Document(
            id="doc-pdf-valid-b",
            version_id="appv-pdf-b-v1",
            doc_type="LAND_DEED",
            original_name="04_LAND_DEED.pdf",
            mime="application/pdf",
            sha256=sha_b,
            storage_key=storage_key_b,
            page_count=1,
            scan_status=ScanStatus.DONE,
        )
        db.add(doc_b)

    # Document 3 (Record exists in DB, but file is MISSING from storage)
    doc_missing = db.query(Document).filter(Document.id == "doc-pdf-missing-file").first()
    if not doc_missing:
        doc_missing = Document(
            id="doc-pdf-missing-file",
            version_id="appv-pdf-a-v1",
            doc_type="FACULTY_LIST",
            original_name="02_FACULTY_LIST.pdf",
            mime="application/pdf",
            sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            storage_key="ff/ff/ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            page_count=1,
            scan_status=ScanStatus.DONE,
        )
        db.add(doc_missing)

    db.commit()
    db.close()

    return {
        "token_off1": create_access_token({"sub": "pdf-user-off1", "email": "off1@pdf-test.example", "role": "SCRUTINY_OFFICER"}),
        "token_off2": create_access_token({"sub": "pdf-user-off2", "email": "off2@pdf-test.example", "role": "SCRUTINY_OFFICER"}),
        "token_sup": create_access_token({"sub": "pdf-user-sup", "email": "sup@pdf-test.example", "role": "SENIOR_REVIEWER"}),
        "token_insta": create_access_token({"sub": "pdf-user-insta", "email": "admin@inst-a.example", "role": "INSTITUTION_ADMIN"}),
        "token_instb": create_access_token({"sub": "pdf-user-instb", "email": "admin@inst-b.example", "role": "INSTITUTION_ADMIN"}),
    }


def test_pdf_retrieval_requires_auth():
    """Unauthenticated request to retrieve PDF must fail with 401."""
    client = TestClient(app)
    res = client.get("/api/v1/documents/doc-pdf-valid-a/pdf")
    assert res.status_code == 401


def test_pdf_retrieval_success_assigned_officer(pdf_test_env):
    """Officer assigned to the case can successfully retrieve the PDF binary."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {pdf_test_env['token_off1']}"}
    res = client.get("/api/v1/documents/doc-pdf-valid-a/pdf", headers=headers)
    assert res.status_code == 200
    assert "application/pdf" in res.headers["content-type"]
    assert res.content.startswith(b"%PDF-")
    assert "01_APPLICATION_FORM.pdf" in res.headers.get("content-disposition", "")


def test_pdf_retrieval_supervisor_access(pdf_test_env):
    """Supervisor / Senior Reviewer can retrieve documents across any case."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {pdf_test_env['token_sup']}"}
    res_a = client.get("/api/v1/documents/doc-pdf-valid-a/pdf", headers=headers)
    assert res_a.status_code == 200

    res_b = client.get("/api/v1/documents/doc-pdf-valid-b/pdf", headers=headers)
    assert res_b.status_code == 200


def test_pdf_retrieval_case_isolation_officer(pdf_test_env):
    """Officer 1 cannot access Document for Application B (assigned to Officer 2)."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {pdf_test_env['token_off1']}"}
    res = client.get("/api/v1/documents/doc-pdf-valid-b/pdf", headers=headers)
    assert res.status_code == 403
    assert "Access denied" in res.json().get("detail", "")


def test_pdf_retrieval_institution_isolation(pdf_test_env):
    """Institution Admin A can access their own document, but cannot access Institution B document."""
    client = TestClient(app)
    # Own document -> 200
    headers_a = {"Authorization": f"Bearer {pdf_test_env['token_insta']}"}
    res_own = client.get("/api/v1/documents/doc-pdf-valid-a/pdf", headers=headers_a)
    assert res_own.status_code == 200

    # Other institution's document -> 403
    res_other = client.get("/api/v1/documents/doc-pdf-valid-b/pdf", headers=headers_a)
    assert res_other.status_code == 403


def test_pdf_retrieval_non_existent_document(pdf_test_env):
    """Non-existent document ID must return 404."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {pdf_test_env['token_sup']}"}
    res = client.get("/api/v1/documents/non-existent-uuid-9999/pdf", headers=headers)
    assert res.status_code == 404
    assert "Document not found" in res.json().get("detail", "")


def test_pdf_retrieval_missing_storage_file(pdf_test_env):
    """Document record exists in DB but file missing in storage must return 404 with clear message."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {pdf_test_env['token_sup']}"}
    res = client.get("/api/v1/documents/doc-pdf-missing-file/pdf", headers=headers)
    assert res.status_code == 404
    assert "storage" in res.json().get("detail", "").lower()
