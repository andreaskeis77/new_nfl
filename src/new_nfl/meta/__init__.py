"""Meta-Namespace für Hardening-Infrastruktur (T2.7E, ADR-0033 Stream C).

Bündelt querschnittliche Hilfen, die nicht zu einer Domäne gehören:

* :mod:`new_nfl.meta.retention` — Event-Retention (``trim-run-events``)
* :mod:`new_nfl.meta.schema_cache` — Settings-Level-Cache für ``DESCRIBE``
  auf ``core.*`` (reduziert DESCRIBE-Calls der Mart-Rebuilds)
* :mod:`new_nfl.meta.adapter_slice_registry` — Runtime-Projektion der
  Code-``SLICE_REGISTRY`` nach ``meta.adapter_slice``

Die Module bleiben importfrei zueinander (keine ``from new_nfl.meta.X
import …``-Ketten zwischen ihnen), damit ein einzelner Fehlerpfad kein
benachbartes Feature mitzieht.
"""

__all__: list[str] = []
