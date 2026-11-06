# Uzbek boundary audit — continuation checkpoint

Latest published rc15: f009b827cbd11000f9f7ea9c9c692f6d9efe7342.
Windows build 42243629691 succeeded. A fresh full-corpus run is in progress.
Three completed hockey recordings exposed two additional boundary bugs:
leading ASR spaces disabled anchored ordinal detection; an unrecognized first
name hid the first analysis until its later repetition. The candidate trims
ordinal input and uses a narrowly corroborated first-take fallback (intro floor,
at least eight seconds of pause, early distinctive team name, no conflicting
known club). It applies only to the first analysis and never rewrites text.
Same-transcript checks: 03.09 first analysis 119.20 -> 53.50 seconds; 06.09 second
analysis 199.90 -> 181.78 seconds; 04.09 boundaries unchanged. None of these
comparisons constitutes full word/card verification or neural model training.

Published baseline: 459c12d14565c519ae3f8efa8ebca4d48026ca36 (0.8.9rc14).
Windows build 42038404432 succeeded.

Candidate changes in this checkpoint:
- Prefer chronological spoken transitions after a grounded intro floor over
  global draft estimates, which can be wrong by minutes on abridged scripts.
- Corroborate two noisy hockey names with non-overlapping local matches.
  Never reinterpret an exactly recognized different club; protect SKA/CSKA.
- Recognize explicit numbered match transitions only with a matching team
  within the following 30 seconds; halves and scenarios are not match headings.
- Require episode context for recap markers; bare xullas/demak are insufficient.
- Accept Dynamo Moskva as the same qualified club as Dinamo Moskva.

The subsequent rc15 candidate also keeps the Uzbek vocabulary in every decoder
window (hotwords), with resume/cache tests and a changed ASR_RECIPE. 140 Uzbek
tests pass, including a render integration test; 15 vocabulary/performance tests
pass. All 49 supplied scripts parse. Full ASR/corpus validation is NOT complete.
No neural weights were trained. See RELEASE-0.8.9rc15.md for diagnostic scope.

The workspace was pruned between turns; do not count vanished ASR jobs as done.
The attached four archives contain 46 audio recordings; matching filenames are
not proof of content correspondence. Private audit data must not enter GitHub.
Use scripts/check_uz_corpus.py for resumable production ASR and store its JSON
checkpoints durably before returning control. Compare candidate boundaries
against the same saved transcripts, rather than interpreting lower review
counts as accuracy. Reference scripts are frequently abridged in actual speech.
