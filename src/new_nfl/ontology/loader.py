"""Ontology TOML loader (T2.4A, ADR-0026).

Parses ``ontology/<version>/term_*.toml`` files and projects them into the
``meta.ontology_*`` table family. Idempotent on ``content_sha256`` over the
sorted file payloads so repeated calls with identical sources are no-ops.

Only stdlib dependencies — TOML via :mod:`tomllib` (Python 3.12+).
"""
from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from new_nfl._db import connect, new_id, row_to_dict
from new_nfl.metadata import ensure_metadata_surface
from new_nfl.settings import Settings


class OntologyValueSetMember(BaseModel):
    value: str
    label: str | None = None
    ordinal: int | None = None


class OntologyValueSet(BaseModel):
    value_set_key: str
    label: str | None = None
    description: str | None = None
    members: list[OntologyValueSetMember]


class OntologyAlias(BaseModel):
    alias: str


class OntologyTerm(BaseModel):
    term_key: str
    label: str | None = None
    description: str | None = None
    source_path: str
    aliases: list[OntologyAlias]
    value_sets: list[OntologyValueSet]


class OntologyTermDetail(OntologyTerm):
    ontology_version_id: str
    version_label: str


@dataclass(frozen=True)
class OntologyLoadResult:
    ontology_version_id: str
    version_label: str
    source_dir: str
    content_sha256: str
    file_count: int
    term_count: int
    alias_count: int
    value_set_count: int
    value_set_member_count: int
    is_new: bool


def _iter_toml_files(source_dir: Path) -> list[Path]:
    if not source_dir.is_dir():
        raise ValueError(f"ontology source_dir does not exist: {source_dir}")
    files = sorted(p for p in source_dir.iterdir() if p.is_file() and p.suffix == ".toml")
    if not files:
        raise ValueError(f"ontology source_dir contains no .toml files: {source_dir}")
    return files


def _compute_content_sha256(files: list[Path]) -> str:
    hasher = hashlib.sha256()
    for path in files:
        hasher.update(path.name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\n---\n")
    return hasher.hexdigest()


def _parse_term_file(path: Path) -> OntologyTerm:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    term_key = str(data.get("term_key") or "").strip()
    if not term_key:
        raise ValueError(f"{path.name}: missing term_key")
    aliases_raw = data.get("aliases") or []
    if not isinstance(aliases_raw, list):
        raise ValueError(f"{path.name}: aliases must be a list")
    aliases = [OntologyAlias(alias=str(a).strip()) for a in aliases_raw if str(a).strip()]
    value_sets_raw = data.get("value_sets") or []
    if not isinstance(value_sets_raw, list):
        raise ValueError(f"{path.name}: value_sets must be an array of tables")
    value_sets: list[OntologyValueSet] = []
    for vs in value_sets_raw:
        vs_key = str(vs.get("key") or "").strip()
        if not vs_key:
            raise ValueError(f"{path.name}: value_set missing key")
        members_raw = vs.get("members") or []
        if not isinstance(members_raw, list):
            raise ValueError(f"{path.name}: value_set {vs_key} members must be a list")
        members = [
            OntologyValueSetMember(
                value=str(m.get("value") or "").strip(),
                label=(str(m["label"]).strip() if m.get("label") is not None else None),
                ordinal=(int(m["ordinal"]) if m.get("ordinal") is not None else None),
            )
            for m in members_raw
        ]
        for m in members:
            if not m.value:
                raise ValueError(f"{path.name}: value_set {vs_key} has empty member value")
        value_sets.append(
            OntologyValueSet(
                value_set_key=vs_key,
                label=(str(vs["label"]).strip() if vs.get("label") is not None else None),
                description=(
                    str(vs["description"]).strip() if vs.get("description") is not None else None
                ),
                members=members,
            )
        )
    return OntologyTerm(
        term_key=term_key,
        label=(str(data["label"]).strip() if data.get("label") is not None else None),
        description=(
            str(data["description"]).strip() if data.get("description") is not None else None
        ),
        source_path=path.name,
        aliases=aliases,
        value_sets=value_sets,
    )


def load_ontology_directory(
    settings: Settings,
    *,
    source_dir: Path | str,
    version_label: str | None = None,
    activate: bool = True,
) -> OntologyLoadResult:
    """Load a versioned ontology directory into ``meta.ontology_*`` idempotently."""
    ensure_metadata_surface(settings)
    source_path = Path(source_dir).resolve()
    files = _iter_toml_files(source_path)
    content_sha256 = _compute_content_sha256(files)
    version_label_final = version_label or source_path.name
    source_dir_str = str(source_path)

    terms = [_parse_term_file(p) for p in files]
    term_count = len(terms)
    alias_count = sum(len(t.aliases) for t in terms)
    value_set_count = sum(len(t.value_sets) for t in terms)
    value_set_member_count = sum(len(vs.members) for t in terms for vs in t.value_sets)

    con = connect(settings)
    try:
        existing = con.execute(
            """
            SELECT ontology_version_id
            FROM meta.ontology_version
            WHERE source_dir = ? AND content_sha256 = ?
            """,
            [source_dir_str, content_sha256],
        ).fetchone()
        if existing:
            ontology_version_id = existing[0]
            if activate:
                _activate_version(con, ontology_version_id, source_dir_str)
            return OntologyLoadResult(
                ontology_version_id=ontology_version_id,
                version_label=version_label_final,
                source_dir=source_dir_str,
                content_sha256=content_sha256,
                file_count=len(files),
                term_count=term_count,
                alias_count=alias_count,
                value_set_count=value_set_count,
                value_set_member_count=value_set_member_count,
                is_new=False,
            )

        ontology_version_id = new_id()
        con.execute(
            """
            INSERT INTO meta.ontology_version (
                ontology_version_id, version_label, source_dir, content_sha256,
                file_count, term_count, alias_count, value_set_count,
                value_set_member_count, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            """,
            [
                ontology_version_id,
                version_label_final,
                source_dir_str,
                content_sha256,
                len(files),
                term_count,
                alias_count,
                value_set_count,
                value_set_member_count,
            ],
        )
        for term in terms:
            term_id = new_id()
            con.execute(
                """
                INSERT INTO meta.ontology_term (
                    ontology_term_id, ontology_version_id, term_key,
                    label, description, source_path
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    term_id,
                    ontology_version_id,
                    term.term_key,
                    term.label,
                    term.description,
                    term.source_path,
                ],
            )
            for alias in term.aliases:
                con.execute(
                    """
                    INSERT INTO meta.ontology_alias (
                        ontology_alias_id, ontology_term_id, alias, alias_lower
                    ) VALUES (?, ?, ?, ?)
                    """,
                    [new_id(), term_id, alias.alias, alias.alias.lower()],
                )
            for vs in term.value_sets:
                vs_id = new_id()
                con.execute(
                    """
                    INSERT INTO meta.ontology_value_set (
                        ontology_value_set_id, ontology_term_id, value_set_key,
                        label, description
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    [vs_id, term_id, vs.value_set_key, vs.label, vs.description],
                )
                for member in vs.members:
                    con.execute(
                        """
                        INSERT INTO meta.ontology_value_set_member (
                            ontology_value_set_member_id, ontology_value_set_id,
                            value, value_lower, label, ordinal
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        [
                            new_id(),
                            vs_id,
                            member.value,
                            member.value.lower(),
                            member.label,
                            member.ordinal,
                        ],
                    )

        if activate:
            _activate_version(con, ontology_version_id, source_dir_str)
    finally:
        con.close()

    return OntologyLoadResult(
        ontology_version_id=ontology_version_id,
        version_label=version_label_final,
        source_dir=source_dir_str,
        content_sha256=content_sha256,
        file_count=len(files),
        term_count=term_count,
        alias_count=alias_count,
        value_set_count=value_set_count,
        value_set_member_count=value_set_member_count,
        is_new=True,
    )


def _activate_version(con: Any, ontology_version_id: str, source_dir: str) -> None:
    con.execute(
        "UPDATE meta.ontology_version SET is_active = FALSE WHERE source_dir = ? AND ontology_version_id <> ?",
        [source_dir, ontology_version_id],
    )
    con.execute(
        "UPDATE meta.ontology_version SET is_active = TRUE WHERE ontology_version_id = ?",
        [ontology_version_id],
    )


def _active_version_id(con: Any, source_dir: str | None = None) -> str | None:
    if source_dir:
        row = con.execute(
            """
            SELECT ontology_version_id
            FROM meta.ontology_version
            WHERE source_dir = ? AND is_active = TRUE
            ORDER BY loaded_at DESC
            LIMIT 1
            """,
            [source_dir],
        ).fetchone()
    else:
        row = con.execute(
            """
            SELECT ontology_version_id
            FROM meta.ontology_version
            WHERE is_active = TRUE
            ORDER BY loaded_at DESC
            LIMIT 1
            """,
        ).fetchone()
    return row[0] if row else None


def list_terms(settings: Settings) -> list[OntologyTermDetail]:
    """Return all terms in the currently active ontology version."""
    ensure_metadata_surface(settings)
    con = connect(settings)
    try:
        active_id = _active_version_id(con)
        if not active_id:
            return []
        version_row = row_to_dict(
            con,
            "SELECT ontology_version_id, version_label FROM meta.ontology_version WHERE ontology_version_id = ?",
            [active_id],
        )[0]
        term_rows = row_to_dict(
            con,
            """
            SELECT ontology_term_id, term_key, label, description, source_path
            FROM meta.ontology_term
            WHERE ontology_version_id = ?
            ORDER BY term_key
            """,
            [active_id],
        )
        return [
            _hydrate_term(con, active_id, version_row["version_label"], row)
            for row in term_rows
        ]
    finally:
        con.close()


def describe_term(settings: Settings, term_key: str) -> OntologyTermDetail | None:
    """Resolve ``term_key`` (or alias) against the active ontology version."""
    ensure_metadata_surface(settings)
    key = (term_key or "").strip().lower()
    if not key:
        return None
    con = connect(settings)
    try:
        active_id = _active_version_id(con)
        if not active_id:
            return None
        version_row = row_to_dict(
            con,
            "SELECT version_label FROM meta.ontology_version WHERE ontology_version_id = ?",
            [active_id],
        )[0]
        row = con.execute(
            """
            SELECT ontology_term_id, term_key, label, description, source_path
            FROM meta.ontology_term
            WHERE ontology_version_id = ? AND LOWER(term_key) = ?
            """,
            [active_id, key],
        ).fetchone()
        if row is None:
            alias_row = con.execute(
                """
                SELECT t.ontology_term_id, t.term_key, t.label, t.description, t.source_path
                FROM meta.ontology_alias a
                JOIN meta.ontology_term t ON t.ontology_term_id = a.ontology_term_id
                WHERE t.ontology_version_id = ? AND a.alias_lower = ?
                LIMIT 1
                """,
                [active_id, key],
            ).fetchone()
            if alias_row is None:
                return None
            row = alias_row
        row_dict = {
            "ontology_term_id": row[0],
            "term_key": row[1],
            "label": row[2],
            "description": row[3],
            "source_path": row[4],
        }
        return _hydrate_term(con, active_id, version_row["version_label"], row_dict)
    finally:
        con.close()


def _hydrate_term(
    con: Any,
    ontology_version_id: str,
    version_label: str,
    term_row: dict[str, Any],
) -> OntologyTermDetail:
    term_id = term_row["ontology_term_id"]
    alias_rows = row_to_dict(
        con,
        "SELECT alias FROM meta.ontology_alias WHERE ontology_term_id = ? ORDER BY alias",
        [term_id],
    )
    vs_rows = row_to_dict(
        con,
        """
        SELECT ontology_value_set_id, value_set_key, label, description
        FROM meta.ontology_value_set
        WHERE ontology_term_id = ?
        ORDER BY value_set_key
        """,
        [term_id],
    )
    value_sets: list[OntologyValueSet] = []
    for vs in vs_rows:
        member_rows = row_to_dict(
            con,
            """
            SELECT value, label, ordinal
            FROM meta.ontology_value_set_member
            WHERE ontology_value_set_id = ?
            ORDER BY COALESCE(ordinal, 999999), value
            """,
            [vs["ontology_value_set_id"]],
        )
        value_sets.append(
            OntologyValueSet(
                value_set_key=vs["value_set_key"],
                label=vs["label"],
                description=vs["description"],
                members=[
                    OntologyValueSetMember(
                        value=m["value"],
                        label=m["label"],
                        ordinal=m["ordinal"],
                    )
                    for m in member_rows
                ],
            )
        )
    return OntologyTermDetail(
        ontology_version_id=ontology_version_id,
        version_label=version_label,
        term_key=term_row["term_key"],
        label=term_row["label"],
        description=term_row["description"],
        source_path=term_row["source_path"],
        aliases=[OntologyAlias(alias=a["alias"]) for a in alias_rows],
        value_sets=value_sets,
    )
