"""Staff directory with alpha-split routing helpers."""

import re
from dataclasses import dataclass

# Fallback agents for route hardening when alpha-split lookup fails
CL_AE_FALLBACK = "Rayvon"  # Commercial Lines AE fallback (G-O range, middle bucket)
PL_AE_FALLBACK = "Al"  # Personal Lines AE fallback (H-M range)
GENERAL_FALLBACK = "main_line"  # For when neither CL nor PL applies


@dataclass
class StaffMember:
    name: str
    department: str  # "CL AE", "PL Sales", "PL AE"
    ext: str
    alpha_range: tuple[str, str]  # e.g., ("A", "L")
    line_type: str  # "commercial" or "personal"


# Staff directory data
STAFF_DIRECTORY: list[StaffMember] = [
    # Commercial Lines Account Executives
    StaffMember(
        name="Adriana",
        department="CL AE",
        ext="7002",
        alpha_range=("A", "F"),
        line_type="commercial",
    ),
    StaffMember(
        name="Rayvon",
        department="CL AE",
        ext="7018",
        alpha_range=("G", "O"),
        line_type="commercial",
    ),
    StaffMember(
        name="Dionna",
        department="CL AE",
        ext="7006",
        alpha_range=("P", "Z"),
        line_type="commercial",
    ),
    # Personal Lines Sales
    StaffMember(
        name="Queens",
        department="PL Sales",
        ext="7010",
        alpha_range=("A", "L"),
        line_type="personal",
    ),
    StaffMember(
        name="Brad", department="PL Sales", ext="7007", alpha_range=("M", "Z"), line_type="personal"
    ),
    # Personal Lines Account Executives
    StaffMember(
        name="Yarislyn",
        department="PL AE",
        ext="7011",
        alpha_range=("A", "G"),
        line_type="personal",
    ),
    StaffMember(
        name="Al", department="PL AE", ext="7015", alpha_range=("H", "M"), line_type="personal"
    ),
    StaffMember(
        name="Luis", department="PL AE", ext="7017", alpha_range=("N", "Z"), line_type="personal"
    ),
]


def normalize_last_name(name_or_spelling: str) -> str:
    """Extract first letter of last name for routing.

    Args:
        name_or_spelling: A name like "John Smith" or spelled "S-M-I-T-H"

    Returns:
        Uppercase first letter for routing (e.g., "S")
    """
    if not name_or_spelling:
        return ""

    text = name_or_spelling.strip().upper()

    # Handle spelled names like "S-M-I-T-H" or "G-A-R-C-I-A"
    if "-" in text:
        parts = text.split("-")
        if parts and parts[0]:
            return parts[0][0]

    # Handle "John Smith" -> take last word's first letter
    words = text.split()
    if words:
        last_word = words[-1]
        if last_word:
            return last_word[0]

    return ""


def normalize_business_name(name: str) -> str:
    """Extract first significant letter of business name for routing.

    Args:
        name: Business name like "The Acme Company" or "Law Offices of Smith"

    Returns:
        Uppercase first letter for routing (e.g., "A" or "S")
    """
    if not name:
        return ""

    text = name.strip().upper()

    # Strip common prefixes
    prefixes = ["THE ", "LAW OFFICES OF ", "LAW OFFICE OF ", "OFFICES OF ", "OFFICE OF "]
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break

    # Strip punctuation and get first letter
    text = re.sub(r"[^\w\s]", "", text).strip()

    if text:
        return text[0]

    return ""


def alpha_in_range(letter: str, range_tuple: tuple[str, str]) -> bool:
    """Check if letter falls in alpha range (inclusive).

    Args:
        letter: Single uppercase letter
        range_tuple: Tuple of (start, end) letters

    Returns:
        True if letter is in range [start, end]
    """
    if not letter:
        return False

    letter = letter.upper()
    start, end = range_tuple[0].upper(), range_tuple[1].upper()

    return start <= letter <= end


def pick_pl_sales(last_name: str) -> StaffMember:
    """Pick PL Sales staff member by last name alpha split.

    Args:
        last_name: Caller's last name or spelled name

    Returns:
        StaffMember for Queens (A-L) or Brad (M-Z)
    """
    letter = normalize_last_name(last_name)

    # A-L -> Queens
    if alpha_in_range(letter, ("A", "L")):
        return next(s for s in STAFF_DIRECTORY if s.name == "Queens")

    # M-Z -> Brad (default)
    return next(s for s in STAFF_DIRECTORY if s.name == "Brad")


def pick_pl_ae(last_name: str) -> StaffMember:
    """Pick PL AE staff member by last name alpha split.

    Args:
        last_name: Caller's last name or spelled name

    Returns:
        StaffMember for Yarislyn (A-G), Al (H-M), or Luis (N-Z)
    """
    letter = normalize_last_name(last_name)

    # A-G -> Yarislyn
    if alpha_in_range(letter, ("A", "G")):
        return next(s for s in STAFF_DIRECTORY if s.name == "Yarislyn")

    # H-M -> Al
    if alpha_in_range(letter, ("H", "M")):
        return next(s for s in STAFF_DIRECTORY if s.name == "Al")

    # N-Z -> Luis (default)
    return next(s for s in STAFF_DIRECTORY if s.name == "Luis")


def pick_cl_ae(business_name: str) -> StaffMember:
    """Pick CL AE staff member by business name alpha split.

    Args:
        business_name: Business name

    Returns:
        StaffMember for Adriana (A-F), Rayvon (G-O), or Dionna (P-Z)
    """
    letter = normalize_business_name(business_name)

    # A-F -> Adriana
    if alpha_in_range(letter, ("A", "F")):
        return next(s for s in STAFF_DIRECTORY if s.name == "Adriana")

    # G-O -> Rayvon
    if alpha_in_range(letter, ("G", "O")):
        return next(s for s in STAFF_DIRECTORY if s.name == "Rayvon")

    # P-Z -> Dionna (default)
    return next(s for s in STAFF_DIRECTORY if s.name == "Dionna")


__all__ = [
    "StaffMember",
    "STAFF_DIRECTORY",
    "CL_AE_FALLBACK",
    "PL_AE_FALLBACK",
    "GENERAL_FALLBACK",
    "normalize_last_name",
    "normalize_business_name",
    "alpha_in_range",
    "pick_pl_sales",
    "pick_pl_ae",
    "pick_cl_ae",
]
