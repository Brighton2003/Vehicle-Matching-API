"""Natural-language search (bonus A): turn a sentence into structured criteria.

A small, dependency-free rule-based parser. It understands phrases such as
"I need an automatic Toyota SUV under R250k with less than 100,000 km".
Explicit structured fields on the request always take priority over anything
parsed from the sentence.
"""
import re
from collections.abc import Iterable

from app.enums import (
    BODY_TYPE_ALIASES, FUEL_TYPE_ALIASES, TRANSMISSION_ALIASES,
    BodyType, FuelType, Transmission, normalise, text_key,
)
from app.services.matching import BRAND_ALIASES

# 250,000 | 250 000 | 250000 | 250.5, optionally followed by k / m / million
_NUM = r"(\d{1,3}(?:[ ,]\d{3})+|\d+(?:\.\d+)?)\s*(k|m|million)?"
_LIMIT_WORDS = r"(?:under|below|less than|fewer than|max(?:imum)?(?: of)?|up to|within|not more than|<=?)"

_MILEAGE_RE = re.compile(rf"(?:{_LIMIT_WORDS}\s*)?{_NUM}\s*(?:km|kms|kilometres|kilometers)\b", re.I)
_BUDGET_KEYWORD_RE = re.compile(rf"(?:{_LIMIT_WORDS}|budget(?: of| is)?)\s*r?\s*{_NUM}(?!\s*(?:km|kms)\b)", re.I)
_BUDGET_RAND_RE = re.compile(rf"\br\s*{_NUM}", re.I)
_YEAR_AFTER_RE = re.compile(r"\b((?:19|20)\d{2})\s*(?:\+|or (?:newer|later)|and (?:newer|later))", re.I)
_YEAR_BEFORE_RE = re.compile(r"\b(?:from|since|newer than|after|no older than)\s+((?:19|20)\d{2})\b", re.I)

_TRANSMISSION_RE = re.compile(r"\b(automatic|auto|manual|stick|cvt|dct|tiptronic)\b", re.I)
_BODY_RE = re.compile(r"\b(suv|crossover|hatchback|hatch|sedan|saloon|bakkie|pick-?up|truck|coupe|minivan|mpv|van)\b", re.I)
_FUEL_RE = re.compile(r"\b(petrol|diesel|hybrid|electric|ev)\b", re.I)


def _to_number(raw: str, suffix: str | None) -> float:
    value = float(raw.replace(",", "").replace(" ", ""))
    if suffix:
        suffix = suffix.lower()
        value *= 1_000 if suffix == "k" else 1_000_000
    return value


def _cut(text: str, match: re.Match) -> str:
    """Blank out a matched span so later patterns don't re-use its digits."""
    return text[: match.start()] + " " + text[match.end():]


def _find_brand(text: str, known_makes: Iterable[str]) -> str | None:
    known = list(known_makes)
    candidates: list[tuple[str, str]] = []  # (phrase to look for, canonical make)
    for make in known:
        candidates.append((make, make))
        if "-" in make:
            candidates.append((make.split("-")[0], make))
    for alias, target in BRAND_ALIASES.items():
        canonical = next((m for m in known if text_key(m) == text_key(target)), None)
        if canonical:
            candidates.append((alias, canonical))
    # "merc" style abbreviations
    for make in known:
        if len(make) > 4:
            candidates.append((make[:4], make))

    best: tuple[int, str] | None = None
    for phrase, canonical in candidates:
        m = re.search(rf"\b{re.escape(phrase)}\b", text, re.I)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), canonical)
    return best[1] if best else None


def parse_query(text: str, known_makes: Iterable[str] = ()) -> dict:
    """Extract whatever requirements can be found. Returns only the keys found."""
    found: dict = {}
    remaining = text

    m = _MILEAGE_RE.search(remaining)
    if m:
        found["max_mileage"] = int(_to_number(m.group(1), m.group(2)))
        remaining = _cut(remaining, m)

    m = _YEAR_AFTER_RE.search(remaining) or _YEAR_BEFORE_RE.search(remaining)
    if m:
        found["min_year"] = int(m.group(1))
        remaining = _cut(remaining, m)

    m = _BUDGET_KEYWORD_RE.search(remaining) or _BUDGET_RAND_RE.search(remaining)
    if m:
        found["budget_max"] = _to_number(m.group(1), m.group(2))
        remaining = _cut(remaining, m)

    m = _TRANSMISSION_RE.search(remaining)
    if m:
        found["transmission"] = normalise(m.group(1), TRANSMISSION_ALIASES, Transmission)

    m = _BODY_RE.search(remaining)
    if m:
        found["body_type"] = normalise(m.group(1), BODY_TYPE_ALIASES, BodyType)

    m = _FUEL_RE.search(remaining)
    if m:
        found["fuel_type"] = normalise(m.group(1), FUEL_TYPE_ALIASES, FuelType)

    brand = _find_brand(remaining, known_makes)
    if brand:
        found["brand"] = brand

    return {k: v for k, v in found.items() if v is not None}
