"""T3.1S — live HTTP smoke for the seven primary slices.

The default-cut Pytest run (``addopts = -q -m 'not network'``) excludes
this module. Operators run it on demand before a release cut::

    pytest -m network

Why it exists: the v1.0 cut had no end-to-end HTTP gate against the real
nflverse-data release URLs. Two upstream drifts (URL move + column rename)
landed on 2026-04-24 and slipped past the 445-test default suite because
every test relied on fixtures or ``remote_url_override``. The lesson on
the same date prescribes a network-marker smoke that exercises every
primary slice URL once. This module is that smoke.

Coverage:

- The four static-URL slices (``schedule_field_dictionary``, ``teams``,
  ``games``, ``players``) are probed at the URL declared on their
  ``SliceSpec.remote_url``.
- The three per-season slices (``rosters``, ``team_stats_weekly``,
  ``player_stats_weekly``) are probed for a pinned reference season; the
  pinned year is a closed NFL season (2024) so the asset is guaranteed
  to exist regardless of when the smoke runs.

Failure semantics: HTTP 200 with a non-empty body and a comma in the
first line (CSV header heuristic). HEAD is preferred to avoid bandwidth;
GitHub release-asset URLs follow redirects and can return non-200 on
HEAD, so the helper falls back to a small GET on any non-200 HEAD.
"""
from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from new_nfl.adapters.slices import SLICE_REGISTRY, SliceSpec, resolve_remote_url

# Pin the per-season probe to the latest fully closed NFL season at the
# time of T3.1S. Deliberately not coupled to ``default_nfl_season`` so a
# calendar-flip mid-test cannot cause a green-to-red transition for a
# reason that has nothing to do with the asset's availability.
PINNED_SMOKE_SEASON = 2024

NETWORK_TIMEOUT_SECONDS = 30.0


def _primary_slices() -> list[SliceSpec]:
    return [
        spec
        for spec in SLICE_REGISTRY.values()
        if spec.tier_role == 'primary' and spec.adapter_id == 'nflverse_bulk'
    ]


def _probe(url: str) -> tuple[int, bytes]:
    """Return ``(http_status, first_kib_of_body)`` for *url*.

    Tries HEAD first; falls back to a 1-KiB ranged GET on any non-200
    HEAD. GitHub release assets answer HEAD with 302 + Location to the
    pre-signed S3 URL, so the helper follows redirects in either path.
    """
    head_request = urllib.request.Request(url, method='HEAD')
    try:
        with urllib.request.urlopen(head_request, timeout=NETWORK_TIMEOUT_SECONDS) as resp:
            if resp.status == 200:
                return resp.status, b''
    except urllib.error.HTTPError as exc:
        if exc.code != 405:  # 405 Method Not Allowed -> fall through to GET
            raise
    except urllib.error.URLError:
        # Connection-level failures should propagate as test failures
        # rather than be silently downgraded to GET; the operator needs
        # the network signal.
        raise

    get_request = urllib.request.Request(url, headers={'Range': 'bytes=0-1023'})
    with urllib.request.urlopen(get_request, timeout=NETWORK_TIMEOUT_SECONDS) as resp:
        if resp.status not in (200, 206):
            return resp.status, b''
        body = resp.read(1024)
        return resp.status, body


@pytest.mark.network
@pytest.mark.parametrize(
    'spec',
    _primary_slices(),
    ids=lambda spec: spec.slice_key,
)
def test_primary_slice_url_is_reachable(spec: SliceSpec) -> None:
    url = resolve_remote_url(spec, season=PINNED_SMOKE_SEASON)
    assert url, f'slice {spec.slice_key!r} resolved to an empty URL'

    status, body = _probe(url)
    assert status in (200, 206), (
        f'slice {spec.slice_key!r} ({url}) returned HTTP {status}; '
        'either the URL drifted again or the upstream is down'
    )
    if body:
        # CSV header heuristic — every primary slice publishes CSV. A
        # non-empty body without a comma is almost certainly an HTML
        # error page that returned 200.
        first_line = body.split(b'\n', 1)[0]
        assert b',' in first_line, (
            f'slice {spec.slice_key!r} returned a 200 body that does not '
            f'look like CSV (first line: {first_line!r})'
        )


@pytest.mark.network
def test_all_seven_primary_slices_are_covered() -> None:
    # Catches the case where a future slice is added to the registry but
    # not to the network smoke. The seven primary nflverse-bulk slices
    # are: schedule_field_dictionary, teams, games, players, rosters,
    # team_stats_weekly, player_stats_weekly. Anything else here is a
    # registry change that warrants a deliberate test edit.
    keys = sorted(spec.slice_key for spec in _primary_slices())
    assert keys == [
        'games',
        'player_stats_weekly',
        'players',
        'rosters',
        'schedule_field_dictionary',
        'team_stats_weekly',
        'teams',
    ]
