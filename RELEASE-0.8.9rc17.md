# 0.8.9rc17

- Replace the fixed -35 dB silence gate with level-aware, peak-based pause detection. Quiet speech is retained; recognized word intervals are protected from pause cuts. Legacy phrase-only timings conservatively protect the entire phrase.
- Normalize speech before conservative, non-tracking noise suppression, for both single and multiple host recordings, including external microphones. Keep the existing denoise toggle and strength setting.
- Compensate the noise filter's 25 ms latency and flush its tail, preserving duration and lip sync. Add a broadband timing regression test.
- Invalidate old automatic pause/edit caches and mobile audio previews. Existing projects should run timing analysis again before rendering; already removed speech cannot be restored by re-encoding a finished video.
- Regression coverage includes quiet signals at different levels, genuine pauses, opposite-phase stereo, word protection and actual packaged-FFmpeg processing. Source recordings are not included in this repository.
