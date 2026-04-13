# NEW NFL — UI Style Guide v0.1

**Status:** Draft for adoption
**Last Updated:** 2026-04-13
**Scope:** Verbindliche Design-, Typografie-, Farb- und Komponentenregeln für die Web-UI von NEW NFL ab v1.0.

## 0. Designhaltung

NEW NFL ist eine private, datenintensive Sport-Analytics-Plattform für **einen** Operator. Das UI soll wirken wie eine moderne Sport-Analytics-Site (FiveThirtyEight-Klasse, The Athletic-Klasse), nicht wie ein Excel-Report oder ein Behörden-Dashboard.

**Drei Leitwerte:**

1. **Lesbarkeit vor Schmuck.** Zahlen und Namen müssen sofort lesbar sein. Dekoration ist nachrangig.
2. **Ruhe statt Reizüberflutung.** Großzügiger Whitespace, klare Hierarchie, wenige Akzente.
3. **Konsistenz vor Kreativität.** Komponenten, Spacing, Farben, Typo werden wiederverwendet. Keine Sonderlocken pro View.

## 1. Verbindliche Naming-Regel

**Personen- und Teamnamen werden immer in offizieller, vollständiger Form angezeigt.**

- Korrekt: „Travis Kelce", „Patrick Mahomes", „Kansas City Chiefs"
- Falsch: „T. Kelce", „T Kel", „Mahomes", „KC Chiefs"

Erlaubte Abkürzungen sind ausschließlich offizielle Team-Codes (z. B. „KC", „SF", „BUF"), und nur dort, wo Platz wirklich knapp ist (Tabellen-Headers, Sparkline-Labels, Box-Score-Spaltenköpfe). In Überschriften, Karten, Profil-Seiten und Vergleichen gilt immer der vollständige offizielle Name.

Diese Regel ist Teil des `mart.*`-Vertrags: Read-Modelle liefern eine `display_name`-Spalte mit der kanonischen Display-Form. UI-Code formatiert nicht selbst; er konsumiert `display_name`.

## 2. Typografie

### 2.1 Schriften
- **UI-Sans:** `Inter` (variable), Fallback `system-ui, -apple-system, Segoe UI, Roboto, sans-serif`.
- **Tabellen-Mono:** `JetBrains Mono` (variable), Fallback `ui-monospace, Menlo, Consolas, monospace`.
- **Optional Display:** `Inter` mit `font-feature-settings: "ss01"` für leicht engere Headlines. Keine separate Display-Schrift.

Schriften werden self-hosted (Lizenz prüfen, woff2). Kein Google-Fonts-Live-Loading.

### 2.2 Numerische Darstellung
Bei allen Zahlen (Tabellen, Stat-Karten, Sparkline-Achsen) gilt:

```css
font-feature-settings: "tnum", "lnum";
font-variant-numeric: tabular-nums lining-nums;
```

Damit fluchten Ziffern in Spalten. Tausender-Trennzeichen nach US-Konvention (Komma) für reine Zahlen, Punkte für Yards-Decimals.

### 2.3 Schriftgrade (Type Scale)
Maximal 6 Größen, 1.250-Skala (Major Third), Basis 16 px:

| Token | px | rem | Verwendung |
|---|---|---|---|
| `text-xs` | 12 | 0.75 | Meta (Timestamps, Quellen-Tags) |
| `text-sm` | 14 | 0.875 | Tabellen-Body, sekundärer Text |
| `text-base` | 16 | 1.0 | Body-Standard |
| `text-lg` | 20 | 1.25 | Card-Titel, Sub-Headlines |
| `text-2xl` | 25 | 1.5625 | Page-Section-Headlines |
| `text-3xl` | 32 | 2.0 | Page-Title (nur einmal pro View) |

Pro View **maximal 3 Schriftgrade** in der Hauptansicht. Mehr ist Designfehler.

### 2.4 Zeilenhöhe und Tracking
- Body: `line-height: 1.5`, `letter-spacing: 0`.
- Headlines (≥ `text-2xl`): `line-height: 1.2`, `letter-spacing: -0.01em`.
- Tabellen-Body: `line-height: 1.4`.

### 2.5 Gewichte
- 400 Regular — Body
- 500 Medium — Tabellen-Header, Labels, Card-Titel
- 600 Semibold — Page-Headlines
- 700 Bold — sehr sparsam, nur für KPI-Kacheln

Keine Gewichte unter 400. Kein Italic für Datenwerte.

## 3. Farbsystem

### 3.1 Basis (neutrale Palette)
Tailwind-`zinc`-Skala als Basis:

| Rolle | Dark Mode | Light Mode |
|---|---|---|
| `bg/canvas` | `zinc-950` (#09090b) | `zinc-50` (#fafafa) |
| `bg/surface` | `zinc-900` (#18181b) | `white` |
| `bg/surface-elevated` | `zinc-800` (#27272a) | `zinc-100` (#f4f4f5) |
| `border/subtle` | `zinc-800` | `zinc-200` |
| `border/strong` | `zinc-700` | `zinc-300` |
| `text/primary` | `zinc-50` | `zinc-900` |
| `text/secondary` | `zinc-400` | `zinc-600` |
| `text/muted` | `zinc-500` | `zinc-500` |

### 3.2 Akzent
**Ein** Akzent für interaktive Elemente, Links, aktive States:
- `accent` = `emerald-500` (#10b981) — neutral, sportlich, gut lesbar auf Dark.
- Hover: `emerald-400`. Active: `emerald-600`.

### 3.3 Status-Farben
| Rolle | Token | Hex |
|---|---|---|
| Success / fresh | `success` | `emerald-500` |
| Warn / stale | `warn` | `amber-500` (#f59e0b) |
| Danger / failed / quarantined | `danger` | `rose-500` (#f43f5e) |
| Info | `info` | `sky-500` (#0ea5e9) |

Status-Farben werden **nur** für Status genutzt, nie für dekorative Akzente.

### 3.4 Dark Mode
Dark Mode ist Standard. Light Mode optional als Toggle. Beim ersten Lade gilt `prefers-color-scheme`, dann persistiert in `localStorage`.

### 3.5 Kontrast
WCAG AA Pflicht. Body-Text gegen Surface ≥ 4.5:1. Zahlen in Tabellen ≥ 7:1 (AAA-Anspruch, weil Datenfokus).

## 4. Spacing und Layout

### 4.1 Spacing-Skala
4-px-Basis: `4, 8, 12, 16, 24, 32, 48, 64, 96`. Tailwind-Defaults (`gap-2, gap-4, …`) gelten.

### 4.2 Layout-Grid
- Maximale Inhaltsbreite: `1280 px` (Tailwind `max-w-7xl`).
- Seitenränder: `24 px` mobil, `48 px` ab `md`.
- Hauptgrid: 12 Spalten, `gap-6`.

### 4.3 Card-Pattern
- `border border-border-subtle`, `rounded-lg` (8 px), `bg-surface`.
- Innenabstand: `p-6` (24 px) Standard, `p-4` für dichte Tabellen.
- Card-Title: `text-lg`, `font-medium`, `mb-4`.

### 4.4 Tabellen
- Sticky Header.
- Zebra-Streifen: **nein** (lenkt von Zahlen ab). Stattdessen Hover-Highlight `bg-surface-elevated`.
- Numerische Spalten rechtsbündig, mono.
- Text-Spalten linksbündig, sans.
- Spaltenabstand `px-4 py-2`.
- Header `text-xs uppercase tracking-wide text-secondary font-medium`.

## 5. Komponenten (v1.0-Kern)

### 5.1 Pflicht-Komponenten
- `<Page>` — Layout-Wrapper mit Header, Breadcrumb, Content-Slot.
- `<NavBar>` — globale Navigation, Dark/Light-Toggle, später Command-Palette-Trigger.
- `<Card>` — siehe 4.3.
- `<StatTile>` — KPI-Kachel: Label (text-xs), Value (text-3xl mono tnum), optional Delta (text-sm + Status-Farbe).
- `<DataTable>` — siehe 4.4.
- `<FreshnessBadge>` — Pill mit Status-Farbe + relativer Zeitangabe („vor 12 min", „vor 3 Tagen").
- `<ProvenancePopover>` — auf Klick auf einen Wert: Quelle(n), Run-ID, Abrufzeit, Konfliktstatus.
- `<Sparkline>` — kleine Liniengrafik in Tabellenzellen, max. 80 × 20 px.
- `<Breadcrumb>` — Saison › Woche › Spiel.
- `<EmptyState>` — wenn Daten fehlen: Icon, Titel, Erklärung, ggf. CLI-Befehl, der die Daten füllen würde.

### 5.2 Charts
- Bibliothek: **Observable Plot** als Erstwahl (deklarativ, leichtgewichtig, gute Defaults).
- Alternative: **ECharts** für komplexere interaktive Charts.
- Keine Chart.js, keine D3-Eigenbauten in v1.0.
- Charts nutzen die Status- und Akzent-Farben aus 3.2/3.3, kein eigenes Farbschema pro Chart.
- Achsen-Labels minimal, Gitter dezent, keine 3D-Effekte, keine Schatten.

### 5.3 Icons
- **Lucide** (MIT-lizenziert, leichtgewichtig).
- Größe `16 px` inline, `20 px` in Buttons, `24 px` in Empty-States.
- Strichstärke einheitlich `1.5`.

## 6. Interaktion

### 6.1 Tastatur (v1.0 Minimum)
- `g h` — Home
- `g s` — Seasons
- `g t` — Teams
- `g p` — Players
- `/` — Suche fokussieren (Suche selbst v1.1)

### 6.2 Hover und Focus
- Alle interaktiven Elemente haben sichtbaren Focus-Ring: `ring-2 ring-accent ring-offset-2 ring-offset-canvas`.
- Hover auf Tabellenzeilen: Background-Tint, kein Border-Shift (verhindert Layout-Sprung).

### 6.3 Loading-Verhalten
- Server-Render zuerst, dann ggf. htmx-Partial-Updates.
- Loading-Skeletons statt Spinner für Tabellen und Cards.
- Spinner nur für Aktionen unter 2 Sekunden Erwartung.

### 6.4 Fehleranzeige
- Inline-Fehler in Cards mit `danger`-Border-Tint und Klartext-Erklärung.
- Bei Quell-Fehlschlag in einer Domäne: View bleibt sichtbar, betroffene Werte zeigen `—` mit `<ProvenancePopover>` „letzter erfolgreicher Run: …".

## 7. Accessibility (verbindlich)

- WCAG AA für Kontraste, Tastaturnavigation, Focus.
- Semantisches HTML (`<table>`, `<thead>`, `<th scope="col">`, `<nav>`, `<main>`).
- ARIA nur dort, wo HTML-Semantik nicht reicht.
- `prefers-reduced-motion` respektieren: keine Auto-Animationen, Sparkline-Drawing nur statisch.

## 8. Tech-Stack-Bindung

- **Server-Rendering:** Jinja2-Templates in `src/new_nfl/web/templates/`.
- **Styling:** Tailwind CSS, Build über `tailwindcss` CLI in einen statischen Output unter `src/new_nfl/web/static/`.
- **Komponenten:** Jinja-Macros in `src/new_nfl/web/templates/_components/`.
- **Interaktivität:** htmx für gezielte Partial-Updates, kein SPA-Framework.
- **Charts:** Observable Plot als ESM-Import per `<script type="module">`, lokal abgelegt.
- **Icons:** Lucide als statisches Sprite-SVG.
- **Keine** clientseitige Build-Pipeline jenseits Tailwind und einer optionalen `esbuild`-Bündelung für Plot/htmx.

## 9. Anti-Patterns (verboten)

- Abgekürzte Personen-/Teamnamen in Headlines, Cards, Profilen, Vergleichen.
- Drei oder mehr Akzentfarben pro View.
- Zebra-Streifen in Stat-Tabellen.
- Mehr als 3 Schriftgrade in der Hauptansicht.
- Auto-Refreshende Charts ohne Anwender-Trigger.
- Modal-Dialoge für Drilldowns (stattdessen Popover oder eigene Route).
- Tooltips als Träger nicht-redundanter Information (Touch-Inkompatibilität).
- Eigene Farbschemata pro Chart.
- Inline-CSS in Templates (außer Sparkline-Größenangaben).

## 10. Entwicklungs- und Review-Disziplin

- Jede neue View braucht einen Screenshot im Handoff (Dark + Light).
- UI-PRs verlinken den `UI_STYLE_GUIDE`-Abschnitt, gegen den sie geprüft wurden.
- Verstöße gegen Abschnitt 1 (Naming) und Abschnitt 9 (Anti-Patterns) sind Blocker.

## 11. Verweise

- `concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md` — Layer- und Read-Modell-Disziplin
- `ENGINEERING_MANIFEST_v1_3.md` — Prinzip 3.10 „UI-Qualität ist Systemqualität"
- `USE_CASE_VALIDATION_v0_1.md` — UI-Pflicht-Views v1.0
- Inter: <https://rsms.me/inter/>
- JetBrains Mono: <https://www.jetbrains.com/lp/mono/>
- Tailwind CSS: <https://tailwindcss.com/>
- Observable Plot: <https://observablehq.com/plot/>
- Lucide Icons: <https://lucide.dev/>
- htmx: <https://htmx.org/>
