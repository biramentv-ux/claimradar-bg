from __future__ import annotations

import io
import os
import re
import statistics
from html import escape as html_escape
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

import app as app_module

try:  # PDF export is optional at import time but installed in production requirements.
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except Exception:  # pragma: no cover
    colors = None
    A4 = None
    cm = None
    ParagraphStyle = None
    getSampleStyleSheet = None
    pdfmetrics = None
    TTFont = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    Table = None
    TableStyle = None

JsonRowsReader = Callable[[Path, int], List[Dict[str, Any]]]

OFFICIAL_DOMAINS = {
    "nsi.bg": 100,
    "bnb.bg": 100,
    "nssi.bg": 100,
    "nra.bg": 100,
    "cik.bg": 100,
    "parliament.bg": 100,
    "dv.parliament.bg": 100,
    "gov.bg": 96,
    "minfin.bg": 96,
    "ec.europa.eu": 96,
    "eurostat": 96,
    "factcheck.bg": 92,
    "bta.bg": 82,
    "bnr.bg": 78,
}

MANUAL_SEARCH_PENALTY = 35
MAX_EXPORT_ITEMS = int(os.getenv("EXPORT_MAX_ITEMS", "40"))


def _domain(url: str) -> str:
    host = urlparse(url or "").netloc.lower().replace("www.", "")
    return host.split(":", 1)[0]


def _tokens(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[A-Za-zА-Яа-я0-9]{4,}", (text or "").lower()) if len(tok) >= 4}


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", text or ""))


def _trusted_domain_score(domain: str) -> int:
    domain = (domain or "").lower()
    for trusted, score in OFFICIAL_DOMAINS.items():
        if trusted in domain:
            return score
    if domain.endswith(".bg"):
        return 60
    if domain:
        return 45
    return 20


def score_evidence_item(claim: str, evidence: Dict[str, Any], cited: bool = False) -> Dict[str, Any]:
    title = str(evidence.get("title") or "")
    snippet = str(evidence.get("snippet") or "")
    url = str(evidence.get("url") or "")
    source = str(evidence.get("source") or evidence.get("name") or "")
    domain = _domain(url)
    reasons: List[str] = []

    base = _trusted_domain_score(domain)
    if base >= 90:
        reasons.append("официален/първичен източник")
    elif base >= 75:
        reasons.append("познат публичен/медиен източник")
    elif domain:
        reasons.append("външен източник")
    else:
        reasons.append("липсва разпознат домейн")

    if evidence.get("manual"):
        base -= MANUAL_SEARCH_PENALTY
        reasons.append("само ръчен search линк")
    else:
        base += 5
        reasons.append("автоматично намерен резултат")

    claim_tokens = _tokens(claim)
    ev_tokens = _tokens(" ".join([title, snippet, source, domain]))
    overlap = len(claim_tokens & ev_tokens)
    if overlap >= 5:
        base += 12
        reasons.append("силно текстово съвпадение")
    elif overlap >= 2:
        base += 7
        reasons.append("частично текстово съвпадение")
    else:
        base -= 6
        reasons.append("слабо текстово съвпадение")

    claim_numbers = _numbers(claim)
    ev_numbers = _numbers(" ".join([title, snippet]))
    if claim_numbers and claim_numbers & ev_numbers:
        base += 10
        reasons.append("съвпадение на число/година")
    elif claim_numbers:
        base -= 4
        reasons.append("липсва числово съвпадение")

    if cited:
        base += 8
        reasons.append("използвано като цитат във verdict")

    score = max(0, min(100, int(base)))
    label = "силно evidence" if score >= 85 else "добро evidence" if score >= 70 else "средно evidence" if score >= 50 else "слабо/ръчно evidence"
    return {
        "score": score,
        "label": label,
        "domain": domain,
        "source": source,
        "reasons": reasons,
    }


def enrich_item_with_evidence_quality(item: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(item)
    claim = str(item.get("claim") or item.get("text") or item.get("title") or "")
    citations = {int(c) for c in item.get("citations", []) if str(c).isdigit()}
    evidence = list(item.get("evidence") or [])
    if not evidence and item.get("sources"):
        evidence = [dict(src, title=src.get("name", "източник"), snippet="Препоръчан source link", source=src.get("name", "source"), manual=True) for src in item.get("sources", [])]

    enriched_evidence = []
    scores = []
    for idx, ev in enumerate(evidence, 1):
        ev_copy = dict(ev)
        quality = score_evidence_item(claim, ev_copy, cited=idx in citations)
        ev_copy["quality"] = quality
        enriched_evidence.append(ev_copy)
        scores.append(quality["score"])
    enriched["evidence"] = enriched_evidence

    if scores:
        top_score = max(scores)
        avg_score = round(statistics.mean(scores), 1)
        strong_count = len([s for s in scores if s >= 70])
    else:
        top_score = 0
        avg_score = 0
        strong_count = 0
    overall = max(top_score, int(avg_score)) if scores else 0
    enriched["evidence_quality"] = {
        "score": overall,
        "average_score": avg_score,
        "top_score": top_score,
        "strong_evidence_count": strong_count,
        "evidence_count": len(scores),
        "label": "силна evidence база" if overall >= 85 else "добра evidence база" if overall >= 70 else "ограничена evidence база" if overall >= 45 else "слаба/липсваща evidence база",
    }
    return enriched


def enrich_check_record(record: Dict[str, Any]) -> Dict[str, Any]:
    items = [enrich_item_with_evidence_quality(item) for item in (record.get("items") or [])[:MAX_EXPORT_ITEMS] if isinstance(item, dict)]
    item_scores = [int(item.get("evidence_quality", {}).get("score") or 0) for item in items]
    return {
        "id": record.get("id"),
        "title": record.get("title", "ClaimRadar BG report"),
        "mode": record.get("mode", ""),
        "created_at": record.get("created_at", ""),
        "visibility": record.get("visibility", "public"),
        "text_preview": record.get("text_preview", ""),
        "copy_text": record.get("copy_text", ""),
        "items": items,
        "evidence_quality_summary": {
            "score": round(statistics.mean(item_scores), 1) if item_scores else 0,
            "top_score": max(item_scores) if item_scores else 0,
            "items_scored": len(item_scores),
            "strong_items": len([s for s in item_scores if s >= 70]),
        },
        "export_links": {
            "json": f"/api/export/check/{record.get('id')}",
            "markdown": f"/export/check/{record.get('id')}.md",
            "pdf": f"/export/check/{record.get('id')}.pdf",
        },
        "disclaimer": app_module.DISCLAIMER,
    }


def markdown_escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\r", " ").strip()


def check_to_markdown(bundle: Dict[str, Any]) -> str:
    lines = [
        f"# {markdown_escape(bundle.get('title') or 'ClaimRadar BG report')}",
        "",
        f"- **ID:** `{markdown_escape(bundle.get('id'))}`",
        f"- **Mode:** {markdown_escape(bundle.get('mode'))}",
        f"- **Created:** {markdown_escape(bundle.get('created_at'))}",
        f"- **Evidence quality:** {bundle.get('evidence_quality_summary', {}).get('score', 0)} / 100",
        "",
        f"> {markdown_escape(bundle.get('disclaimer'))}",
        "",
        "## Preview",
        "",
        markdown_escape(bundle.get("text_preview")),
        "",
        "## Claims and evidence",
        "",
    ]
    for idx, item in enumerate(bundle.get("items", []), 1):
        q = item.get("evidence_quality", {})
        lines += [
            f"### {idx}. {markdown_escape(item.get('claim') or item.get('title') or item.get('text') or 'Claim')}",
            "",
            f"- **Topic:** {markdown_escape(item.get('topic'))}",
            f"- **Verdict/label:** {markdown_escape(item.get('verdict') or item.get('label'))}",
            f"- **Claim confidence:** {markdown_escape(item.get('confidence') or item.get('verdict_score'))}",
            f"- **Evidence quality:** {q.get('score', 0)} / 100 — {markdown_escape(q.get('label'))}",
            "",
            "| # | Source | Quality | Title | URL |",
            "|---:|---|---:|---|---|",
        ]
        evidence = item.get("evidence") or []
        if not evidence:
            lines.append("| - | - | 0 | Няма evidence | - |")
        for ev_idx, ev in enumerate(evidence, 1):
            quality = ev.get("quality", {})
            lines.append(f"| {ev_idx} | {markdown_escape(ev.get('source') or ev.get('name'))} | {quality.get('score', 0)} | {markdown_escape(ev.get('title'))} | {markdown_escape(ev.get('url'))} |")
        lines += ["", markdown_escape(item.get("short_reason") or item.get("explanation") or item.get("reason") or ""), ""]
    return "\n".join(lines).strip() + "\n"


def _register_pdf_font() -> str:
    if pdfmetrics is None or TTFont is None:
        return "Helvetica"
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/local/share/fonts/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("DejaVuSans", path))
                return "DejaVuSans"
            except Exception:
                continue
    return "Helvetica"


def markdown_to_pdf_bytes(markdown: str, title: str = "ClaimRadar BG report") -> bytes:
    if SimpleDocTemplate is None:
        return minimal_pdf_bytes(markdown)
    buf = io.BytesIO()
    font = _register_pdf_font()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1.4 * cm, bottomMargin=1.4 * cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CRTitle", parent=styles["Title"], fontName=font, fontSize=18, leading=22, spaceAfter=12))
    styles.add(ParagraphStyle(name="CRHeading", parent=styles["Heading2"], fontName=font, fontSize=13, leading=16, spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name="CRBody", parent=styles["BodyText"], fontName=font, fontSize=9.5, leading=13, spaceAfter=5))
    story: List[Any] = [Paragraph(html_escape(title), styles["CRTitle"])]
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            story.append(Spacer(1, 0.16 * cm))
            continue
        if line.startswith("# "):
            story.append(Paragraph(html_escape(line[2:]), styles["CRTitle"]))
        elif line.startswith("##"):
            story.append(Paragraph(html_escape(line.lstrip("# ").strip()), styles["CRHeading"]))
        elif line.startswith("|---"):
            continue
        elif line.startswith("|"):
            cells = [html_escape(cell.strip()) for cell in line.strip("|").split("|")]
            story.append(Table([[Paragraph(cell, styles["CRBody"]) for cell in cells]], colWidths=[1.0 * cm, 2.5 * cm, 1.4 * cm, 6.5 * cm, 5.0 * cm], style=TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        else:
            story.append(Paragraph(html_escape(line), styles["CRBody"]))
    doc.build(story)
    return buf.getvalue()


def minimal_pdf_bytes(text: str) -> bytes:
    safe_lines = [line.encode("latin-1", "replace").decode("latin-1")[:100] for line in text.splitlines()[:70]]
    stream = "BT /F1 10 Tf 50 800 Td 14 TL " + " ".join([f"({line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')}) Tj T*" for line in safe_lines]) + " ET"
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream.encode('latin-1'))} >> stream\n{stream}\nendstream endobj",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode("latin-1")))
        pdf += obj + "\n"
    xref_start = len(pdf.encode("latin-1"))
    pdf += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n"
    pdf += f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
    return pdf.encode("latin-1")


def load_check_record(storage: Any, read_jsonl: JsonRowsReader, check_id: str) -> Optional[Dict[str, Any]]:
    check_id = (check_id or "").strip()
    if not check_id:
        return None
    if getattr(storage, "configured", False):
        try:
            rec = storage.get_check(check_id)
            if rec:
                return rec
        except Exception:
            pass
    for rec in read_jsonl(app_module.CHECKS_FILE, limit=5000):
        if rec.get("id") == check_id:
            return rec
    return None


def _extract_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return request.query_params.get("admin_key") or request.query_params.get("api_key") or request.headers.get("x-admin-key") or request.headers.get("x-api-key") or ""


def register_evidence_export_routes(
    app: FastAPI,
    can_admin: Callable[[str], bool],
    storage: Any,
    read_jsonl: JsonRowsReader,
    visibility_for: Callable[[str], str] | None = None,
) -> None:
    def get_bundle_or_response(check_id: str, request: Request):
        rec = load_check_record(storage, read_jsonl, check_id)
        if not rec:
            return JSONResponse({"ok": False, "error": "check_not_found", "id": check_id}, status_code=404)
        visibility = visibility_for(check_id) if visibility_for else rec.get("visibility", "public")
        if visibility != "public" and not can_admin(_extract_token(request)):
            return JSONResponse({"ok": False, "error": "private_check", "id": check_id}, status_code=403)
        rec = dict(rec)
        rec["visibility"] = visibility
        return enrich_check_record(rec)

    @app.get("/api/export/check/{check_id}")
    def api_export_check(check_id: str, request: Request):
        bundle = get_bundle_or_response(check_id, request)
        if isinstance(bundle, JSONResponse):
            return bundle
        return JSONResponse({"ok": True, "export": bundle})

    @app.get("/export/check/{check_id}.md")
    def export_check_markdown(check_id: str, request: Request):
        bundle = get_bundle_or_response(check_id, request)
        if isinstance(bundle, JSONResponse):
            return bundle
        md = check_to_markdown(bundle)
        filename = f"claimradar-{check_id}.md"
        return Response(md, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    @app.get("/export/check/{check_id}.pdf")
    def export_check_pdf(check_id: str, request: Request):
        bundle = get_bundle_or_response(check_id, request)
        if isinstance(bundle, JSONResponse):
            return bundle
        md = check_to_markdown(bundle)
        pdf = markdown_to_pdf_bytes(md, title=str(bundle.get("title") or "ClaimRadar BG report"))
        filename = f"claimradar-{check_id}.pdf"
        return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
