"""M06 PDF report built ONLY from stored database records (reproducible)."""
import hashlib, io, json, os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, KeepTogether
from xml.sax.saxutils import escape
import re
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .. import models as m

_AR = re.compile("[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_FONT_OK = False

def _ensure_font():
    global _FONT_OK
    if not _FONT_OK:
        pdfmetrics.registerFont(TTFont("NotoArabic", os.path.join(os.path.dirname(__file__), "assets", "NotoSansArabic-Regular.ttf")))
        a = os.path.join(os.path.dirname(__file__), "assets")
        for n, f in (("SpaceGrotesk-SemiBold", "SpaceGrotesk-SemiBold.ttf"), ("SpaceGrotesk", "SpaceGrotesk-Regular.ttf"), ("PlexMono", "IBMPlexMono-Regular.ttf")):
            pdfmetrics.registerFont(TTFont(n, os.path.join(a, f)))
        _FONT_OK = True

def T(x):
    """XML-escape user text; Arabic text is shaped (joined letters), bidi-reordered and set in an embedded Arabic-capable font."""
    x = "-" if x is None else str(x)
    if not _AR.search(x):
        return escape(x)
    import arabic_reshaper
    from bidi.algorithm import get_display
    _ensure_font()
    shown = get_display(arabic_reshaper.reshape(x))
    out, cur, ar = [], "", None
    for ch in shown:  # Arabic letters in the embedded Arabic font, everything else in the base font (Noto Arabic has no Latin glyphs)
        a = bool(_AR.match(ch))
        if ar is not None and a != ar:
            out.append((cur, ar)); cur = ""
        cur += ch; ar = a
    out.append((cur, ar))
    return "".join('<font name="NotoArabic">%s</font>' % escape(t) if a else escape(t) for t, a in out)

LIMITS = [
    "Indicators are statistical hints, not proof that hidden data exists.",
    "Statistical tests and the model target sequential LSB replacement; other hiding methods may not be detected.",
    "A SHA-256 match proves identical bytes only; it does not prove the image is authentic.",
    "The default ML model (v8: gradient boosting on LSB, SPAM and SRM-lite residual features, scored on 128px tiles) was trained on 128px crops of Imagenette and Oxford Pets photos plus synthetic covers. On a locked test of unseen photos and two photo families never seen in training, about 2-6% of clean lossless images were flagged and LSB matching at 10% payload was caught 87-93% of the time (docs/locked_eval_v8.json). Your own covers can differ: calibrate on clean images from your source. Stego that was recompressed as JPEG is mostly missed (about 7% caught), third-party tools and non-LSB methods were not tested, and no CNN is used. Older models (v7 and below) are weaker and stay selectable.",
    "Visual aids (heatmaps, difference maps) show where statistics differ, not where a message is hidden.",
]

def collect(db, case, run_ids=None):
    q = db.query(m.AnalysisRun).join(m.Evidence, m.Evidence.id == m.AnalysisRun.evidence_id).filter(m.Evidence.case_id == case.id)
    if run_ids:
        q = q.filter(m.AnalysisRun.id.in_(run_ids))
    runs = q.order_by(m.AnalysisRun.id).all()
    items = []
    for r in runs:
        ev = db.get(m.Evidence, r.evidence_id)
        mv = db.get(m.ModelVersion, r.model_version_id) if r.model_version_id else None
        items.append({"run_id": r.id, "analysed_at": r.started_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                      "evidence": {"id": ev.id, "name": ev.original_name, "size": ev.size_bytes, "format": ev.fmt,
                                   "dims": f"{ev.width}x{ev.height}", "sha256": ev.sha256,
                                   "received": ev.uploaded_at.strftime("%Y-%m-%d %H:%M:%S UTC")},
                      "result": json.loads(r.result_json),
                      "model": ({"name": mv.name, "algo": mv.algo, "trained_at": mv.trained_at, "seed": mv.seed,
                                 "metrics": json.loads(mv.metrics_json)} if mv else None)})
    return {"case": {"code": case.case_code, "title": case.title, "created": case.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")},
            "items": items, "limitations": LIMITS}

def content_hash(content: dict) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()

def render_pdf(content: dict, analyst: str) -> bytes:
    _ensure_font(); ch = content_hash(content)
    ss = getSampleStyleSheet()
    INK, AMBER, GHOST = colors.HexColor("#0A101E"), colors.HexColor("#FFB224"), colors.HexColor("#5F7099")
    H = ParagraphStyle("h", parent=ss["Heading2"], textColor=INK, fontName="SpaceGrotesk-SemiBold")
    B = ss["BodyText"]; mono = ParagraphStyle("mono", parent=B, fontName="PlexMono", fontSize=7, leading=9)
    buf = io.BytesIO()
    def footer(c, d):
        c.saveState(); c.setFont("Helvetica", 7.5); c.setFillColor(colors.HexColor("#5F7099"))
        c.drawString(15 * mm, 10 * mm, f"Sublumen | forensic report | content hash {ch[:16]}... | page {d.page}")
        c.restoreState()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
                            title=f"Forensic Report {content['case']['code']}", author=analyst, invariant=1)
    logo = Image(os.path.join(os.path.dirname(__file__), "assets", "mark.png"), width=14 * mm, height=14 * mm)
    word = Paragraph('<font name="SpaceGrotesk-SemiBold" size="20" color="#5F7099">sub</font><font name="SpaceGrotesk-SemiBold" size="20" color="#0A101E">lumen</font><br/>'
                     '<font size="8" color="#5F7099">FIND WHAT THE PIXELS HIDE.</font>', ss["BodyText"])
    head = Table([[logo, word, Paragraph('<font size="14" color="#0A101E"><b>Forensic Report</b></font>', ss["BodyText"])]], colWidths=[18 * mm, 80 * mm, 82 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (2, 0), (2, 0), "RIGHT")]))
    S = [head, HRFlowable(width="100%", thickness=2, color=AMBER, spaceBefore=4, spaceAfter=8),
         Paragraph(f"<b>Case:</b> {T(content['case']['code'])} - {T(content['case']['title'])}<br/><b>Case opened:</b> {content['case']['created']}<br/><b>Analyst:</b> {T(analyst)}", B),
         Spacer(1, 4)]
    if not content["items"]:
        S.append(Paragraph("No analyses are recorded for this case.", B))
    for n, it in enumerate(content["items"], 1):
        ev, res = it["evidence"], it["result"]
        S.append(Paragraph(f"{n}. Evidence: {T(ev['name'] or '-')}", H))
        t = Table([["File", Paragraph(T(ev["name"] or "-"), ss["BodyText"])], ["Format / size", f"{ev['format']} / {ev['dims']} / {ev['size']} bytes"],
                   ["Received", ev["received"]], ["Analysed", it["analysed_at"]], ["Run id", str(it["run_id"])]],
                  colWidths=[35 * mm, 145 * mm])
        t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke)]))
        S += [t, Spacer(1, 3), Paragraph("SHA-256 (at intake):", B), Paragraph(ev["sha256"], mono), Spacer(1, 4)]
        S.append(Paragraph("Findings (indicators, not a verdict)", ParagraphStyle("h3", parent=ss["Heading3"])))
        rows = [["Indicator", "Value", "Level"]] + [[i["name"], "-" if i["value"] is None else str(i["value"]), i["level"].upper()] for i in res["indicators"]]
        if res.get("ml"):
            rows.append([f"ML score ({res['ml']['model']}, {res['ml']['algo']})", f"{res['ml']['score']:.3f}", res["ml"]["level"].upper()])
        t = Table(rows, colWidths=[85 * mm, 45 * mm, 50 * mm], repeatRows=1)
        t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF1F7")), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
        S.append(t)
        for w in res.get("warnings", []):
            S.append(Paragraph("<b>Warning:</b> " + T(w), B))
        mdl = it["model"]
        S.append(Paragraph("Model information", ParagraphStyle("h3b", parent=ss["Heading3"])))
        if mdl:
            tm = mdl["metrics"]["test"].get(mdl["algo"], {})
            S.append(Paragraph(f"{T(mdl['name'])} ({T(mdl['algo'])}), trained {T(str(mdl['trained_at']))}, seed {mdl['seed']}.<br/>"
                               f"Held-out test metrics recorded at training: accuracy {tm.get('accuracy', 0):.3f}, recall {tm.get('recall', 0):.3f}, FPR {tm.get('fpr', 0):.3f} (n={tm.get('n', '-')}). "
                               "Training data: synthetic images plus real photos (see Limitations).", B))
        else:
            S.append(Paragraph("No ML model was used for this run (statistics only).", B))
        S.append(Spacer(1, 6))
    S.append(KeepTogether([Paragraph("Limitations", H)] + [Paragraph("- " + T(x), B) for x in content["limitations"]]))
    S += [Spacer(1, 6), Paragraph("Report content hash (SHA-256 of the data this report is built from):", B), Paragraph(ch, mono)]
    doc.build(S, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
