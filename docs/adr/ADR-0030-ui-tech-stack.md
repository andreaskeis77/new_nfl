# ADR-0030: UI Tech Stack — Jinja + Tailwind + htmx + Observable Plot

## Status
Proposed (target: Accepted at end of T2.6A)

## Kontext
Die Web-UI muss bis v1.0 (Ende Juni 2026) sieben Pflicht-Views liefern, optisch Sport-Analytics-Niveau erreichen und auf einem Single-Operator-Stack laufen. SPA-Frameworks würden Build-Pipeline, Hydration und Test-Komplexität erhöhen, ohne v1.0-Funktionalität zu rechtfertigen.

## Entscheidung
Verbindlicher UI-Stack für v1.0:

- **Server-Rendering:** Jinja2-Templates in `src/new_nfl/web/templates/`.
- **Styling:** Tailwind CSS, Build über `tailwindcss` CLI in statisches `src/new_nfl/web/static/css/`.
- **Komponenten:** Jinja-Macros in `_components/`.
- **Interaktivität:** htmx für gezielte Partial-Updates.
- **Charts:** Observable Plot als ESM-Import, lokal gehostet. ECharts erlaubt für Sonderfälle.
- **Icons:** Lucide als statisches Sprite-SVG.
- **Schriften:** Inter (UI-Sans), JetBrains Mono (Tabellen-Mono), self-hosted.

**Nicht** in v1.0: React, Vue, Svelte, Next.js, eigene Component-Library jenseits Jinja-Macros, Webpack/Vite-Build (außer optional `esbuild` für Plot-Bündelung).

Style- und Komponentenregeln sind verbindlich in `UI_STYLE_GUIDE_v0_1.md`.

## Begründung
- minimaler Build-Stack — passt zu Single-Operator-Setup.
- Jinja ist im Python-First-Stack natürlich.
- Tailwind erlaubt konsistente, hochwertige Optik ohne CSS-Architektur-Eigenbau.
- htmx liefert Interaktivität dort, wo sie wirklich gebraucht wird, ohne SPA-Komplexität.
- Observable Plot ist deklarativ, leichtgewichtig und visuell modern.

## Konsequenzen
**Positiv:** schnelle Entwicklung, einfache Tests (Server-rendered HTML), kein Hydration-Risiko, gute Performance.
**Negativ:** komplexe Client-Interaktionen wären mühsam — bewusst akzeptiert für v1.0; v1.1+ kann einzelne Views punktuell auf SPA umstellen, falls nötig.

## Alternativen
1. Streamlit — schnell, aber Look-&-Feel passt nicht zum Style-Guide-Anspruch.
2. React + FastAPI-API — übersteigt v1.0-Scope.
3. Plain HTML/CSS ohne Tailwind — Designkonsistenz schwerer zu halten.

## Rollout
- T2.6A: Tailwind-Setup, Komponenten-Skelett, Layout, Dark-Mode-Toggle, Inter+JetBrains Mono.
- T2.6B–H: Pflicht-Views nacheinander.

## Offene Punkte
- Tailwind v3 vs v4 — Default v4, falls bis T2.6A stabil.
- htmx-Version — neueste Stable.
