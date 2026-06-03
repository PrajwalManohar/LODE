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
# Curated from the live Mines newsroom (minesnewsroom.com), refreshed for the
# June 2026 demo. Every item links to its real source article. Ordered newest
# first and skewed toward instrumentation / critical-minerals / facilities
# content that's directly relevant to the SIF and to LODE.
ANNOUNCEMENTS: list[dict] = [
    {
        "title": "Mines & ElementUSA win $67M DOE award to build rare-earth processing plant",
        "body": "The U.S. Department of Energy is funding a Louisiana facility to process rare "
                "earth elements and recover critical minerals — extending Mines' lead across "
                "the full critical-minerals value chain.",
        "tag": "Critical Minerals",
        "date": "2026-06-02",
        "url": "https://www.minesnewsroom.com/news/colorado-school-mines-and-elementusa-awarded-67m-doe-construction-rare-earth-processing-plant",
    },
    {
        "title": "Mark Van Dyke named Vice President for Research",
        "body": "Van Dyke will lead the university's research portfolio spanning energy, "
                "critical minerals, quantum and advanced materials — the domains the Shared "
                "Instrumentation Facility supports every day.",
        "tag": "Leadership",
        "date": "2026-06-02",
        "url": "https://www.minesnewsroom.com/news/mark-van-dyke-named-vice-president-research-colorado-school-mines",
    },
    {
        "title": "13 Mines students and alumni win NSF Graduate Research Fellowships",
        "body": "This year's recipients are pursuing work from quantum sensors to wildfire "
                "prevention, backed by the NSF's flagship graduate fellowship.",
        "tag": "Students",
        "date": "2026-05-29",
        "url": "https://www.minesnewsroom.com/news/13-mines-students-alumni-win-nsf-graduate-research-fellowships",
    },
    {
        "title": "$6.56M structural-modeling license expands geology instrumentation toolset",
        "body": "An educational license gives geology students and faculty advanced modeling "
                "software to test and validate structural data alongside lab characterization.",
        "tag": "Facility",
        "date": "2026-05-27",
        "url": "https://www.minesnewsroom.com/news/modeling-tools-allow-mines-geology-students-faculty-test-and-validate-structural-data-1",
    },
    {
        "title": "How Mines is positioned to lead the critical-minerals conversation",
        "body": "Leveraging 150 years of expertise plus a new 50,000 sq ft innovation & "
                "commercialization hub, Mines is tackling U.S. critical-minerals supply-chain "
                "challenges from exploration to processing.",
        "tag": "Critical Minerals",
        "date": "2026-05-26",
        "url": "https://www.minesnewsroom.com/news/rush-how-mines-positioned-lead-critical-minerals-conversation-exploration-and-processing",
    },
    {
        "title": "USGS–Mines Energy & Minerals Research Facility nears completion",
        "body": "The 190,000 sq ft building — set to open Fall 2026 — will house ~250 USGS "
                "researchers with 68 Mines researchers and 150 students working side by side on "
                "energy and mineral-resource questions.",
        "tag": "Facility",
        "date": "2026-05-20",
        "url": "https://www.minesnewsroom.com/news/colorado-school-mines-and-usgs-join-forces-address-geological-and-mineral-resource-questions",
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
    "The Mineral & Materials Characterization Facility (CMRS) pairs SEM-EDS, XRD and "
    "ICP-MS for full mineral-to-microstructure analysis.",
    "The USGS–Mines Energy & Minerals Research Facility (190,000 sq ft) opens Fall 2026, "
    "co-locating ~250 USGS and 68 Mines researchers.",
    "Mines' new 50,000 sq ft Critical Minerals Innovation & Commercialization Hub takes "
    "ideas from bench-scale proof-of-concept to pilot demonstration.",
    "The atom-probe core runs a Cameca LEAP 4000X Si for near-atomic 3D composition maps.",
]

RESEARCH_THEMES: list[dict] = [
    {"theme": "Critical minerals", "detail": "Exploration → processing → manufacturing → recycling, end-to-end."},
    {"theme": "Rare-earth recovery", "detail": "$67M DOE rare-earth processing plant with ElementUSA."},
    {"theme": "Energy & minerals (USGS)", "detail": "Joint 190,000 sq ft research facility opening Fall 2026."},
    {"theme": "Quantum & sensing", "detail": "NSF-fellowship work on quantum sensors and materials."},
    {"theme": "Space resources", "detail": "$5M Angel Family Foundation gift advancing planetary tech."},
]


def _fallback_digest() -> str:
    return (
        "Good day from the Mines Shared Instrumentation Facility. Big news this week: a "
        "$67M DOE award with ElementUSA to build a rare-earth processing plant, a new "
        "Vice President for Research, and 13 students and alumni winning NSF Graduate "
        "Research Fellowships. The USGS–Mines Energy & Minerals Research Facility is on "
        "track to open this fall. On the floor: book instrument time through LODE, finish "
        "your safety training first, and route any HF/perchloric work through EH&S. Have a "
        "productive day in the lab."
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
