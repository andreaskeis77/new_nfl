"""Stage 1 — deterministic name normalization (T2.4B, ADR-0027 §1).

Stdlib only. Lowercase, NFKD-Diakritik-Strip, Suffix-Erkennung
(Jr./Sr./II/III/IV), Whitespace-Kollaps. Keine probabilistische Logik.
"""
from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field

_SUFFIX_PATTERN = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$", re.IGNORECASE)
_NON_NAME = re.compile(r"[^a-z0-9 \-']")
_WS = re.compile(r"\s+")


class RawPlayerRecord(BaseModel):
    """Single row going into the pipeline.

    ``record_id`` must be unique across the input set; the pipeline does not
    invent IDs because every Score/Review-Trace has to point back into
    something the operator can look up.
    """
    record_id: str
    full_name: str
    position: str | None = None
    birth_year: int | None = None
    source_ref: str | None = None


class NormalizedPlayer(BaseModel):
    record_id: str
    full_name: str
    full_name_normalized: str
    first_name: str
    last_name: str
    first_initial: str
    suffix: str | None = None
    position: str | None = None
    position_normalized: str | None = None
    birth_year: int | None = None
    source_ref: str | None = None
    extra_tokens: list[str] = Field(default_factory=list)


def _strip_diacritics(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _clean_name(value: str) -> str:
    cleaned = _strip_diacritics(value).lower()
    cleaned = cleaned.replace(".", " ")
    cleaned = _NON_NAME.sub(" ", cleaned)
    return _WS.sub(" ", cleaned).strip()


def normalize_player_record(record: RawPlayerRecord) -> NormalizedPlayer:
    cleaned = _clean_name(record.full_name)
    suffix: str | None = None
    if cleaned:
        match = _SUFFIX_PATTERN.search(cleaned)
        if match:
            suffix = match.group(1).lower()
            cleaned = _SUFFIX_PATTERN.sub("", cleaned).strip()
    tokens = [t for t in cleaned.split(" ") if t]
    if not tokens:
        first_name = ""
        last_name = ""
        extra: list[str] = []
    elif len(tokens) == 1:
        first_name = ""
        last_name = tokens[0]
        extra = []
    else:
        first_name = tokens[0]
        last_name = tokens[-1]
        extra = tokens[1:-1]
    first_initial = first_name[:1] if first_name else ""
    position_normalized = (
        record.position.strip().upper() if record.position and record.position.strip() else None
    )
    return NormalizedPlayer(
        record_id=record.record_id,
        full_name=record.full_name,
        full_name_normalized=" ".join(filter(None, [first_name, *extra, last_name])),
        first_name=first_name,
        last_name=last_name,
        first_initial=first_initial,
        suffix=suffix,
        position=record.position,
        position_normalized=position_normalized,
        birth_year=record.birth_year,
        source_ref=record.source_ref,
        extra_tokens=extra,
    )
