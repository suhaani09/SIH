"""Applications API: create applications, upload documents, trigger verification."""
from __future__ import annotations
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel

from app.database import get_db
from app.models import (
    Application, ApplicationVersion, Document, User,
    RulebookVersion, VerificationRun, VerificationResult,
    ExtractedField, EvidenceRef, ReviewDecision, Deficiency,
    ConsistencyEdge, Rule, Page, AuditEvent,
    AppStatus, ScanStatus,
)
from app.auth import get_current_user, require_roles
from app.pipeline.ingest import validate_and_store, IngestionError
from app.services.storage import retrieve_path
from app.services.audit import record_event

router = APIRouter(prefix="/api/v1", tags=["applications"])


# ─── Application CRUD ─────────────────────────────────────────────────────────

class CreateApplicationRequest(BaseModel):
    institution_id: str
    academic_year: str
    program_type: str
    category: str


@router.post("/applications", status_code=201)
def create_application(
    req: CreateApplicationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("INSTITUTION_ADMIN", "SYSTEM_ADMIN")),
):
    app = Application(
        institution_id=req.institution_id,
        academic_year=req.academic_year,
        program_type=req.program_type,
        category=req.category,
        status=AppStatus.DRAFT,
    )
    db.add(app)
    db.flush()

    version = ApplicationVersion(
        application_id=app.id,
        version_no=1,
        submitted_by=current_user.id,
    )
    db.add(version)
    db.flush()

    record_event(db, "APPLICATION_CREATED", actor_id=current_user.id,
                 object_type="application", object_id=app.id)
    db.commit()
    return {"application_id": app.id, "version_id": version.id, "version_no": 1}


@router.get("/applications")
def list_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status: Optional[str] = Query(None),
    institution_id: Optional[str] = Query(None),
):
    q = db.query(Application)

    # Row-level security:
    # 1. Institution admins only see their own
    if current_user.role == "INSTITUTION_ADMIN":
        q = q.filter(Application.institution_id == current_user.institution_id)
    # 2. Scrutiny officers: see applications assigned to them, or unassigned applications (general queue)
    elif current_user.role == "SCRUTINY_OFFICER":
        q = q.filter(
            or_(
                Application.assigned_officer_id == current_user.id,
                Application.assigned_officer_id == None
            )
        )
    elif institution_id:
        q = q.filter(Application.institution_id == institution_id)

    if status:
        q = q.filter(Application.status == status)

    apps = q.order_by(Application.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "institution_id": a.institution_id,
            "assigned_officer_id": a.assigned_officer_id,
            "academic_year": a.academic_year,
            "program_type": a.program_type,
            "category": a.category,
            "status": a.status,
            "current_version_no": a.current_version_no,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in apps
    ]


@router.get("/applications/{app_id}")
def get_application(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    _check_app_access(app, current_user)

    return {
        "id": app.id,
        "institution_id": app.institution_id,
        "academic_year": app.academic_year,
        "program_type": app.program_type,
        "category": app.category,
        "status": app.status,
        "current_version_no": app.current_version_no,
        "versions": [{"id": v.id, "version_no": v.version_no, "status": v.status,
                      "submitted_at": v.submitted_at.isoformat() if v.submitted_at else None}
                     for v in app.versions],
    }


# ─── Document upload ──────────────────────────────────────────────────────────

@router.post("/applications/{app_id}/versions/{vno}/documents", status_code=201)
async def upload_document(
    app_id: str,
    vno: int,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("INSTITUTION_ADMIN", "SYSTEM_ADMIN", "SCRUTINY_OFFICER")),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    _check_app_access(app, current_user)

    version = db.query(ApplicationVersion).filter(
        ApplicationVersion.application_id == app_id,
        ApplicationVersion.version_no == vno,
    ).first()
    if not version:
        raise HTTPException(404, "Version not found")

    file_bytes = await file.read()
    try:
        stored = validate_and_store(file_bytes, file.filename or "upload")
    except IngestionError as e:
        raise HTTPException(400, str(e))

    doc = Document(
        version_id=version.id,
        doc_type=doc_type,
        original_name=file.filename or "upload",
        mime=stored["mime"],
        sha256=stored["sha256"],
        storage_key=stored["storage_key"],
        page_count=stored["page_count"],
        scan_status=ScanStatus.QUEUED,
    )
    db.add(doc)
    db.flush()

    record_event(db, "DOCUMENT_UPLOADED", actor_id=current_user.id,
                 object_type="document", object_id=doc.id,
                 payload={"doc_type": doc_type, "sha256": stored["sha256"]})
    db.commit()

    # Enqueue background OCR job
    try:
        import redis
        from rq import Queue
        from app.config import get_settings
        settings = get_settings()
        conn = redis.from_url(settings.REDIS_URL)
        q = Queue("sih_pipeline", connection=conn)
        from app.worker import process_document
        q.enqueue(process_document, doc.id)
    except Exception as e:
        # Redis not available - process synchronously (demo mode)
        background_tasks.add_task(_process_doc_sync, doc.id)

    return {
        "document_id": doc.id,
        "sha256": stored["sha256"],
        "scan_status": ScanStatus.QUEUED,
        "page_count": stored["page_count"],
    }


def _process_doc_sync(document_id: str):
    """Fallback: run OCR synchronously if Redis unavailable."""
    from app.worker import process_document
    process_document(document_id)


# ─── Document PDF retrieval ───────────────────────────────────────────────────

@router.get("/documents/{doc_id}/pdf")
def get_document_pdf(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the raw PDF binary for a document, after verifying access rights.

    Access rules mirror the application-level access check:
    - Institution admin may only access documents belonging to their institution.
    - Scrutiny officer may only access documents from applications that are
      either unassigned or assigned to themselves.
    - Senior reviewers, system admins, auditors, and curators have read access.
    The storage key is never exposed to the caller.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Resolve owning application for access check
    version = db.query(ApplicationVersion).filter(
        ApplicationVersion.id == doc.version_id
    ).first()
    if not version:
        raise HTTPException(404, "Application version not found")

    owning_app = db.query(Application).filter(
        Application.id == version.application_id
    ).first()
    if not owning_app:
        raise HTTPException(404, "Application not found")

    _check_app_access(owning_app, current_user)

    pdf_path = retrieve_path(doc.storage_key)
    if not pdf_path.exists():
        raise HTTPException(404, "Document file not found in storage")

    safe_name = Path(doc.original_name).name if doc.original_name else "document.pdf"
    return FileResponse(
        str(pdf_path),
        media_type=doc.mime or "application/pdf",
        filename=safe_name,
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@router.get("/applications/{app_id}/versions/{vno}/documents")
def list_documents(
    app_id: str,
    vno: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all documents for an application version."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    _check_app_access(app, current_user)

    version = db.query(ApplicationVersion).filter(
        ApplicationVersion.application_id == app_id,
        ApplicationVersion.version_no == vno,
    ).first()
    if not version:
        raise HTTPException(404, "Version not found")

    docs = db.query(Document).filter(Document.version_id == version.id).order_by(Document.created_at.asc()).all()
    return [
        {
            "id": d.id,
            "doc_type": d.doc_type,
            "original_name": d.original_name,
            "mime": d.mime,
            "sha256": d.sha256,
            "page_count": d.page_count,
            "scan_status": d.scan_status.value if hasattr(d.scan_status, "value") else str(d.scan_status),
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


# ─── Verification ─────────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    rulebook_version_id: Optional[str] = None


@router.post("/applications/{app_id}/versions/{vno}/verify")
def start_verification(
    app_id: str,
    vno: int,
    req: VerifyRequest = VerifyRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SCRUTINY_OFFICER", "SENIOR_REVIEWER", "SYSTEM_ADMIN")),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    version = db.query(ApplicationVersion).filter(
        ApplicationVersion.application_id == app_id,
        ApplicationVersion.version_no == vno,
    ).first()
    if not version:
        raise HTTPException(404, "Version not found")

    # Find published rulebook version
    rb_version_id = req.rulebook_version_id
    if not rb_version_id:
        rb_version = db.query(RulebookVersion).filter(
            RulebookVersion.status == "PUBLISHED"
        ).order_by(RulebookVersion.published_at.desc()).first()
        if not rb_version:
            raise HTTPException(400, "No published rulebook version found")
        rb_version_id = rb_version.id

    version.rulebook_version_id = rb_version_id
    version.status = "UNDER_REVIEW"
    db.flush()

    # Submit to worker
    run = VerificationRun(
        version_id=version.id,
        rulebook_version_id=rb_version_id,
        status="QUEUED",
    )
    db.add(run)
    db.flush()

    record_event(db, "VERIFICATION_STARTED", actor_id=current_user.id,
                 object_type="verification_run", object_id=run.id)
    db.commit()

    try:
        import redis
        from rq import Queue
        from app.config import get_settings
        settings = get_settings()
        conn = redis.from_url(settings.REDIS_URL)
        q = Queue("sih_pipeline", connection=conn)
        from app.worker import run_verification
        q.enqueue(run_verification, version.id, rb_version_id, run.id)
    except Exception:
        background_tasks.add_task(_run_verification_sync, version.id, rb_version_id, run.id)

    return {"run_id": run.id, "status": "QUEUED"}


def _run_verification_sync(version_id: str, rulebook_version_id: str, run_id: Optional[str] = None):
    from app.worker import run_verification
    run_verification(version_id, rulebook_version_id, run_id)


@router.get("/runs/{run_id}")
def get_run_status(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.query(VerificationRun).filter(VerificationRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    results = db.query(VerificationResult).filter(VerificationResult.run_id == run_id).all()
    counts = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return {
        "run_id": run_id,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "counts": counts,
    }


# ─── Findings ─────────────────────────────────────────────────────────────────

@router.get("/applications/{app_id}/versions/{vno}/findings")
def get_findings(
    app_id: str,
    vno: int,
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = db.query(ApplicationVersion).filter(
        ApplicationVersion.application_id == app_id,
        ApplicationVersion.version_no == vno,
    ).first()
    if not version:
        raise HTTPException(404, "Version not found")

    run = db.query(VerificationRun).filter(
        VerificationRun.version_id == version.id,
        VerificationRun.status == "DONE",
    ).order_by(VerificationRun.started_at.desc()).first()

    if not run:
        return {"findings": [], "consistency_edges": []}

    q = db.query(VerificationResult).filter(VerificationResult.run_id == run.id)
    if status:
        q = q.filter(VerificationResult.status == status)

    results = q.all()
    findings = []
    for r in results:
        rule = db.query(Rule).filter(Rule.id == r.rule_id).first()
        if severity and rule and rule.severity != severity:
            continue

        evidence_refs = db.query(EvidenceRef).filter(EvidenceRef.result_id == r.id).all()
        evidence_data = []
        for ev in evidence_refs:
            page = db.query(Page).filter(Page.id == ev.page_id).first() if ev.page_id else None
            doc = db.query(Document).filter(Document.id == page.document_id).first() if page else None
            evidence_data.append({
                "document_id": doc.id if doc else None,
                "document_name": doc.original_name if doc else None,
                "page": page.page_no if page else None,
                "bbox": ev.bbox,
                "snippet": ev.snippet,
            })

        findings.append({
            "result_id": r.id,
            "rule_id": rule.rule_key if rule else r.rule_id,
            "clause_ref": rule.clause_ref if rule else "",
            "title": rule.title if rule else "",
            "status": r.status,
            "severity": rule.severity if rule else "MAJOR",
            "required": r.required_value,
            "observed": r.observed_value,
            "confidence": r.confidence,
            "explanation": r.explanation,
            "evidence": evidence_data,
        })

    # Consistency edges
    edges = db.query(ConsistencyEdge).filter(
        ConsistencyEdge.version_id == version.id
    ).all()

    return {
        "findings": findings,
        "consistency_edges": [
            {
                "id": e.id,
                "relation": e.relation,
                "status": e.status,
                "similarity": e.similarity,
                "severity": e.severity,
                "detail": e.detail,
            }
            for e in edges
        ],
    }


# ─── Review actions ───────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    action: str  # CONFIRM | OVERRIDE | REQUEST_CORRECTION
    reason: Optional[str] = None


@router.post("/results/{result_id}/review", status_code=201)
def review_result(
    result_id: str,
    req: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SCRUTINY_OFFICER", "SENIOR_REVIEWER")),
):
    result = db.query(VerificationResult).filter(VerificationResult.id == result_id).first()
    if not result:
        raise HTTPException(404, "Result not found")

    # OVERRIDE of CRITICAL result requires SENIOR_REVIEWER
    rule = db.query(Rule).filter(Rule.id == result.rule_id).first()
    if req.action == "OVERRIDE" and rule and rule.severity == "CRITICAL":
        if current_user.role != "SENIOR_REVIEWER":
            raise HTTPException(403, "Overriding CRITICAL rules requires SENIOR_REVIEWER role")

    if req.action == "OVERRIDE" and not req.reason:
        raise HTTPException(400, "Reason is required for OVERRIDE action")

    decision = ReviewDecision(
        result_id=result_id,
        reviewer_id=current_user.id,
        action=req.action,
        reason=req.reason,
    )
    db.add(decision)

    record_event(db, f"REVIEW_{req.action}", actor_id=current_user.id,
                 object_type="verification_result", object_id=result_id,
                 payload={"action": req.action, "reason": req.reason})
    db.commit()
    return {"id": decision.id, "action": decision.action, "created_at": decision.created_at.isoformat()}


# ─── Field correction ─────────────────────────────────────────────────────────

class FieldCorrectionRequest(BaseModel):
    value: str
    unit: Optional[str] = None
    reason: str


@router.patch("/fields/{field_id}")
def correct_field(
    field_id: str,
    req: FieldCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SCRUTINY_OFFICER", "SENIOR_REVIEWER")),
):
    field = db.query(ExtractedField).filter(ExtractedField.id == field_id).first()
    if not field:
        raise HTTPException(404, "Field not found")

    field.old_value = field.raw_value
    field.raw_value = req.value
    field.unit = req.unit
    field.status = "MANUAL"
    field.corrected_by = current_user.id
    field.corrected_at = datetime.now(timezone.utc).replace(tzinfo=None)
    field.fail_reason = None
    # Re-normalise
    field.normalised_value = {"value": req.value, "unit": req.unit}

    record_event(db, "FIELD_CORRECTED", actor_id=current_user.id,
                 object_type="extracted_field", object_id=field_id,
                 payload={"old_value": field.old_value, "new_value": req.value, "reason": req.reason})
    db.commit()
    return {"id": field.id, "field_key": field.field_key, "raw_value": field.raw_value, "status": field.status}


class ManualFieldRequest(BaseModel):
    page_no: int
    bbox: list[float]
    value: str
    unit: Optional[str] = None
    reason: str


@router.post("/fields/{field_id}/manual")
def save_manual_field(
    field_id: str,
    req: ManualFieldRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SCRUTINY_OFFICER", "SENIOR_REVIEWER")),
):
    field = db.query(ExtractedField).filter(ExtractedField.id == field_id).first()
    if not field:
        raise HTTPException(404, "Field not found")

    field.raw_value = req.value
    field.unit = req.unit
    field.bbox = req.bbox
    field.status = "MANUAL"
    field.corrected_by = current_user.id
    field.corrected_at = datetime.now(timezone.utc).replace(tzinfo=None)
    field.fail_reason = None
    field.confidence = 1.0  # manual entry = full confidence
    field.normalised_value = {"value": req.value, "unit": req.unit}

    record_event(db, "FIELD_MANUAL_ENTRY", actor_id=current_user.id,
                 object_type="extracted_field", object_id=field_id,
                 payload={"value": req.value, "reason": req.reason, "bbox": req.bbox})
    db.commit()
    return {"id": field.id, "status": "MANUAL"}


@router.get("/queue/indeterminate")
def get_indeterminate_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SCRUTINY_OFFICER", "SENIOR_REVIEWER")),
):
    """Return INDETERMINATE fields ordered by severity of dependent rules."""
    fields = db.query(ExtractedField).filter(
        ExtractedField.status == "INDETERMINATE"
    ).all()
    return [
        {
            "field_id": f.id,
            "field_key": f.field_key,
            "fail_reason": f.fail_reason,
            "confidence": f.confidence,
            "page_id": f.page_id,
            "version_id": f.version_id,
        }
        for f in fields
    ]


# ─── Deficiencies ─────────────────────────────────────────────────────────────

class IssueDeficienciesRequest(BaseModel):
    result_ids: list[str]
    due_days: int = 15


@router.post("/applications/{app_id}/deficiencies", status_code=201)
def issue_deficiencies(
    app_id: str,
    req: IssueDeficienciesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SCRUTINY_OFFICER", "SENIOR_REVIEWER")),
):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")

    version = db.query(ApplicationVersion).filter(
        ApplicationVersion.application_id == app_id,
        ApplicationVersion.version_no == app.current_version_no,
    ).first()

    due_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, tzinfo=None)
    from datetime import timedelta
    due_date = due_date + timedelta(days=req.due_days)

    deficiencies = []
    for result_id in req.result_ids:
        result = db.query(VerificationResult).filter(VerificationResult.id == result_id).first()
        if not result:
            continue
        rule = db.query(Rule).filter(Rule.id == result.rule_id).first()
        text = f"{rule.title if rule else result_id}: {result.explanation}"
        d = Deficiency(
            version_id=version.id,
            result_id=result_id,
            text=text,
            due_date=due_date,
        )
        db.add(d)
        deficiencies.append(d)

    app.status = AppStatus.DEFICIENCY_ISSUED
    record_event(db, "DEFICIENCIES_ISSUED", actor_id=current_user.id,
                 object_type="application", object_id=app_id,
                 payload={"count": len(deficiencies)})
    db.commit()
    return [{"id": d.id, "text": d.text, "due_date": d.due_date.isoformat()} for d in deficiencies]


# ─── Status transitions ───────────────────────────────────────────────────────

ALLOWED_TRANSITIONS = {
    "DRAFT": ["SUBMITTED"],
    "SUBMITTED": ["UNDER_REVIEW"],
    "UNDER_REVIEW": ["DEFICIENCY_ISSUED", "RECOMMENDED", "REJECTED_RECOMMENDED"],
    "DEFICIENCY_ISSUED": ["RESUBMITTED"],
    "RESUBMITTED": ["UNDER_REVIEW"],
}


class StatusUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None


@router.patch("/applications/{app_id}/status")
def update_status(
    app_id: str,
    req: StatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")

    allowed = ALLOWED_TRANSITIONS.get(app.status, [])
    if req.status not in allowed:
        raise HTTPException(400, f"Transition from {app.status} to {req.status} not allowed")

    old_status = app.status
    app.status = req.status
    record_event(db, "APPLICATION_STATUS_CHANGED", actor_id=current_user.id,
                 object_type="application", object_id=app_id,
                 payload={"from": old_status, "to": req.status, "reason": req.reason})
    db.commit()
    return {"status": app.status}


# ─── Report export ────────────────────────────────────────────────────────────

from fastapi.responses import Response


@router.get("/applications/{app_id}/versions/{vno}/report")
def export_report(
    app_id: str,
    vno: int,
    format: str = Query("json", pattern="^(pdf|json)$"),
    db: Session = Depends(get_db),

    current_user: User = Depends(get_current_user),
):
    version = db.query(ApplicationVersion).filter(
        ApplicationVersion.application_id == app_id,
        ApplicationVersion.version_no == vno,
    ).first()
    if not version:
        raise HTTPException(404, "Version not found")

    from app.reports import render_pdf_report, render_json_report
    if format == "pdf":
        try:
            pdf_bytes = render_pdf_report(db, version.id)
            return Response(content=pdf_bytes, media_type="application/pdf",
                            headers={"Content-Disposition": f"attachment; filename=report_{app_id}_v{vno}.pdf"})
        except Exception as e:
            raise HTTPException(500, f"PDF generation failed: {e}")
    else:
        data = render_json_report(db, version.id)
        return data


# ─── Version diff ─────────────────────────────────────────────────────────────

@router.get("/applications/{app_id}/versions/{vno}/diff")
def version_diff(
    app_id: str,
    vno: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare findings between version vno and vno-1."""
    if vno < 2:
        return {"message": "No previous version to compare", "changes": []}

    def get_findings(v_no: int):
        ver = db.query(ApplicationVersion).filter(
            ApplicationVersion.application_id == app_id,
            ApplicationVersion.version_no == v_no,
        ).first()
        if not ver:
            return {}
        run = db.query(VerificationRun).filter(
            VerificationRun.version_id == ver.id,
            VerificationRun.status == "DONE",
        ).order_by(VerificationRun.started_at.desc()).first()
        if not run:
            return {}
        results = db.query(VerificationResult).filter(VerificationResult.run_id == run.id).all()
        return {r.rule_id: r.status for r in results}

    prev_findings = get_findings(vno - 1)
    curr_findings = get_findings(vno)

    changes = []
    all_rule_ids = set(prev_findings) | set(curr_findings)
    for rule_id in all_rule_ids:
        prev = prev_findings.get(rule_id, "N/A")
        curr = curr_findings.get(rule_id, "N/A")
        if prev != curr:
            rule = db.query(Rule).filter(Rule.id == rule_id).first()
            changes.append({
                "rule_key": rule.rule_key if rule else rule_id,
                "prev_status": prev,
                "curr_status": curr,
            })

    return {"version_no": vno, "prev_version_no": vno - 1, "changes": changes}


# ─── Audit log ────────────────────────────────────────────────────────────────

@router.get("/audit")
def get_audit_log(
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("AUDITOR", "SYSTEM_ADMIN", "SENIOR_REVIEWER")),
):
    events = db.query(AuditEvent).order_by(AuditEvent.id.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": e.id,
            "actor_id": e.actor_id,
            "action": e.action,
            "object_type": e.object_type,
            "object_id": e.object_id,
            "payload": e.payload,
            "event_hash": e.event_hash,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


@router.get("/audit/verify-chain")
def verify_audit_chain(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("AUDITOR", "SYSTEM_ADMIN")),
):
    from app.services.audit import verify_chain
    return verify_chain(db)


# ─── Helper ───────────────────────────────────────────────────────────────────

def _check_app_access(app: Application, user: User):
    if user.role == "INSTITUTION_ADMIN" and app.institution_id != user.institution_id:
        raise HTTPException(403, "Access denied: not your institution's application")
    # For scrutiny officers: if application has an assigned officer, enforce that only assigned officer
    # (or supervisor/system_admin) can access the case.
    if user.role == "SCRUTINY_OFFICER" and app.assigned_officer_id:
        if app.assigned_officer_id != user.id:
            raise HTTPException(403, "Access denied: this case is assigned to another scrutiny officer")
