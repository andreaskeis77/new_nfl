# ADR-0027: Dedupe Pipeline as Explicit Stage

## Status
Accepted (T2.4B, 2026-04-16)

## Kontext
Mehrere Quellen liefern überlappende Player- und Team-Records mit unterschiedlichen IDs, Schreibweisen, Suffixen und Trade-bedingten Zuordnungen. Implizite Dedupe-Logik im Stage-Load-Code wäre schwer auditierbar und würde gegen das Manifest-Prinzip „Fail loud on data integrity" verstoßen.

## Entscheidung
Dedupe ist eine **eigene, benannte Pipeline-Stufe** mit fünf Schritten:

1. **Normalize** — deterministisch: Lowercase, Diacritics, Suffix-Erkennung (Jr./Sr./III), Whitespace.
2. **Block** — Kandidatengenerierung über Block-Keys (Last-Name + Position + DOB-Year).
3. **Score** — Match-Score (Phase-1: regelbasiert; Interface offen für späteres probabilistisches Modell).
4. **Cluster** — Connected-Components über Score-Schwellwert.
5. **Review-Queue** — Grenzfälle (Score zwischen unterer und oberer Schwelle) landen in `meta.review_item` mit Operator-Aktion.

Code-Layout: `src/new_nfl/dedupe/{normalize,block,score,cluster,review}.py`. CLI: `cli dedupe-run --domain players`.

**Nicht Teil dieser Entscheidung:** ML-basiertes Matching. Bleibt späterer ADR vorbehalten.

## Begründung
- explizite Stufen sind testbar und auditierbar.
- Review-Queue erlaubt Fortschritt trotz offener Grenzfälle (Designed Degradation).
- Interface-Trennung ermöglicht spätere probabilistische Erweiterung ohne Rewrite.

## Konsequenzen
**Positiv:** Dedupe-Entscheidungen sind nachvollziehbar; Operator-Overrides sind dokumentiert.
**Negativ:** mehr Tabellen, mehr CLI-Surface; Phase-1 ohne ML-Matcher.

## Alternativen
1. Dedupe in Stage-Load — implizit, schlecht auditierbar.
2. Splink/Dedupe-Lib direkt einbauen — überdimensioniert für v1.0, bleibt Option für v1.1+.

## Rollout
- T2.4B (erledigt): Skelett mit deterministischer Normalisierung, regelbasiertem Score, Connected-Components-Cluster, Review-Queue als `meta.review_item`. CLI `dedupe-run --domain players --demo` als Smoke-Pfad.
- T2.5C nutzt die Pipeline für Player-Stammdaten als ersten Praxisfall.

## Implementierungs-Notizen (T2.4B, 2026-04-16)
- Code: [src/new_nfl/dedupe/](../../src/new_nfl/dedupe) mit fünf Modulen plus `pipeline.py`. Stdlib-only (`unicodedata`, `re`, `itertools`) — keine neue Runtime-Abhängigkeit.
- `Scorer` ist als `typing.Protocol` implementiert. v0_1 enthält `RuleBasedPlayerScorer` (`kind = "rule_based_v1"`) mit sechs Score-Stufen 1.00 / 0.95 / 0.80 / 0.70 / 0.60 / 0.50 / 0.00. Spätere ML-Scorer hängen sich an dasselbe Interface.
- Default-Schwellwerte: `lower_threshold = 0.50` (Review-Untergrenze), `upper_threshold = 0.85` (Auto-Merge ab hier).
- Block-Key Player: `last_name | position | birth_year`. Records ohne Last-Name werden komplett aus dem Block-Pool gehalten — sind im realen Daten-Set Datenfehler, kein Match-Kandidat.
- Cluster: Singletons (Records ohne Auto-Merge-Kante) werden mitgezählt, damit `cluster_count` die wahre Anzahl distinkter Entitäten widerspiegelt — nicht nur die Auto-Merge-Cluster.
- Review-Queue: nur Pairs mit `lower <= score < upper` landen in `meta.review_item` mit `status='open'`. Auto-Merge und No-Match werden nicht persistiert; Counts liegen in `meta.dedupe_run`.
- `meta.dedupe_run` hält pro Lauf: Domain, Source-Ref, Scorer-Kind, Schwellwerte, Counts (Input, Candidate, Auto-Merge, Review, Cluster), Status, Start/Ende. Das ist Evidence-Surface analog zu `meta.job_run`.
- Demo-Set in [src/new_nfl/dedupe/pipeline.py](../../src/new_nfl/dedupe/pipeline.py): 6 synthetische QB-Records (Mahomes-Twin auto-merge, A. Rodgers Initial-Review, Tom Brady singleton). Genug, um alle drei Buckets in einem Lauf zu treffen.
- Cluster-Persistenz (`meta.cluster_assignment`) ist bewusst nicht in v0_1 — kommt mit T2.5C, wenn die Pipeline gegen reale `core.player`-Records läuft.

## Offene Punkte (für spätere Tranchen)
- Persistente Cluster-Zuordnung in `meta.cluster_assignment` (T2.5C).
- Adapter, der echte `core.player`-Records statt `RawPlayerRecord` ins Pipeline-Eingangs-Format hebt (T2.5C).
- `dedupe-review-resolve` CLI, parallel zu `quarantine-resolve` (T2.5C oder eigenes Bolt).
- Optionaler probabilistischer Scorer-Wrapper (Splink o. ä.) — eigener ADR.
