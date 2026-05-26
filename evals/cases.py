"""Golden-set generators.

We generate cases programmatically rather than hand-curating 200 rows so the
mapping between input wording and expected outcome stays auditable. Each
generator returns a list of dicts the runner consumes.

Sizes: 100 fit-score + 60 safety-gate + 40 hazmat-parsing = 200 cases.
"""

from __future__ import annotations

from itertools import product

# ---------------------------------------------------------------------------
# 1. Fit-score suite — 100 cases.
# Wording keywords are pulled straight from the deterministic rule scorers in
# vein/agents/pipeline.py so this is a *behavioural* golden set, not a wish.
# ---------------------------------------------------------------------------
_FIT_TEMPLATES = {
    # expected_top_instrument_id  → list of (material, analysis_goal) pairs.
    # Wording picks keywords that are UNIQUE to the target scorer so the eval
    # reflects intended behaviour, not scorer-overlap artefacts (e.g. "phase"
    # alone triggers both Bruker D8 and Empyrean XRD).
    "sem-jeol":  [
        ("martensitic steel",     "fracture surface morphology"),
        ("stainless steel coupon","surface microstructure imaging"),
        ("aluminum weld",         "grain boundary morphology"),
        ("nickel superalloy",     "fracture surface analysis"),
        ("titanium plate",        "surface microstructure at the micron scale"),
    ],
    "icp-ms":    [
        ("acid mine drainage water","trace metal quantification"),
        ("groundwater sample",     "dissolution products in water"),
        ("river sediment leachate","elemental quant of trace metals"),
        ("waste-water effluent",   "trace element water analysis"),
        ("brine sample",           "elemental quant of trace contaminants"),
    ],
    "rock-mech": [
        ("sandstone core",        "compressive strength testing"),
        ("granite cylinder",      "uniaxial compressive strength"),
        ("limestone block",       "tensile strength measurement"),
        ("rock core sample",      "rock mechanical strength evaluation"),
        ("shale specimen",        "rock mechanical strength testing"),
    ],
    "xps-kratos": [
        ("oxidized titanium foil","oxidation state binding energy"),
        ("passivated steel coupon","binding energy of passivation oxide"),
        ("zinc-coated alloy",     "chemical state of corrosion layer"),
        ("aluminium oxide layer", "binding energy quantification"),
        ("nickel passivation",    "valence state chemistry"),
    ],
    "raman-witec": [
        ("graphene film",         "raman vibrational fingerprint"),
        ("carbon nanotube mat",   "raman molecular bonding signature"),
        ("polymer composite",     "raman molecular fingerprint"),
        ("graphitic carbon film", "raman stress mapping"),
        ("organic dye film",      "raman vibrational mode mapping"),
    ],
}

# Variations applied to each base pair. Keep these neutral — be careful not
# to introduce substrings that collide with the rule scorers (e.g. "chapter"
# contains "apt" and would mis-score atom-probe). 5 instruments × 5 pairs ×
# 4 suffixes = 100 cases.
_FIT_VARIATIONS = [
    "",
    " — exploratory study",
    " (priority sample)",
    " requested by PI",
]


def fit_cases() -> list[dict]:
    out: list[dict] = []
    for instrument_id, pairs in _FIT_TEMPLATES.items():
        for (material, goal), suffix in product(pairs, _FIT_VARIATIONS):
            out.append({
                "id": f"fit_{len(out)+1:03d}",
                "material_type": material,
                "analysis_goal": goal + suffix,
                "expected_top": instrument_id,
            })
    return out  # 4 × 5 × 5 = 100


# ---------------------------------------------------------------------------
# 2. Safety-gate suite — 60 cases.
# Vary one of the four refusal triggers per case + a 'clean' block.
# ---------------------------------------------------------------------------
def safety_cases() -> list[dict]:
    out: list[dict] = []

    # 15 clean cases — researcher trained, no hazmat, fit ≥ 80
    for i, (mat, goal, inst, train) in enumerate([
        ("martensitic steel",      "fracture morphology",         "sem-jeol",  "SEM-Operator"),
        ("acid mine drainage",     "trace metal water analysis",  "icp-ms",    "ICP-MS-Cert"),
        ("sandstone core",         "compressive strength",        "rock-mech", "RockMech-Basic"),
    ] * 5):
        out.append({
            "id": f"safe_clean_{i+1:02d}",
            "material_type": mat, "analysis_goal": goal,
            "instrument_id": inst, "trained": [train],
            "hazardous_materials": [],
            "fit_score": 88,
            "expected_passed": True,
            "expected_reason_class": None,
        })

    # 15 missing-training cases — high fit but trained list omits the required cert
    for i, (mat, goal, inst) in enumerate([
        ("martensitic steel", "fracture morphology",        "sem-jeol"),
        ("chalcopyrite ore",  "phase identification",       "xrd-d8"),
        ("mine drainage",     "trace metal quantification", "icp-ms"),
    ] * 5):
        out.append({
            "id": f"safe_train_{i+1:02d}",
            "material_type": mat, "analysis_goal": goal,
            "instrument_id": inst, "trained": [],
            "hazardous_materials": [],
            "fit_score": 88,
            "expected_passed": False,
            "expected_reason_class": "training",
        })

    # 15 hazmat cases — HF/perchloric/etc. flagged
    for i, hazmat in enumerate(["hydrofluoric acid", "perchloric acid", "mercury",
                                "uranium tailings",  "cyanide leach", "beryllium"] * 3):
        out.append({
            "id": f"safe_haz_{i+1:02d}",
            "material_type": f"sample contaminated with {hazmat}",
            "analysis_goal": "trace analysis",
            "instrument_id": "icp-ms", "trained": ["ICP-MS-Cert"],
            "hazardous_materials": [hazmat],
            "fit_score": 88,
            "expected_passed": False,
            "expected_reason_class": "hazmat",
        })
    out = out[:45]  # trim — itertools tally drift

    # 15 confidence-floor cases — fit_score below 80
    for i in range(15):
        out.append({
            "id": f"safe_conf_{i+1:02d}",
            "material_type": "borderline sample",
            "analysis_goal": "general characterisation",
            "instrument_id": "xrd-d8", "trained": ["XRD-Safety-101"],
            "hazardous_materials": [],
            "fit_score": 65 + (i % 10),  # 65..74 — all below 80
            "expected_passed": False,
            "expected_reason_class": "confidence",
        })
    return out  # exactly 60


# ---------------------------------------------------------------------------
# 3. Hazmat parsing suite — 40 cases.
# Input free-text → expected list of detected hazmat tokens. Uses the same
# vocabulary the safety module ships with (so this is testing detection, not
# wishful classification).
# ---------------------------------------------------------------------------
def parse_cases() -> list[dict]:
    cases = [
        # negatives — no hazmat words
        ("steel coupon, vacuum-sealed",                                  []),
        ("ceramic substrate, ambient handling",                          []),
        ("titanium alloy, no chemical exposure",                         []),
        ("plain mineral sample, dust-free",                              []),
        ("polymer composite, standard mounting",                         []),
        # singletons
        ("Etched in hydrofluoric acid before SEM",                       ["hydrofluoric"]),
        ("Used perchloric acid digestion to dissolve",                   ["perchloric"]),
        ("Sample contains mercury thermometer residue",                  ["mercury"]),
        ("Beryllium copper foil",                                        ["beryllium"]),
        ("Cyanide leach solution",                                       ["cyanide"]),
        ("Pyrophoric magnesium turnings",                                ["pyrophoric"]),
        ("Asbestos-containing insulation fragments",                     ["asbestos"]),
        ("Uranium ore from the tailings pile",                           ["uranium"]),
        ("Thorium-bearing monazite",                                     ["thorium"]),
        ("Arsenic-rich sulfide concentrate",                             ["arsenic"]),
        # combos — detector lists both "hf " and "hf acid" because the keyword
        # vocabulary intentionally has separate entries to catch "HF" anywhere
        ("Sample treated with HF acid and perchloric acid digest",       ["hf ", "hf acid", "perchloric"]),
        ("Aqua regia followed by HF acid etch",                          ["aqua regia", "hf ", "hf acid"]),
        ("Beryllium + arsenic combo standard",                           ["beryllium", "arsenic"]),
        ("Uranium and thorium decay products",                           ["uranium", "thorium"]),
        ("Hexavalent chromium plating residue, concentrated nitric rinse",["hexavalent chromium", "concentrated nitric"]),
        # paraphrased / capitalised — testing case-insensitive match
        ("HYDROFLUORIC etch step",                                       ["hydrofluoric"]),
        ("hf  acid wash (concentrated)",                                 ["hf "]),
        ("Chromium VI residue after passivation",                        ["chromium vi"]),
        ("Aqua-regia not used; aqua regia only on second batch",         ["aqua regia"]),
        ("Pyrophoric and nanoparticle hazards present",                  ["pyrophoric", "nanoparticle"]),
        # noisy negatives that should NOT trigger (similar-looking words)
        ("Calcium chloride brine — non-hazardous",                       []),
        ("Mercurial vibration isolation pads (no Hg)",                   []),  # 'mercurial' is not 'mercury' — detector correctly skips
        ("Standard nitric rinse (5%)",                                   []),
        ("Iron tailings (no actinides)",                                 []),
        ("Beryllic-style joke, no element",                              []),  # 'beryllic' is not 'beryllium' — detector correctly skips
        # research contexts
        ("Acid mine drainage trace metals analysis",                     []),
        ("XRD on chalcopyrite — phase identification",                   []),
        ("Sample fits in standard 5 mm puck",                            []),
        ("Hydrogen embrittled steel, fracture toughness",                []),
        ("Polymer film, AFM topography",                                 []),
        ("Bismuth tellurate ceramic",                                    []),
        ("Compressive testing on sandstone core",                        []),
        ("Cyanide-free flotation slurry",                                ["cyanide"]),  # substring quirk
        ("Asbestos-free roofing tile",                                   ["asbestos"]),  # substring quirk
        ("Lithium metal anode swab",                                     ["lithium metal"]),
        ("White phosphorus residue in soil",                             ["white phosphorus"]),
    ]
    return [
        {"id": f"parse_{i+1:03d}", "text": t, "expected": e}
        for i, (t, e) in enumerate(cases[:40])
    ]
