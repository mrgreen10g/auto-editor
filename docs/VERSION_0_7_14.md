# 0.7.14rc1 — Uzbek combat speech and cards

Combat timing uses actual recognized, word-timed speech instead of forcing all
written script sentences onto an improvised recording. Explicit section times
remain authoritative. Empty recognition still opens a recoverable review draft.
Written montage notes and URLs are not treated as spoken content.

- Deduplicated intro pairs, timed individually from spoken names.
- Fighter identity ignores quoted nicknames/rematch suffixes for source binding;
  nicknames and observed Uzbek transliterations remain recognition aliases.
- Concrete records no longer require the word “rekord”. Bundles retain age,
  record, KO/SUB counts and fighting background; supported UFC rates, percentages,
  first-round finishes and qualified tactical arguments are selected separately
  from ordinary prose. Fighter labels are added where ownership is known.
- False “1 KO” from “every second seeks a knockout” and age-difference confusion
  are covered by regression tests. Written but unspoken numbers are not inserted.
- Repeat recognition is limited to uncertain important clauses. The original
  survives retries that lose a bet, lack textual overlap, change clear numbers,
  or fail to improve word confidence. The prompt contains names/terminology,
  not the script’s narrative or statistics. Both Uzbek profiles use this pass.
- Clear active-fight candidates retain selective automatic acceptance. Source
  name normalization and more spoken action cues make more inserts eligible;
  this does not lower scene/timer validation thresholds or use another fighter.
- Opaque ivory/red/blue graphics with a glove symbol; statistics at upper right.
  The same artwork is used in export and interactive preview.

## Public name catalogue

Snapshot 2026-09-24: 3,214 unique UFC directory names, pagination exhausted.
Sources: https://www.ufc.com/athletes/all and individual linked athlete cards.

TOP DOG snapshot is **partial: 37 names**, from the first directory page and the
announced TOP DOG 43 card: https://topdogfc.ru/fighters/ and https://topdogfc.ru/.
The official directory advertises 321 fighters; fetching the remaining dynamic
pages was blocked by connection failures/empty browser content. Do not advertise
full TOP DOG coverage. No career statistics are frozen into the name catalogue.

## Verification and limits

Regression suite covers speech timing, numeric contradictions, rematches,
nicknames, fighter ownership, multiple intro pairs, tactical cards and football
word-number facts. All six supplied scripts parse (17 analysis blocks). Actual
saved project ASR reproduces the three intro pairs and grounded numeric facts.
Rendered designs were inspected over a frame of the supplied prepared video.
A whole-recording beam-5 experiment lost an existing bet and was rejected;
the production path keeps baseline recognition and uses guarded local retries.
The supplied archive lacks the full original fight sources, so full rescanning
of those 25–30 minute originals has not been claimed as verified.

For an existing episode, rerun speech analysis and fight-insert selection to
apply the new timing and source bindings. Existing rendered MP4 files do not
change automatically. Keep the original project when comparing results.
