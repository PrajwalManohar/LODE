from vein.db.database import get_conn, init_db


INSTRUMENTS = [
    {
        "id": "xrd-d8",
        "name": "Bruker D8 Advance XRD",
        "type": "XRD",
        "manufacturer": "Bruker",
        "model": "D8 Advance",
        "location": "Hill Hall 204",
        "warmup_minutes": 45,
        "cooldown_minutes": 20,
        "status": "operational",
        "required_training": "XRD-Safety-101",
        "calibration_interval_hours": 500,
        "last_calibrated_at": None,
    },
    {
        "id": "sem-jeol",
        "name": "JEOL JSM-IT800 SEM-EDS",
        "type": "SEM",
        "manufacturer": "JEOL",
        "model": "JSM-IT800",
        "location": "Brown Hall B12",
        "warmup_minutes": 30,
        "cooldown_minutes": 15,
        "status": "operational",
        "required_training": "SEM-Operator",
        "calibration_interval_hours": 400,
        "last_calibrated_at": None,
    },
    {
        "id": "icp-ms",
        "name": "Agilent 7900 ICP-MS",
        "type": "ICP-MS",
        "manufacturer": "Agilent",
        "model": "7900",
        "location": "Hill Hall 118",
        "warmup_minutes": 60,
        "cooldown_minutes": 30,
        "status": "operational",
        "required_training": "ICP-MS-Cert",
        "calibration_interval_hours": 300,
        "last_calibrated_at": None,
    },
    {
        "id": "rock-mech",
        "name": "MTS Rock Mechanics Test Rig",
        "type": "Rock Mechanics",
        "manufacturer": "MTS",
        "model": "Criterion C44",
        "location": "Brown Hall G04",
        "warmup_minutes": 20,
        "cooldown_minutes": 10,
        "status": "operational",
        "required_training": "RockMech-Basic",
        "calibration_interval_hours": 800,
        "last_calibrated_at": None,
    },
    {
        "id": "tube-furnace",
        "name": "High-Temperature Tube Furnace",
        "type": "Furnace",
        "manufacturer": "Thermo Scientific",
        "model": "HTF-1200",
        "location": "Hill Hall 210",
        "warmup_minutes": 90,
        "cooldown_minutes": 60,
        "status": "maintenance",
        "required_training": "Furnace-Safety",
        "calibration_interval_hours": 600,
        "last_calibrated_at": None,
    },
    # --- Additional Mines Shared Instrumentation Facility (SIF) instruments ---
    # Modeled on the real SIF cores (sif.mines.edu). Buildings reflect Mines'
    # campus (Hill Hall = metallurgy/materials; CoorsTek/CASE; Coolbaugh = chem).
    {
        "id": "tem-talos",
        "name": "FEI Talos F200X (S)TEM",
        "type": "TEM",
        "manufacturer": "FEI / Thermo Fisher",
        "model": "Talos F200X",
        "location": "Hill Hall 50 (EM Lab)",
        "warmup_minutes": 60,
        "cooldown_minutes": 30,
        "status": "operational",
        "required_training": "TEM-Operator",
        "calibration_interval_hours": 600,
        "last_calibrated_at": None,
    },
    {
        "id": "fib-helios",
        "name": "FEI Helios NanoLab 600i FIB-SEM",
        "type": "FIB-SEM",
        "manufacturer": "FEI / Thermo Fisher",
        "model": "Helios NanoLab 600i",
        "location": "Hill Hall 50 (EM Lab)",
        "warmup_minutes": 45,
        "cooldown_minutes": 20,
        "status": "operational",
        "required_training": "FIB-SEM-Cert",
        "calibration_interval_hours": 500,
        "last_calibrated_at": None,
    },
    {
        "id": "xrd-empyrean",
        "name": "PANalytical Empyrean XRD",
        "type": "XRD",
        "manufacturer": "Malvern PANalytical",
        "model": "Empyrean",
        "location": "Hill Hall 230 (XRD & CT)",
        "warmup_minutes": 45,
        "cooldown_minutes": 20,
        "status": "operational",
        "required_training": "XRD-Safety-101",
        "calibration_interval_hours": 450,
        "last_calibrated_at": None,
    },
    {
        "id": "raman-witec",
        "name": "WITec alpha300 Confocal Raman",
        "type": "Raman",
        "manufacturer": "WITec",
        "model": "alpha300 R",
        "location": "Hill Hall 52 (Scanning Probe & Optical)",
        "warmup_minutes": 30,
        "cooldown_minutes": 15,
        "status": "operational",
        "required_training": "Raman-Basic",
        "calibration_interval_hours": 400,
        "last_calibrated_at": None,
    },
    {
        "id": "afm-asylum",
        "name": "Asylum MFP-3D AFM",
        "type": "AFM",
        "manufacturer": "Asylum Research / Oxford",
        "model": "MFP-3D",
        "location": "Hill Hall 52 (Scanning Probe & Optical)",
        "warmup_minutes": 20,
        "cooldown_minutes": 10,
        "status": "operational",
        "required_training": "AFM-Operator",
        "calibration_interval_hours": 400,
        "last_calibrated_at": None,
    },
    {
        "id": "xps-kratos",
        "name": "X-ray Photoelectron Spectrometer (XPS)",
        "type": "XPS",
        "manufacturer": "Kratos",
        "model": "AXIS Supra",
        "location": "CoorsTek 140 (Surface Analysis)",
        "warmup_minutes": 60,
        "cooldown_minutes": 30,
        "status": "operational",
        "required_training": "XPS-Operator",
        "calibration_interval_hours": 500,
        "last_calibrated_at": None,
    },
    {
        "id": "xct-versa",
        "name": "Zeiss Xradia Versa 520 micro-CT",
        "type": "X-ray CT",
        "manufacturer": "Zeiss",
        "model": "Xradia Versa 520",
        "location": "Hill Hall 230 (XRD & CT)",
        "warmup_minutes": 40,
        "cooldown_minutes": 20,
        "status": "operational",
        "required_training": "XCT-Basic",
        "calibration_interval_hours": 600,
        "last_calibrated_at": None,
    },
    {
        "id": "apt-leap",
        "name": "Cameca LEAP 4000X Si Atom Probe",
        "type": "Atom Probe Tomography",
        "manufacturer": "Cameca",
        "model": "LEAP 4000X Si",
        "location": "CoorsTek 145 (Atom Probe Core)",
        "warmup_minutes": 90,
        "cooldown_minutes": 45,
        "status": "operational",
        "required_training": "APT-Operator",
        "calibration_interval_hours": 700,
        "last_calibrated_at": None,
    },
    {
        "id": "ms-orbitrap",
        "name": "Thermo Orbitrap Exploris 240 LC-MS",
        "type": "Mass Spectrometry",
        "manufacturer": "Thermo Scientific",
        "model": "Orbitrap Exploris 240",
        "location": "Coolbaugh Hall 215 (Mass Spec)",
        "warmup_minutes": 60,
        "cooldown_minutes": 30,
        "status": "operational",
        "required_training": "MS-Operator",
        "calibration_interval_hours": 300,
        "last_calibrated_at": None,
    },
    {
        "id": "gleeble-3500",
        "name": "DSI Gleeble 3500-GTC Thermomechanical Simulator",
        "type": "Thermomechanical",
        "manufacturer": "Dynamic Systems Inc.",
        "model": "Gleeble 3500-GTC",
        "location": "Hill Hall G10 (Mechanical Testing)",
        "warmup_minutes": 45,
        "cooldown_minutes": 30,
        "status": "operational",
        "required_training": "Gleeble-Safety",
        "calibration_interval_hours": 800,
        "last_calibrated_at": None,
    },
]

RUN_LOGS = [
    ("xrd-d8", "Dr. Martinez", "chalcopyrite", "2θ: 10-80°, Cu Kα, step 0.02°", "Clear pyrite peaks identified", 5),
    ("sem-jeol", "A. Chen", "martensitic steel", "15 kV, EDS mapping, carbon coated", "Fracture surface morphology captured", 4),
    ("icp-ms", "J. Okonkwo", "mine drainage water", "43 elements, dilution 1:100", "Trace Cu, Zn above detection", 5),
    ("xrd-d8", "S. Patel", "high-strength steel", "2θ: 30-100°, Co Kα", "Martensite phase confirmed", 4),
    ("sem-jeol", "M. Thompson", "hydrogen embrittled steel", "20 kV, EBSD, 70° tilt", "Grain boundary decohesion visible", 5),
]

MAINTENANCE = [
    ("xrd-d8", "DET-SAT", "Detector saturation on high-intensity peak", "Reduced tube current to 30 mA", "warning"),
    ("xrd-d8", "DET-SAT", "Detector saturation error repeated", "Scheduled detector service", "critical"),
    ("sem-jeol", "VAC-LOW", "Chamber pressure above threshold", "Pumped down, O-ring inspected", "warning"),
    ("tube-furnace", "TEMP-DRIFT", "Setpoint drift >15°C at 1100°C", "Thermocouple recalibration scheduled", "critical"),
]


def seed_database() -> None:
    init_db()
    with get_conn() as conn:
        # Upsert instruments by id so new SIF instruments get added on the next
        # boot WITHOUT wiping existing rows (ON CONFLICT DO NOTHING). This
        # replaces the old all-or-nothing guard, which skipped new instruments
        # once the table had any rows.
        for inst in INSTRUMENTS:
            conn.execute(
                """INSERT INTO instruments (id, name, type, manufacturer, model, location,
                   warmup_minutes, cooldown_minutes, status, required_training,
                   calibration_interval_hours, last_calibrated_at)
                   VALUES (%(id)s, %(name)s, %(type)s, %(manufacturer)s, %(model)s, %(location)s,
                   %(warmup_minutes)s, %(cooldown_minutes)s, %(status)s, %(required_training)s,
                   %(calibration_interval_hours)s, %(last_calibrated_at)s)
                   ON CONFLICT (id) DO NOTHING""",
                inst,
            )

        # Demo run/maintenance history seeds only once (when empty) to avoid dups.
        rl_count = conn.execute("SELECT COUNT(*) AS n FROM run_logs").fetchone()["n"]
        if rl_count and rl_count > 0:
            return

        for i, (inst_id, researcher, material, params, outcome, quality) in enumerate(RUN_LOGS):
            conn.execute(
                """INSERT INTO run_logs (instrument_id, researcher_name, material_type,
                   parameters, outcome, quality_rating, run_date)
                   VALUES (%s, %s, %s, %s, %s, %s, now() - make_interval(days => %s))""",
                (inst_id, researcher, material, params, outcome, quality, i * 7),
            )

        for i, (inst_id, code, desc, action, sev) in enumerate(MAINTENANCE):
            conn.execute(
                """INSERT INTO maintenance_logs (instrument_id, error_code, description,
                   action_taken, severity, logged_at)
                   VALUES (%s, %s, %s, %s, %s, now() - make_interval(days => %s))""",
                (inst_id, code, desc, action, sev, i * 5),
            )
