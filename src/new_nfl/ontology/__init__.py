"""Ontology-as-Code surface (T2.4A, ADR-0026).

Public entry points used by the CLI and tests.
"""
from __future__ import annotations

from new_nfl.ontology.loader import (
    OntologyAlias,
    OntologyLoadResult,
    OntologyTerm,
    OntologyTermDetail,
    OntologyValueSet,
    OntologyValueSetMember,
    describe_term,
    list_terms,
    load_ontology_directory,
)

__all__ = [
    "OntologyAlias",
    "OntologyLoadResult",
    "OntologyTerm",
    "OntologyTermDetail",
    "OntologyValueSet",
    "OntologyValueSetMember",
    "describe_term",
    "list_terms",
    "load_ontology_directory",
]
