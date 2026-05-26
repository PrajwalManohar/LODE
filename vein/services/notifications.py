"""Campus & facility notifications feed for the dashboard.

Curated, referenced Colorado School of Mines content (news, circulars, facts,
research) plus an AI-generated "daily digest" that summarizes the feed in an
engaging way. The digest uses the configured LLM when available and falls back
to a written summary otherwise — so the feature is AI-powered but never breaks
the dashboard in demo mode.

Sources are real Mines pages (minesnewsroom.com, sif.mines.edu, cpr.org, etc.)
so every card can deep-link to its reference.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("vein.notifications")

# --- Curated CSM content (real, with references) ---------------------------
ANNOUNCEMENTS: list[dict] = [
    {
        "title": "Mines launches Critical Minerals Hub with National Laboratory of the Rockies",
        "body": "A new 50,000 sq ft lab + high-bay facility will accelerate the full "
                "critical-minerals value chain — from resource development and processing "
                "to manufacturing, recycling and workforce development.",
        "tag": "Partnership",
        "date": "2026-05-06",
        "url": "https://www.minesnewsroom.com/newsroom",
    },
    {
        "title": "2026 Faculty Awards recognize teaching, research and mentorship",
        "body": "University Distinguished Professor Rob Braun received the Faculty Excellence "
                "Award for pioneering work in fuel cells, hydrogen and energy-systems modeling, "
                "backed by nearly $30M in external funding.",
        "tag": "Awards",
        "date": "2026-04-28",
        "url": "https://www.minesnewsroom.com/news/2026-faculty-awards-recognize-excellence-teaching-research-and-mentorship",
    },
    {
        "title": "New Nature Synthesis paper opens a field of porous-materials chemistry",
        "body": "A Mines-led study reveals a method to build porous materials that could seed "
                "an entirely new field of materials chemistry.",
        "tag": "Research",
        "date": "2026-04-15",
        "url": "https://www.minesnewsroom.com/newsroom",
    },
    {
        "title": "Historic Edgar Mine to host a quantum-computing cryolab",
        "body": "Part of the dark, dusty gold-mine tunnel is being turned into a cryolab — a "
                "stable, ultra-cold environment to run quantum-computing experiments.",
        "tag": "Research",
        "date": "2026-03-02",
        "url": "https://www.cpr.org/2026/03/02/colorado-school-of-mines-quantum-lab/",
    },
    {
        "title": "Geophysics junior wins 2026 Goldwater Scholarship",
        "body": "Anna Williams was awarded one of the most prestigious STEM undergraduate "
                "scholarships for her work on air-sea interactions in intense tropical cyclones "
                "(part of a $9M Office of Naval Research project).",
        "tag": "Students",
        "date": "2026-03-28",
        "url": "https://www.minesnewsroom.com/news/mines-geophysics-student-wins-2026-goldwater-scholarship",
    },
]

# Facility circulars / operational policy (internal to the SIF).
CIRCULARS: list[dict] = [
    {
        "title": "Instrument time is reserved online",
        "body": "Reserve SIF instrument time through LODE. Staff-assisted analysis is available "
                "for a technical-assistance fee.",
        "tag": "Facility",
        "url": "https://sif.mines.edu/",
    },
    {
        "title": "Hazmat work requires EH&S sign-off",
        "body": "Experiments referencing HF, perchloric acid, or other flagged hazards must be "
                "run in an EH&S-approved hood and reviewed before a booking can proceed.",
        "tag": "Safety",
        "url": "https://www.mines.edu/environmental-health-safety/",
    },
    {
        "title": "Complete instrument-specific training first",
        "body": "New users must hold the required certification (e.g. SEM-Operator, "
                "XRD-Safety-101) before reservations are auto-approved by the safety gate.",
        "tag": "Training",
        "url": "https://sif.mines.edu/",
    },
]

FACTS: list[str] = [
    "Mines' Shared Instrumentation Facility spans 14 core areas — from atom-probe "
    "tomography and micro-CT to nanofabrication cleanrooms.",
    "Founded in 1874, Colorado School of Mines in Golden, CO is a top public university "
    "for earth, energy and the environment.",
    "The Edgar Experimental Mine in Idaho Springs is a real underground teaching mine "
    "used for hands-on instruction and research.",
    "SIF mass-spec includes a Thermo Orbitrap Exploris 240 and a Delta-Q isotope-ratio MS.",
    "The atom-probe core runs a Cameca LEAP 4000X Si for near-atomic 3D composition maps.",
]

RESEARCH_THEMES: list[dict] = [
    {"theme": "Critical minerals", "detail": "Resource → processing → manufacturing → recycling, end-to-end."},
    {"theme": "Hydrogen & energy systems", "detail": "Fuel cells and energy-systems modeling."},
    {"theme": "Quantum materials", "detail": "Cryogenic platforms for quantum-computing experiments."},
    {"theme": "Porous materials chemistry", "detail": "New synthesis routes (Nature Synthesis, 2026)."},
]


def _fallback_digest() -> str:
    return (
        "Good day from the Mines Shared Instrumentation Facility. Big news this month: "
        "the new Critical Minerals Hub with the National Laboratory of the Rockies, a "
        "Nature Synthesis breakthrough in porous materials, and a quantum cryolab taking "
        "shape inside the historic Edgar Mine. On the floor: book instrument time through "
        "LODE, finish your safety training first, and route any HF/perchloric work through "
        "EH&S. Have a productive day in the lab."
    )


def build_digest() -> str:
    """An engaging 2-4 sentence digest of today's feed. LLM when available,
    curated fallback otherwise (so it never breaks in demo mode)."""
    try:
        from vein.agents.llm import has_llm, invoke_text

        if not has_llm():
            return _fallback_digest()
        headlines = "; ".join(a["title"] for a in ANNOUNCEMENTS[:4])
        circ = "; ".join(c["title"] for c in CIRCULARS)
        system = (
            "You are LODE, the lab assistant for the Colorado School of Mines Shared "
            "Instrumentation Facility. Write a warm, engaging 2-3 sentence daily digest for "
            "researchers. Mention 1-2 campus highlights and 1 facility reminder. No preamble."
        )
        user = f"Campus highlights: {headlines}\nFacility reminders: {circ}"
        text = invoke_text(system, user, temperature=0.5).strip()
        return text or _fallback_digest()
    except Exception as exc:  # noqa: BLE001
        logger.warning("notifications digest fell back to curated copy: %s", exc)
        return _fallback_digest()


def get_feed() -> dict:
    """Everything the dashboard's Campus & Facility panel renders."""
    return {
        "digest": build_digest(),
        "announcements": ANNOUNCEMENTS,
        "circulars": CIRCULARS,
        "facts": FACTS,
        "research_themes": RESEARCH_THEMES,
        "source": "Colorado School of Mines — minesnewsroom.com & sif.mines.edu",
    }
