# NEW NFL — Lessons Learned (Sammeldatei)

**Format und Regeln:** siehe `LESSONS_LEARNED_PROTOCOL.md`.
**Reihenfolge:** neueste oben.

---

## 2026-04-23 — T2.6B Home/Freshness: `expected_domains`-CTE statt NULLable-Marts, und `meta.*` als Mart-Quelle
**Status:** draft (wartet auf Operator-Freigabe)

1. **Was lief gut:**
   - **`mart.*` darf aus `meta.*` lesen, nicht nur aus `core.*` — und das ist der strukturell richtige Schnitt.** Die ADR-0029-Regel ist „Read-Modelle lesen ausschließlich aus `mart.*`", und der Mart-Layer selbst ist die Schicht, in der Denormalisierung legal stattfindet. `meta.load_events` und `meta.quarantine_case` sind Observability-Ground-Truth — wenn sie als Primärquelle eines Marts (statt eines Read-Moduls) dienen, bleibt die Invariante erhalten: das UI liest `mart.freshness_overview_v1`, nie direkt `meta.*`. Der Mart-Builder wiederum hat explizites Wissen über die `meta.*`-Schemata, das ist sein Job. Diese Asymmetrie (Builder darf aus vielen Quellen lesen, Leser nur aus `mart.*`) ist nicht durch AST-Lint durchgesetzt, aber durch die Konvention, dass nur `src/new_nfl/mart/*.py` SQL gegen `meta.*` oder `core.*` formulieren dürfen.
   - **`expected_domains`-CTE im Mart-Builder liefert stabiles Schema auch bei leerer Metadaten-Tabelle.** Naiver Ansatz wäre ein `GROUP BY target_schema, target_object FROM meta.load_events` — das liefert auf frischer DB null Zeilen, und die UI-View müsste einen `empty_state`-Zweig haben, der vom Service erkannt wird. Stattdessen: eine inline `(VALUES ('core','team','Teams',1), …)`-Tabelle im Mart-SQL, LEFT JOIN auf die Aggregate. Die Projektion hat immer genau sechs Zeilen (eine pro erwartete Core-Domäne), und die abgeleitete `freshness_status`-Spalte kollabiert zu `'stale'` für Domänen ohne Events. Vorteil: der Service und die View brauchen keine Cold-Start-Sonderlogik, das Template rendert denselben Pfad für Tag 1 wie für Produktion mit Millionen Events.
   - **Kaskadierte `freshness_status`-Ableitung `stale → fail → warn → ok` ist einfach zu erklären und zu testen.** `CASE WHEN last_event_at IS NULL THEN 'stale' WHEN last_event_status = 'failed' THEN 'fail' WHEN open_quarantine_count > 0 THEN 'warn' ELSE 'ok' END` — die Reihenfolge reflektiert die Operator-Priorität: „hat noch nie gelaufen" schlägt „letzter Lauf schlug fehl" schlägt „Daten-Disagreement" schlägt „alles grün". Tests parametrisieren diese vier Pfade getrennt, die Logik ist als Single-Expression in der SQL hinterlegt statt in Python-Service-Code — d.h. jede View, die den Mart liest, bekommt den Status „umsonst".
   - **`ARG_MAX(…, recorded_at)` ist die idiomatische DuckDB-Antwort auf „letzter Event pro Gruppe".** Alternativen wären: `ROW_NUMBER() OVER (PARTITION BY target_schema, target_object ORDER BY recorded_at DESC) = 1`-Filter oder ein korrelierter Subquery. `ARG_MAX` ist auf einen Ausdruck pro Aggregat beschränkt, aber er liest den Intent wortwörtlich und DuckDB optimiert ihn gut. Für mehrere Felder pro Gruppe rufen wir `ARG_MAX` mehrfach auf (einmal pro Feld) — das ist redundant in der Ausführung (DuckDB scannt mehrfach), aber die SQL ist deutlich lesbarer als eine QUALIFY/ROW_NUMBER-Variante und die Datenmengen in `meta.load_events` sind so klein, dass die Mehrfach-Scans irrelevant sind.
   - **Service-Fallback auf synthetische `stale`-Zeilen entkoppelt UI-Render von Mart-Build-Reihenfolge.** Wenn jemand `render_home_from_settings(settings)` aufruft, bevor `mart.freshness_overview_v1` je gebaut wurde, fängt `load_freshness_rows` den `duckdb.Error` ab und liefert sechs synthetische `stale`-Zeilen. Die UI rendert die gleiche Liste wie mit einem „echten" Mart, nur eben alles grau. Das ist wichtig für die Bootstrap-Sequenz (bootstrap → Template rendern, bevor jemals ein Mart-Job lief) und für Tests, die die UI ohne Runner-Setup prüfen.

2. **Was lief nicht gut:**
   - **Pre-existing Ruff-Errors in `src/new_nfl/jobs/runner.py` und `tests/test_mart.py` tauchen jetzt bei jedem Scoped-Check auf.** `UP035` auf `typing.Callable` und `UP037` auf String-Annotationen sowie `I001` auf Import-Ordering plus `E741 l`-Variable-Name waren vor T2.6B schon da, werden aber jetzt wieder sichtbar, weil beide Dateien im Scope dieser Tranche sind (runner-Executor-Switch, test_mart.py READ_MODULES-Erweiterung). Das Projekt hat keine harte „ruff muss komplett clean sein"-CI-Gate, aber es ist unangenehm, dass die Scoped-Checks nicht einfach weiterhin grün bleiben. Notiz: vor dem nächsten Tranchen-Start einmal quer durch mit `ruff check --fix` gehen und die Autofixes committen, sonst schleppt sich das durch alle weiteren T2.6-Bolzen mit.
   - **Template-Pfad `preview_rows is defined` vs. `preview_rows` muss zwei Bedeutungen gleichzeitig tragen.** Der T2.6A-Skelett-Test (`test_empty_state_rendered_when_no_preview_rows`) erwartet bei `preview_rows=()` explizit das „Noch keine Spiele"-Empty-State; aber `render_home_from_settings` soll den Preview-Abschnitt ganz ausblenden (weil er aus T2.6B-Perspektive irrelevant ist — T2.6C wird ihn wieder einführen). Das Template löst das mit `{% if preview_rows is defined and preview_rows %} … {% elif preview_rows is defined %}empty_state{% endif %}` — funktioniert, aber die Bedeutung von „nicht definiert" vs. „leer" wird jetzt als semantischer Kanal genutzt. Das ist fragil, wenn jemand später `preview_rows=None` setzt. Entscheidung: solange T2.6C den Preview-Block neu aufsetzt, trägt die Fragilität nicht weit; bei T2.6C wird die Variable dann explizit aus dem Context entfernt, und der `is defined`-Zweig entfällt.
   - **Freshness-Service und Mart-Builder kennen beide die `expected_domains`-Liste — das ist eine doppelte Quelle der Wahrheit.** `EXPECTED_CORE_DOMAINS` steht einmal in `mart/freshness_overview.py` (als Tuple für die SQL-`VALUES`-Klausel) und einmal in `web/freshness.py` (für den Fallback, wenn der Mart fehlt). Die Werte sind identisch, aber das ist Redundanz, die jemand synchron halten muss. Alternativen: Service importiert `EXPECTED_CORE_DOMAINS` aus dem Mart-Modul — das macht den Service aber wieder von einem Mart-Implementierungsdetail abhängig, das eigentlich nur im Builder relevant ist. Akzeptabel für v1.0, aber Kandidat für Deduplizierung, wenn eine dritte Stelle dieselbe Liste braucht.

3. **Root Cause:**
   - Ein Mart wie `freshness_overview_v1` ist ein *observability-Mart*, kein *business-Domänen-Mart*. Observability-Marts leben vom Zusammenführen mehrerer `meta.*`-Tabellen plus Wissen über die erwarteten Domänen; business-Marts denormalisieren genau eine `core.*`-Tabelle. Die Abstraktion „Mart-Builder darf aus vielen Quellen lesen" trägt beide Fälle, weil der Builder selbst die Kontext-Schicht ist (er weiß, was ein Mart „ist" und welche Quellen relevant sind). Die Invariante „Leser lesen nur `mart.*`" ist damit nicht weichgespült — sie zieht lediglich die Grenze zwischen Build-Phase (darf alles) und Read-Phase (darf nur `mart.*`).
   - `ARG_MAX` ist als Aggregat deklarativ — es sagt „gib mir den Wert von X an der Stelle, wo Y maximal ist". Das ist näher an der natürlichen Sprache der Query („letzter Event") als Fenster-Funktionen mit Ordnung und Filter. Für Query-Lesbarkeit zahlt sich das aus, auch wenn die Runtime-Kosten bei kleinen Tabellen ungenutzt bleiben.
   - Das Cold-Start-Problem existiert immer, wenn ein Mart nicht semantisch „eine Tabelle denormalisiert", sondern „eine Frage beantwortet". Die Frage „wie fresh sind meine Domänen?" hat eine Antwort auch dann, wenn nie etwas geladen wurde — nämlich „nichts ist fresh, alles ist stale". Diese Antwort im Schema statt im Service zu verankern (via `expected_domains`-CTE) macht die Cold-Start-Eigenschaft zu einem Mart-Schema-Property statt zu einem View-Rendering-Property.

4. **Konkrete Methodänderung:**
   - **Ab T2.6B: Observability-Marts bauen ihre „Pflicht-Grain-Achsen" als inline-`VALUES`-CTE in die SQL, damit die Projektion eine stabile Zeilen-Kardinalität hat.** Regel für T2.6C–H: wenn eine Mart-View „alle erwarteten Dinge, einige davon leer" beantworten soll (Season-Liste mit geplanten aber noch nicht geladenen Seasons; Team-Profil-View mit allen 32 Teams immer präsent), dann führe die Achse als `VALUES`-CTE ein und LEFT JOIN die Daten ran. Der Empty-State wandert vom Service ins Schema.
   - **Observability-Status-Kaskaden als single-SQL-CASE statt Python-Service.** `freshness_status` ist ein abgeleitetes Feld im Mart, nicht im Service. Regel: wenn eine UI-Farb-/Status-Entscheidung aus Mart-Spalten deterministisch abgeleitet werden kann, leite sie im Mart ab. Der Service transportiert das Feld unverändert, das Template mappt nur noch `status` → CSS-Klasse (`ok → success`, `warn → warn`, `fail → danger`, `stale → neutral`).
   - **Pre-Commit-Scoped-Ruff-Check**: Vor jedem Bolt-Start einmal `ruff check --fix src/` + `ruff check --fix tests/` laufen lassen, Autofix-Commit separat, damit Scoped-Checks in der Tranche wirklich sauber starten. Preexisting-Warnings schleifen sonst durch, und jeder Bolt braucht den Disclaimer „die 4 Fehler waren schon da". Klarere Historie: ein expliziter „chore: ruff autofix sweep"-Commit trennt Mechanik von Architektur.

---

## 2026-04-23 — T2.6A UI-Fundament: Jinja + CSS-Custom-Properties ohne Node-Toolchain
**Status:** draft (wartet auf Operator-Freigabe)

1. **Was lief gut:**
   - **CSS-Custom-Properties als Dark/Light-Strategie statt doppelter Tailwind-Builds.** Der Style Guide §3.1 listet eine Token-Tabelle mit Dark- und Light-Werten pro semantischer Rolle (`bg/canvas`, `text/primary`, `border/subtle`, …). Eine naive Tailwind-Umsetzung würde entweder zwei komplette CSS-Outputs bauen (`app-dark.css` + `app-light.css`) oder pro Utility-Klasse zwei Varianten emittieren (`bg-zinc-950 dark:bg-zinc-50 …`) — beides verschiebt Komplexität auf die Build-Pipeline. Stattdessen definieren wir die Tokens als CSS-Custom-Properties auf `html[data-theme='dark']` bzw. `html[data-theme='light']` und binden sie per semantischen Utility-Klassen (`bg-canvas`, `text-primary`, …). Die Theme-Umschaltung ist ein einziger Attribute-Flip auf `<html>`, keine CSS-Rekompilierung, keine doppelten Klassen-Permutationen, keine `dark:`-Prefix-Duplikation. Die Jinja-Templates bleiben theme-agnostisch — das ist die strukturell richtige Grenze für einen Token-basierten Style.
   - **Pre-FOUC-Theme-Bootstrap inline im `<head>` vor dem Stylesheet-Link.** Das Theme-Script (`try { localStorage.getItem('new-nfl-theme') || prefers-color-scheme … setAttribute('data-theme') } catch {}`) läuft synchron, bevor der Browser die erste Style-Regel auswertet. Ohne diesen Schritt würde die Seite erst im Default-Theme flackern, dann auf die persistierte Wahl umspringen — ein FOUC, der bei Dark-Mode besonders auffällt (Weiß-auf-Weiß-Blitz). Ein expliziter Test (`test_base_template_bootstraps_theme_before_stylesheet`) prüft per String-Index-Vergleich, dass das Script vor dem Stylesheet steht — der Test ist knapp, aber er friert die strukturelle Invariante ein.
   - **Jinja `FileSystemLoader` + `select_autoescape(('html','xml'))` als sichere Default-Kombination.** Autoescape auf HTML ist der kritische XSS-Schutz beim User-input-Rendering (später für htmx-Partial-Responses relevant); `trim_blocks/lstrip_blocks` räumt die Whitespace-Kontrolle auf, sodass `{% for %}`-Schleifen nicht jede Iteration mit einer Leerzeile einleiten. Der Renderer ist ansonsten bewusst zustandslos — Theme, Nav, Breadcrumb werden pro `render()`-Call injiziert, keine Request-Globale. Das macht Tests trivial: jede View ist eine reine Funktion von Input-Context zu HTML-Output.
   - **Hand-assemblierter Tailwind-Subset als pragmatischer v1.0-Bootstrap.** Der Style Guide schreibt Tailwind-Utility-Klassen vor (`text-sm`, `bg-surface`, `grid-cols-4`, …) — ein vollständiger Tailwind-Build würde eine Node-Toolchain als Operator-Dependency einführen, was am Single-Operator-Windows-Setup reibt. Die pragmatische Alternative: die tatsächlich im Template verwendeten Klassen per Hand schreiben und mit den Token-Custom-Properties verbinden. Das CSS bleibt klein (~200 Zeilen statt ~10k), die Template-Struktur ist 1:1 kompatibel mit einem späteren CLI-Build — wenn das Subset in T2.6B–H zu stark wächst, kann Tailwind v4 CLI Standalone-Binary das handgeschriebene CSS mechanisch ersetzen, ohne dass eine einzige `*.html`-Datei angepasst werden muss.
   - **Jinja-Filter `fmt_number` liefert deutsche Non-Breaking-Thousands via `\u00a0` statt Komma.** Der Style Guide schreibt tabelarische Zahlen mit Tausender-Trennern vor. Ein gewöhnlicher `,` würde in deutschen Datenkontexten (wo `,` Dezimaltrenner ist) verwirren, ein Punkt wäre korrekt aber würde bei `float`-Werten mit dem englischen Dezimalpunkt kollidieren. `\u00a0` (Non-Breaking-Space) ist die ISO-korrekte und sprach-neutrale Wahl und sorgt zusätzlich dafür, dass `3 072` nicht am Zeilenende umbricht. Ein Test (`test_stat_tile_formats_integer_value_with_non_breaking_thousands`) friert die Entscheidung fest, sodass spätere Refactorings diese Invariante nicht stillschweigend kippen.

2. **Was lief nicht gut:**
   - **`setuptools.package-data`-Glob ist für Templates nicht offensichtlich.** Erster Versuch ohne `include-package-data=true` + explizitem `[tool.setuptools.package-data]`-Block hätte die Templates und statischen Assets nicht in ein `pip install`-Artefakt gepackt — sie existierten nur im Quellbaum. In unserer Konstellation (lokales Dev-Setup, kein Wheel-Roll-Out in T2.6A) fällt das nicht direkt auf, aber spätestens beim ersten VPS-Roll-out oder bei `pip install -e .` mit isoliertem Build wäre `templates/*.html` nicht verfügbar. Die Lösung (`include-package-data=true` plus `[tool.setuptools.package-data]` Glob) ist mechanisch, aber ohne expliziten Test kein Regression-Guard — die Lint-Test-Suite weiß nichts über Wheel-Packaging. Notiz für T2.6B: ersten echten View-Build gegen installiertes Package testen, nicht nur gegen Source-Baum.
   - **Ruff-Autofix hat `datetime.timezone.utc` durch `datetime.UTC` ersetzt — was nur Python 3.11+ ist.** Der Autofix ist korrekt (`target-version = "py312"` ist gesetzt), aber das impliziert eine Minimum-Runtime-Kopplung, die in keiner Runtime-Prüfung explizit steht. Die Import-Struktur `from datetime import UTC, datetime` wird ab Python 3.10 brechen — obwohl wir 3.12 als Minimum setzen (pyproject `requires-python = ">=3.12,<3.14"`), ist das eine stille Invariante, die ruff und pyproject konsistent halten, aber ohne CI-Matrix-Test nicht aktiv verifiziert wird. Für v1.0 akzeptabel (Windows-VPS-Target hat 3.12), aber Dokumentations-Schuld gegenüber zukünftigen Contributor-Situationen.
   - **`StaticAssetResolver.base_path` ist konfigurierbar, aber noch nirgends gesetzt.** Der Gedanke war, v1.1+ Content-Hash-Cache-Buster über den Resolver einzuführen (`/static/a1b2c3/app.css`) ohne Template-Changes. Aktuell verwendet aber nichts die Konfigurierbarkeit — es gibt nur den Default `/static/`. Das ist eine YAGNI-Verletzung im Keim, aber der Aufwand, den Resolver generisch zu machen, war minimal (ein `dataclass`-Feld + ein `base_path.rstrip('/')`-Join), und die strukturelle Klarheit (Single-Source-of-Truth für Static-URLs) ist auch ohne Cache-Buster wertvoll. Grenzfall: wenn T2.6B–H den Resolver nicht mehr berührt, kann der Default direkt in `base.html` stehen und das Dataclass-Konstrukt entfällt. Entscheidung vertagt bis zum ersten Schmerz.

3. **Root Cause:**
   - Theme-Tokens gehören konzeptionell in eine Schicht, die kein Build-Tool braucht: sie sind Runtime-Wissen (welche Farbe hat „primary text in dark mode"?), nicht Compile-Time-Wissen. CSS-Custom-Properties sind die native Sprach-Ebene für Runtime-Werte — sie existieren genau, weil solche Fragen nicht durch Preprocessor-Durchlauf gelöst werden sollten. Tailwind-Utility-Klassen hingegen sind Compile-Time-Konzepte (sie erzeugen statisches CSS für bekannte Token-Permutationen). Die Mischung „Tailwind-Utility-Namen + CSS-Custom-Property-Werte" ist die natürliche Arbeitsteilung: Utilities sind lookup-Shortcuts, Werte sind Runtime-Tokens.
   - Das Pre-FOUC-Script muss inline im `<head>` stehen, weil externe Skripte (selbst mit `defer`) nach dem ersten Paint laufen würden. Browser-Spezifisches Detail: `defer` wartet auf DOMContentLoaded, aber nicht auf den ersten Paint; `async` ist noch schlimmer (läuft parallel zum Parser). Inline-Synchronous-Execution ist die einzige Garantie für "vor der ersten Style-Auswertung". Der eine Test-Bruch bei Falsch-Reihenfolge wäre sehr lokal (Reihenfolge zweier `<head>`-Kinder), aber die Konsequenz (FOUC) wäre extrem sichtbar.
   - Hand-assembliertes CSS statt Tailwind-CLI reflektiert die Dependency-Hygiene-Haltung des Projekts: Python + DuckDB ist der Kern-Stack, alles andere muss den Preis der Toolchain-Erweiterung begründen. Für die v1.0-Pflicht-Views reicht ein kleiner Utility-Satz; der Tailwind-CLI-Preis (Node-Toolchain auf Windows) hat im v1.0-Scope keine ROI-Begründung. Wenn die UI-Komplexität in v1.1 explodiert, wechselt man zum CLI — aber dann ist der Preis eine Operator-Entscheidung, nicht eine Architektur-Vorentscheidung.

4. **Konkrete Methodänderung:**
   - **Ab T2.6A: Runtime-Tokens werden als CSS-Custom-Properties auf `html[data-theme=…]` modelliert; Compile-Time-Utilities nutzen diese Tokens statt fester Werte.** Regel für T2.6B–H: jede neue Farb-/Spacing-/Typo-Entscheidung landet entweder als neuer Token (wenn sie semantisch ist — „danger-border") oder nutzt einen bestehenden Token. Fest kodierte Hex-Werte in Utility-Klassen sind ein Style-Guide-Bruch.
   - **Packaging-Tests für Python-Module mit statischen Assets**: Bei Modulen, die Non-Python-Dateien verwenden (`templates/*.html`, `static/*`), muss `include-package-data=true` plus ein expliziter `[tool.setuptools.package-data]`-Block gesetzt sein. Der AST-Lint-Test deckt das nicht ab; ein dedizierter Packaging-Smoke-Test ist für T2.6B eingeplant (baut ein Wheel, installiert es in eine Scratch-Venv, verifiziert `importlib.resources.files('new_nfl.web').joinpath('templates/base.html').is_file()`).
   - **Python-Minimum-Version als explizite Laufzeit-Assertion statt nur `pyproject`-Constraint**: Ruff-Autofix-Drifts (`datetime.UTC` ab 3.11) sind nur dann stabil, wenn die Runtime-Binding aktiv durchgesetzt wird. Eine kleine `_check_python_version()`-Funktion im `bootstrap.py`-Modul oder ein pytest-Collection-Guard kann die `pyproject`-Erklärung aktiv machen.

---

## 2026-04-22 — T2.5F Player-Stats-Domäne: Multi-Position-Tolerance und drei-Mart-Rebuild
**Status:** draft (wartet auf Operator-Freigabe)

1. **Was lief gut:**
   - **Position-agnostische Aggregation im Season-Mart löst Multi-Position-Spieler sauber.** Der Taysom-Hill-Edge-Case (QB Woche 1 → TE Woche 2 → RB Woche 3 in derselben Saison) bedeutet im Grain `(season, week, player_id)` drei unterschiedliche `position`-Werte in `core.player_stats_weekly`. Das Season-Mart aggregiert `GROUP BY (season, player_id)` ohne `position` in der Gruppierung und projiziert `MODE(position) AS primary_position` — d.h. der Spieler bekommt einen „dominierenden" Positions-Label aus den tatsächlichen Wochen, seine Stats werden vollständig aggregiert (passing + rushing + receiving in derselben Zeile). Für Taysom Hill: `passing_yards=180` aus der QB-Woche, `rushing_yards=115` aus der RB-Woche, `receiving_yards=67` aus der TE-Woche, alle in einer `(2023, 00-0033357)`-Zeile. Das Career-Mart geht noch weiter: `GROUP BY player_id` ohne Saison-Dimension, mit `current_position` aus `core.player` via LEFT-JOIN (nicht aus den Stats-Wochen) — weil Karriere-Position eine Stammdaten-Eigenschaft ist, keine Stats-Eigenschaft.
   - **`COUNT(CASE WHEN <has-any-stat>)` statt `COUNT(primary_metric)` passt für heterogene Spielerpositionen.** Bei Team-Stats (T2.5E) war `COUNT(points_for)` das richtige Maß für `games_played`, weil jedes Team in jedem Spiel Punkte hat. Bei Spieler-Stats ist das nicht zutreffend: ein Defensive-Spieler hat `passing_yards=NULL`, `rushing_yards=NULL`, `receiving_yards=NULL`, `touchdowns=NULL` — würde `COUNT(passing_yards)` für QB-Hill-Wochen funktionieren, aber nicht für McCaffrey-RB-Wochen. Die OR-Disjunktion `CASE WHEN passing_yards IS NOT NULL OR rushing_yards IS NOT NULL OR receiving_yards IS NOT NULL OR touchdowns IS NOT NULL THEN 1 END` erkennt „diese Wochen-Zeile hat irgendeinen Stat-Wert" und ist positions-agnostisch. Dasselbe Muster im Career-Mart für `seasons_played`.
   - **Drei Marts in einer Promoter-Transaktion als Evidence-Einheit.** `execute_core_player_stats_load` baut `core.player_stats_weekly` + rebuildet sequenziell `mart.player_stats_weekly_v1`, `mart.player_stats_season_v1`, `mart.player_stats_career_v1` und loggt alle drei Row-Counts im `record_load_event`-Payload. Ein einziger `core-load --execute --slice player_stats_weekly`-Aufruf liefert konsistente Saison- und Karriere-Sichten. Das ist billiger als drei separate Runner-Jobs + teurer als ein Mart, aber die Konsistenz-Garantie (alle drei Marts reflektieren denselben `_loaded_at`-Snapshot des Core-Tables) ist wertvoll und entspricht der Patterns-Konvergenz: Weekly-Passthrough + Season-GroupBy + Career-GroupBy aus derselben Basis.
   - **Best-effort LEFT-JOIN auf `core.player` für `display_name`/`current_position` funktioniert über alle drei Marts einheitlich.** Das T2.5B-Pattern (DESCRIBE-Fallback, NULL wenn nicht vorhanden) ist jetzt in neun Marts identisch und damit stabil genug, um im UI-Layer (T2.6) davon auszugehen. Testisoliert ohne Teams/Players gebootstrappte Fixtures funktionieren weiter, weil LEFT-JOIN auf fehlende Tabelle degradiert zu NULL-Spalten statt zu einem Fehler.
   - **API-Verifikation vor Test-Formulierung als konkrete T2.5E-Methodänderung zahlt sich direkt aus.** Für T2.5F wurde `list_quarantine_cases(status_filter=...)` und `resolve_quarantine_case(action=..., triggered_by=...)` sofort mit der korrekten Signatur geschrieben, ohne die T2.5E-Iteration zu wiederholen. Eine explizit formulierte Lektion, die sich unmittelbar in weniger Reibung übersetzt.

2. **Was lief nicht gut:**
   - **`MODE(position)` löst nicht deterministisch bei exakt gleicher Häufigkeit.** Wenn Taysom Hill QB 1x, TE 2x, RB 1x hat, gewinnt TE. Wenn aber QB 2x und TE 2x mit gleicher Häufigkeit, ist das DuckDB-Verhalten nicht spezifiziert (erster Treffer implementierungsabhängig). Für das Season-Mart ist das okay — ein Spieler mit genau 50/50 QB/TE ist kein reales Szenario, das die UI-Darstellung bricht. Aber für die Demonstrations-Tests wurde absichtlich QB 1x + TE 2x + RB 1x gewählt, um ein eindeutiges `primary_position='TE'` zu erzwingen. Dokumentiert: Bei ex-aequo-Häufigkeit ist `primary_position` nicht-deterministisch, das UI muss eine Sortier-Regel (z.B. Offensive vor Defensive) via Ontologie lesen, nicht via SQL-Tie-Breaking.
   - **`seasons_played` vs. `games_played` im Career-Mart: definitorische Spitzfindigkeit.** `seasons_played = COUNT(DISTINCT CASE WHEN <has-any-stat> THEN season END)` zählt Saisons, in denen der Spieler irgendwann irgendwelche Stats hatte. Eine Saison mit nur einer Special-Teams-Woche ohne Offense-Stat zählt nicht — konsistent mit der `games_played`-Definition. Das ist richtig für Offense-Spieler, aber würde für Defense-Spieler (die in diesem Modell gar keine Stat-Spalten haben) immer `seasons_played=0` liefern, solange der Stat-Grain nur Offense-Metriken enthält. Für v1.0 akzeptabel (Defensive-Stats sind vertagt), aber ein Signal, dass T2.5G (falls geplant) ein Defense-Stat-Grain braucht und die Career-Mart-Definition dann generalisiert werden muss.
   - **Drei Marts bedeuten drei DESCRIBE-Fallback-Roundtrips pro Promoter-Call.** Der Schema-Cache-Verzicht aus T2.5E wird jetzt konkreter: ein `core-load --execute` öffnet jetzt 6-7 DuckDB-Verbindungen (Dedupe-Rebuild + drei Mart-Rebuilds + Quarantäne-Hook-Checks + Load-Event-Write). Noch unterhalb der Schmerzschwelle, aber das Muster skaliert nicht linear mit UI-Views — T2.6 sollte explizit darauf verzichten, pro Request einen `DESCRIBE`-Call auf `core.player` zu machen.

3. **Root Cause:**
   - Multi-Position-Spieler sind ein fachlicher Edge-Case, der sich strukturell im Daten-Layout zeigt: das Grain `(season, week, player_id)` enthält `position` als Attribute, nicht als Key-Dimension — weil ein Spieler zwar pro Woche eine Position hat, aber über die Saison mehrere Positions spielen kann. Das Season-Mart muss entscheiden: Position ist Gruppierungs-Key (würde Taysom Hill in drei Zeilen splitten) oder Attribut (eine Zeile, `MODE`-projiziert). Die Attribut-Variante ist fachlich korrekter, weil Saison-Stats-Totalen ökonomisch auf den Spieler, nicht auf die Positionsrolle bezogen sind.
   - `<has-any-stat>`-OR-Disjunktion statt `COUNT(<konkrete Metrik>)` fällt aus der Heterogenität der Spieler-Kohorte: Positions-spezifische Metriken sind `NULL` für andere Positionen. Der Stats-Grain muss „diese Zeile ist ein Datenpunkt für diesen Spieler" robust erkennen, nicht „dieser Spieler hat in dieser Zeile den kanonischen Offense-Stat gesetzt". Konzeptionell: presence (gab es Stats?) statt content (welche Stats?) als Game-Played-Definition.
   - Drei Marts als Evidence-Einheit sind die richtige Transaktionsgrenze: die Weekly-, Season-, Career-Sicht müssen konsistent sein, weil eine Season-Zeile mathematisch aus den Weekly-Zeilen folgt und eine Career-Zeile aus den Season-Zeilen. Ein Drift zwischen Marts wäre ein Evidence-Bruch. Der zusätzliche Latenz-Overhead ist der Preis für diese Konsistenz-Garantie.

4. **Konkrete Methodänderung:**
   - **Aggregierende Marts mit heterogener Kohorte verwenden `COUNT(CASE WHEN <has-any-key-metric>)` für Zähl-Semantik.** Bei Stats-Marts mit Positions-spezifischen Spalten wird nicht mehr naiv eine „repräsentative Spalte" angenommen — stattdessen wird die Presence-OR über alle primären Stat-Gruppen formuliert. Für zukünftige Aggregate (Defense-Stats, Special-Teams-Stats) wird dieses Pattern erweitert, nicht durch ein abweichendes `COUNT(*)`-Fallback ersetzt.
   - **Karriere-/Stammdaten-Joins lesen aus der Truth-Quelle, nicht aus Stats-Zeilen.** Das Career-Mart holt `current_position` via LEFT-JOIN aus `core.player`, nicht über `MODE(position)` aus Karriere-Stats. Regel: „aktuelle/kanonische" Attribute kommen aus der Stammdaten-Domäne, „Saison-Kontext"-Attribute aus der Stats-Domäne. Das vermeidet Doppel-Wahrheit (was ist Taysom Hills „aktuelle" Position — der letzte Snap aus Stats oder der Stammdaten-Eintrag?).
   - **Promoter mit multiplen Marts loggen alle Row-Counts im `record_load_event`-Payload.** Operator-Browse über `meta.load_event` soll erkennbar machen, dass ein einziger Core-Load mehrere Mart-Rebuilds ausgelöst hat und welcher Row-Count welches Mart hatte. Pattern ab T2.5F: `payload={..., 'weekly_mart_row_count': X, 'season_mart_row_count': Y, 'career_mart_row_count': Z}`. Das wird für T2.6G (Provenance-Drilldown) essentiell.

---

## 2026-04-22 — T2.5E Team-Stats-Domäne: erste aggregierende Domäne + Bye-Week-Toleranz
**Status:** draft (wartet auf Operator-Freigabe)

1. **Was lief gut:**
   - **`COUNT(points_for)` statt `COUNT(*)` für `games_played` trägt Bye-Week-Semantik direkt im SQL.** Das Saison-Aggregat würde mit `COUNT(*)` jede vorhandene Wochen-Zeile zählen — auch wenn alle Metrik-Spalten `NULL` sind (etwa aus einer fehlerhaften Stage-Zeile). Mit `COUNT(points_for)` wird nur gezählt, wenn die Kernmetrik tatsächlich gesetzt ist, was die ökonomisch richtige Definition von „gespieltes Spiel" ist: ein bye ist keine Zeile, ein Forfeit ist eine Zeile mit `points_for=NULL`, ein echtes Spiel ist eine Zeile mit `points_for=IntegerWert`. Ein synthetischer 7-Wochen-Kalender mit Bye in Woche 5 → rebuild bringt `games_played=6`, nicht 7 und nicht 5 — die Semantik bleibt stabil, auch wenn die Stage-Zeilen-Menge schwankt.
   - **Dedupe per `_loaded_at DESC` als pragmatischer Default für aggregierende Domänen.** Anders als bei Stammdaten (Teams/Players), wo ein Konflikt fachlich wichtig ist und Quarantäne triggern soll, ist bei wöchentlichen Stats der wahrscheinlichste Konfliktfall ein Reprocessing der Quelle (korrigierte Boxscore-Werte, nachgelieferte Stats). `ROW_NUMBER() OVER (PARTITION BY season, week, team_id ORDER BY _loaded_at DESC NULLS LAST, _source_file_id DESC) = 1` behält standardmäßig die letzte Version und bleibt deterministisch. Tier-B-Cross-Check bleibt orthogonal — er vergleicht Tier-A (jetzt eindeutig dedupiert) gegen Tier-B, nicht Tier-A-Rows untereinander.
   - **Zwei Read-Modelle (weekly + season) statt eines rollierenden Aggregats.** `mart.team_stats_weekly_v1` ist fast Passthrough (nur abgeleitete `point_diff`/`yard_diff`), `mart.team_stats_season_v1` ist das GROUP-BY-Aggregat. UI-Views für Team-Profil (Season-Tabelle) vs. Box-Score (Weekly-Tabelle) zeigen auf unterschiedliche Marts, ohne Aggregations-Logik im Template. Konsistent mit ADR-0029-Lektion aus T2.5D: lieber zwei kleine versionierte Marts als ein großer mit Filter-Flag.
   - **Cross-Check-Feld-Liste (`points_for`, `points_against`, `yards_for`, `turnovers`) ist absichtlich kurz.** Der Vorschlag in T2.5D-Lessons, `_CROSS_CHECK_FIELDS` in `SliceSpec` zu heben, wurde wieder nicht realisiert — diesmal aus einem anderen Grund: bei Stats ist die Feld-Auswahl diskriminierend (nicht alle Zahlen sind gleich wichtig). Die vier Kernmetriken sind die, wo Tier-A vs. Tier-B-Diskrepanz fachlich relevant ist. `penalties_for` oder `yards_against` zu vergleichen würde Noise erzeugen, weil Quellen dort oft schon unterschiedliche Counting-Regeln haben. Die lokale Konstante bleibt besser als eine erzwungene Listen-Vereinheitlichung.
   - **Best-effort LEFT JOIN mit `DESCRIBE`-Fallback bleibt robust über vier Marts hinweg.** Das T2.5B-Pattern (Team-Name aus `core.team` holen wenn da, sonst `NULL`) ist jetzt in fünf Marts identisch: `game_overview`, `player_overview`, `roster_current`, `roster_history`, `team_stats_weekly`, `team_stats_season`. Der Fall „Tests bootstrappen Teams nicht" wird deterministisch gefangen. Das wird ein bewährtes Muster für T2.5F und die UI-Views — kein Bootstrap muss mehr schematisch synchron sein.

2. **Was lief nicht gut:**
   - **`list_quarantine_cases(status_filter='open')` statt `statuses=OPEN_STATUSES` — API-Drift beim Test-Schreiben.** Zwei der acht T2.5E-Tests scheiterten beim ersten Lauf mit `TypeError: unexpected keyword argument 'statuses'`. Die echte Signatur ist `status_filter: str`, die `OPEN_STATUSES`-Tupel ist eine intern verwendete Konstante. Dasselbe Muster bei `resolve_quarantine_case`: `action='override'` + `triggered_by='andreas'`, nicht `action_kind` + `operator`. Lektion: beim ersten Test-Schreiben für eine Domäne, die `meta.quarantine_case` öffnet, die Jobs-Quarantine-API via `grep -n "def list_quarantine\|def resolve_quarantine"` einmal verifizieren, bevor die Tests formuliert werden. Kostet 30 Sekunden, spart zwei Iterationen.
   - **`mart.team_stats_season_v1` aggregiert blind über alle Stage-Zeilen, die nach Dedupe in `core` landen — kein expliziter Saison-Filter.** Für eine korrekte Saison-Sicht müsste man `WHERE season = <aktuelle>` plus Regular-Season-Filter (keine Playoff-Wochen) setzen, was nflverse implizit über die Source-Datei macht. Aktuell vertraut das Mart auf die Input-Stage, Playoff-Wochen würden mitgezählt. Für T2.5E okay, weil die Test-Fixtures keine Playoffs enthalten, aber bei realen Daten muss das ein `week <= 18`-Filter oder ein `season_type`-Join werden. Dokumentiert für T2.6D (Team-Profil UI).
   - **`_has_table('core.team')`-DESCRIBE-Fallback läuft pro Mart einmal durch DuckDB — kein Cache.** Bei drei Marts im selben `execute_core_team_stats_load`-Call sind das drei `DESCRIBE`-Queries. Trivialer Overhead heute, aber wenn T2.5F zwei Marts und T2.6 sieben UI-Views hinzufügt, summiert sich das. Optimierung (Schema-Cache in Settings oder Connection) ist bewusst vertagt — erst wenn es messbar stört.

3. **Root Cause:**
   - `COUNT(<metric>)` statt `COUNT(*)` fällt aus der SQL-Semantik: `COUNT(col)` zählt Non-NULL-Werte, `COUNT(*)` zählt Zeilen. Die Definition „gespieltes Spiel = es gibt Kernmetrik-Werte" ist intuitiv, aber muss im SQL explizit gemacht werden. Analog zu Datumsvergleichen in Finance-Code: lieber den expliziten Effekt im SQL als die Erwartung an „korrekte Input-Zeilen".
   - Dedupe per `_loaded_at DESC` bei Stats und Tier-A-Dominanz bei Stammdaten sind zwei unterschiedliche Strategien, weil die Fachsemantik unterschiedlich ist: Stammdaten ändern sich selten, eine Diskrepanz ist informativ; Stats werden oft korrigiert, eine Diskrepanz zwischen zwei nflverse-Builds ist Noise. Das passt zur generellen ADR-0007-Regel (Tier-A gewinnt), nur dass die Dedupe-Achse innerhalb von Tier-A zeitlich ist (neuestes gewinnt), nicht Tier-basiert.
   - Zwei Read-Modelle (weekly + season) sind eine Anwendung von ADR-0029 §3: „Marts sind small, targeted, versioned". Ein aggregiertes Mart mit `grain`-Flag wäre ein Antipattern, weil es UI-Views zwingt, Filter-Logik zu kennen.

4. **Konkrete Methodänderung:**
   - **Ab T2.5F: API-Verifikation vor Test-Formulierung.** Wenn ein neuer Test Funktionen aus `src/new_nfl/jobs/quarantine.py` oder `src/new_nfl/metadata/*` aufruft, deren Signatur nicht in der aktuellen Domäne bereits verwendet wurde, einmal `grep -n "def <fn>"` machen und die Signatur lesen. Keine Parameter-Namen aus Memory raten. Der Verifikationsschritt wird in die T2-Tranche-Checkliste aufgenommen (vor „Tests schreiben").
   - **Aggregierende Marts dokumentieren Saison-Filter-Annahmen im Modul-Docstring.** `mart.team_stats_season_v1` bekommt einen expliziten Kommentar „vertraut auf Stage-Filter; für Playoff-Trennung erwartet Upstream `season_type`-Spalte oder `week <= 18`-Constraint". Gleiche Regel für T2.5F und jede zukünftige GROUP-BY-basierte Read-Projektion.
   - **`games_played = COUNT(<metric_col>)`-Pattern als Standard für Event-basierte Aggregate.** Jedes zukünftige Aggregat, das „wie viele Events/Games/Spiele" zählt, nimmt `COUNT(primary_metric)` statt `COUNT(*)`, außer es ist semantisch wirklich „wie viele Zeilen existieren". Die primäre Metrik ist die, deren Fehlen den Event als „nicht gezählt" qualifiziert (points bei Team-Stats, attempts/completions bei Player-Stats).

5. **Verifikation:**
   - `pytest` grün: 175/175 (+8 in [tests/test_team_stats.py](../tests/test_team_stats.py): dry-run-profile, happy-execute-baut-beide-Marts, bye-week-game-count, duplicate-stage-rows-dedupe-by-loaded-at, tier-b-disagreement-opens-quarantine, core-load-dispatch-routes-team-stats, operator-override-resolves, protocol-round-trip).
   - CLI: `python -m new_nfl.cli core-load --adapter-id nflverse_bulk --slice team_stats_weekly --execute` druckt `SLICE_KEY=team_stats_weekly`, `DISTINCT_TEAM_SEASON_WEEK_COUNT=…`, `CONFLICT_COUNT=…`, `MART_QUALIFIED_TABLE=mart.team_stats_weekly_v1`, `SEASON_MART_QUALIFIED_TABLE=mart.team_stats_season_v1`, `SEASON_MART_ROW_COUNT=…`; `python -m new_nfl.cli mart-rebuild --mart-key team_stats_weekly_v1` und `--mart-key team_stats_season_v1` rebuilden unabhängig.
   - `PROJECT_STATE.md` markiert T2.5E abgeschlossen, nächster Bolzen T2.5F (Player Stats Aggregate); `T2_3_PLAN.md` §4 T2.5E-Block mit DoD gefüllt.

---

## 2026-04-22 — T2.5D Rosters-Domäne: erstes bitemporales Modell + Trade-Event-Stream
**Status:** draft (wartet auf Operator-Freigabe)

1. **Was lief gut:**
   - **Gap-Trick `week - ROW_NUMBER() OVER (PARTITION BY …, attrs ORDER BY week)` liefert Intervall-Bau in einem Schritt.** Die klassische SQL-Muster-Bibliothek zur Interval-Aggregation fährt typischerweise in Rekursion oder zweifacher Self-Join. Der `week - ROW_NUMBER()`-Trick reduziert das auf eine CTE-Kaskade ohne Rekursion: zwei aufeinanderfolgende Wochen mit identischem Schlüssel-Tupel erzeugen identischen `week - rn`-Wert, also denselben `grp`; ein Gap erzeugt einen neuen `grp`. Die anschließende `GROUP BY grp MIN/MAX(week)` baut die Intervalle direkt. Das passt perfekt zur Bitemporal-Semantik aus ADR-0032, weil Business-Time hier diskret ist (Woche, nicht Sekunde) und das Ergebnis deterministisch stabil bleibt.
   - **`valid_to_week IS NULL ⇔ raw_valid_to_week >= global_max_week` als einfache Close-Regel.** Die Alternative („schließe das Intervall wenn die nächste Woche nicht gelesen wurde") hätte einen zweiten Pass über die Woche-Sequenz gebraucht und Ambiguität bei Bye-Weeks erzeugt. Stattdessen berechnet eine separate `season_max`-CTE die globale Max-Woche pro Saison, und das letzte Intervall eines Spielers gilt genau dann als offen, wenn sein `MAX(week)` diese Grenze erreicht. Tests verwenden einen Anker-Spieler (BUF Wochen 1..9) um die Saison-Max deterministisch zu setzen — damit hängen die Test-Assertions nicht an irgendeinem impliziten Default.
   - **`meta.roster_event`-Rebuild Python-seitig statt als weitere CTE.** Die Event-Ableitung (signed/released/trade/promoted/demoted) scannt die sortierten Intervalle pro Spieler in O(n) Schritten und emittiert Events mit klarer Heuristik (adjacent → trade, gap → released+signed). Das wäre als window-Function-SQL unleserlich geworden (drei `LAG`s mindestens plus CASE-Kaskade). Python-Scan ist idempotent per `DELETE WHERE season=…` vor dem Insert und bleibt beobachtbar (print-bares Zwischenergebnis). Trade-Bewertung als Policy (konservativ: nur lücken-freie Wechsel sind Trades) bleibt isoliert und austauschbar.
   - **Cross-Check-Grain `(player_id, team_id, season, week)` statt Intervall-Grain.** Die Tier-B-Diskrepanz entsteht im Stage-Layer, nicht im Intervall-Layer. Ein Intervall-Grain hätte erfordert, Stage-Rows erst zu Intervallen zu verdichten und dann zu vergleichen, was die Semantik von „zwei Quellen disagreen pro Woche" verwischt. Row-level-Grain liefert stattdessen pro abweichender Woche einen eigenen Quarantäne-Case mit `scope_ref='PLAYER:TEAM:SEASON:Wxx'`, der exakt die betroffene Woche nennt. Konsistent mit T2.5A–C (field-level quarantine).
   - **Zwei Read-Modelle, nicht eines mit Filter-Flag.** `mart.roster_current_v1` und `mart.roster_history_v1` haben unterschiedliche UI-Zielseiten (Current → Team-Roster heute, History → Player-Profil-Timeline). Sie als getrennte versionierte Marts zu materialisieren (beide rebuild-bar via `mart-rebuild --mart-key …`) vermeidet, dass UI-Code Intervall-Filterung kennt. ADR-0029 (Read-Modell-Trennung) bleibt sauber — UI liest `mart.*`, nicht Intervalle.
   - **`CoreRosterLoadResult` satisfies `CoreLoadResultLike` via Protocol-Isinstance-Test.** Die in T2.5C beschlossene Methodänderung („jedes Core-Load-Modul deklariert seinen Protocol-Vertrag explizit") ist in T2.5D erstmalig operationalisiert: `test_core_roster_result_satisfies_core_load_protocol` ruft `isinstance(result, CoreLoadResultLike)` und validiert jedes der elf Kern-Attribute. Bei einem Domänen-Load mit zusätzlichen Feldern (`interval_count`, `event_count`, `history_row_count`) bleibt der gemeinsame CLI-Pfad unberührt, Domänen-spezifische Zeilen werden per `isinstance(result, CoreRosterLoadResult)`-Branch ergänzt.

2. **Was lief nicht gut:**
   - **Dedupe duplicate week rows kam erst als nachträgliche CTE-Stufe rein.** Initial hatte `normalized` → `grouped` direkt hintereinander gehängt, aber Stage-Daten können dieselbe Woche mehrfach enthalten (unterschiedliche `_loaded_at`, Reprocessing). Ohne `deduped`-Stufe (`ROW_NUMBER() OVER (PARTITION BY player_id, team_id, season, week ORDER BY _loaded_at DESC) = 1`) wären duplikate Wochen in den Gap-Trick geflossen und hätten 1-Woche-Intervalle erzeugt. Gut, dass der Fix vor dem ersten Testlauf saß — das Problem wäre im Happy-Case unsichtbar geblieben und erst beim ersten Reprocessing aufgetaucht.
   - **`_CROSS_CHECK_FIELDS` als lokale Konstante wiederholt sich jetzt vier Mal (Teams, Games, Players, Rosters).** Der T2.5C-Vorschlag, das in `SliceSpec` zu ziehen, wurde in T2.5D nicht realisiert — die Liste bleibt im Modul-Kopf. Grund: die SliceSpec müsste dann auch feld-spezifische Canonicalization-Regeln transportieren (z. B. `UPPER` für `position`, `LOWER` für `status`), was den Spec-Schema verdoppeln würde. Die Kopie bleibt akzeptabler als die Abstraktion, aber bei Slice 5+ (Team-Stats, Player-Stats) ist die Gelegenheit da, das Muster neu zu bewerten.
   - **Trade-Heuristik deckt noch keine Same-Day-Wechsel oder Mid-Week-Trades ab.** Die Wochen-Granularität aus ADR-0032 §4 ist eine bewusste Vereinfachung, aber sie kollidiert mit der Realität, dass NFL-Trades oft an Dienstag/Mittwoch stattfinden und die Woche „gespalten" wird. Das aktuelle Modell annotiert den Trade an der Woche, in der der neue Vertrag wirksam wird — die Wahrheit liegt zwischen Dienstag und Freitag, aber wir modellieren Woche-als-Atom. Dokumentiert in ADR-0032 §9, offen für Phase-1.5.

3. **Root Cause:**
   - Der Gap-Trick funktioniert, weil Business-Time hier diskret und dicht ist (Wochen 1..n ohne Sprünge innerhalb einer Saison). Bei kontinuierlicher Time (Timestamp) oder sparser Time (Kalender-Daten) wäre ein anderes Muster nötig gewesen (LAG-basiert oder `tsrange` in Postgres). DuckDB hat keinen nativen Interval-Type für Business-Time, aber das stört nicht — Integer-Wochen sind das richtige Primitiv.
   - `valid_to_week IS NULL` als Open-Flag (statt Sentinel `9999` oder negativer Integer) folgt ADR-0032 §5: `NULL` hat in SQL den semantisch korrekten Effekt („unbekanntes/offenes Ende"), und jede `WHERE valid_to_week IS NULL`-Abfrage bleibt grepbar. Eine Sentinel-Zahl hätte die Gefahr, versehentlich in Vergleiche zu geraten.
   - Die Python-Event-Scan ist idiomatisch für den Use Case: die Heuristik ist fachlich (nicht relational), und sie in SQL zu zwingen würde Lesbarkeit opfern. DuckDB liefert den Input bereits sortiert, also ist der Python-Scan O(n) über das Intervall-Set.

4. **Konkrete Methodänderung:**
   - **Ab T2.5E (Team Stats) wird die Zeitachse explizit im Modul-Header dokumentiert.** Wenn ein Core-Modul bitemporal ist (ADR-0032-Pattern), beginnt der Docstring mit `"""Bitemporal: …"""` und erklärt Business-Time-Granularität + Open-Interval-Regel. Wenn snapshot-basiert, `"""Snapshot: …"""`. Das erlaubt Future-Self einen `grep -l "^Bitemporal"` und macht den Unterschied zwischen den zwei Modell-Typen sichtbar ohne den vollen Modul-Körper zu lesen.
   - **Jeder neue bitemporale Core-Load bekommt einen Interval-Close-Regel-Test** (analog `test_gap_between_teams_emits_released_plus_signed_instead_of_trade`). Die Close-Regel ist die fehleranfälligste Stelle — zu viele Möglichkeiten, versehentlich Intervalle zu früh zu schließen oder zu spät offen zu halten. Der Test muss die Regel in Worten als Kommentar tragen und die Regel in SQL vollständig reflektieren.
   - **Event-Stream-Domänen (Roster-Events, später Stat-Events) trennen Persist-Idempotenz vom Event-Scan.** Pattern: `DELETE FROM meta.<event_table> WHERE scope=…` gefolgt von einem INSERT aller neu abgeleiteten Events für diesen Scope. Kein UPSERT, keine Event-Merge-Logik. Damit ist der Event-Stream garantiert rebuild-bar aus `core.*` und hängt nicht an einer Historie der Event-Tabelle selbst.

5. **Verifikation:**
   - `pytest` grün: 167/167 (+10 in [tests/test_rosters.py](../tests/test_rosters.py): dry-run-profile, happy-execute-baut-beide-Marts, trade-detection-weeks-adjacent, gap-between-teams-released-plus-signed, tier-b-disagreement-opens-quarantine, core-load-dispatch-routes-rosters, operator-override-resolves, roster-current-only-open-intervals, roster-history-full-timeline, protocol-round-trip).
   - CLI: `python -m new_nfl.cli core-load --adapter-id nflverse_bulk --slice rosters --execute` druckt `SLICE_KEY=rosters`, `INTERVAL_COUNT=…`, `OPEN_INTERVAL_COUNT=…`, `EVENT_COUNT=…`, `TRADE_EVENT_COUNT=…`, `CONFLICT_COUNT=…`, `MART_QUALIFIED_TABLE=mart.roster_current_v1`, `HISTORY_QUALIFIED_TABLE=mart.roster_history_v1`, `HISTORY_ROW_COUNT=…`; `python -m new_nfl.cli mart-rebuild --mart-key roster_current_v1` und `--mart-key roster_history_v1` rebuilden unabhängig.
   - `PROJECT_STATE.md` markiert T2.5D abgeschlossen, nächster Bolzen T2.5E (Team Stats Aggregate); ADR-0032 `Proposed`, T2_3_PLAN-Tabelle aktualisiert.

---

## 2026-04-22 — T2.5C Players-Domäne + erste reale Dedupe-Anwendung + Protocol-Refactor
**Status:** draft (wartet auf Operator-Freigabe)

1. **Was lief gut:**
   - **Protocol-Refactor als Vorbedingung lieferte Dividende schon im selben Chat.** `CoreLoadResultLike` in [src/new_nfl/core/result.py](../src/new_nfl/core/result.py) als `@runtime_checkable`-Protocol mit elf Kern-Attributen hat die drei nahezu identischen Teams/Games/Players-Branches im CLI-Dispatch auf einen kollabiert (von ~50 auf ~20 Zeilen). Der Protocol-Ansatz beats Basisklasse, weil `frozen=True`-Dataclasses keine Inheritance-Book­keeping erzwingen — jede Core-Domäne bleibt selbsterklärend. Slice-spezifische Felder (`distinct_team_count`/`distinct_game_count`/`distinct_player_count`) bleiben per `hasattr`-Helper zugänglich. Die T2.5A-Lessons-Prophezeiung „ab Slice 3+ wird der Dispatch unsicher" ist damit abgefangen, nicht ausgesessen.
   - **Ontology-Integration als best-effort, nicht als Vorbedingung.** `mart.player_overview_v1` liefert `position_is_known` aus `meta.ontology_value_set_member` — wenn keine aktive Ontology-Version geladen ist, fällt der Wert auf `NULL` statt den Mart-Rebuild zu blockieren. Kritisch für Umgebungen, in denen `ontology-load` noch nicht lief (fresh bootstrap, Tests ohne Ontology-Seed). Der Mart bleibt rebuildbar, die Ontology-Signatur bleibt zukunftssicher sichtbar.
   - **Dedupe-Brücke bewusst als separate Funktion, nicht als Seiteneffekt von `execute_core_player_load`.** `run_player_dedupe_from_core(settings)` ist operator-getriggert über CLI `dedupe-run --source core-player`, nicht implizit im Core-Load. Grund: Dedupe ist eine eigene, ressourcen- und zeit-intensive Operation (T2.4B-Stufen normalize → block → score → cluster → review) — sie in den Core-Load zu verschmelzen würde die Ingest-Latenz koppeln und den Operator-Workflow unsichtbar machen. Der CLI-Flag `--source core-player` (vs `--demo`) bleibt das einzige neue Vertragselement.
   - **Stage-Schema tolerant für Minimal-Zeilen.** Tier-A-Fixture trägt absichtlich einen Player mit leeren Strings in allen optionalen Spalten; TRY_CAST-Ketten + `NULLIF(TRIM(...), '')` machen aus leeren Strings echte `NULL`s. Keine IntegrityError-Kette, kein „accidentally 0 statt NULL"-Fehler in numerischen Spalten (Risiko bei `CAST(NULLIF(TRIM(''), '') AS INTEGER)` → `NULL`, nicht `0`).
   - **Dedupe-Fixture nutzt denselben echten Cluster wie T2.4B-Demo.** Tier-A enthält zwei Patrick-Mahomes-Player-IDs (`00-0033873` + `00-0099999`) mit identischem Namen, Geburtsjahr und Position — der T2.4B-RuleBasedScorer erzeugt die gleiche Auto-Merge-Score wie im Demo-Set. Damit beweist der T2.5C-Integrationstest nicht nur „Dedupe läuft über `core.player`", sondern „Dedupe produziert den erwarteten Cluster-Output gegen reale Input-Struktur". Das ist die Brücke zwischen T2.4B-Skelett-Test und T2.5C-Anwendungs-Test.

2. **Was lief nicht gut:**
   - **`position_is_known` bleibt ohne Ontology-Load `NULL` — in der Realität fast immer.** Nach T2.4A existiert die Ontology-Surface, aber der Bootstrap aktiviert keine Default-Version. In einer frischen Developer-Umgebung oder einem CI-Run ohne expliziten `ontology-load` ist die Flag weder `TRUE` noch `FALSE`, sondern `NULL` — was den UI-Code später zwingt, einen dritten Zustand („Ontologie nicht geladen") zu rendern. Die Dokumentation ist im Mart-Modul klar, aber der Bootstrap-Default müsste `ontology/v0_1/` als aktive Version aktivieren, damit der Zustandsraum im Regelbetrieb nur `TRUE`/`FALSE` ist.
   - **`_CROSS_CHECK_FIELDS` wiederholt sich zwischen Teams/Games/Players ohne gemeinsame Abstraktion.** Jedes Core-Load-Modul deklariert die Liste der Cross-Check-Felder als lokale Konstante. Bewusst — Feld-Auswahl ist Fachsemantik —, aber bei Slice 4+ (Rosters, Stats) muss man immer wieder im Modul-Kopf nachschlagen, welche Felder überhaupt verglichen werden. Kandidat für eine slice-seitige Deklaration (`SliceSpec.cross_check_fields`) in T2.5D, wenn dort die vierte Liste dazukommt.
   - **Dedupe-Test hängt an der Demo-Threshold-Logik.** Der T2.5C-Cluster-Test verlässt sich auf den Default `lower_threshold=0.50`/`upper_threshold=0.85`. Ändert T2.4B diese Werte in einer späteren Iteration, bricht der T2.5C-Test ohne Warnung. Mitigation: Thresholds wurden in `T2_3_PLAN.md` §4 nicht als Vertrag fixiert, aber `run_player_dedupe_from_core` nimmt sie als benannte Parameter — der Test sollte die Thresholds explizit passieren statt auf Defaults zu vertrauen.

3. **Root Cause:**
   - Protocol-vs-Basisklasse ist kein Design-Zufall: `frozen=True` macht `dataclass`-Vererbung semantisch komplex (Field-Order, Keyword-Only-Defaults, `__eq__`-Kollision). Protocol mit `runtime_checkable` hält die einzelnen Dataclasses flach und erlaubt `isinstance`-Checks, ohne irgendeine Klasse zu zwingen, den Protocol-Typ explizit zu inheritieren — das passt zur Architekturphilosophie „jede Domäne ist lokal selbsterklärend".
   - Die Dedupe-Brücke als separate Funktion ist konsistent mit der T2.4B-Entscheidung, Dedupe als explizite fünfte Ingest-Stufe zu modellieren (ADR-0027). Sie in den Core-Load zu pressen wäre ein Verstoß gegen den ADR-Geist.
   - `position_is_known`-NULL-Fallback ist eine ADR-0026-Konsequenz: die Ontology ist Code-vor-DB, aber die DB-Projektion ist optional pro Environment. Eine globale „Ontology muss aktiv sein"-Invariante würde T2.4A retrospektiv um eine Pflicht erweitern.

4. **Konkrete Methodänderung:**
   - **Ab T2.5D deklariert jedes Core-Load-Modul seinen `CoreLoadResultLike`-Vertrag explizit**, indem es den Protocol importiert und eine Zeile `_: CoreLoadResultLike = CoreXLoadResult(...)`-kompatiblen Instantiierungs-Test mitbringt (MyPy-freundlich, ohne Runtime-Kosten). Damit bleibt die Kompatibilität bei Protocol-Erweiterungen sichtbar.
   - **Der Bootstrap aktiviert ab T2.6A (frühester UI-Konsument) eine Default-Ontology-Version.** Konkret: `bootstrap_local_environment` prüft, ob eine aktive Version existiert, und `ontology-load`-t `ontology/v0_1/` ohne `--no-activate`, wenn nicht. Begründung: `position_is_known` und ähnliche Ontology-Ableitungen müssen im UI-Rendering binäre Wahrheitswerte liefern, nicht dreiwertige.
   - **Reale Anwendung einer Pipeline-Stufe hat einen eigenen Integrationstest mit der ersten Domäne**, nicht als Seiteneffekt. Template für T2.5D: wenn dort ein neuer Pipeline-Schritt Domäne-übergreifend ist (z. B. Trade-Erkennung), bekommt er einen `test_rosters_drives_<feature>`-Test, der die Pipeline gegen live `core.roster_membership` fährt und die erwarteten Cluster/Events assertet.

5. **Verifikation:**
   - `pytest` grün: 157/157 (+9 in [tests/test_players.py](../tests/test_players.py): dry-run-profile, full execute + mart-build mit `full_name`/`is_active`/`position_is_known`-Ableitungen, Tier-B-disagreement-opens-quarantine, operator-override-resolves, core-load-dispatch-routes-players, dedupe-from-core-clusters-mahomes, dedupe-from-core-fails-without-core-player, real-HTTP-roundtrip, HTTP-roundtrip-feeds-Tier-B-quarantine).
   - CLI: `python -m new_nfl.cli core-load --adapter-id nflverse_bulk --slice players --execute` druckt `SLICE_KEY=players`, `DISTINCT_PLAYER_COUNT=…`, `CONFLICT_COUNT=…`, `CROSS_CHECK_ADAPTERS=official_context_web`, `MART_QUALIFIED_TABLE=mart.player_overview_v1`; `python -m new_nfl.cli dedupe-run --domain players --source core-player` druckt `SOURCE_REF=core.player`, `INPUT_RECORD_COUNT=…`, `AUTO_MERGE_PAIR_COUNT=…`, `CLUSTER=…`.
   - `PROJECT_STATE.md` markiert T2.5C abgeschlossen, nächster Bolzen T2.5D (Rosters zeitbezogen).

---

## 2026-04-22 — T2.5B Games-Domäne + erste reale HTTP-Runde
**Status:** draft (wartet auf Operator-Freigabe)

1. **Was lief gut:**
   - **Teams-Muster 1:1 portiert, ohne Copy-Schmerz.** `core/games.py` und `mart/game_overview.py` wurden nach exakt derselben Struktur wie ihre Teams-Pendants gebaut (Required-Columns-Check, `ROW_NUMBER OVER PARTITION BY LOWER(TRIM(key))`, TRY_CAST für numerische/Datum-Felder, spalten-tolerante Mart-Projektion per `DESCRIBE` + `_opt()`). Die Slice-Abstraktion aus T2.5A zahlt sich ab der zweiten Domäne aus: T2.5B kostete keine neuen Entscheidungen, nur Umsetzung — ADR-0031 kann deshalb final `Accepted`.
   - **Abgeleitete Felder im Mart statt im Core.** `is_completed = (home_score IS NOT NULL AND away_score IS NOT NULL)` und `winner_team ∈ {home_team, away_team, 'TIE', NULL}` sind reine Sicht-Konzepte und wurden bewusst nur im `mart.game_overview_v1` materialisiert, nicht in `core.game`. Trennung ADR-0029 bleibt sauber: `core.game` trägt Fakten, `mart.*` trägt Interpretation.
   - **Echter HTTP-Roundtrip ohne neue Testabhängigkeit.** stdlib-`ThreadingHTTPServer` in Daemon-Thread auf Port 0, Custom `BaseHTTPRequestHandler` serviert CSV-Bytes — der Test ruft `execute_remote_fetch(remote_url_override=server.url)` und `execute_stage_load` auf und beweist `urllib.request.urlopen` als produktiven Pfad end-to-end. Kein `respx`, kein `pytest-httpserver`, kein `requests-mock` — die Abhängigkeitsfläche bleibt auf der stdlib.
   - **`list-slices` als pipe-separierter Operator-Befehl.** Acht Spalten (`adapter_id | slice_key | tier_role | stage_qualified_table | core_table | mart_key | has_url | label`), keine Tabelle mit Alignment-Padding — bleibt grepbar aus Shell-Pipes und konsistent mit den vorhandenen pipe-separierten Outputs (`list-sources`, `list-adapters`). Registry ist jetzt ohne Python-Interpreter inspizierbar.
   - **Tie- und ungespielt-Fälle von Anfang an in Fixtures.** Vier Tier-A-Games im Happy-Test decken Auswärtssieg (DET@KC), Heimsieg (SF-NYJ), Tie (BAL-LV 23:23 mit OT=1) und ungespielt/NULL-Scores (KC-DEN Week 18) ab. Die abgeleiteten `winner_team`/`is_completed`-Werte sind damit an allen vier Ecken des Zustandsraums getestet, nicht nur am Happy-Case.

2. **Was lief nicht gut:**
   - **Union-Return-Typ wächst weiter.** `execute_core_load` liefert jetzt `CoreLoadResult | CoreTeamLoadResult | CoreGameLoadResult`. Die T2.5A-Methodnotiz („gemeinsame Basis-Klasse oder Protocol") ist bis T2.5C offen — bei Players wäre der Refactor jetzt dringlich, sonst wächst der Dispatch im CLI um einen vierten `isinstance`-Branch.
   - **`remote_url=""` bleibt stiller Tier-B-Vertrag.** `(official_context_web, games)` hat weiterhin leeres `remote_url` per Design — Operator pinnt pro Lauf eine konkrete URL via `--remote-url`, Tests überschreiben via `remote_url_override`. Das ist dokumentiert im SliceSpec-Kommentar und in ADR-0031-Implementierungsnotizen, aber es ist kein selbst-erklärender Vertrag — ein `list-slices`-Leser könnte `has_url=no` als „defekt" fehlinterpretieren.
   - **Kein separater Mart-Test für `winner_team='TIE'`-Fall ausserhalb der Integrationsebene.** Die Tie-Ableitung wird im vollen Execute-Test geprüft, nicht in einer isolierten Unit. Risiko gering (vier Cases nebeneinander in einem Lauf fangen die Logik ab), aber bei zukünftigen Änderungen am Mart-Builder fehlt der Feingranular-Test.

3. **Root Cause:**
   - Der Union-Return-Drift ist ein natürliches Symptom der „eine Tranche = eine Domäne"-Methodik: Refactor verzögert sich, weil jede einzelne Tranche sauber weiterläuft. Erst die Kaskade aus drei Domänen macht den Refactor zur Vorbedingung.
   - Das Tier-B-`remote_url=""`-Muster ist eine Absicht, keine Nachlässigkeit: Tier-B-Feeds variieren pro Operator und Saison (beta-API, manuelle Snapshots), während Tier-A im nflverse-Release gepinnt ist. Ein Default-URL für Tier-B wäre irreführend. Trotzdem verdient das Muster eine lautere Dokumentation.

4. **Konkrete Methodänderung:**
   - **Ab T2.5C wird der Result-Type-Refactor Vorbedingung.** Gemeinsames Protocol `CoreLoadResultLike` mit `qualified_table`, `row_count`, `mart_qualified_table`, `ingest_run_id`, `run_status` — slice-spezifische Zusatzfelder kommen als optionale Attribute. Motivation: CLI-Dispatch ohne Type-Branching, Runner-Executor-Rückgabe einheitlich.
   - **Jeder neue `cross_check`-Slice mit `remote_url=""` braucht eine Notiz im SliceSpec-`notes`-Feld**, die den Override-Mechanismus nennt. Template: „remote_url empty by design: operators pin a concrete URL per run via --remote-url or tests override via remote_url_override."
   - **Reale HTTP-Flows gegen stdlib-Server sind ab jetzt die Default-Testform für neue Adapter-Slices**, solange kein optionales `respx`/`pytest-httpserver` begründet ist. Fixture-only-Pfad bleibt erlaubt für Stage-Load-Tests, nicht mehr für Fetch-Tests.

5. **Verifikation:**
   - `pytest` grün: 148/148 (+7 in [tests/test_games.py](../tests/test_games.py): dry-run-profile, full execute + mart-build mit `winner_team`-Ableitungen, Tier-B-disagreement-opens-quarantine, operator-override-resolves, core-load-dispatch-routes-games, real-HTTP-roundtrip, HTTP-roundtrip-feeds-Tier-B-quarantine).
   - CLI: `python -m new_nfl.cli list-slices` druckt die fünf Registry-Einträge mit `tier_role`/`has_url`/`core_table`/`mart_key`; `python -m new_nfl.cli core-load --adapter-id nflverse_bulk --slice games --execute` druckt `SLICE_KEY=games`, `DISTINCT_GAME_COUNT=…`, `CONFLICT_COUNT=…`, `CROSS_CHECK_ADAPTERS=official_context_web` (sobald Tier-B-Stage gefüttert ist).
   - ADR-0031 [docs/adr/ADR-0031-adapter-slice-strategy.md](adr/ADR-0031-adapter-slice-strategy.md) final `Accepted` mit Implementierungsnotizen; Index-Tabelle [docs/adr/README.md](adr/README.md) zeigt `Accepted (2026-04-22) | T2.5A / T2.5B`.
   - `PROJECT_STATE.md` markiert T2.5B abgeschlossen, nächster Bolzen T2.5C (Players-Domäne).

---

## 2026-04-22 — T2.5A Teams-Domäne + Adapter-Slice-Registry
**Status:** draft (wartet auf Operator-Freigabe)

1. **Was lief gut:**
   - **Code-Registry statt Datenbank-Tabelle für Slices.** `SliceSpec` als eingefrorener Dataclass in [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py) — drei statische Einträge, drei Zeilen pro Slice, klar gruppiert nach `adapter_id`. Kein `meta.adapter_slice`, keine Seed-SQL, kein Runtime-CRUD. Ein Slice ist heute ein Stück Code, das mit Tests versioniert wird; erst wenn v1.1 Operator-editierbare Slices braucht, wird daraus eine Tabelle (ADR-0031 §Alternativen).
   - **`DEFAULT_SLICE_KEY = "schedule_field_dictionary"` hält T2.0A bit-kompatibel.** Der Default-Slice schaltet im `remote_fetch`/`stage_load`/`core_load`-Pfad den Slice-Registry-Dispatch ab und lässt die alte Filename-basierte Logik durchfallen. Resultat: kein einziger bestehender T2.0A-Test musste angepasst werden (außer `test_runner_cli` für einen vermeintlich-neuen `job_key`-Suffix, der aus demselben Grund wieder entfernt wurde). Operator sieht CLI-Ausgaben für Default-Slice identisch zu vor T2.5A.
   - **Tier-A gewinnt, Tier-B generiert Evidence.** Tier-A-Werte landen in `core.team`, Tier-B-Diskrepanzen werden pro `team_id` zu einem einzelnen `meta.quarantine_case` aggregiert (eine Case-Row mit N Field-Level-Entries in `evidence_refs_json`) — nicht pro Field. Quarantäne-Zahl bleibt operator-verdaubar (eine Entscheidung pro betroffenem Team), Evidenz bleibt vollständig. Test: KC-Farbe + SF-Name → zwei Cases, vier wäre Noise.
   - **Mart-Builder spalten-tolerant per `DESCRIBE`.** `mart.team_overview_v1` liest Stage-Spalten dynamisch; optional fehlende Spalten werden als `NULL` materialisiert. Das vermeidet den T2.3D-Schmerz, wo die erste Version des Mart-Builders fest codierte Spalten-Listen hatte und bei schema-Drift crashte.
   - **Ontologie-Terme `conference` + `division`** ergänzt in TOML — das Slice trägt die Fachsemantik (AFC/NFC, 8 modern divisions) vom Stage bis ins Mart, ohne hartcodierte String-Vergleiche im Core-Load.

2. **Was lief nicht gut:**
   - **Kein echter HTTP-Adapter für `official_context_web` in T2.5A.** Tier-B wird in Tests direkt in die Stage-Tabelle geseedet. Bewusst akzeptiert: das Ziel war die Cross-Check-Mechanik, nicht die HTTP-Implementierung. T2.5B trägt die erste reale HTTP-Variante nach — solange ist ADR-0031 zurecht nur `Proposed`.
   - **`meta.adapter_slice` als Runtime-Registry noch nicht projiziert.** Slices existieren nur im Code; eine Observability-Sicht „welche Slices sind registriert" braucht heute einen Python-Interpreter. Für T2.6 Freshness-Dashboard ist das Backlog.
   - **`_target_object_for_slice`-Fallthrough war subtil.** Erste Version der Funktion gab für den Default-Slice den `SliceSpec.stage_target_object` zurück — bricht damit die Filename-basierte T2.0A-Erwartung `stg.nflverse_bulk_payload`. Fix: `return None` für Default, Caller behält Legacy-Logik. Der Bug zeigt, dass „alles geht durch die Registry" eine verlockende-aber-falsche Generalisierung ist; Default-Slice ist bewusst als Escape-Hatch modelliert.
   - **`CoreLoadResult | CoreTeamLoadResult` als Rückgabetyp.** `execute_core_load` hat jetzt einen Union-Return — CLI muss branch-weise auf den Typ prüfen. Das ist noch sauber in einer Dispatch-Funktion, wird aber ab Slice 3+ (Players, Rosters) unsicher. Refactor-Ziel für T2.5C: gemeinsame Basis-Klasse oder Protocol mit `qualified_table`/`row_count`/`mart_qualified_table` + slice-spezifische Zusatzfelder.

3. **Root Cause:**
   - Slice-Abstraktion vs. Legacy-Pfad: Das Default-Slice-Konstrukt ist eine Brücke, weil T2.0A ohne Slice-Konzept entstanden ist. Sauberer wäre, T2.0A nachträglich in einen expliziten `schedule_field_dictionary`-Slice zu überführen — das ist aber Refactor-Arbeit ohne Nutzen für T2.5A und widerspricht „kleine Tranchen".
   - Tier-B in Tests fixturisiert: `official_context_web` als Adapter-Stub existiert schon seit T1.2 für den `list-sources`-Pfad, aber eine HTTP-Implementierung gehört logisch in die erste Domäne, die sie braucht (Games), nicht in die Setup-Tranche (Teams).

4. **Konkrete Methodänderung:**
   - **Neue Slices kommen ab T2.5B als `SliceSpec`-Eintrag im Registry-Modul**, nicht als `source_registry`-Row. `source_registry` bleibt eine Adapter-Liste, keine Slice-Liste. ADR-0031 §Offene Punkte hält fest, wann das umgedreht wird (frühestens v1.1, wenn Operator-Editierbarkeit zur Anforderung wird).
   - **Jedes neue Core-Load-Modul gibt einen Result-Typ mit denselben drei Kern-Feldern zurück**: `qualified_table`, `row_count`, `mart_qualified_table`. Slice-spezifische Felder kommen als Zusatz. Motivation: der CLI-Dispatcher kann Standard-Ausgabe ohne Type-Branching drucken.
   - **Tier-B-Cross-Check-Felder werden explizit per Konstante im Core-Load-Modul deklariert** (`_CROSS_CHECK_FIELDS` in `core/teams.py`), nicht aus SliceSpec abgeleitet — weil Field-Auswahl Fachsemantik ist (welche Werte sind publikumsrelevant genug für Quarantäne), nicht Technik.

5. **Verifikation:**
   - `pytest` grün: 141/141 (+5 in [tests/test_teams.py](../tests/test_teams.py): dry-run-profile, full execute + mart-build, Tier-B-disagreement-opens-quarantine, operator-override-resolves, core-load-dispatch-routes-teams).
   - CLI: `python -m new_nfl.cli core-load --adapter-id nflverse_bulk --slice teams --execute` erzeugt `core.team` + `mart.team_overview_v1`, druckt `SLICE_KEY=teams`, `CONFLICT_COUNT=…`, `OPENED_QUARANTINE_CASE_IDS=…`, `CROSS_CHECK_ADAPTERS=official_context_web`.
   - ADR-0031 [docs/adr/ADR-0031-adapter-slice-strategy.md](adr/ADR-0031-adapter-slice-strategy.md) als `Proposed` im Index aufgenommen; Acceptance wartet auf erste reale HTTP-Variante in T2.5B.
   - `PROJECT_STATE.md` markiert T2.5A abgeschlossen, nächster Bolzen T2.5B (Games-Domäne).

---

## 2026-04-16 — T2.4B Dedupe-Pipeline-Skelett
**Status:** draft (wartet auf Operator-Freigabe)

1. **Was lief gut:**
   - **Fünf-Stufen-Trennung explizit als Module** (`normalize`, `block`, `score`, `cluster`, `review`, plus `pipeline.py`). Jede Stufe hat eine schlanke API (Funktion in, Datenklasse out), ist isoliert testbar (sechs Stage-Tests vor dem ersten E2E-Lauf) und lässt sich später ohne Pipeline-Rewrite austauschen — speziell `Scorer` als `typing.Protocol` macht den späteren ML-Tausch zu einer Drei-Zeilen-Änderung in `pipeline.py`.
   - **Demo-Set deckt alle drei Buckets in einem Lauf** (Auto-Merge: Mahomes-Twin, Review: A. Rodgers vs Aaron Rodgers + P. Mahomes Initial-Match, No-Match: Tom Brady singleton). Damit ist der DoD-Smoke-Pfad nicht synthetisch-leer, sondern führt jeden Code-Pfad einmal aus.
   - **Score-Tabelle ist bewusst flach** (sechs feste Stufen 1.00/0.95/0.80/0.70/0.60/0.50). Reicht für Phase-1, ist trivial dokumentier- und review-bar; Operator versteht nach 30 Sekunden, warum ein Pair in Auto-Merge oder Review landet. Komplexere gewichtete Summen wären für einen Stub Premature Optimization.
   - **Block-Drop für Records ohne Last-Name.** Statt sie als O(n)-Vergleichspartner durchzuschieben, fallen sie aus dem Block-Pool — fail-loud-Prinzip aus dem Manifest. In realen Daten sind das Datenfehler, kein Match-Kandidat.
   - **Singletons als eigene Cluster gezählt.** `cluster_count` spiegelt die wahre Anzahl distinkter Entitäten, nicht nur die Auto-Merge-Cluster — sonst gäbe es bei sechs Inputs ohne jeden Auto-Merge `cluster_count = 0`, was irreführend ist.

2. **Was lief nicht gut:**
   - **`meta.cluster_assignment` fehlt.** Cluster werden in v0_1 nicht persistiert (nur `cluster_count`). Für T2.5C ist das ein Vorausschulden — die Pipeline kann nicht out-of-the-box „welche Records gehören zur selben Entität" beantworten, sobald sie den DuckDB-Lebenszyklus verlässt. Bewusst akzeptiert: persistente Cluster-Tabelle wäre Vorgriff auf T2.5C-Anforderungen, die heute nicht bekannt sind.
   - **`dedupe-review-resolve` CLI fehlt.** Operator kann Review-Items nur lesen (`dedupe-review-list`), nicht direkt schließen. Analog zu `quarantine-resolve` aus T2.3C — wäre symmetrisch sinnvoll, ist aber nicht im DoD von T2.4B. Backlog-Eintrag in ADR-0027 §Offene Punkte.
   - **Kein Adapter zwischen `core.player` und `RawPlayerRecord`.** Die Pipeline läuft heute nur gegen das eingebaute Demo-Set oder gegen extern injizierte `list[RawPlayerRecord]`. Sobald T2.5C echte Player-Records erzeugt, braucht es einen `core_to_dedupe_input(...)`-Adapter. Heute zu früh — Schema von `core.player` steht noch nicht fest.
   - **Kein Runner-Executor für `dedupe-run`.** Der CLI-Pfad ruft `run_player_dedupe` direkt, nicht über `meta.job_run`. Begründung: T2.3D/T2.3C-Pattern routen Schreibpfade über den Runner, aber Demo-Smokes sind keine Produktions-Runs. Sobald T2.5C Dedupe gegen reale Daten fährt, sollte ein `dedupe_run`-Executor analog zu `mart_build` her.

3. **Root Cause:**
   - Cluster-Persistenz und Review-Resolve-Pfad hängen am Player-Schema. Solange `core.player` nicht existiert (kommt mit T2.5C), gibt es keinen Pin, an dem ein FK festgemacht werden könnte. Manifest §3.7: keine Schema-Entscheidungen unter spekulativem Druck.
   - Runner-Bypass ist temporär — der Demo-Pfad braucht keine Replay-Garantie. Sobald „echte" Dedupe-Runs Quarantäne erzeugen können, dreht sich das.

4. **Konkrete Methodänderung:**
   - **Pipeline-Stufen werden ab T2.5 immer mit eigenem Pydantic-Modell als Stage-Output definiert** (nicht: Tuple/Dict). T2.4B folgt dem schon (`NormalizedPlayer`, `BlockedPair`, `ScoredPair`, `Cluster`); ist die Default-Form für jede neue Pipeline.
   - **Stub-Pipelines bekommen Demo-Inputs aus dem Code, nicht aus Test-Fixtures.** Tests fahren auf demselben Demo-Set wie der CLI-Smoke (`DEMO_PLAYER_RECORDS`). Gleichzeitig sind sie Doku — ein neuer Mitarbeiter sieht in einer Datei, was die Pipeline tut.
   - **Scorer-Tausch geht über `Scorer`-Protocol-Argument** in der Top-Level-Funktion (`run_player_dedupe(scorer=...)`). Kein Registry, kein Settings-Schalter. Wenn T2.5C einen anderen Scorer braucht, wird er als Default-Argument durchgereicht.

5. **Verifikation:**
   - `pytest` grün: 13 Tests in [tests/test_dedupe.py](../tests/test_dedupe.py), gesamte Suite 136 passed.
   - `cli dedupe-run --domain players --demo` erzeugt einen `meta.dedupe_run`-Datensatz mit `RUN_STATUS=success`, `INPUT_RECORD_COUNT=6`, `AUTO_MERGE_PAIR_COUNT >= 1`, `REVIEW_PAIR_COUNT >= 1`.
   - `cli dedupe-review-list --domain players` listet die offenen Review-Pairs sortiert nach Score.
   - ADR-0027 final `Accepted` mit Implementierungs-Notizen + Offenen-Punkte-Backlog für T2.5C.
   - `PROJECT_STATE.md` markiert T2.4 vollständig abgeschlossen, nächster Bolzen ist T2.5A (Teams-Domäne).

---

## 2026-04-16 — T2.4A Ontology-as-Code-Skelett
**Status:** draft (wartet auf Operator-Freigabe)

1. **Was lief gut:**
   - **TOML statt YAML.** Stdlib `tomllib` (Python 3.12+) deckt die rein deklarative Struktur (Term, Aliases, Value Sets) vollständig ab — keine zusätzliche Runtime-Abhängigkeit (PyYAML), keine Versionspflege. ADR-0026 hatte YAML als Default vorgesehen, das war im Implementierungs-Druck eine vermeidbare Abhängigkeit.
   - **`content_sha256`-Idempotenz** über sortierten Hash aus `(Dateiname, Inhalt)` — wiederholter Load identischer Quelle ist garantiert No-Op und liefert dieselbe `ontology_version_id` zurück. Kein Diff-Vergleich pro Tabelle, kein UPSERT-Pfad: einmal geladen, fertig. `is_active`-Flag pro `source_dir` macht Versions-Switching billig.
   - **Service-Surface mit Pydantic-Modellen** (`OntologyTerm`, `OntologyValueSet`, `OntologyValueSetMember`, `OntologyTermDetail`) — CLI, Tests und (später) Web-Routen reden über stabile Typen, nicht über rohe Dicts. Konsistenz zur Quarantäne- und Mart-Surface aus T2.3C/D.
   - **Alias-Auflösung in `describe_term`** — `cli ontology-show --term-key pos` findet `position`, ohne dass Operator die kanonische Form raten muss. `alias_lower`-Spalte ist vorberechnet, kein `LOWER(...)` in der WHERE-Klausel.

2. **Was lief nicht gut:**
   - `meta.ontology_mapping` ist als Tabelle angelegt, in v0_1 aber unbenutzt — der Schema-Aufwand ist gerechtfertigt, weil T2.5 die Tabelle braucht, aber das ist genau der Typ Vorgriff, vor dem Manifest §3.7 warnt. Bewusst akzeptiert: das Schema einer einzelnen Tabelle ist günstig, ein Migration-Pfad mit FK-Hinzufügung später wäre teurer.
   - Kein impliziter Bootstrap-Load. Der Operator muss `cli ontology-load --source-dir ontology/v0_1` einmal explizit ausführen. Das ist gewollt (Promotion soll explizite Version referenzieren), aber für die nächste Tranche eine offene UX-Frage: `cli bootstrap` könnte v0_1 aus dem Repo-Root automatisch laden.
   - Im Loader hartcodiert: TOML-Erwartung an `term_key`, `aliases`, `value_sets[*].key`, `value_sets[*].members[*].value`. Kein Schema-Validator (Pydantic gegen Roh-TOML) — Fehler werden als `ValueError` mit Dateiname geworfen. Reicht für v0_1, aber sobald externe Beiträger Terme schreiben, will man Pydantic-Validation auf der Rohstruktur.

3. **Root Cause:**
   - YAML im ADR war Erblast aus dem A0-Konzept, wo eine breite Werkzeug-Auswahl noch sinnvoll war. Im Implementierungs-Druck zeigt sich, dass für drei flach strukturierte Term-Dateien TOML reicht — und die Manifest-§3.13-Pflicht zur minimal-möglichen Abhängigkeit gewinnt.
   - `ontology_mapping`-Tabelle ohne Loader-Pfad: bewusster Trade-off zwischen jetzigem Schema-Vorgriff und späterem ALTER-TABLE-Risiko.

4. **Konkrete Methodänderung:**
   - **Default-Format für deklarative Repo-Quellen ist TOML**, solange stdlib reicht. YAML nur, wenn Anchors/Multiline/Komplexstruktur das brauchen. ADR-Updates spiegeln diese Entscheidung als Implementierungs-Notiz wider.
   - **Neue Domänen-Loader stempeln `content_sha256`** auf der Versions-Zeile (nicht erst pro Datei). Erlaubt Idempotenz auf Verzeichnisebene.
   - Nächster Bolzen (T2.4B) prüft, ob ein gemeinsamer `Loader`-Helper-Layer (`hash_directory`, `apply_idempotent`) die Wiederholung lohnt — heute zu früh, T2.4A ist die erste Instanz.

5. **Verifikation:**
   - `pytest` grün: 11 Tests in [tests/test_ontology.py](../tests/test_ontology.py), gesamte Suite 123 passed.
   - CLI-Smoke: `ontology-load` druckt `IS_NEW=yes` beim ersten Lauf, `IS_NEW=no` beim zweiten gegen identische Quelle.
   - `meta.ontology_version` enthält pro Quellverzeichnis genau eine `is_active=TRUE`-Zeile; ein zweiter Load aus alternativem Verzeichnis erzeugt zweite aktive Version (parallele Quellen erlaubt).
   - ADR-0026 final `Accepted` mit Implementierungs-Notizen; `docs/adr/README.md` zeigt neuen Status; `PROJECT_STATE.md` markiert T2.4A ✅.

---

## 2026-04-14 — T2.3E ADR-Index abgeschlossen
**Status:** accepted (Operator-Freigabe 2026-04-14)

1. **Was lief gut:**
   - `docs/adr/README.md` ist jetzt ein vollständiger Index ADR-0001–ADR-0030 mit Status + Tranchen-Anker. Status-Quelle bleibt das ADR-Dokument selbst (single source of truth), der Index ist nur Navigations- und Übersichts-Layer.
   - Bewusste Trennung: T2.3-eigene ADRs (0025/0028/0029) sind `Accepted`. ADR-0026/0027/0030 bleiben `Proposed` bis zur Umsetzung in T2.4A/T2.4B/T2.6A — keine vorgezogene Akzeptanz, die später relativiert werden müsste.

2. **Was lief nicht gut:**
   - ADR-0001 bis ADR-0018 verwenden eine ältere Status-Konvention (`Status: Accepted` als Inline-Zeile statt eigener Section). Der Index normalisiert das nach außen, aber die Heterogenität bleibt im Bestand. Kein Refactor, weil low-value.
   - Die Tabelle ist statisch — Status-Drift im ADR-Dokument selbst wird nicht automatisch gespiegelt. Bei nächster Tranche prüfen, ob ein Mini-Skript den Index regeneriert.

3. **Root Cause:**
   - Die Inline-Status-Konvention der frühen ADRs ist Erblast aus A0 vor `LESSONS_LEARNED_PROTOCOL.md`. Die neueren ADRs nutzen `## Status` als Section, was maschinenlesbar ist.

4. **Konkrete Methodänderung:**
   - Neue ADRs (ab ADR-0031) verwenden ausschließlich die `## Status`-Section-Konvention. Bestand bleibt unangetastet.
   - Beim nächsten Index-Update (T2.4-ADRs `Accepted` setzen) Snippet `awk '/^## Status/{getline; print}'` als Regenerator verwenden.

5. **Verifikation:**
   - `docs/adr/README.md` mit Tabelle ADR-0001–ADR-0030 + Status + Tranchen-Anker.
   - `PROJECT_STATE.md` und `T2_3_PLAN.md` markieren T2.3E ✅; nächster Bolzen ist T2.4A (Ontology-as-Code).

---

## 2026-04-14 — T2.3D Read-Modell-Trennung (`mart.*`)
**Status:** accepted (Operator-Freigabe 2026-04-14)

1. **Was lief gut:**
   - Schema + Builder + Runner-Executor + CLI + Lint-Test in einer geschlossenen Tranche. Nach Abschluss zeigt der `qualified_table` aller Read-Wege auf `mart.schedule_field_dictionary_v1`, kein gemischter Zustand.
   - `core-load --execute` ruft den Mart-Builder direkt am Ende des Execute-Pfads — kein zweiter Operator-Schritt nötig, kein Risiko, dass UI gegen veraltetes Mart läuft. Gleichzeitig bleibt `cli mart-rebuild` als unabhängiger Runner-Job verfügbar (für `_v2`-Bumps oder Repair).
   - **AST-basierter Lint-Test** (`test_read_modules_do_not_reference_core_or_stg_directly`) erkennt String-Literale, die `core.` / `stg.` / `raw/` enthalten — Docstrings sind sauber exempt. Damit wird die ADR-0029-Pflicht zu einem objektiven Code-Review-Kriterium statt einer Erinnerung.
   - **Spalten-toleranter Builder**: Quell-Schema von `core.schedule_field_dictionary` darf optionale Provenance-Spalten (`_source_file_id`, `_adapter_id`, `_canonicalized_at`/`_loaded_at`) tragen oder weglassen. Tests-Fixtures, die die alte Form pflegten, brauchten keine Schema-Anpassung.

2. **Was lief nicht gut:**
   - Die Read-Module heißen weiterhin `core_browse.py`/`core_lookup.py`/`core_summary.py`. Inhaltlich sind es jetzt Mart-Reader. Konsistente Umbenennung bewusst aufgeschoben, weil sie ansonsten Diff-Volumen ohne Verhaltensgewinn produziert; bleibt offener Refactor-Punkt für T2.5.
   - `MAX(built_at)`-Roundtrip in DuckDB schlug initial mit `ModuleNotFoundError: pytz` fehl — aufgefallen erst beim Test, nicht beim Local-Smoke. Dropdown auf `datetime.now()` aus Python war die richtige Wahl, aber das Pytz-Problem ist eine Latenzbombe für jede künftige `MAX(timestamp)`-Aggregation.
   - `assert qualified_table == MART_SCHEDULE_FIELD_DICTIONARY_V1` ist in den Read-Modulen verteilt redundant. Bleibt als billige Defense-in-Depth, lässt sich aber bei jedem neuen Mart-Reader vergessen — sollte beim Refactor in T2.5 zentralisiert werden.

3. **Root Cause:**
   - DuckDB-`pytz`-Abhängigkeit für Timestamp-Aggregate ist eine bekannte Eigenheit, die in unserem `requirements.txt` nicht abgedeckt ist. Wir vermeiden sie heute, indem Build-Timestamps Python-seitig erzeugt werden — aber die Falle bleibt für jeden, der naiv `SELECT MAX(timestamp_col)` in DuckDB schreibt.
   - Die Read-Modul-Namensgebung stammt aus T2.0C, wo es noch keine Mart-Schicht gab. Refactor-Aufschub ist eine Scope-Entscheidung.

4. **Konkrete Methodänderung:**
   - Jeder neue Mart-Reader-Modul wird ab T2.5 direkt unter dem `mart_*.py`-Präfix angelegt; bestehende `core_*.py`-Reader werden im Rahmen der ersten T2.5-Domäne mit umbenannt (atomarer Rename + Test-Update).
   - DuckDB-Pytz-Falle in `LESSONS_LEARNED` als Snippet-Warnung dokumentiert; bei künftigen `built_at`/`updated_at`-Aggregaten Python-seitig oder über `epoch_ms`-Casts arbeiten.
   - Lint-Wand erweitern, sobald HTTP-API-Module entstehen (T2.6): die `READ_MODULES`-Liste wird einfach ergänzt.

5. **Verifikation:**
   - `tests/test_mart.py` (9 Tests) + volle Suite grün (112/112).
   - ADR-0029 auf `Accepted` mit Implementierungs-Notizen.
   - `PROJECT_STATE.md` und `T2_3_PLAN.md` aktualisiert auf Nächstpunkt T2.3E (ADR-Indexpflege).

---

## 2026-04-14 — T2.3C Quarantäne-Domäne
**Status:** accepted (Operator-Freigabe 2026-04-14)

1. **Was lief gut:**
   - Schema + Domain-Modul + Runner-Hook + CLI + Tests in einem geschlossenen Rutsch. Kein Pfad bleibt „still" — jeder `runner_exhausted`-Run öffnet automatisch einen `meta.quarantine_case` (Manifest §3.5 / §3.12 erfüllt).
   - DoD-Test (`test_quarantine_replay_resolves_case_on_success`) deckt den vollen Operator-Zyklus ab: Fehler → Auto-Case → Defektbehebung → `quarantine-resolve --action replay` → neuer `job_run_id` → Case `resolved` → `recovery_action` verlinkt.
   - Replay-Failed-Pfad explizit getestet (`test_quarantine_replay_failed_keeps_case_in_progress`): alter Case bleibt `in_progress`, Runner-Hook öffnet sauber einen neuen Case für den neuen Failed Run — keine stille Vermischung.
   - Import-Zyklus `runner ↔ quarantine` ohne neue Zwischenschicht gelöst (Lazy-Imports in beiden Hook-Funktionen). Kein Architektur-Krater für einen technischen Import-Effekt.

2. **Was lief nicht gut:**
   - Severity-Eskalation ist im SQL mit mehrstufiger `CASE`-Kaskade umgesetzt. Funktionsfähig und getestet, aber die Ordnungsregel (`info < warning < error < critical`) lebt halb in Python-Literalen und halb in SQL. Wenn ein fünftes Level dazukommt, muss an zwei Stellen gepflegt werden.
   - Das CLI-Kommando für die „offenen" Listenansicht zeigt beide Stati (`open` + `in_progress`) zusammen, filtert aber nicht prominent in der Ausgabe — Operator muss den Detailview nehmen, um `in_progress` zu erkennen. Akzeptabel in v1.0 CLI-Only, aber bleibt UI-Punkt für T2.6.
   - `evidence_refs_json` bleibt frei-form. Für den Auto-Quarantäne-Pfad ist das Schema implizit stabil, aber externe Opener (künftige Stage-Load-Parser-Fehler) haben noch keinen Vertrag.

3. **Root Cause:**
   - Severity-Ordnung als Literal-Strings war Design-Default aus T2.3A-Mustern; für Phase-1 tragfähig, aber nicht skalierend. Eine `meta.quarantine_severity`-Referenz-Tabelle wäre konsequenter, ist aber für nur vier Werte Overkill.
   - Das generische `evidence_refs`-Feld ist gewollt offen gelassen, weil jede Quell-Domäne eine andere Art Beleg liefert (Dateizeile, Adapter-Request, Schema-Diff). Formalisierung kommt, wenn die ersten drei Opener-Stellen existieren (T2.4/T2.5).

4. **Konkrete Methodänderung:**
   - Bei jedem neuen Executor in T2.4/T2.5: Fehlerpfad muss explizit entscheiden, ob er `open_quarantine_case` selbst ruft (mit scope-spezifischem `reason_code`) oder auf den Runner-Hook vertraut. Wird als Checkliste in den LL-Eintrag jeder Domäne-Tranche aufgenommen.
   - Sobald drei verschiedene Opener existieren: `evidence_refs`-Shape konsolidieren (Pydantic-Model oder JSON-Schema).
   - `quarantine-resolve --action replay` wird zur erwarteten Demo-Flow-Abnahme für jede Phase-1-Domäne (T2.5).

5. **Verifikation:**
   - `tests/test_quarantine.py` (13 Tests) + volle Suite grün (103/103).
   - ADR-0028 auf `Accepted` mit Implementierungs-Notizen.
   - `PROJECT_STATE.md` und `T2_3_PLAN.md` aktualisiert auf Nächstpunkt T2.3D.

---

## 2026-04-13 — T2.3B Internal Runner
**Status:** accepted (Operator-Freigabe 2026-04-13)

1. **Was lief gut:**
   - Klares Bündel Runner-Modul + CLI-Migration + geteilter DB-Helper in einem Rutsch. Kein halber Pfad übrig: `fetch-remote` und `stage-load` laufen ausschließlich über den Runner, jedes CLI-Invocation hinterlässt `meta.job_run`-Evidence (Manifest §3.13 erfüllt).
   - Test-Paket deckt alle DoD-Punkte ab: Claim-Atomarität (Threads + `duckdb.Error`-Toleranz), Concurrency-Key-Block, Retry-Pfad, Retry-Exhausted, deterministischer Replay mit Event-Verkettung, Serve-Mode mit `stop_when_idle`.
   - Suche nach „darkem" Pfad an CLI-Surface vor Runner-Routing hat sich gelohnt: die vorhandene `_run_cli_job`-Helper-Klammer hält beide Kommandos symmetrisch und erlaubt spätere Executor-Zuschaltung ohne Reib.

2. **Was lief nicht gut:**
   - `JobType`-Literal musste mitten im Testlauf zu `str` geöffnet werden, weil Pydantic bei Test-Executoren (`flaky_test`, `always_fails_test`) validiert und ablehnte. Hätte beim Design früher auffallen können — Executor-Registry ist der wahre Gate, nicht das Pydantic-Feld.
   - `metadata.py` behält eigene private Helper (`_connect`/`_row_to_dict`/`_new_id`). Der geteilte `_db.py` ist eingeführt, aber die Alt-Duplikate sind nicht entfernt. Bewusste Scope-Begrenzung, aber bleibt offener Refactor-Punkt.
   - Zwei Alt-Tests (`test_cli_remote_fetch`, `test_cli_stage_load`) prüfen nicht, dass ein `meta.job_run` entsteht — sie bleiben grün, weil die CLI-Ausgabe strukturgleich ist. Der neue Test `test_cli_fetch_remote_routes_through_runner_records_job_run` schließt die Lücke.

3. **Root Cause:**
   - Pydantic-`Literal` wurde aus Dokumentationsnutzen gewählt, nicht als echte Vertragsfläche — die Erweiterbarkeit (ADR-0026 Ontology, ADR-0028 Quarantäne, Tests) erzwingt offene Job-Type-Strings.
   - Der geteilte Helper ist jetzt eingeführt, aber die vorhandene Duplikation in `metadata.py` wurde als nicht blockierend eingestuft, um die Tranche fokussiert zu halten.

4. **Konkrete Methodänderung:**
   - Künftig bei neuen Pydantic-Feldern zwischen „dokumentarischer Liste" (Tuple/Set von Konstanten) und „harter Vertragsfläche" (Literal) explizit unterscheiden. Aufnehmen in `ENGINEERING_MANIFEST` beim nächsten Bump (v1.4).
   - Alt-Helper in `metadata.py` konsolidieren, sobald eine ohnehin anstehende Migration dort Code anfasst (z. B. T2.3D Read-Modell-Trennung). Kein eigener Refactor-Sprint.
   - Ab T2.3C wird jede Operator-CLI, die Daten verändert, in einem Runner-Job gekapselt — keine neuen Direktpfade zu Core- oder Mart-Schreibungen.

5. **Verifikation:**
   - `tests/test_jobs_runner.py::test_replay_failed_run_reproduces_deterministically` bleibt grün.
   - Nächste CLI-Erweiterung (Quarantäne in T2.3C) wird reviewed darauf, dass sie `meta.job_run` erzeugt.
   - `docs/adr/ADR-0025-internal-job-and-run-model.md` auf Status `Accepted`, inklusive „Implementierungs-Notizen (T2.3B)".

---

## 2026-04-13 — T2.3A Job-/Run-Modell-Skeleton
**Status:** accepted (Operator-Freigabe 2026-04-13)

1. **Was lief gut:**
   - Wiederverwendung der bestehenden `TABLE_SPECS`/`ensure_metadata_surface`-Infrastruktur hat 7 neue `meta.*`-Tabellen ohne separates Migrations-Framework erlaubt. Idempotent, Test-grün im ersten Lauf.
   - Klarer Schnitt: Schema + Pydantic-Modelle + Service-Funktionen + CLI als eine Tranche. Keine halbe Abstraktion zurückgelassen.
   - Test-First-Gefühl durch deterministische `tmp_path`-Bootstraps — 12 neue Tests, volle Suite grün (73/73) in ~78s.

2. **Was lief nicht gut:**
   - `src/new_nfl/jobs/model.py` hat eine kleine Helfer-Duplikation (`_connect`, `_row_to_dict`, `_new_id`) gegenüber `metadata.py`. Bewusst in Kauf genommen, um zirkuläre Imports zu vermeiden, aber riecht nach Refactor-Bedarf spätestens bei T2.3B.
   - Kein expliziter Rollback-Test (Tabellen löschen + neu aufbauen mit Bestandsdaten). Für T2.3A akzeptabel, weil Neu-Tabellen; ab T2.3B nachziehen.

3. **Root Cause:**
   - `metadata.py` exportiert die privaten Helper nicht, und bei Erstanlage eines neuen Sub-Pakets war der Weg des geringsten Widerstands, sie zu duplizieren.
   - Die Test-Strategie in `TEST_STRATEGY.md` nennt Replay-Tests, aber keinen expliziten Schema-Rollback-Test für neue Migrations-Schritte.

4. **Konkrete Methodänderung:**
   - In T2.3B: gemeinsames Basis-Modul `src/new_nfl/_db.py` (oder `metadata._internal`) für `_connect`/`_row_to_dict`/`_new_id`, bevor Runner, Quarantine und Ontology weitere Duplikate erzeugen. Als To-do im ADR-0025-Folge-Eintrag festhalten.
   - `TEST_STRATEGY.md` um Punkt „Schema-Evolution: neues `TABLE_SPECS`-Feld muss mit Alt-DB und leerer DB getestet werden" ergänzen, ab T2.3B verbindlich.

5. **Verifikation:**
   - In T2.3B existiert ein geteiltes DB-Helper-Modul und `jobs/model.py` importiert es (kein eigenes `_connect` mehr).
   - `TEST_STRATEGY.md` enthält die Schema-Evolution-Regel; der Runner-Test nutzt sie.

---

## 2026-04-13 — Use-Case-Validierung + Architektur-Baseline (v0.3 / v1.3)
**Status:** accepted (Operator-Freigabe 2026-04-13)

1. **Was lief gut:**
   - Strukturiertes Use-Case-Dokument mit OK/Nein/Kommentar-Slots hat in einem Durchgang vollständige Abnahme aller fachlichen Punkte ermöglicht.
   - Bündel-Lieferung (5 Dokumente in einem Durchgang) hat Architektur-, Manifest-, UI-, Plan- und ADR-Ebene konsistent verzahnt.
   - Frühzeitiges Aufdecken des Widerspruchs UC-14/UC-15 (UI-Aktionen) ↔ Frage 6 (CLI-only) hat eine spätere Doppelarbeit verhindert.

2. **Was lief nicht gut:**
   - Erster Zeitplan-Vorschlag (v1.0 bis Ende April) war ohne Rückfrage übernommen und hätte zu unrealistischer Tranche-Dichte geführt. Korrektur erst auf Operator-Hinweis.
   - Kein expliziter Chat-Handoff-Plan vor Freigabe der 5 Dokumente — Operator musste das Thema selbst einbringen.

3. **Root Cause:**
   - Termin wurde aus User-Antwort übernommen, ohne gegen real vorhandene Tranche-Last geprüft zu werden.
   - Es gab bisher kein Protokoll, das die KI verpflichtet, proaktiv Chat-Handoffs vorzuschlagen.

4. **Konkrete Methodänderung:**
   - `CHAT_HANDOFF_PROTOCOL.md` §2.2: KI ist verpflichtet, Chat-Handoff aktiv vorzuschlagen, sobald Trigger zutreffen.
   - Vor Übernahme von Terminen prüft die KI implizit: passt das in den existierenden Plan? Wenn nicht, Hinweis vor Übernahme.
   - In Manifest v1.4 (späterer Bump) Aufnahme als eigenes Prinzip „Termine werden gegen reale Tranche-Last validiert".

5. **Verifikation:**
   - Nächste Termin-Übernahme erfolgt mit explizitem Sanity-Check.
   - Die KI bietet im nächsten logischen Schnittpunkt (z. B. nach T2.3) den Chat-Handoff aktiv an.

---
