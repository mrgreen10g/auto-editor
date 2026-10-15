# 0.7.27rc2

- Russian football long-form profile, with shared football club identities,
  archive footage selection, Russian cards and player-name vocabulary.
- Template selector separates Russian and Uzbek speakers.
- Shorts folder import reads the presenter and text.txt from the child shorts
  folder and match footage from the selected long-form episode folder.
- Optional horizontal mirroring affects the presenter, not footage, cards or
  the disclaimer. The setting is saved with the project and presets.
- Folder-import button aligned with the analysis controls; obsolete separate
  import-from-long button removed.
- Uzbek review includes actual recognized speech and word timestamps when
  available; script text is never substituted for missing recognized speech.
  Old projects without stored speech evidence require re-analysis.
- Spoken fixture announcements accept conjunctions, opponent wording,
  ordinals and city qualifiers. Their original script wording is retained
  for alignment. Historical prose is not treated as a fixture heading.
- Script-backed retake removal supports restarts spanning up to three Russian
  sentences, with limited spoken linking words. It protects numbers, negation,
  authored repeats and distant recaps. Competing cuts cannot erase the start
  of the successful replacement. Re-analysis invalidates the old edit plan.

## Validation and limits

Private corpus contents are not included in this repository. All 45 scripts
were inventoried: 42 football/hockey scripts passed structural parsing; three
combat/esports scripts were excluded from these templates. This is a parsing
check, not proof of perfect timing or card extraction.

Four complete recordings were transcribed for this release. Real repeated
takes were found and inspected in recognized word sequences. One recording's
match content differs from its same-named script; only matching portions can
serve as script-backed examples. Further examples may expose missed retakes.

No ASR model weights were trained. Player vocabulary is a seed catalog of
names and aliases, not a complete or current team-roster database. Automatic
cuts require the pause/retake cleanup setting and a fresh analysis; installing
the update does not rewrite an already rendered video.
