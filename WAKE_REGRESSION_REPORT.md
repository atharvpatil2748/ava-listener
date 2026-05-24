# Wake Regression Report -- AVAListener (F3)

> **Date:** 2026-05-23 12:28:59
> **Overall:** PASS  |  **Total:** 127/127 passed  |  **Failed:** 0

---

## 1. Suite Results

| Suite | Passed/Total | Failed | Elapsed | Status |
|-------|-------------|--------|---------|--------|
| Smoke (SMOKE-01..10) | 79/79 | 0 | 0.1s | PASS |
| Replay (Phase 0 Fixtures) | 23/23 | 0 | 0.0s | PASS |
| Pipeline (25 cases) | 25/25 | 0 | 0.0s | PASS |

## 2. Coverage

| Suite | What It Tests |
|-------|--------------|
| Smoke (79 checks) | Environment, imports, config, model integrity, matcher, cooldown, buffer, FSM |
| Replay (23 fixtures) | Phase 0 ASR hypothesis sequences replayed through full detection pipeline |
| Pipeline (25 cases) | Anchor gate, EMA confidence scoring, variant schema correctness |

## 3. False Positive / Negative Baseline (Replay Fixtures)

| Category | Count | Behavior |
|----------|-------|----------|
| True Positives -- canonical | 4 | Trigger correctly |
| True Positives -- phonetic variants | 6 | Trigger to correct canonical |
| True Positives -- multi-chunk buildup | 2 | Trigger correctly |
| Phrase boundary (listen / listen-arv) | 2 | Trigger as 'listen' (expected baseline) |
| Known false positive (wake-up-ourselves) | 1 | Triggers 'wake up arvsal' -- frozen baseline |
| True Negatives (noise, unrelated, partial) | 8 | No trigger |

> All outcomes match the frozen Phase 0 baseline exactly -- zero regression.

## 4. Wake Accuracy Deltas vs Baseline

| Metric | Baseline | Current | Delta |
|--------|----------|---------|-------|
| True positives | 12 | 20 | 0 |
| Known false positives | 1 | 1 | 0 |
| True negatives | 8 | 8 | 0 |
| False negatives | 0 | 0 | 0 |

## 5. Detailed Output

### Smoke

```
  PASS  anchor_present('hey arvsal')
  PASS  anchor_present('wake up arvsal')
  PASS  anchor_present('listen arvsal')
  PASS  NOT anchor_present('wake up')
  PASS  NOT anchor_present('hey')
  PASS  NOT anchor_present('hello world')
  PASS  NOT anchor_present('the weather is nice')
  PASS  get_variants() deduplicated (39 variants)
  PASS  get_variants() all lowercase
  PASS  get_canonical('arvsal') -> 'arvsal'
  PASS  get_canonical('arsal') -> 'arvsal'
  PASS  get_canonical('our whistle') -> 'arvsal'
  PASS  get_canonical('hey arsel') -> 'hey arvsal'
  PASS  best_match('arvsal'            ) -> phrase='arvsal' score=1.00
  PASS  best_match('hey arvsal'        ) -> phrase='hey arvsal' score=1.00
  PASS  best_match('our whistle'       ) -> phrase='arvsal' score=0.90
  PASS  best_match('the weather is nice today'   ) -> no match (phrase='')
  PASS  best_match('hello world'                 ) -> no match (phrase='')
  PASS  best_match('open the browser'            ) -> no match (phrase='')

================================================================
  SMOKE-07: Cooldown Gate
================================================================
  PASS  can_trigger() = True initially
  PASS  can_trigger() = False after mark_triggered()
  PASS  time_remaining() = 2.00s

================================================================
  SMOKE-08: Hypothesis Buffer
================================================================
  PASS  get_window() returned 1 entries
  PASS  after clear(), window is empty

================================================================
  SMOKE-09: Runtime State Machine
================================================================
  PASS  RuntimeStateMachine() instantiates
  PASS  transition('start') runs without error

================================================================
  SMOKE-10: Models Manifest Schema
================================================================
  PASS  models_manifest.json valid JSON
  PASS  5 model entries with required keys
  PASS  All load_status == 'OK'

================================================================
  Results: 79/79 passed  |  0 failed  |  0.1s
================================================================

```

### Replay

```
  AVAListener — Replay Regression Tests (Phase 0 Baseline)
  23 fixtures
========================================================================
  [PASS]  bare arvsal                         raw=0.87  thr=0.72  trigger=Y  phrase='arvsal'
  [PASS]  hey arvsal                          raw=0.87  thr=0.68  trigger=Y  phrase='hey arvsal'
  [PASS]  wake up arvsal                      raw=0.87  thr=0.68  trigger=Y  phrase='wake up arvsal'
  [PASS]  listen arvsal                       raw=0.87  thr=0.72  trigger=Y  phrase='listen arvsal'
  [PASS]  arsal variant                       raw=0.84  thr=0.68  trigger=Y  phrase='hey arvsal'
  [PASS]  arsel variant                       raw=0.79  thr=0.68  trigger=Y  phrase='hey arvsal'
  [PASS]  our whistle — direct                raw=0.79  thr=0.72  trigger=Y  phrase='arvsal'
  [PASS]  wake up our whistle                 raw=0.79  thr=0.68  trigger=Y  phrase='wake up arvsal'
  [PASS]  hey our whistle                     raw=0.79  thr=0.68  trigger=Y  phrase='hey arvsal'
  [PASS]  arzal variant                       raw=0.79  thr=0.72  trigger=Y  phrase='arvsal'
  [PASS]  multi-chunk buildup                 raw=0.79  thr=0.68  trigger=Y  phrase='hey arvsal'
  [PASS]  arzal with preamble                 raw=0.79  thr=0.68  trigger=Y  phrase='hey arvsal'
  [PASS]  listen alone                        raw=0.87  thr=0.72  trigger=Y  phrase='listen'
  [PASS]  wake alone                          raw=0.00  thr=0.78  trigger=N  phrase=''
  [PASS]  listen arv candidate only           raw=0.87  thr=0.72  trigger=Y  phrase='listen'
  [PASS]  listen arvsal full                  raw=0.81  thr=0.72  trigger=Y  phrase='listen arvsal'
  [PASS]  empty window                        raw=0.00  thr=0.00  trigger=N  phrase=''
  [PASS]  random everyday speech              raw=0.00  thr=0.78  trigger=N  phrase=''
  [PASS]  context only - no anchor            raw=0.00  thr=0.78  trigger=N  phrase=''
  [PASS]  hey alone                           raw=0.00  thr=0.78  trigger=N  phrase=''
  [PASS]  wake up ourselves                   raw=0.72  thr=0.68  trigger=Y  phrase='wake up arvsal'
  [PASS]  unrelated high-stability speech     raw=0.00  thr=0.78  trigger=N  phrase=''
  [PASS]  arsenal football club - false anchor raw=0.00  thr=0.78  trigger=N  phrase=''
========================================================================
  Results: 23/23 passed  (0 failed)
========================================================================

```

### Pipeline

```
  [PASS]  phrase 'hey arvsal' in index
  [PASS]  phrase 'wake up arvsal' in index
  [PASS]  phrase 'listen arvsal' in index
  [PASS]  phrase 'listen buddy' in index
  [PASS]  phrase 'listen' in index
========================================================


===========================================================================
  AVAListener -- Pipeline Test (25 cases)
===========================================================================
  [PASS]  bare arvsal                  score=1.00  conf=0.80  threshold=0.72  phrase='arvsal'              variant='arvsal'
  [PASS]  hey arvsal                   score=1.00  conf=0.80  threshold=0.68  phrase='hey arvsal'          variant='hey arvsal'
  [PASS]  wake up arvsal               score=1.00  conf=0.80  threshold=0.68  phrase='wake up arvsal'      variant='wake up arvsal'
  [PASS]  listen arvsal                score=1.00  conf=0.80  threshold=0.72  phrase='listen arvsal'       variant='listen arvsal'
  [PASS]  arsal variant                score=0.97  conf=0.77  threshold=0.68  phrase='hey arvsal'          variant='hey arsal'
  [PASS]  arsel variant                score=0.90  conf=0.72  threshold=0.68  phrase='hey arvsal'          variant='hey arsel'
  [PASS]  ar sal spaced                score=0.94  conf=0.75  threshold=0.68  phrase='hey arvsal'          variant='hey ar sal'
  [PASS]  our whistle                  score=0.90  conf=0.72  threshold=0.72  phrase='arvsal'              variant='our whistle'
  [PASS]  wake up our whistle          score=0.90  conf=0.72  threshold=0.68  phrase='wake up arvsal'      variant='wake up our whistle'
  [PASS]  wreak up our whistle         score=0.80  conf=0.64  threshold=0.68  phrase='wake up arvsal'      variant='wreak up our whistle'
  [PASS]  hey our whistle              score=0.90  conf=0.72  threshold=0.68  phrase='hey arvsal'          variant='hey our whistle'
  [PASS]  arzal variant                score=0.90  conf=0.72  threshold=0.72  phrase='arvsal'              variant='arzal'
  [PASS]  arzal with context           score=0.90  conf=0.72  threshold=0.68  phrase='hey arvsal'          variant='hey arzal'
  [PASS]  multi-chunk buildup          score=0.90  conf=0.72  threshold=0.68  phrase='hey arvsal'          variant='hey arvsal'
  [PASS]  empty                        score=0.00  conf=0.00  threshold=0.78  phrase=''                    variant=''
  [PASS]  random speech                score=0.00  conf=0.00  threshold=0.78  phrase=''                    variant=''
  [PASS]  context only no anchor       score=0.00  conf=0.00  threshold=0.78  phrase=''                    variant=''
  [PASS]  hey alone                    score=0.00  conf=0.00  threshold=0.78  phrase=''                    variant=''
  [PASS]  wake up ourselves            score=0.81  conf=0.65  threshold=0.68  phrase='wake up arvsal'      variant=''
  [PASS]  unrelated high stability     score=0.00  conf=0.00  threshold=0.78  phrase=''                    variant=''
  [PASS]  arsenal false                score=0.00  conf=0.00  threshold=0.78  phrase=''                    variant=''
  [PASS]  listen alone                 score=1.00  conf=0.80  threshold=0.72  phrase='listen'              variant='listen'
  [PASS]  wake alone                   score=0.00  conf=0.00  threshold=0.78  phrase=''                    variant=''
  [PASS]  listen arv candidate         score=1.00  conf=0.80  threshold=0.72  phrase='listen'              variant='listen'
  [PASS]  listen arvsal full           score=0.93  conf=0.74  threshold=0.72  phrase='listen arvsal'       variant='listen arvsal'
===========================================================================
  Results: 25/25 passed  - all good
===========================================================================

```
