"""T3.1 Step 2 — Static validation for the Windows VPS deployment scripts.

These tests do not invoke PowerShell. They read the ``.ps1`` files as bytes
and assert the cross-shell invariants that bit us in earlier Tranchen:

- **ASCII-only.** Windows PowerShell 5.1 reads UTF-8 without a BOM as
  CP1252; em-dashes / umlauts in `.ps1` files crash the parser at load
  time (see commit ``3c15751`` and the operator memory note). Every byte
  must be < 0x80.
- **No pipeline-chain operators.** PowerShell 5.1 has no ``&&`` or
  ``||`` statement separators. Use ``;`` or ``if ($?)`` instead.
- **Task wiring contract.** The Step 2 installer registers exactly six
  ``NewNFL-Fetch-*`` tasks at the scheduled times the operator runbook
  expects. A drift in either name or time is a wiring bug, so we pin
  both.

End-to-end validation (operator triggers each task on VPS, ``LastTaskResult=0``,
two-day observation) is the T3.1-final closer and stays out of pytest scope.
"""
from __future__ import annotations

from pathlib import Path

import pytest

DEPLOY_DIR = Path(__file__).resolve().parents[1] / 'deploy' / 'windows-vps'

ALL_PS1_SCRIPTS: tuple[Path, ...] = (
    DEPLOY_DIR / 'vps_bootstrap.ps1',
    DEPLOY_DIR / 'vps_install_tasks.ps1',
    DEPLOY_DIR / 'vps_install_tasks_step2.ps1',
    DEPLOY_DIR / 'run_slice.ps1',
    DEPLOY_DIR / 'run_backup.ps1',
)

STEP2_SCRIPT = DEPLOY_DIR / 'vps_install_tasks_step2.ps1'


@pytest.mark.parametrize(
    'script',
    ALL_PS1_SCRIPTS,
    ids=lambda p: p.name,
)
def test_ps1_script_is_ascii_only(script: Path) -> None:
    # PowerShell 5.1 + UTF-8-without-BOM == CP1252 decoder == em-dash / umlaut
    # parser-error landmine. The fix is operational discipline: keep all
    # `.ps1` files strictly ASCII.
    assert script.exists(), f'expected deployment script {script}'
    raw = script.read_bytes()
    non_ascii = [(idx, byte) for idx, byte in enumerate(raw) if byte >= 0x80]
    assert not non_ascii, (
        f'{script.name} contains {len(non_ascii)} non-ASCII bytes; '
        f'first offset: {non_ascii[0][0]} byte=0x{non_ascii[0][1]:02x}'
    )


@pytest.mark.parametrize(
    'script',
    ALL_PS1_SCRIPTS,
    ids=lambda p: p.name,
)
def test_ps1_script_has_no_pipeline_chain_operators(script: Path) -> None:
    # `&&` / `||` parse as TokenError on Windows PowerShell 5.1. Operators
    # who copy our snippets see "The token '&&' is not a valid statement
    # separator in this version." — the memory feedback note pins this as
    # a delivery rule.
    text = script.read_text(encoding='ascii')
    forbidden = ('&&', '||')
    for token in forbidden:
        assert token not in text, (
            f'{script.name} contains forbidden PowerShell 5.1 token {token!r}; '
            'split into separate lines or use `; if ($?) {{ ... }}` instead'
        )


def test_step2_script_registers_six_fetch_tasks() -> None:
    # The Step 2 installer is the contract between T3.1S (slices ready)
    # and T3.1 final (operator beobachtet 2 Tage). The six task names
    # must match the operator runbook and the LastTaskResult-grid in
    # PROJECT_STATE.
    text = STEP2_SCRIPT.read_text(encoding='ascii')
    expected_tasks = (
        'NewNFL-Fetch-Schedule',
        'NewNFL-Fetch-Games',
        'NewNFL-Fetch-Players',
        'NewNFL-Fetch-Rosters',
        'NewNFL-Fetch-TeamStats',
        'NewNFL-Fetch-PlayerStats',
    )
    for name in expected_tasks:
        # Each task name must appear at least once as a `-TaskName "<name>"`
        # argument to Install-NewNflTask. Using the quoted form makes the
        # search robust against the comment-block re-mention of names.
        needle = f'-TaskName    "{name}"'
        assert needle in text, (
            f'{STEP2_SCRIPT.name} does not register {name!r}; '
            f'expected line containing {needle!r}'
        )


def test_step2_script_uses_staggered_15_minute_triggers() -> None:
    # The 15-minute stagger sits between Step-1 Teams (05:00) and a
    # one-hour-window cap. Anything tighter risks hitting the GitHub
    # rate-limit parallelism budget when six fetches kick off at once.
    text = STEP2_SCRIPT.read_text(encoding='ascii')
    expected_times = ('05:15', '05:30', '05:45', '06:00', '06:15', '06:30')
    for time_str in expected_times:
        needle = f'(Get-Date "{time_str}")'
        assert needle in text, (
            f'{STEP2_SCRIPT.name} does not configure trigger {time_str}; '
            f'expected line containing {needle!r}'
        )


def test_step2_script_drives_run_slice_with_canonical_keys() -> None:
    # Slice keys must match SLICE_REGISTRY exactly. A typo here means
    # `run_slice.ps1` errors out on the first manual trigger with
    # "unknown slice", and the operator pings me at 04:30.
    text = STEP2_SCRIPT.read_text(encoding='ascii')
    expected_slice_args = (
        '-Slice "schedule_field_dictionary"',
        '-Slice "games"',
        '-Slice "players"',
        '-Slice "rosters"',
        '-Slice "team_stats_weekly"',
        '-Slice "player_stats_weekly"',
    )
    for arg in expected_slice_args:
        assert arg in text, (
            f'{STEP2_SCRIPT.name} missing canonical slice arg {arg!r}'
        )


def test_step2_script_does_not_pass_explicit_season_to_run_slice() -> None:
    # Per-season slices must let the Python side resolve the season via
    # default_nfl_season(). Hard-coding -Season here would bake the
    # current calendar year into the deployment artifact and require an
    # annual edit. SliceSpec.remote_url_template + resolve_remote_url
    # already handle the calendar logic.
    text = STEP2_SCRIPT.read_text(encoding='ascii')
    # The flag only appears in comments / Write-Host trace lines; the
    # Install-NewNflTask + New-SliceArgs invocations must not contain
    # it. Search for the explicit invocation pattern instead.
    bad = '-Season '
    # Accept the flag in comments (lines starting with '#') and in
    # Write-Host trace text; flag only in code lines that build the
    # ScheduledTaskAction argument.
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith('#'):
            continue
        if 'Write-Host' in line:
            continue
        if bad in line:
            pytest.fail(
                f'{STEP2_SCRIPT.name}:{line_no} hard-codes a -Season '
                f"argument: {line.strip()!r}. Per-season slices should "
                'rely on default_nfl_season() in the Python pipeline.'
            )


def test_step2_script_idempotent_unregister_pattern() -> None:
    # Step 2 must follow the same idempotency pattern as Step 1: if a
    # task with the same name already exists, drop and recreate. Otherwise
    # a re-run of the installer would silently fail at Register-ScheduledTask
    # with "task already exists".
    text = STEP2_SCRIPT.read_text(encoding='ascii')
    assert 'Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false' in text, (
        'Install-NewNflTask must drop a pre-existing task before re-registering'
    )


def test_run_slice_script_passes_season_only_when_provided() -> None:
    # run_slice.ps1 is the per-season hand-off. It must forward -Season
    # to the new-nfl CLI when the operator passes it, and omit the flag
    # otherwise so default_nfl_season() picks the year. This test pins
    # that branching so a future "always pass --season" simplification
    # doesn't quietly break the Step 2 contract.
    text = (DEPLOY_DIR / 'run_slice.ps1').read_text(encoding='ascii')
    assert 'if ($Season -ne $null)' in text
    assert '"--season"' in text
