# ADR-0030: UI Tech Stack — Jinja + Tailwind + htmx + Observable Plot

## Status
Accepted — 2026-04-23 (T2.6A)

## Kontext
Die Web-UI muss bis v1.0 (Ende Juni 2026) sieben Pflicht-Views liefern, optisch Sport-Analytics-Niveau erreichen und auf einem Single-Operator-Windows-Stack laufen. SPA-Frameworks würden Build-Pipeline, Hydration und Test-Komplexität erhöhen, ohne v1.0-Funktionalität zu rechtfertigen.

## Entscheidung
Verbindlicher UI-Stack für v1.0:

- **Server-Rendering:** Jinja2-Templates in `src/new_nfl/web/templates/`.
- **Styling:** Tailwind-CSS-kompatible Utility-Klassen. Für v1.0-Bootstrap wird ein hand-assemblierter Tailwind-Subset (`src/new_nfl/web/static/css/app.css`) committet, der nur die tatsächlich in den Templates verwendeten Utilities enthält. Eine spätere Re-Generierung mit dem `tailwindcss` CLI (Standalone-Binary unter Windows, keine globale Node-Installation) ersetzt diesen Subset ohne Template-Änderungen.
- **Komponenten:** Jinja-Macros in `src/new_nfl/web/templates/_components/`.
- **Interaktivität:** htmx für gezielte Partial-Updates, lokal unter `src/new_nfl/web/static/js/vendor/htmx.min.js`.
- **Charts:** Observable Plot als ESM-Import, lokal unter `src/new_nfl/web/static/js/vendor/plot.mjs`. ECharts erlaubt für Sonderfälle.
- **Icons:** Lucide als statisches Sprite-SVG unter `src/new_nfl/web/static/icons/lucide-sprite.svg`.
- **Schriften:** Inter (UI-Sans), JetBrains Mono (Tabellen-Mono), self-hosted unter `src/new_nfl/web/static/fonts/`. Falls `woff2`-Dateien fehlen, degradiert das CSS stillschweigend auf die dokumentierten Fallback-Familien.

**Nicht** in v1.0: React, Vue, Svelte, Next.js, eigene Component-Library jenseits Jinja-Macros, Webpack/Vite-Build, globale Node-Installation als Voraussetzung.

Style- und Komponentenregeln sind verbindlich in `UI_STYLE_GUIDE_v0_1.md`.

## Implementierungs-Notizen (T2.6A)
- Jinja2 ist Pflicht-Dependency (`jinja2>=3.1` in `pyproject.toml`); MarkupSafe kommt automatisch mit.
- Template-Loader ist `FileSystemLoader` gegen den gepackten `templates/`-Pfad; Rendering ist seitenpur, keine Request-Globale.
- Alle Read-Pfade lesen ausschließlich aus `mart.*` (ADR-0029) — der AST-Lint-Test erweitert sich auf `src/new_nfl/web/`.
- Dark Mode ist Default; Toggle über `data-theme`-Attribut am `<html>`-Element, Persistenz in `localStorage`, initialer Mode aus `prefers-color-scheme`. Die Theme-Schaltung ist ein einziges JS-Snippet inline im `<head>`, damit kein Flash-of-Unstyled-Content auftritt.
- CSS-Custom-Properties für Palette-Tokens (`--bg-canvas`, `--text-primary`, `--accent`, …); Utility-Klassen greifen auf diese Tokens zu, damit Dark/Light durch einen Attribute-Swap umgeschaltet werden kann, ohne CSS neu zu kompilieren.
- Ein `StaticAssetResolver` (`src/new_nfl/web/assets.py`) gibt statische Pfade idempotent zurück und wird später um Cache-Buster-Hashes erweitert (v1.1+).

## Begründung
- minimaler Build-Stack — passt zu Single-Operator-Windows-Setup, keine Node-Abhängigkeit im kritischen Pfad.
- Jinja ist im Python-First-Stack natürlich.
- Tailwind-Tokens via CSS-Custom-Properties erlauben Dark/Light ohne Rekompilierung und ohne Dual-Build.
- htmx liefert Interaktivität dort, wo sie wirklich gebraucht wird, ohne SPA-Komplexität.
- Observable Plot ist deklarativ, leichtgewichtig und visuell modern.
- Hand-assemblierter Tailwind-Subset als Bootstrap akzeptiert kleine Redundanz (einige Utilities mehrfach in Template und CSS definiert) gegen den Gewinn, keine Node-Toolchain im Operator-Flow zu brauchen. Die Migration auf vollständige Tailwind-Compilation ist mechanisch (Input-CSS bleibt gleich, CLI ersetzt Subset).

## Konsequenzen
**Positiv:** schnelle Entwicklung, einfache Tests (Server-rendered HTML), kein Hydration-Risiko, gute Performance, funktioniert offline.
**Negativ:** komplexe Client-Interaktionen wären mühsam — bewusst akzeptiert für v1.0; v1.1+ kann einzelne Views punktuell auf SPA umstellen, falls nötig. Der hand-assemblierte CSS-Subset muss pro neuem Utility manuell erweitert werden, bis der Tailwind-CLI-Pfad aktiviert ist.

## Alternativen
1. Streamlit — schnell, aber Look-&-Feel passt nicht zum Style-Guide-Anspruch.
2. React + FastAPI-API — übersteigt v1.0-Scope.
3. Plain HTML/CSS ohne Tailwind-Tokens — Designkonsistenz schwerer zu halten, Dark/Light-Umschaltung müsste pro Komponente kodiert werden.
4. Tailwind via CDN (`<script src="https://cdn.tailwindcss.com">`) — verletzt Self-Hosting-Ziel des Style Guides.
5. Tailwind CLI via globales Node — würde Operator-Setup um ein Werkzeug erweitern, das außerhalb des Python-Ökosystems lebt; Standalone-Binary bleibt der bevorzugte Pfad für den Fall, dass der Subset nicht mehr reicht.

## Rollout
- T2.6A: Jinja2-Setup, Tailwind-CSS-Subset, Komponenten-Skelett, `base.html`, Dark-Mode-Toggle, Inter+JetBrains-Mono-Slots, Lucide-Sprite-Slot. **Abgeschlossen 2026-04-23.**
- T2.6B–H: Pflicht-Views nacheinander, jede View erweitert den CSS-Subset um die tatsächlich genutzten Utilities.

## Offene Punkte
- Tailwind CLI v4 Standalone-Binary vs. manueller Subset — Entscheidung vertagt bis zum ersten Schmerz mit dem hand-assemblierten Ansatz.
- htmx-Version — neueste Stable, wird beim ersten Integrationsschritt (T2.6B) vendoriert.
- Observable Plot ESM-Bundle wird beim ersten Chart-View (vermutlich T2.6D Team-Profil) vendoriert, nicht pauschal in T2.6A.
- Font-Dateien (Inter, JetBrains Mono als `woff2`) werden nicht in T2.6A committet, weil sie nur beim ersten sichtbaren UI-Lauf gebraucht werden; das CSS fällt elegant auf die dokumentierten Fallback-Stacks zurück.
