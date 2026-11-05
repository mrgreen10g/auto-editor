# 0.8.9rc13 — Uzbek section recognition fixes (partial corpus result)

- Keep introductory fixture announcements in the introduction when the script
  has explicit analysis headings. Previously this created duplicate match blocks.
  Reproduced in 22 of the 46 supplied audio/script pairs; all 49 scripts parse.
- Preserve mixed spoken/explicit headings and normalize apostrophes in ordinal
  headings; do not treat a fight weight prefix as part of a fighter name.
- Recognize Uzbek letter pronunciations of OKMK in acoustic name matching.
- Recognize shortened `Demi` and `Demek` recap cues only with recap context.
- Invalidate old football speech annotations so new analysis applies the fix.
- Include a resumable private-corpus audit utility. Its outputs must not be
  committed. Inferred profiles require review; scripts are not necessarily
  verbatim transcripts and cannot be used as unqualified WER ground truth.

Validation: 125 Uzbek regression tests (including full-section, mixed-layout,
curly-apostrophe and weight-announcement cases). Windows integration/build results are recorded in PROJECT_HANDOFF.

Scope: this is NOT a retrained neural model or completion of the 46-recording
review. The previous identical-transcript comparison on 12.10 reduced speech
annotation review flags from 73 to 3; on 14.08 both versions had 0 flags.
Those counts are not final rendered-card counts or verified timing accuracy.
Three scripts (14.10, 18.08, 19.08) have no corresponding audio in the archives.
The remaining audio evaluation and quiet-tail recognition are still open.

For projects imported before this fix, reimport the script if duplicate analysis
blocks already exist. Existing user-edited project structure is not silently
rewritten. Re-run analysis to apply updated acoustic section matching.
