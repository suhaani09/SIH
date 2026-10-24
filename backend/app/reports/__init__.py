"""Report generator: produce PDF (WeasyPrint) and JSON evidence-linked reports."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from jinja2 import Environment, DictLoader
from sqlalchemy.orm import Session

from app.models import (
    ApplicationVersion, VerificationResult, VerificationRun,
    EvidenceRef, ExtractedField, Document, Page, Rule,
    ReviewDecision, Deficiency, ConsistencyEdge, Application
)

# ─── HTML template ─────────────────────────────────────────────────────────────

REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Compliance Report - {{ app_id }} v{{ version_no }}</title>
<style>
  body { font-family: Arial, sans-serif; font-size: 11pt; color: #222; }
  h1 { color: #1a237e; }
  h2 { color: #283593; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
  .watermark { color: #ccc; font-size: 9pt; text-align: center; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 16px; }
  th { background: #e8eaf6; text-align: left; padding: 6px; }
  td { padding: 5px 6px; border-bottom: 1px solid #eee; }
  .FAIL { color: #c62828; font-weight: bold; }
  .PASS { color: #2e7d32; }
  .INDETERMINATE { color: #f57f17; }
  .NOT_APPLICABLE { color: #666; }
  .CRITICAL { background: #ffebee; }
  .MAJOR { background: #fff3e0; }
  .MINOR { background: #fffde7; }
  .ADVISORY { background: #f3e5f5; }
  .evidence { font-size: 9pt; color: #555; background: #f5f5f5; padding: 3px 6px; }
  .disclaimer { font-size: 9pt; color: #888; border-top: 1px solid #ccc; margin-top: 20px; padding-top: 8px; }
</style>
</head>
<body>
<p class="watermark">SYNTHETIC DOCUMENT — FOR DEMONSTRATION ONLY — NOT AN OFFICIAL AICTE DOCUMENT</p>
<h1>AICTE Compliance Verification Report</h1>

<table>
<tr><th>Application</th><td>{{ app_id }}</td><th>Version</th><td>{{ version_no }}</td></tr>
<tr><th>Institution</th><td>{{ institution_name }}</td><th>Program</th><td>{{ program_type }}</td></tr>
<tr><th>Academic Year</th><td>{{ academic_year }}</td><th>Generated</th><td>{{ generated_at }}</td></tr>
<tr><th>Rulebook Version</th><td>{{ rulebook_label }}</td><th>Engine Version</th><td>{{ engine_version }}</td></tr>
<tr><th>Run Status</th><td>{{ run_status }}</td><th>Overall</th><td class="{{ overall_status }}">{{ overall_status }}</td></tr>
</table>

<h2>Summary</h2>
<table>
<tr><th>PASS</th><th>FAIL</th><th>INDETERMINATE</th><th>NOT APPLICABLE</th></tr>
<tr>
  <td class="PASS">{{ counts.PASS }}</td>
  <td class="FAIL">{{ counts.FAIL }}</td>
  <td class="INDETERMINATE">{{ counts.INDETERMINATE }}</td>
  <td class="NOT_APPLICABLE">{{ counts.NOT_APPLICABLE }}</td>
</tr>
</table>

<h2>Rule Findings</h2>
{% for f in findings %}
<div class="{{ f.severity }}">
<table>
<tr><th>Rule</th><td>{{ f.rule_key }}</td><th>Status</th><td class="{{ f.status }}">{{ f.status }}</td></tr>
<tr><th>Title</th><td colspan="3">{{ f.title }}</td></tr>
<tr><th>Clause</th><td colspan="3">{{ f.clause_ref }}</td></tr>
<tr><th>Severity</th><td>{{ f.severity }}</td><th>Confidence</th><td>{{ "%.2f"|format(f.confidence) }}</td></tr>
<tr><th>Required</th><td>{{ f.required_value }}</td><th>Observed</th><td>{{ f.observed_value }}</td></tr>
<tr><th>Explanation</th><td colspan="3">{{ f.explanation }}</td></tr>
{% if f.evidence %}
<tr><th>Evidence</th><td colspan="3">
  {% for ev in f.evidence %}
  <div class="evidence">Document {{ ev.doc_name }}, Page {{ ev.page_no }}, BBox {{ ev.bbox }} — {{ ev.snippet }}</div>
  {% endfor %}
</td></tr>
{% endif %}
{% if f.review %}
<tr><th>Officer Action</th><td colspan="3">{{ f.review.action }} by {{ f.review.reviewer }} — {{ f.review.reason }}</td></tr>
{% endif %}
</table>
</div>
{% endfor %}

{% if consistency_findings %}
<h2>Cross-Document Consistency Findings</h2>
<table>
<tr><th>Relation</th><th>Status</th><th>Similarity</th><th>Detail</th></tr>
{% for c in consistency_findings %}
<tr>
  <td>{{ c.relation }}</td>
  <td class="{{ c.status }}">{{ c.status }}</td>
  <td>{{ "%.1f"|format(c.similarity) if c.similarity is not none else "-" }}%</td>
  <td>{{ c.detail }}</td>
</tr>
{% endfor %}
</table>
{% endif %}

{% if deficiencies %}
<h2>Issued Deficiencies</h2>
<table>
<tr><th>#</th><th>Deficiency</th><th>Due Date</th><th>Status</th></tr>
{% for d in deficiencies %}
<tr>
  <td>{{ loop.index }}</td>
  <td>{{ d.text }}</td>
  <td>{{ d.due_date }}</td>
  <td>{{ "Resolved" if d.resolved_version else "Open" }}</td>
</tr>
{% endfor %}
</table>
{% endif %}

<div class="disclaimer">
  <strong>Disclaimer:</strong> This is a functional prototype for demonstration purposes only.
  It is NOT a production government system, NOT security-audited, NOT certified, and does NOT issue official AICTE approvals.
  All rule thresholds are ILLUSTRATIVE unless marked VERIFIED. Decisions remain with authorised officers.
  Rulebook version: {{ rulebook_label }} (verified={{ rulebook_verified }}).
</div>
</body>
</html>
"""


def generate_report_data(db: Session, version_id: str, run_id: Optional[str] = None) -> dict:
    """Assemble all data needed for the report."""
    version = db.query(ApplicationVersion).filter(ApplicationVersion.id == version_id).first()
    if not version:
        return {}

    app = version.application
    institution = app.institution

    # Get the latest run if not specified
    if not run_id:
        run = db.query(VerificationRun).filter(
            VerificationRun.version_id == version_id
        ).order_by(VerificationRun.started_at.desc()).first()
    else:
        run = db.query(VerificationRun).filter(VerificationRun.id == run_id).first()

    if not run:
        return {"error": "No verification run found"}

    rb_version = db.query(RulebookVersion).filter(RulebookVersion.id == run.rulebook_version_id).first() if run else None

    results = db.query(VerificationResult).filter(VerificationResult.run_id == run.id).all()

    counts = {"PASS": 0, "FAIL": 0, "INDETERMINATE": 0, "NOT_APPLICABLE": 0}
    findings_data = []

    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
        rule = db.query(Rule).filter(Rule.id == r.rule_id).first()

        # Get evidence
        evidence_refs = db.query(EvidenceRef).filter(EvidenceRef.result_id == r.id).all()
        evidence_data = []
        for ev in evidence_refs:
            page = db.query(Page).filter(Page.id == ev.page_id).first() if ev.page_id else None
            doc = db.query(Document).filter(Document.id == page.document_id).first() if page else None
            evidence_data.append({
                "doc_id": doc.id if doc else None,
                "doc_name": doc.original_name if doc else "",
                "page_no": page.page_no if page else None,
                "bbox": ev.bbox,
                "snippet": ev.snippet,
            })

        # Get review decision
        review = db.query(ReviewDecision).filter(ReviewDecision.result_id == r.id).first()
        review_data = None
        if review:
            reviewer = db.query(User).filter(User.id == review.reviewer_id).first()
            review_data = {
                "action": review.action,
                "reviewer": reviewer.name if reviewer else review.reviewer_id,
                "reason": review.reason,
            }

        findings_data.append({
            "rule_key": rule.rule_key if rule else r.rule_id,
            "title": rule.title if rule else "",
            "clause_ref": rule.clause_ref if rule else "",
            "status": r.status,
            "severity": rule.severity if rule else "MAJOR",
            "required_value": r.required_value,
            "observed_value": r.observed_value,
            "explanation": r.explanation,
            "confidence": r.confidence or 0.0,
            "evidence": evidence_data,
            "review": review_data,
        })

    # Consistency edges
    edges = db.query(ConsistencyEdge).filter(ConsistencyEdge.version_id == version_id).all()
    consistency_data = [
        {
            "relation": e.relation,
            "status": e.status,
            "similarity": e.similarity,
            "detail": json.dumps(e.detail) if e.detail else "",
        }
        for e in edges if e.status == "MISMATCH"
    ]

    # Deficiencies
    deficiencies = db.query(Deficiency).filter(Deficiency.version_id == version_id).all()

    overall = "PASS"
    if counts["FAIL"] > 0:
        overall = "FAIL"
    elif counts["INDETERMINATE"] > 0:
        overall = "INDETERMINATE"

    return {
        "app_id": app.id[:8].upper(),
        "version_no": version.version_no,
        "institution_name": institution.name if institution else "",
        "program_type": app.program_type,
        "academic_year": app.academic_year,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "rulebook_label": rb_version.version_label if rb_version else "unknown",

        "rulebook_verified": all(r.verified for r in (rb_version.rules if rb_version and rb_version.rules else [])),
        "engine_version": run.engine_version if run else ENGINE_VERSION,
        "run_status": run.status if run else "UNKNOWN",
        "overall_status": overall,
        "counts": counts,
        "findings": findings_data,
        "consistency_findings": consistency_data,
        "deficiencies": [
            {
                "text": d.text,
                "due_date": d.due_date.strftime("%Y-%m-%d") if d.due_date else "",
                "resolved_version": d.resolved_in_version_id,
            }
            for d in deficiencies
        ],
    }


def _render_pure_python_pdf(data: dict) -> bytes:
    """Generate a valid, structured PDF report in pure Python without external dependencies."""
    lines = [
        "SYNTHETIC DOCUMENT -- FOR DEMONSTRATION ONLY -- NOT AN OFFICIAL AICTE DOCUMENT",
        "=" * 75,
        "AICTE COMPLIANCE VERIFICATION REPORT",
        "=" * 75,
        f"Application ID: {data.get('app_id', '-')}        Version: {data.get('version_no', '-')}",
        f"Institution:    {data.get('institution_name', '-')}",
        f"Program Type:   {data.get('program_type', '-')}   Academic Year: {data.get('academic_year', '-')}",
        f"Rulebook Label: {data.get('rulebook_label', '-')} Engine Version: {data.get('engine_version', '-')}",
        f"Generated At:   {data.get('generated_at', '-')}   Run Status: {data.get('run_status', '-')}",
        f"OVERALL STATUS: {data.get('overall_status', '-')}",
        "-" * 75,
        f"SUMMARY: PASS: {data.get('counts', {}).get('PASS', 0)} | "
        f"FAIL: {data.get('counts', {}).get('FAIL', 0)} | "
        f"INDETERMINATE: {data.get('counts', {}).get('INDETERMINATE', 0)} | "
        f"NOT_APPLICABLE: {data.get('counts', {}).get('NOT_APPLICABLE', 0)}",
        "-" * 75,
        "",
        "RULE FINDINGS:",
    ]

    for f in data.get("findings", []):
        lines.append(f"  [{f.get('status', '-')}] {f.get('rule_key', '-')} -- {f.get('title', '-')}")
        lines.append(f"      Severity: {f.get('severity', '-')} | Confidence: {f.get('confidence', 0.0):.2f} | Clause: {f.get('clause_ref', '-') or '-'}")
        lines.append(f"      Required: {f.get('required_value', '-')} | Observed: {f.get('observed_value', '-')}")
        if f.get("explanation"):
            lines.append(f"      Explanation: {f.get('explanation')}")
        for ev in f.get("evidence", []):
            lines.append(f"      Evidence: Doc {ev.get('doc_name')} (Page {ev.get('page_no')}) BBox {ev.get('bbox')}")
        if f.get("review"):
            lines.append(f"      Review: {f['review'].get('action')} by {f['review'].get('reviewer')} - {f['review'].get('reason')}")
        lines.append("")

    consistency = data.get("consistency_findings", [])
    if consistency:
        lines.append("-" * 75)
        lines.append("CROSS-DOCUMENT CONSISTENCY FINDINGS (MISMATCHES):")
        for c in consistency:
            sim_str = f"{c.get('similarity'):.1f}%" if c.get("similarity") is not None else "-"
            lines.append(f"  [{c.get('status', '-')}] {c.get('relation', '-')} (Similarity: {sim_str}): {c.get('detail', '')}")
        lines.append("")

    deficiencies = data.get("deficiencies", [])
    if deficiencies:
        lines.append("-" * 75)
        lines.append("DEFICIENCIES:")
        for idx, d in enumerate(deficiencies, 1):
            lines.append(f"  {idx}. {d.get('text', '')} (Due: {d.get('due_date', '-')}) [{d.get('resolved_version') or 'Open'}]")
        lines.append("")

    lines.extend([
        "-" * 75,
        "DISCLAIMER: This is a functional prototype for demonstration purposes only.",
        "It is NOT a production government system, NOT security-audited, NOT certified,",
        "and does NOT issue official AICTE approvals. Rule thresholds are ILLUSTRATIVE.",
        "=" * 75,
    ])

    # Paginate lines: ~48 lines per page
    PAGE_SIZE = 48
    pages_lines = [lines[i:i + PAGE_SIZE] for i in range(0, len(lines), PAGE_SIZE)]
    if not pages_lines:
        pages_lines = [["AICTE Compliance Report (Empty)"]]

    objs = []
    # 1: Catalog
    objs.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    page_count = len(pages_lines)
    # Page object numbers: starting from 3, page objects are 3, 5, 7, ...; content streams 4, 6, 8, ...
    kids_refs = " ".join(f"{3 + i * 2} 0 R" for i in range(page_count))
    objs.append(f"2 0 obj\n<< /Type /Pages /Kids [{kids_refs}] /Count {page_count} >>\nendobj\n".encode("latin1"))

    # Font object at the end
    font_obj_no = 3 + page_count * 2

    for i, plines in enumerate(pages_lines):
        p_obj_no = 3 + i * 2
        s_obj_no = 4 + i * 2

        content_stream = "BT\n/F1 9 Tf\n40 800 Td\n15 TL\n"
        for line in plines:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            # Truncate line length to avoid off-page bleed
            if len(safe) > 95:
                safe = safe[:92] + "..."
            content_stream += f"({safe}) '\n"
        content_stream += "ET\n"
        s_bytes = content_stream.encode("latin1", errors="replace")

        objs.append(
            f"{p_obj_no} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {s_obj_no} 0 R /Resources << /Font << /F1 {font_obj_no} 0 R >> >> >>\nendobj\n".encode("latin1")
        )
        objs.append(
            f"{s_obj_no} 0 obj\n<< /Length {len(s_bytes)} >>\nstream\n".encode("latin1") + s_bytes + b"\nendstream\nendobj\n"
        )

    # Font object
    objs.append(f"{font_obj_no} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n".encode("latin1"))

    body = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objs:
        offsets.append(len(body))
        body += obj

    xref_start = len(body)
    body += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("latin1")
    for off in offsets[1:]:
        body += f"{off:010d} 00000 n \n".encode("latin1")
    body += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("latin1")
    return body


def render_pdf_report(db: Session, version_id: str, run_id: Optional[str] = None) -> bytes:
    """Render the report as PDF bytes using WeasyPrint if available, or pure Python fallback."""
    data = generate_report_data(db, version_id, run_id)
    try:
        from weasyprint import HTML
        env = Environment(loader=DictLoader({"report.html": REPORT_TEMPLATE}))
        template = env.get_template("report.html")
        html_str = template.render(**data)
        return HTML(string=html_str).write_pdf()
    except Exception:
        return _render_pure_python_pdf(data)


def render_json_report(db: Session, version_id: str, run_id: Optional[str] = None) -> dict:
    """Return the report as a JSON-serialisable dict."""
    return generate_report_data(db, version_id, run_id)


# Models and constants
from app.models import User, RulebookVersion
from app.engine.evaluator import ENGINE_VERSION

