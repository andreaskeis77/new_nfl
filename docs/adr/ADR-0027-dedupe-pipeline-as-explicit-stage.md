# ADR-0027: Dedupe Pipeline as Explicit Stage

## Status
Proposed (target: Accepted at end of T2.4B)

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
- T2.4B: Skelett mit deterministischer Normalisierung, Score-Stub, Review-Queue-Stub.
- T2.5C nutzt die Pipeline für Player-Stammdaten als ersten Praxisfall.
