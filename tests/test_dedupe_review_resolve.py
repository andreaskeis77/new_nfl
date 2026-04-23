"""Operator resolution of meta.review_item (T2.7E-5)."""
from __future__ import annotations

import pytest

from new_nfl._db import connect
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.dedupe.review import (
    InvalidReviewActionError,
    ReviewItemAlreadyResolvedError,
    ReviewItemNotFoundError,
    ReviewResolution,
    resolve_review_item,
)
from new_nfl.settings import load_settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("NEW_NFL_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("NEW_NFL_SKIP_ONTOLOGY_AUTOLOAD", "1")
    settings = load_settings()
    bootstrap_local_environment(settings)
    return settings


def _seed_open_item(settings, review_item_id: str = "ri_42") -> str:
    con = connect(settings)
    try:
        con.execute(
            """
            INSERT INTO meta.review_item (
                review_item_id, dedupe_run_id, domain,
                left_record_id, right_record_id, score, block_key,
                left_payload_json, right_payload_json, status
            ) VALUES (?, 'run_1', 'player', 'L', 'R', 0.75, 'blk', '{}', '{}', 'open')
            """,
            [review_item_id],
        )
    finally:
        con.close()
    return review_item_id


def _load_item(settings, review_item_id: str):
    con = connect(settings)
    try:
        row = con.execute(
            """
            SELECT status, resolution, note, resolved_at
            FROM meta.review_item WHERE review_item_id = ?
            """,
            [review_item_id],
        ).fetchone()
    finally:
        con.close()
    return row


def test_resolve_merge_updates_status_and_resolution(settings):
    item_id = _seed_open_item(settings)
    result = resolve_review_item(
        settings, review_item_id=item_id, action="merge", notes="same player"
    )
    assert isinstance(result, ReviewResolution)
    assert result.new_status == "resolved"
    assert result.resolution == "merge"
    row = _load_item(settings, item_id)
    assert row[0] == "resolved"
    assert row[1] == "merge"
    assert row[2] == "same player"
    assert row[3] is not None


def test_resolve_reject_marks_resolved_with_reject_resolution(settings):
    item_id = _seed_open_item(settings, "ri_reject")
    resolve_review_item(settings, review_item_id=item_id, action="reject")
    row = _load_item(settings, item_id)
    assert row[0] == "resolved"
    assert row[1] == "reject"


def test_resolve_defer_marks_deferred_and_is_re_overridable(settings):
    item_id = _seed_open_item(settings, "ri_defer")
    first = resolve_review_item(
        settings, review_item_id=item_id, action="defer", notes="need birth date"
    )
    assert first.new_status == "deferred"
    # Deferred items can still be re-resolved (e.g. after more evidence).
    second = resolve_review_item(
        settings, review_item_id=item_id, action="merge"
    )
    assert second.previous_status == "deferred"
    assert second.new_status == "resolved"
    assert second.resolution == "merge"


def test_resolve_rejects_unknown_review_id(settings):
    with pytest.raises(ReviewItemNotFoundError):
        resolve_review_item(settings, review_item_id="ri_missing", action="merge")


def test_resolve_rejects_invalid_action(settings):
    item_id = _seed_open_item(settings, "ri_invalid_action")
    with pytest.raises(InvalidReviewActionError):
        resolve_review_item(
            settings, review_item_id=item_id, action="APPROVE"
        )


def test_resolve_refuses_to_overwrite_resolved(settings):
    item_id = _seed_open_item(settings, "ri_terminal")
    resolve_review_item(settings, review_item_id=item_id, action="reject")
    with pytest.raises(ReviewItemAlreadyResolvedError):
        resolve_review_item(
            settings, review_item_id=item_id, action="merge"
        )


def test_cli_dispatch_prints_fields_and_returns_zero(settings, capsys, monkeypatch):
    import sys

    from new_nfl.cli import main

    item_id = _seed_open_item(settings, "ri_cli")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "new-nfl",
            "dedupe-review-resolve",
            "--review-id",
            item_id,
            "--action",
            "merge",
            "--notes",
            "cli-path",
        ],
    )
    rc = main()
    out = capsys.readouterr().out
    assert rc == 0
    assert f"REVIEW_ITEM_ID={item_id}" in out
    assert "NEW_STATUS=resolved" in out
    assert "RESOLUTION=merge" in out
    assert "NOTES=cli-path" in out


def test_cli_dispatch_returns_nonzero_for_missing_review(settings, capsys, monkeypatch):
    import sys

    from new_nfl.cli import main

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "new-nfl",
            "dedupe-review-resolve",
            "--review-id",
            "does_not_exist",
            "--action",
            "merge",
        ],
    )
    rc = main()
    out = capsys.readouterr().out
    assert rc == 2
    assert "ERROR=not_found" in out


def test_cli_dispatch_returns_nonzero_for_already_resolved(
    settings, capsys, monkeypatch
):
    import sys

    from new_nfl.cli import main

    item_id = _seed_open_item(settings, "ri_twice")
    resolve_review_item(settings, review_item_id=item_id, action="merge")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "new-nfl",
            "dedupe-review-resolve",
            "--review-id",
            item_id,
            "--action",
            "reject",
        ],
    )
    rc = main()
    out = capsys.readouterr().out
    assert rc == 3
    assert "ERROR=already_resolved" in out
