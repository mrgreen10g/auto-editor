# 0.8.9rc19

- Scan up to two independent matches concurrently on both server profiles. Keep separate OCR state, deduplicate identical cache keys, preserve input/result ordering, collect individual failures, and limit each scanner to two CPU/filter threads. Fall back to one scanner on small CPUs or less than 3 GiB available Windows memory.
- Keep all sampling rates, OCR models, detection thresholds and speech-recognition settings unchanged.
- Apply HDR conversion only to retained 30-fps camera frames. Keep the same tone mapper, resolution and encoding quality. Verify identical decoded frame hashes against the previous operation order.
- Replace linear evaluation of every zoom window with balanced lazy lookup. Preserve easing, positions, oversampling resolution and frame hashes; overlapping custom windows keep the additive fallback.
- Raise the older 8-vCPU profile's encoder budget from four to six and filter budget from two to three, with CPU-count caps. Keep the new profile at seven/four. Label the new profile by resources rather than an assumed CPU brand.
- Tests cover parallel execution, duplicate sources, individual errors, cancellation, scoped CPU budgets, identical zoom frames and identical HDR frames.

Measured user baseline: new server 18:00 search + 7:46 alignment + 9:19 render = 35:05; old server 62:25 + 22:32 + 35:03 = 120:00. New-server screenshots identify EPYC 7763 (8 virtual CPUs), not Ryzen 7950X. Local 4-second HDR selection fixture: 4.085 s before, 2.438 s after, identical frame hashes. This fixture is not a prediction of full-episode acceleration; rerun the same uncached episode for end-to-end results. Private benchmark files are excluded from the repository.
