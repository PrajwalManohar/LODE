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


# ---------------------------------------------------------------------------
# Additional Mines SIF instrument guides (for the 10 instruments added to the
# seed). Grounds SOP generation + fit rationale for the new instruments so
# their bookings cite real technique guidance, same as the original five.
# ---------------------------------------------------------------------------
INSTRUMENT_DOC_CHUNKS = [
    {
        "id": "tem-talos-guide-1", "source": "Mines SIF Instrument Guide — FEI Talos F200X",
        "section": "Imaging & STEM-EDS", "page": "1", "corpus_type": "manual", "instrument_id": "tem-talos",
        "text": (
            "The FEI Talos F200X is a 200 kV (scanning) transmission electron microscope with a "
            "high-brightness X-FEG source and four-detector Super-X EDS for fast elemental mapping. "
            "Use for atomic-scale imaging, selected-area and nano-beam diffraction, dislocation and "
            "precipitate analysis. Specimens must be electron-transparent (<100 nm) — prepare by "
            "twin-jet electropolishing, ion milling, or FIB lift-out. Beam-sensitive samples require "
            "reduced dose; check eucentric height before tilting."
        ),
    },
    {
        "id": "fib-helios-guide-1", "source": "Mines SIF Instrument Guide — Helios NanoLab 600i FIB-SEM",
        "section": "TEM Lamella & Cross-Sections", "page": "1", "corpus_type": "manual", "instrument_id": "fib-helios",
        "text": (
            "The Helios NanoLab 600i is a dual-beam Ga+ focused-ion-beam SEM for site-specific "
            "cross-sectioning and TEM lamella preparation by in-situ lift-out. Deposit a protective "
            "Pt cap before milling to avoid curtaining and beam damage. Coarse mill at high current, "
            "then polish at low current (≤93 pA) to <100 nm. Use for failure analysis, buried "
            "interfaces, and 3D serial sectioning. Charging on insulators requires a thin conductive coat."
        ),
    },
    {
        "id": "xrd-empyrean-guide-1", "source": "Mines SIF Instrument Guide — PANalytical Empyrean",
        "section": "Thin-Film, Texture & Residual Stress", "page": "1", "corpus_type": "manual", "instrument_id": "xrd-empyrean",
        "text": (
            "The PANalytical Empyrean supports Bragg-Brentano powder diffraction plus grazing-incidence "
            "(GIXRD) for thin films, pole-figure texture, reflectometry, and sin²ψ residual-stress "
            "measurement via interchangeable PreFIX optics. For steels use Co Kα to suppress Fe "
            "fluorescence. Powder samples: finely ground, surface level, <1 mm height to avoid preferred "
            "orientation. Complements the Bruker D8 for film and stress work."
        ),
    },
    {
        "id": "raman-witec-guide-1", "source": "Mines SIF Instrument Guide — WITec alpha300",
        "section": "Confocal Raman Mapping", "page": "1", "corpus_type": "manual", "instrument_id": "raman-witec",
        "text": (
            "The WITec alpha300 confocal Raman microscope provides vibrational/molecular fingerprinting "
            "with sub-micron spatial resolution and hyperspectral mapping. Common lasers 532/633 nm. "
            "Keep laser power low on carbon, polymers, and biological samples to avoid thermal damage "
            "(the D/G band ratio characterizes carbon disorder). Use for phase ID of molecular/covalent "
            "materials, stress mapping, and 2D-material layer counting."
        ),
    },
    {
        "id": "afm-asylum-guide-1", "source": "Mines SIF Instrument Guide — Asylum MFP-3D",
        "section": "Topography & Nanomechanics", "page": "1", "corpus_type": "manual", "instrument_id": "afm-asylum",
        "text": (
            "The Asylum MFP-3D atomic force microscope measures nanoscale topography, RMS roughness, "
            "and nanomechanical properties (modulus, adhesion) in contact, tapping, and force-mapping "
            "modes. Choose a tip by application: stiff cantilevers for hard surfaces, soft for delicate "
            "films. Samples must be flat, clean, and firmly mounted; vibration isolation is essential "
            "for atomic/step-edge resolution."
        ),
    },
    {
        "id": "xps-kratos-guide-1", "source": "Mines SIF Instrument Guide — Kratos XPS",
        "section": "Surface Chemistry & Oxidation State", "page": "1", "corpus_type": "manual", "instrument_id": "xps-kratos",
        "text": (
            "X-ray photoelectron spectroscopy (XPS/ESCA) quantifies elemental composition and chemical "
            "(oxidation) state in the top ~5–10 nm from core-level binding energies. Use a charge "
            "neutralizer for insulators and reference to adventitious C 1s at 284.8 eV. Ar+ sputter "
            "depth-profiling reveals layer structure (e.g., passive-film growth). Samples must be "
            "UHV-compatible: dry, vacuum-clean, outgassed; no volatiles."
        ),
    },
    {
        "id": "xct-versa-guide-1", "source": "Mines SIF Instrument Guide — Zeiss Xradia Versa 520",
        "section": "Non-Destructive 3D Micro-CT", "page": "1", "corpus_type": "manual", "instrument_id": "xct-versa",
        "text": (
            "The Zeiss Xradia Versa 520 performs non-destructive 3D X-ray micro-computed tomography with "
            "sub-micron resolution via dual-stage (geometric + optical) magnification. Use for internal "
            "porosity, cracks, voids, additive-manufacturing defects, and composite architecture without "
            "sectioning. Smaller samples and higher density yield finer resolution; scans range minutes "
            "to hours. Reconstruct and segment volumes for quantitative porosity."
        ),
    },
    {
        "id": "apt-leap-guide-1", "source": "Mines SIF Instrument Guide — Cameca LEAP 4000X Si",
        "section": "Atom Probe Tomography", "page": "1", "corpus_type": "manual", "instrument_id": "apt-leap",
        "text": (
            "The Cameca LEAP 4000X Si performs atom-probe tomography: 3D, near-atomic-resolution "
            "compositional maps with ppm-level sensitivity. Specimens are sharp needles (<100 nm tip "
            "radius) made by FIB annular milling. Laser-pulsing mode suits semiconductors/ceramics; "
            "voltage mode suits metals. Ideal for solute clustering, grain-boundary segregation, and "
            "nanoscale precipitate chemistry not resolvable by EDS."
        ),
    },
    {
        "id": "ms-orbitrap-guide-1", "source": "Mines SIF Instrument Guide — Thermo Orbitrap Exploris 240",
        "section": "High-Resolution LC-MS", "page": "1", "corpus_type": "manual", "instrument_id": "ms-orbitrap",
        "text": (
            "The Thermo Orbitrap Exploris 240 is a high-resolution accurate-mass LC-MS for organic and "
            "biomolecule analysis: small-molecule ID, metabolomics, and polymer/additive characterization. "
            "Electrospray (ESI) in positive/negative mode; sub-ppm mass accuracy enables formula "
            "assignment. Samples must be dissolved, filtered, and free of non-volatile salts/buffers. "
            "Not for bulk metals — see ICP-MS for trace-metal quantification."
        ),
    },
    {
        "id": "gleeble-3500-guide-1", "source": "Mines SIF Instrument Guide — Gleeble 3500",
        "section": "Thermomechanical Simulation", "page": "1", "corpus_type": "manual", "instrument_id": "gleeble-3500",
        "text": (
            "The DSI Gleeble 3500-GTC physically simulates thermomechanical processing: resistive heating "
            "to 1700+°C at up to 10,000°C/s with synchronized mechanical loading. Use for weld heat-affected-"
            "zone (HAZ) simulation, hot-ductility and hot-tensile tests, CCT/phase-transformation studies, "
            "and hot compression. Thermocouples must be percussion-welded to the specimen; verify grip "
            "alignment and water cooling before heating."
        ),
    },
    {
        "id": "xps-kratos-sop-1", "source": "Mines XPS Lab SOP",
        "section": "Vacuum & Charge Neutralization", "page": "1", "corpus_type": "sop", "instrument_id": "xps-kratos",
        "text": (
            "Load only dry, vacuum-clean samples (no fingerprints, oils, or volatiles); outgas porous "
            "samples in the load-lock overnight. Enable the charge neutralizer for insulating samples and "
            "verify the C 1s reference at 284.8 eV. Do not vent the analysis chamber. Record source power, "
            "pass energy, and sputter conditions in the post-run report."
        ),
    },
]

# ---------------------------------------------------------------------------
# Broader Mines knowledge: SIF handbook, EH&S regulations, responsible-AI
# guidance, technique-selection principles, and 2026 research highlights.
# Sourced from minesnewsroom.com & sif.mines.edu.
# ---------------------------------------------------------------------------
CSM_KNOWLEDGE_CHUNKS = [
    {
        "id": "sif-handbook-access", "source": "Mines SIF User Handbook",
        "section": "Access & Reservations", "page": "1", "corpus_type": "handbook", "instrument_id": "",
        "text": (
            "The Colorado School of Mines Shared Instrumentation Facility (SIF) provides centralized "
            "access to characterization and fabrication equipment across campus. Reserve instrument time "
            "online; new users must complete instrument-specific safety training before reservations are "
            "approved. Staff-assisted analysis is available for a technical-assistance fee. Instruments are "
            "organized into cores by technique and location."
        ),
    },
    {
        "id": "sif-handbook-cores", "source": "Mines SIF User Handbook",
        "section": "Core Areas", "page": "2", "corpus_type": "handbook", "instrument_id": "",
        "text": (
            "The SIF spans 14 core areas: Electron Microscopy; Mass Spectrometry; Materials Manufacturing; "
            "Mechanical Testing; Microscopy Sample Prep; Nanofabrication; Optical & Electrical Surface "
            "Characterization; Research Machine Shop; Scanning Probe & Optical Microscopy; Thin Film "
            "Deposition; Water Quality Analysis; X-ray Diffraction & CT; X-ray Photoelectron Spectroscopy; "
            "and Cleanrooms. Equipment ranges from atom-probe tomography to micro-CT and e-beam lithography."
        ),
    },
    {
        "id": "ehs-hazmat", "source": "Mines EH&S Lab Safety Manual",
        "section": "Hazardous Materials", "page": "4", "corpus_type": "regulation", "instrument_id": "",
        "text": (
            "Experiments involving hazardous materials — hydrofluoric or perchloric acid, mercury, "
            "beryllium, cyanide, arsenic, pyrophorics, or radioactive sources — require Environmental "
            "Health & Safety (EH&S) review and an approved fume hood before work begins. A current Safety "
            "Data Sheet (SDS) must be on file. HF requires calcium gluconate gel on hand. Declare all "
            "hazards at sample submission; LODE's safety gate escalates flagged materials for sign-off."
        ),
    },
    {
        "id": "ehs-ppe-xray", "source": "Mines EH&S Lab Safety Manual",
        "section": "PPE, X-ray & Radiation Safety", "page": "7", "corpus_type": "regulation", "instrument_id": "",
        "text": (
            "Safety glasses are mandatory in all instrument bays; closed-toe shoes and lab coats where "
            "indicated. X-ray instruments (XRD, micro-CT) use shielded enclosures with shutter interlocks "
            "that must be verified before each session — never defeat an interlock. Radiation-producing "
            "equipment users must complete radiation-safety training. Report any interlock fault or unusual "
            "exposure to EH&S immediately."
        ),
    },
    {
        "id": "ai-use-research", "source": "Mines Responsible AI Use Guidance",
        "section": "AI in Research & Lab Operations", "page": "1", "corpus_type": "policy", "instrument_id": "",
        "text": (
            "AI assistants (including LODE) support — but do not replace — researcher judgment. Keep a human "
            "in the loop for safety and approval decisions; the safety gate's refusals require human review. "
            "Verify AI-generated SOPs, parameters, and citations against authoritative manuals before use. "
            "Do not enter export-controlled, proprietary, or personally identifiable data into external AI "
            "tools. Disclose material AI assistance in publications per journal and Mines policy."
        ),
    },
    {
        "id": "ai-use-integrity", "source": "Mines Responsible AI Use Guidance",
        "section": "Data Handling & Academic Integrity", "page": "2", "corpus_type": "policy", "instrument_id": "",
        "text": (
            "Never fabricate or alter data with generative tools. AI may summarize, draft, or suggest, but "
            "results and conclusions must be reproducible from real measurements. Cite data sources and "
            "retain provenance (instrument, parameters, run logs). Respect privacy: booking and researcher "
            "details are visible only to the owner and authorized administrators."
        ),
    },
    {
        "id": "principles-technique-selection", "source": "Mines Materials Characterization Principles",
        "section": "Choosing the Right Technique", "page": "1", "corpus_type": "handbook", "instrument_id": "",
        "text": (
            "Match technique to question: XRD for crystalline phase ID and texture; SEM/EDS for surface "
            "morphology and micron-scale chemistry; TEM for nanostructure, defects, and lattice imaging; "
            "XPS for surface chemistry and oxidation state (top ~10 nm); ICP-MS/LC-MS for trace-element and "
            "molecular analysis of dissolved samples; AFM for nanoscale topography and mechanics; Raman for "
            "molecular/vibrational fingerprinting; micro-CT for non-destructive 3D internal structure; atom "
            "probe for 3D near-atomic composition. Combine complementary methods for a complete picture."
        ),
    },
    {
        "id": "research-critical-minerals", "source": "Mines Research Highlights 2026",
        "section": "Critical Minerals", "page": "1", "corpus_type": "research", "instrument_id": "",
        "text": (
            "Mines partnered with the U.S. Department of Energy's National Laboratory of the Rockies to "
            "advance critical-minerals innovation. The new 50,000 sq ft Critical Minerals Innovation & "
            "Commercialization Hub spans the full value chain — resource development, processing, "
            "manufacturing, recycling, and workforce development — relying heavily on SIF characterization "
            "(XRD, SEM/EDS, ICP-MS, atom probe) of ores, concentrates, and recovered materials."
        ),
    },
    {
        "id": "research-hydrogen-quantum", "source": "Mines Research Highlights 2026",
        "section": "Energy & Quantum", "page": "2", "corpus_type": "research", "instrument_id": "",
        "text": (
            "Active themes include hydrogen and fuel-cell energy-systems modeling, a Nature Synthesis "
            "breakthrough opening a field of porous-materials chemistry, and a quantum-computing cryolab "
            "being built inside the historic Edgar Mine. Materials for these programs are characterized at "
            "the SIF — e.g., XPS for catalyst surface chemistry and TEM for nanostructured membranes."
        ),
    },
    {
        "id": "sop-sample-submission", "source": "Mines Sample Submission SOP",
        "section": "General Sample Preparation", "page": "1", "corpus_type": "sop", "instrument_id": "",
        "text": (
            "Label every sample with researcher, date, and material. Declare all hazards and provide an SDS "
            "for any chemical exposure. Vacuum instruments (SEM, TEM, XPS, atom probe) require dry, "
            "outgassed, non-volatile specimens; non-conductive samples for electron microscopy need a thin "
            "conductive coating. Keep samples within the size/format limits of the chosen core, and record "
            "actual parameters in the LODE post-run report so the knowledge base stays current."
        ),
    },
]


def all_corpus_chunks() -> list[dict]:
    from vein.rag.chunking import load_corpus_from_disk

    chunks = (
        list(MANUAL_CHUNKS) + list(SOP_CHUNKS) + list(ERROR_CHUNKS)
        + list(INSTRUMENT_DOC_CHUNKS) + list(CSM_KNOWLEDGE_CHUNKS)
    )
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
