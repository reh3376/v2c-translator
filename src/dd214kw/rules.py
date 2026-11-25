"""Rule-based keywords from pay grade, military education, decorations and service time.

These complement the O*NET-derived keywords. Every rule is a plain table so it can be
reviewed and edited; keywords are only emitted when the DD-214 shows direct evidence.
"""

from __future__ import annotations

import re

from .models import Keyword, ServiceRecord

# --------------------------------------------------------------------------- pay grade

LEADERSHIP_BY_GRADE: list[tuple[str, list[str]]] = [
    (r"E[1-3]", ["Teamwork", "Procedural Compliance"]),
    (r"E4", ["Teamwork", "Peer Training", "Procedural Compliance"]),
    (
        r"E[5-6]",
        [
            "First-Line Supervision",
            "Team Leadership",
            "On-the-Job Training",
            "Performance Counseling",
            "Equipment Accountability",
        ],
    ),
    (
        r"E[7-9]",
        [
            "Operations Management",
            "Personnel Management",
            "Training Program Management",
            "Resource Management",
            "Policy Implementation",
            "Mentoring",
        ],
    ),
    (r"E[8-9]", ["Organizational Leadership", "Strategic Planning", "Senior Advisor"]),
    (
        r"W[1-5]",
        [
            "Subject Matter Expert",
            "Technical Advisor",
            "Technical Program Management",
            "Systems Management",
        ],
    ),
    (
        r"O[1-3]",
        [
            "Project Management",
            "Department Management",
            "Operations Planning",
            "Personnel Management",
            "Risk Management",
        ],
    ),
    (
        r"O[4-6]",
        [
            "Senior Management",
            "Program Management",
            "Strategic Planning",
            "Budget Management",
            "Organizational Leadership",
        ],
    ),
    (r"O([7-9]|10)", ["Executive Leadership", "Enterprise Strategy", "Stakeholder Management"]),
]

# --------------------------------------------------------------------------- courses

IGNORE_COURSE_RE = re.compile(
    r"BASIC (COMBAT )?TRAINING|\bBCT\b|RECRUIT TRAINING|BASIC MILITARY TRAINING|\bBMT\b|"
    r"BOOT CAMP|ONE STATION UNIT|\bOSUT\b|INITIAL ENTRY"
)

COURSE_RULES: list[tuple[str, list[str]]] = [
    (
        r"BASIC LEADER|WARRIOR LEADER|PRIMARY LEADERSHIP|\bBLC\b|\bWLC\b|\bPLDC\b|"
        r"AIRMAN LEADERSHIP|\bALS\b|CORPORALS? COURSE|PETTY OFFICER.*LEADERSHIP|"
        r"LEADING PETTY OFFICER|LEADERSHIP COURSE",
        ["Leadership Training", "Team Supervision", "Performance Counseling"],
    ),
    (
        r"ADVANCED LEADER|\bALC\b|ANCOC|BNCOC|SENIOR LEADER COURSE|\bSLC\b|NCO ACADEMY|"
        r"SNCO ACADEMY|SERGEANTS COURSE|CHIEF PETTY OFFICER|MASTER LEADER|SERGEANTS MAJOR|"
        r"CAREER COURSE|STAFF COLLEGE|COMMAND AND GENERAL|WAR COLLEGE",
        ["Advanced Leadership", "Operations Management", "Organizational Planning"],
    ),
    (
        r"COMBAT LIFESAVER|\bCLS\b|TACTICAL COMBAT CASUALTY|\bTCCC\b|FIRST AID|\bCPR\b",
        ["First Aid", "CPR", "Emergency Response"],
    ),
    (
        r"\bEMT\b|EMERGENCY MEDICAL TECH|PARAMEDIC",
        ["Emergency Medical Technician (EMT)", "Patient Assessment", "Emergency Medical Services"],
    ),
    (
        r"HAZ(ARDOUS)?\s*MAT|HAZARDOUS (MATERIAL|WASTE)",
        ["Hazardous Materials Handling", "Environmental Compliance"],
    ),
    (r"SAFETY|\bOSHA\b", ["Workplace Safety", "OSHA Compliance", "Risk Assessment"]),
    (
        r"INSTRUCTOR|TRAIN THE TRAINER|FACILITATOR|INSTRUCTIONAL|DRILL SERGEANT|MILITARY TRAINING "
        r"INSTRUCTOR",
        ["Instructional Delivery", "Curriculum Development", "Training Facilitation"],
    ),
    (
        r"EQUAL OPPORTUNITY|\bEOL\b|\bSHARP\b|SEXUAL ASSAULT|VICTIM ADVOC|\bSARC\b",
        ["EEO Compliance", "Conflict Resolution", "Victim Advocacy"],
    ),
    (
        r"UNIT PREVENTION|\bUPL\b|DRUG TESTING|SUBSTANCE ABUSE",
        ["Drug Testing Program Administration", "Compliance Monitoring"],
    ),
    (
        r"SUPPLY|LOGISTIC|PROPERTY BOOK|INVENTORY|WAREHOUS",
        ["Inventory Management", "Supply Chain Operations", "Property Accountability"],
    ),
    (r"ARMORER|SMALL ARMS REPAIR", ["Weapons Maintenance", "Inventory Control"]),
    (r"FORKLIFT|MATERIAL HANDLING|\bMHE\b", ["Forklift Operation", "Material Handling"]),
    (
        r"CYBER|NETWORK|SECURITY\+|INFORMATION ASSURANCE|COMPTIA|CISCO|\bCCNA\b",
        ["Network Administration", "Cybersecurity"],
    ),
    (
        r"FITNESS TRAINER|MASTER FITNESS|FITNESS LEADER|PHYSICAL TRAINING LEADER",
        ["Fitness Program Design", "Health & Wellness Coaching"],
    ),
    (r"RESILIENCE|SUICIDE PREVENTION|\bASIST\b", ["Resilience Training", "Crisis Intervention"]),
    (
        r"BATTLE STAFF|STAFF NCO|OPERATIONS PLANNING|PLANNERS? COURSE",
        ["Operations Planning", "Staff Coordination"],
    ),
    (
        r"AIR ASSAULT|SLING LOAD|PATHFINDER",
        ["Sling Load Operations", "Load Inspection", "Aviation Ground Operations"],
    ),
    (
        r"DRIVER|VEHICLE OPERATOR|LICENSING|MOTOR TRANSPORT",
        ["Commercial Vehicle Operation", "Fleet Operations"],
    ),
    (r"FOOD SERVICE|CULINARY|\bCOOK", ["Food Service Operations", "Food Safety"]),
    (
        r"FINANCE|BUDGET|TRAVEL CARD|PURCHASE CARD|\bGPC\b|CONTRACTING",
        ["Budget Management", "Procurement", "Financial Compliance"],
    ),
    (
        r"MAINTENANCE|MECHANIC|REPAIR",
        ["Equipment Maintenance", "Preventive Maintenance", "Troubleshooting"],
    ),
    (
        r"LANGUAGE|LINGUIST|\bDLI\b",
        ["Foreign Language Proficiency", "Translation & Interpretation"],
    ),
    (r"INTELLIGENCE|ANALYST", ["Intelligence Analysis", "Research & Reporting"]),
    (r"FIRE ?FIGHT|FIRE PROTECTION|FIRE ACADEMY", ["Fire Protection", "Emergency Response"]),
    (
        r"MILITARY POLICE|SECURITY FORCES|LAW ENFORCEMENT|CORRECTIONS",
        ["Law Enforcement", "Physical Security", "Access Control"],
    ),
]

# --------------------------------------------------------------------------- decorations

PERFORMANCE_AWARD_RE = re.compile(
    r"MERITORIOUS SERVICE|BRONZE STAR|LEGION OF MERIT|COMMENDATION MEDAL|ACHIEVEMENT MEDAL|"
    r"DISTINGUISHED SERVICE|DEFENSE SUPERIOR"
)
AWARD_RULES: list[tuple[str, list[str]]] = [
    (r"GOOD CONDUCT", ["Dependability"]),
    (r"NCO PROFESSIONAL DEVELOPMENT|\bNCOPDR\b", ["Professional Development"]),
    (
        r"CAMPAIGN|EXPEDITIONARY MEDAL|OVERSEAS SERVICE|INHERENT RESOLVE|KOREA DEFENSE|\bNATO\b|"
        r"KOSOVO",
        ["International Operations", "Deployed Operations"],
    ),
    (r"SEA SERVICE|SEA DUTY", ["Maritime Operations"]),
    (r"DRIVER AND MECHANIC|DRIVER BADGE", ["Professional Vehicle Operation"]),
    (r"MARKSMAN|SHARPSHOOTER|EXPERT (RIFLE|PISTOL|MARKSMANSHIP)", ["Firearms Proficiency"]),
    (r"COMBAT MEDICAL|EXPERT FIELD MEDICAL", ["Trauma Care", "Emergency Medical Response"]),
    (r"AIR ASSAULT", ["Sling Load Operations", "Load Inspection"]),
    (r"HUMANITARIAN SERVICE", ["Disaster Response", "Humanitarian Operations"]),
    (r"VOLUNTEER SERVICE", ["Community Service", "Volunteer Leadership"]),
    (r"JOINT SERVICE|JOINT MERITORIOUS", ["Joint & Interagency Coordination"]),
    (
        r"UNIT (CITATION|COMMENDATION|AWARD)|VALOROUS UNIT|MERITORIOUS UNIT|OUTSTANDING UNIT|"
        r"SUPERIOR UNIT|EFFICIENCY",
        ["High-Performing Team"],
    ),
    (r"COMBAT ACTION|COMBAT INFANTRYMAN", ["Performance Under Pressure", "Crisis Decision-Making"]),
    (
        r"WARFARE SPECIALIST|\bESWS\b|\bEAWS\b|SUBMARINE|WARFARE INSIGNIA",
        ["Cross-Functional Systems Qualification"],
    ),
    (r"RECRUIT(ER|ING)", ["Recruiting", "Outreach & Relationship Building"]),
    (r"DRILL SERGEANT|INSTRUCTOR", ["Instructional Delivery"]),
]


ACRONYMS = {
    "NCO",
    "SNCO",
    "NCOPD",
    "NATO",
    "CPR",
    "EMT",
    "US",
    "USS",
    "BLC",
    "ALC",
    "SLC",
    "ALS",
    "WLC",
    "IT",
    "ET",
    "HAZMAT",
    "OSHA",
    "EO",
    "EOL",
    "SHARP",
    "UPL",
    "TCCC",
    "CLS",
    "DLI",
    "MP",
    "AF",
    "W/",
    "II",
    "III",
    "IV",
    "GPC",
    "MHE",
    "ESWS",
    "EAWS",
    "CBRN",
    "JAG",
    "AIT",
    "OSUT",
}
SMALL_WORDS = {"AND", "OR", "OF", "THE", "FOR", "IN", "ON", "TO", "WITH"}


def smart_title(s: str) -> str:
    """Title-case an all-caps military string without mangling acronyms or ordinals."""
    words = []
    for i, w in enumerate(s.split()):
        core = w.strip("(),.;:")
        if core.upper() in ACRONYMS or any(ch.isdigit() for ch in core) or "/" in core[1:-1]:
            words.append(w.upper())
        elif i and core.upper() in SMALL_WORDS:
            words.append(w.lower())
        else:
            words.append(w.capitalize() if not w.startswith("(") else "(" + w[1:].capitalize())
    return " ".join(words)


def _add(out: dict[str, Keyword], cat: str, term: str, score: float, source: str) -> None:
    key = f"{cat}:{term.casefold()}"
    if key in out:
        out[key].score = max(out[key].score, score)
        if source not in out[key].sources:
            out[key].sources.append(source)
    else:
        out[key] = Keyword(term=term, category=cat, score=score, sources=[source])


def _award_count(s: str) -> int:
    if m := re.search(r"\((\d+)\)|(\d+)(?:ST|ND|RD|TH)?\s*(?:AWARD|AWD|OLC|OAK)", s):
        return int(m.group(1) or m.group(2))
    return 1


def rule_keywords(rec: ServiceRecord) -> list[Keyword]:
    out: dict[str, Keyword] = {}

    # Pay grade -> leadership scope
    if pg := rec.pay_grade:
        for pat, terms in LEADERSHIP_BY_GRADE:
            if re.fullmatch(pat, pg):
                for t in terms:
                    _add(out, "leadership", t, 0.8, f"pay grade {pg}")

    # Military education
    for c in rec.education:
        u = c.title.upper()
        if IGNORE_COURSE_RE.search(u):
            continue
        label = smart_title(c.title) + (f" ({c.year})" if c.year else "")
        weight = 0.6 + min((c.weeks or 1) / 20, 0.3)
        _add(out, "training", label, weight, "military education")
        for pat, terms in COURSE_RULES:
            if re.search(pat, u):
                cat = "leadership" if "Leadership" in terms[0] else "skills"
                for t in terms:
                    _add(out, cat, t, weight, f"course: {smart_title(c.title)}")

    # Decorations
    perf = 0
    for d in rec.decorations:
        if PERFORMANCE_AWARD_RE.search(d):
            perf += _award_count(d)
        for pat, terms in AWARD_RULES:
            if re.search(pat, d):
                for t in terms:
                    _add(out, "recognition", t, 0.5, f"award: {smart_title(d)}")
    if perf:
        _add(
            out,
            "recognition",
            "Recognized for Performance Excellence",
            0.7,
            f"{perf} individual performance award{'s' if perf > 1 else ''}",
        )

    # Record of service
    if rec.branch:
        _add(out, "experience", f"U.S. {rec.branch} Veteran", 1.0, "block 2")
    months = rec.net_active.total_months if rec.net_active else 0
    if rec.prior_active:
        months += rec.prior_active.total_months
    if not months:
        months = sum(s.months or 0 for s in rec.specialties)
    if months >= 12:
        yrs = months // 12
        _add(out, "experience", f"{yrs}+ Years Professional Experience", 0.9, "record of service")
    if rec.foreign_service and not rec.foreign_service.is_zero:
        _add(out, "experience", "International Operations", 0.6, "foreign service time")
        _add(out, "experience", "Cross-Cultural Collaboration", 0.5, "foreign service time")
    if rec.sea_service and not rec.sea_service.is_zero:
        _add(out, "experience", "Maritime Operations", 0.6, "sea service time")

    return list(out.values())
