"""Synthetic Mines lab knowledge corpus for RAG indexing."""

MANUAL_CHUNKS = [
    {
        "id": "xrd-manual-4.3",
        "source": "Bruker D8 Advance Manual",
        "section": "4.3 Phase Identification",
        "page": "67",
        "corpus_type": "manual",
        "instrument_id": "xrd-d8",
        "text": (
            "For polycrystalline ore minerals such as chalcopyrite (CuFeS2), use Cu Kα radiation "
            "with 2θ range 10–80° and step size 0.02°. Peak overlap with pyrite is common; "
            "compare against ICDD reference patterns. Sample preparation: finely ground powder "
            "in sample holder, surface level. Avoid excessive sample height (>1mm) which causes "
            "preferred orientation artifacts."
        ),
    },
    {
        "id": "xrd-manual-5.1",
        "source": "Bruker D8 Advance Manual",
        "section": "5.1 High-Strength Steel Analysis",
        "page": "89",
        "corpus_type": "manual",
        "instrument_id": "xrd-d8",
        "text": (
            "Martensitic and bainitic steel phases are best resolved using Co Kα or Mo Kα to "
            "minimize fluorescence from Fe. Recommended 2θ: 30–100°. Tube current should not "
            "exceed 40 mA if detector saturation errors (DET-SAT) have occurred recently."
        ),
    },
    {
        "id": "sem-manual-3.2",
        "source": "JEOL JSM-IT800 Manual",
        "section": "3.2 Fracture Surface Imaging",
        "page": "42",
        "corpus_type": "manual",
        "instrument_id": "sem-jeol",
        "text": (
            "For uncoated conductive samples (metals), accelerating voltage 10–20 kV is suitable "
            "for fracture surface morphology. Non-conductive or fine-feature samples require "
            "carbon coating (5–10 nm) at the sputter coater — typical coating time 90 seconds "
            "for 5mm specimens. Uncoated steel fracture surfaces may charge and degrade image quality."
        ),
    },
    {
        "id": "sem-manual-6.1",
        "source": "JEOL JSM-IT800 EDS/EBSD Attachment Guide",
        "section": "6.1 EDS vs EBSD Selection",
        "page": "112",
        "corpus_type": "manual",
        "instrument_id": "sem-jeol",
        "text": (
            "EDS is optimal for elemental mapping at grain boundaries and precipitate chemistry "
            "(e.g., hydrogen embrittlement studies). EBSD requires polished, carbon-coated samples "
            "and 70° stage tilt; use for crystallographic texture, not primary fracture morphology. "
            "For hydrogen embrittlement fracture surfaces, start with SE imaging + EDS before EBSD."
        ),
    },
    {
        "id": "icp-manual-2.4",
        "source": "Agilent 7900 ICP-MS Manual",
        "section": "2.4 Sample Types",
        "page": "31",
        "corpus_type": "manual",
        "instrument_id": "icp-ms",
        "text": (
            "ICP-MS requires complete sample dissolution. Not suitable for morphology, phase, or "
            "surface analysis. Ideal for trace element quantification in aqueous mine drainage, "
            "ore digests, and water samples. Detection limits ppt–ppb range for most metals."
        ),
    },
]

SOP_CHUNKS = [
    {
        "id": "sop-sem-coating",
        "source": "Mines SEM Lab SOP",
        "section": "Sample Preparation — Carbon Coating",
        "page": "3",
        "corpus_type": "sop",
        "instrument_id": "sem-jeol",
        "text": (
            "Station 2B: Carbon coater. Uncoated specimens must be coated before SEM session. "
            "5mm × 5mm steel samples: 90 second coating at 10 mA. Verify coating thickness "
            "with test slide if image charging occurs. Allow 15 min chamber pump-down after coating."
        ),
    },
    {
        "id": "sop-xrd-safety",
        "source": "Mines XRD Lab SOP",
        "section": "Safety and Warm-up",
        "page": "1",
        "corpus_type": "sop",
        "instrument_id": "xrd-d8",
        "text": (
            "X-ray shutter interlock must be verified before each session. Warm-up: 45 minutes "
            "from cold start. Log tube hours after each run. PPE: safety glasses required in bay."
        ),
    },
    {
        "id": "sop-sem-warmup",
        "source": "Mines SEM Lab SOP",
        "section": "Instrument Warm-up",
        "page": "5",
        "corpus_type": "sop",
        "instrument_id": "sem-jeol",
        "text": (
            "SEM warm-up procedure: 30 min. Steps: (1) Turn on filament, (2) Pump chamber to "
            "<5×10⁻⁴ Pa, (3) Set accelerating voltage to operating value, (4) Auto gun alignment, "
            "(5) Calibrate EDS detector. Do not open chamber during pump cycle."
        ),
    },
]

ERROR_CHUNKS = [
    {
        "id": "maint-xrd-sat",
        "source": "XRD Maintenance Log",
        "section": "DET-SAT History",
        "page": "",
        "corpus_type": "maintenance",
        "instrument_id": "xrd-d8",
        "text": (
            "Detector saturation errors (DET-SAT) occurred on three consecutive runs last month "
            "at tube current 40 mA with high-intensity steel samples. Recommend reducing to 30 mA "
            "and using Co Kα source until service completed."
        ),
    },
]


def all_corpus_chunks() -> list[dict]:
    from vein.rag.chunking import load_corpus_from_disk

    chunks = list(MANUAL_CHUNKS) + list(SOP_CHUNKS) + list(ERROR_CHUNKS)
    disk = load_corpus_from_disk()
    seen_ids = {c["id"] for c in chunks}
    for c in disk:
        if c["id"] not in seen_ids:
            chunks.append(c)
            seen_ids.add(c["id"])
    for log in _run_log_chunks():
        if log["id"] not in seen_ids:
            chunks.append(log)
    return chunks


def _run_log_chunks() -> list[dict]:
    from vein.db.database import get_run_logs

    chunks = []
    for log in get_run_logs(100):
        chunks.append({
            "id": f"run-{log['id']}",
            "source": "Historical Run Log",
            "section": f"Run #{log['id']}",
            "page": "",
            "corpus_type": "run_log",
            "instrument_id": log["instrument_id"],
            "text": (
                f"Researcher {log['researcher_name']} ran {log['material_type']} on "
                f"{log['instrument_id']}. Parameters: {log['parameters']}. "
                f"Outcome: {log['outcome']}. Quality: {log['quality_rating']}/5."
            ),
        })
    return chunks
