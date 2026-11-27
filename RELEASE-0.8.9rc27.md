# 0.8.9rc27 — Uzbek football information and Windows text shortcuts

- Uzbek football Long and Shorts use the same information-panel renderers as Russian football, including numeric tiles, possession indicators and winning/losing streak markers. Timed facts cover squads, injuries, substitutions, discipline, VAR, results, form, table points, attacks, defence, tactics, workload and risks. Conditional statements retain their uncertainty; numbers are not inferred from hypothetical outcomes.
- Fact cards follow spoken sentence boundaries. Explicit forecasts, Telegram overlays and manual card edits retain their own protected intervals. Spoken numbers are formatted as digits; limited acoustic spelling repairs require the value in the authored block. Unrecognized statements are not expanded into unspoken script paragraphs.
- Editorial headings no longer become extra fixtures or forecasts. Forecast matching checks the beneficiary and market, isolates personal selections from preceding reasoning, and separates a new fixture embedded in the previous ASR window. “Bavariya” no longer matches the forecast cue “variant”.
- Added recognition of spoken recap wording and common acoustic variants in Liverpool forecasts. Short, bounded retries recover obvious repeated-syllable decoder failures from the original audio; this changes recognition only, never the audio mix, levels, speed or timing.
- Native Windows shortcuts are handled by physical key code for editable Entry, Text, Spinbox and Combobox fields. A thread-local message hook queues actions for the Tk event loop instead of re-entering Tcl. Copy/paste, select-all, cut, undo and redo are exercised with actual Windows input under Russian and Latin layouts, both standalone and in the full application.
- Template groups: РУ лонг / РУ шортс / УЗ лонг / УЗ шортс.

## Reference checks

Both audio/script pairs in the supplied Uzbek football archive were processed with the product's local Uzbek model and recognition settings. Each script now produces two analyses. The sources are shortened spoken versions of the scripts, so absent script paragraphs are not displayed as spoken facts.

- 16.11: section starts 38.14 / 190.92 s, recap 342.54 s; both primary forecasts and both recap forecasts mapped to their spoken selections.
- 24.11: section starts 24.14 / 131.26 s, recap 261.96 s; primary choices at approximately 126.84 s and 259.03 s; recap choices at 266.48 s and 271.36 s. The corrupt 241–262 s decoder window was re-recognized in short chunks, recovering the second choice rather than placing it at the match introduction.
- Every generated information card from both references was exported in Long and Shorts geometry without layout errors. Automated regression checks cover historical-statistic/forecast confusion, incorrect beneficiary, recap boundaries, spoken-number guards and decoder-retry caching.

Recognition is still probabilistic. These checks do not establish perfect transcription of every word or name; ambiguous selections retain the review path. Existing manually edited timelines are preserved. Run analysis again to apply new detection to an existing episode.
