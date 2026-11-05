# 0.8.9rc14 — preserve grounded Uzbek hockey boundaries

- Recognize narrowly scoped decoder spellings of Lokomotiv, Avtomobilist and
  Ak Bars only when the other expected hockey team is recognized exactly.
  These spellings never replace club identities or displayed script text.
- Use contextual Uzbek recap cues for hockey outros. Bare `demak` or a club
  finishing its season is no longer enough to identify the episode ending.
- If a later transition is missing, keep independently confirmed earlier
  sections and draft only the unresolved tail. Its boundaries remain flagged.
- Reject strongly evidenced football recordings paired with combat scripts:
  require repeated football teams spread across time, football discussion,
  and absence of expected fighters or explicit combat discussion. Missing
  fighter names alone never triggers this check.
- Invalidate affected annotation caches while reusing existing ASR audio caches.

Validation: 133 Uzbek tests passed locally. Same-refined-transcript comparison
on one 443.76-second hockey recording changed analysis starts from
7.580/12.380/17.380 seconds to 57.740/198.940/351.080 seconds; outro starts at
396.560 seconds. Both versions retain two annotation warnings. This is a
boundary regression result, not a corpus-wide ASR accuracy measurement.

Full-corpus review remains in progress: 46 audio recordings, 49 scripts.
No neural model weights were trained or replaced. Scripts remain unverified
against spoken content and must not be used as verbatim training labels.
