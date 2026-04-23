"""Observability namespace (T2.7A / T2.7B).

Stream A scope per ADR-0033 parallel-development plan:

* :mod:`new_nfl.observability.health` — JSON health-response builder for the
  ``new-nfl health-probe`` CLI (``live`` / ``ready`` / ``freshness`` /
  ``deps``).
* :mod:`new_nfl.observability.logging` — structured logger factory with the
  mandatory ``event_id``, ``ts``, ``level``, ``msg``, ``details`` record
  shape plus the optional ``adapter_id`` / ``source_file_id`` /
  ``job_run_id`` context fields.

Downstream readers: the CLI plugin in :mod:`new_nfl.plugins.health`
and the runner hooks in :mod:`new_nfl.jobs.runner`.
"""

__all__: list[str] = []
