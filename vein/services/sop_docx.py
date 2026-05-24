from datetime import datetime
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt

from vein.config import OUTPUT_DIR, ensure_dirs
from vein.models.experiment import BookingOption, ExperimentContext, InstrumentFit
from vein.rag.indexer import query_corpus


def generate_sop_document(
    ctx: ExperimentContext,
    fit: InstrumentFit,
    booking: BookingOption,
) -> Path:
    ensure_dirs()
    chunks = query_corpus(
        f"{ctx.material_type} {ctx.analysis_goal} {fit.instrument_id}",
        n_results=6,
        instrument_id=fit.instrument_id,
    )

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    title = doc.add_heading("VEIN 2.0 — Custom Session SOP", 0)
    title.runs[0].font.size = Pt(20)

    doc.add_paragraph(f"Colorado School of Mines · Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc.add_paragraph(f"Instrument: {fit.instrument_name}")
    doc.add_paragraph(f"Researcher: {ctx.researcher_name or '—'}")
    doc.add_paragraph(f"Session: {booking.start_time.strftime('%Y-%m-%d %H:%M')} – {booking.end_time.strftime('%H:%M')}")
    doc.add_paragraph(f"Material: {ctx.material_type} · Goal: {ctx.analysis_goal}")

    doc.add_heading("1. Pre-Session Checklist", level=1)
    if fit.prep_time_minutes:
        doc.add_paragraph(
            f"☐ Carbon coat sample at Station 2B ({fit.prep_time_minutes} min for {ctx.sample_dimensions or 'specimens'})",
            style="List Bullet",
        )
    doc.add_paragraph("☐ Verify training certification current", style="List Bullet")
    doc.add_paragraph("☐ Review safety data sheet for sample material", style="List Bullet")
    doc.add_paragraph(f"☐ Arrive by {booking.prep_start.strftime('%H:%M')} for warm-up and prep", style="List Bullet")

    doc.add_heading("2. Instrument Warm-up", level=1)
    for c in chunks:
        if c.get("corpus_type") == "sop" and "warm" in c["text"].lower():
            doc.add_paragraph(c["text"])
            doc.add_paragraph(f"[Source: {c['source']}, {c['section']}, p.{c.get('page', '—')}]")
            break
    else:
        doc.add_paragraph(f"Allow instrument warm-up per Mines SOP (~{fit.run_duration_minutes // 6} min).")

    doc.add_heading("3. Recommended Operating Parameters", level=1)
    doc.add_paragraph(fit.rationale)
    for c in chunks[:3]:
        if c.get("corpus_type") == "manual":
            doc.add_paragraph(c["text"][:400])
            cite = f"[Source: {c['source']}, {c['section']}"
            if c.get("page"):
                cite += f", p.{c['page']}"
            cite += "]"
            doc.add_paragraph(cite)

    doc.add_heading("4. Safety Precautions", level=1)
    doc.add_paragraph(f"Material-specific: Handle {ctx.material_type} per Mines EH&S guidelines.")
    for c in chunks:
        if "safety" in c["text"].lower() or "PPE" in c["text"]:
            doc.add_paragraph(c["text"][:300])
            break

    doc.add_heading("5. Shutdown Procedure", level=1)
    doc.add_paragraph("Follow instrument-specific shutdown checklist in lab binder. Log session in VEIN post-run report.")

    doc.add_heading("6. Post-Run Data Logging", level=1)
    doc.add_paragraph("☐ Export raw data to lab server", style="List Bullet")
    doc.add_paragraph("☐ Submit VEIN post-run report with actual parameters and quality rating", style="List Bullet")
    doc.add_paragraph("☐ Note any anomalies for maintenance log", style="List Bullet")

    fname = f"sop_{fit.instrument_id}_{booking.start_time.strftime('%Y%m%d_%H%M')}.docx"
    path = OUTPUT_DIR / fname
    doc.save(path)
    return path
