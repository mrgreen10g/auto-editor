# 0.8.9rc15 — continuous Uzbek vocabulary and grounded transitions

- Pass the per-project name/terminology vocabulary through faster-whisper's
  hotwords parameter in every decoder window. Previously initial_prompt was
  discarded after the first window with condition_on_previous_text=False.
  Do not duplicate the vocabulary in initial_prompt. Russian ASR is unchanged.
- Preserve vocabulary when resuming interrupted recognition. Invalidate an
  incompatible raw checkpoint and the old Uzbek recognition recipe cache.
- Prefer chronological spoken section evidence after the intro over late
  global draft estimates. Corroborate explicit numbered match transitions.
- Match two distinct noisy hockey names locally. Exact different club identities
  cannot be overridden, and SKA/CSKA remain distinct. Display text is unchanged.
- Require episode-level context for hockey recaps; ordinary in-analysis
  xullas/demak are insufficient. Preserve the earlier rc14 partial-tail recovery.

Validation: 140 Uzbek tests and 15 vocabulary/performance tests. Controlled
same-audio experiments cover seven pairs of approximately 30-second excerpts:
hockey names, football, combat, markets, and a mismatched combat script over
football audio. Names improved in several examples; number/word errors remain.
The mismatch sample stayed football rather than adopting the script's fighters.
This is diagnostic evidence, not a WER score or verification of every card.

All 49 supplied scenarios parse. Full-corpus ASR review of 46 recordings is
still in progress. No neural weights have been trained or replaced. Scripts
are not necessarily verbatim transcripts and must not be used as training labels
without content/alignment verification. Re-running Uzbek analysis recomputes
old recognition caches once to apply the new decoding recipe.
