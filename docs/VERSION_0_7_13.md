# 0.7.13rc1 — NHL, speech cleanup and editing workflow

- NHL catalog: 32 official English names, distinctive Russian spellings and scoreboard abbreviations. Source: https://www.nhl.com/info/teams/ (checked 2026-09-24). New York alone never selects Rangers/Islanders. Historical source matching, script headings, cards and filename-based logos share identities. English/Russian names also share lexical speech anchors.
- Full Russian script import accepts numbered headings, hyphenated city names and varied recap intentions; unlabelled recaps require evidence from several repeated fixture choices. Uncertain separation stays explicit instead of inventing a boundary. Speech alignment uses the first analysis body and intro evidence when the familiar transition/Telegram cue is absent.
- Silence cutting no longer switches off for an entire block because one card has uncertain alignment. Script-backed Russian speech alignment removes nearby failed takes only when a strong corrected replacement is confirmed; distant recaps and authored repeated sentences remain. Cleanup uses the same source ranges for video and audio. Turning off pause cleanup preserves takes too. Conservative detection can retain a restart if its first words cannot be confirmed.
- Uncertain ordinary speech does not generate information cards for any profile. Automatic text-only Telegram/subscription fallbacks are omitted; real asset inserts remain reviewable. The review window identifies the card's type, section and placement. Saved, proven automatic prose cards are removed without overwriting authored text.
- Settings → My settings: named presets per RU hockey / UZ football / UZ combat profile. Saves voice, music file/level, image, insertion and export settings plus logo folder, but not scripts, events or timelines.
- Settings → Match card → Logo folder: remembers the folder per profile and matches PNG/JPEG/WebP filenames through club aliases. Existing manual logos win. Ambiguous duplicate files require manual selection. Combat remains names-only. Missing folders/music are reported; files are not copied into projects.
- Timeline: +/−, Ctrl+wheel, fit whole episode, horizontal scrolling. Selecting an item without moving it does not create an edit or invalidate preview. After one base-video preview build, non-video cards update while dragging and after text/timing edits, including undo/redo, without rendering video again. The same artwork and animation parameters are used for preview/export. Video inserts and animated asset changes still require preview rebuild. Final export remains full-resolution FFmpeg rendering.

## Existing projects

Open the project, then run timing analysis once for the new cleanup/boundaries. The existing speech transcript cache can be reused; user card/insert edits are rebased where their input identity still matches. Review warnings where a manual edit falls into a removed pause. Keep a copy of the old project if comparing results.

## Validation

200 local unit/integration tests passed before Windows packaging, including 13 new regressions for NHL, retakes, review filtering/migration, presets, logo matching and live compositing. Windows CI additionally exercises the desktop workflow, actual FFmpeg preview, OCR and packaged executable.

The user's NHL ZIP did not materialize in this session. The secondary `textNHL.rar` contained a zero-byte text file. The real reported NHL recording and the two intended scripts have therefore not been reproduced; usable uploads are still required for that case validation.
