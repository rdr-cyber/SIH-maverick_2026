# ML / NLP MODEL — Stylometry, Behavior, Correlation (Phase 1 design)

> This document describes the algorithms powering AI-assisted persona correlation.
> All outputs are **explainable signals**, not black-box scores. Nothing in this document
> is claimed to be a scientifically validated probability of identity.

## 1. Design targets

1. Reproducible: deterministic seed, pure functions where possible.
2. Offline: no network calls at inference/demo time (TF-IDF based, spaCy optional).
3. Explainable: every score decomposes into features with concrete post excerpts.
4. Defensive: never asserts identity; produces similarity signals for analyst review.

## 2. Stylometric analyzer (`backend/app/services/stylometry.py`)

### 2.1 Preprocessing
- Lowercase + preserve punctuation as tokens where relevant.
- Tokenization: spaCy `en_core_web_sm` **if** installed; otherwise a built-in regex
  tokenizer (`\w+|[^\w\s]`) — identical behavior for the feature families below.
- Per-handle corpora: aggregate posts authored by the same canonical handle within a window.
- Signals published per post: normalized to per-100-words to be comparable between authors.

### 2.2 Feature families

| Family | Features | Notes |
|--------|----------|-------|
| Character n-grams | counts of 2–5 grams over normalized text | sqlite-free; vectorized via `CountVectorizer(analyzer='char_wb', ngram_range=(2,5))` |
| Word n-grams | 1–2 grams, top-K by frequency | `CountVectorizer(analyzer='word', ngram_range=(1,2))` |
| Sentence length | mean/median/std/max, short-sentence rate (≤5 words) | per post + pooled |
| Vocabulary richness | TTR, corrected TTR (Herdan), hapax ratio | capped at corpus tolerance |
| Punctuation patterns | rates of `.` `,` `!` `?` `;` `:` `"` `'` `-` `(` `)` `*` `_` | per-100-words |
| Function-word rates | rates of ~50 closed-class words (`the`,`and`,`of`,`to`…) | |
| Repeated phrases | top 20 3–5 word n-gram phrases with frequency | used in explanation text |

### 2.3 Similarity computation
- Build a combined TF-IDF vector space over: char n-grams (weight 0.5) + word n-grams
  (weight 0.4) + sentence/punctuation/function-word ratio vector (weight 0.1) — concatenated.
- Cosine similarity over the concatenated vector → `stylometric_similarity` (0..1).
- **Gate:** if either corpus has < 8 posts or < 800 tokens, emit similarity with
  `reliability: "low"` and it contributes at most half the stylometry weight.
- Optional (if `sentence-transformers` is installed): a secondary cosine on mean-pooled
  embeddings; used only as a cross-check, not in the score.

### 2.4 Output structure
```json
{
  "similarity": 0.91,
  "reliability": "adequate",
  "features": [
    {"name": "char_ngram_4_cosine", "value": 0.9, "weight": 0.5},
    {"name": "word_bigram_cosine", "value": 0.88, "weight": 0.4}
  ],
  "explanation": "darkmerchant's posts reuse shadow_vendor's distinctive phrase 'escrow
                  only, no FE' (8×) and mirror mean sentence length (11.2 vs 11.0).",
  "supporting_posts": [{"handle": "shadow_vendor", "excerpt": "…"}, {"handle": "darkmerchant", "excerpt": "…"}],
  "limitations": ["Small corpus (11 posts)", "Domain vocabulary may dominate: compare on off-topic posts too"]
}
```

## 3. Behavior analyzer (`backend/app/services/behavior.py`)

### 3.1 Features (per handle, time-binned)
| Feature | Definition |
|---------|-----------|
| Posting frequency | posts/day (windowed) |
| Interval stats | mean/median/std of inter-post gaps (hours) |
| Time-of-day | 24-bin histogram of UTC-normalized hour |
| Day-of-week | 7-bin histogram |
| Lifecycle | first_seen, last_seen, active span, gap structure (hibernation) |
| Migration | platform-change events w/ timestamps |
| Momentum | max posts in 48h window (burstiness) |
| Silence ratio | share of active span with no posts |

### 3.2 Similarity
- Histogram distances: per-bin min(a,b)/sum normalized overlap (Wasserstein-lite), weighted:
  time-of-day 0.4, weekday 0.2, interval distribution 0.25, burstiness 0.15.
- Combine → `behavior_similarity` (0..1) with the same reliability gate as stylometry.
- Migration narrative: "{handle} moved from Marketplace A to Marketplace B on 2025-08-14;
  gap 94 days, consistent with hibernation pattern."

### 3.3 Output
`{ similarity, reliability, features, explanation, migration_narrative, limitations }` —
mirrors the stylometry output shape for uniform UI rendering.

## 4. Correlation engine (`backend/app/services/correlation.py`)

### 4.1 Mandated cost model (configurable via `correlation_weights`)

| Signal | Default weight (0–100 total) | Trigger |
|--------|------------------------------|---------|
| PGP fingerprint match | 30 | full 40-hex equality between two personas' keys |
| Wallet address match | 25 | normalized address equality |
| Unique handle exact match | 15 | canonical handle equality |
| Infrastructure reuse | 15 | ≥2 shared infra signals (cert/domain/IP/SES/ASN) |
| Stylometric similarity | 10 | cosine ≥ threshold (gated) |
| Behavior similarity | 5 | histogram overlap (gated) |

**Sub-rules:**
- Handle similarity **without** equality: caps at 5 (never enough alone to exceed Low band).
- Stylometry/behavior: half points if `reliability=low`.
- No single signal may sum to High: High (≥70) requires at least two independent
  identity-anchor signals (PGP/wallet/exact-handle) or one strong anchor + stylometry+behavior.
- Scores are additive up to 100, stored as RCS 0–100.

### 4.2 Confidence bands
| Band | Range |
|------|-------|
| Weak | 0–29 |
| Low | 30–49 |
| Moderate | 50–69 |
| High | 70–84 |
| Very High | 85–100 |

Display label everywhere: **Relationship Confidence Score**; UI tooltip explains this is a
decision heuristic, not a probability.

### 4.3 Explainability contract
Every relationship serializes: `scoring_factors` (signal/weight/score/note), `evidence_ids`
of supporting evidence, and a generated `explanation` prose sentence built from the
contributing factors (`see §1.5 of API.md`).

### 4.4 False-positive defenses (validated in tests)
- Actor Beta that shares only a similar username must land in **Weak/Low** → not merged.
- Shared infrastructure alone (shared hosting) must land **≤ Moderate**.
- Copycat writing (high stylometric similarity but no identity anchors) must land **≤ Moderate**.
- Candidate generation explores the graph neighborhood (shared platforms, shared wallet/PGP,
  infra clusters) — bounded fan-out to keep cost linear in graph size.
## 5. Data flows

```
posts (Postgres)
   ├─► stylometry.compute(handle, corpus)      → stylometric_profile row
   ├─► behavior.compute(handle, events)        → behavior_profile row
candidate personas detected in graph neighborhood
   └─► correlation.evaluate(personaA, personaB, weights)
        ├─ PGP signal    (query pgp_keys by fingerprint)
        ├─ Wallet signal (query wallets by address)
        ├─ Handle signal (canonical handle equality)
        ├─ Infra signal  (query domains/certs/infrastructure cluster)
        ├─ Stylo signal  (compare stylometric_profiles)
        ├─ Behavior sig  (compare behavior_profiles)
        └─ ► RCS + factors + explanation → Relationship row (Postgres)
           ► evidence rows per signal → Relationship_observations
           ► graph sync → POSSIBLY_SAME_AS edge (Neo4j, status=pending)
```

## 6. Determinism & reproducibility

- Generators and analyzers use explicit `random.seed()`/`np.random.RandomState(seed)`;
  seeds stored in `AppSettings.seed` and per-dataset versions.
- Feature extraction is a pure function of the corpus — unit tests compare exact output
  hashes for the flagship scenarios (Alpha migration, Beta false positive).
- All vectors stored as compact JSONB feature maps; top-K features exposed for UX.

## 7. Evaluation strategy (synthetic ground truth)

Two labeled fixtures in `backend/tests/fixtures`:
1. `migration_story.yaml` — the "hidden relationship" (Alpha: shadow_vendor → darkmerchant)
   with known ground truth pairs; tests assert RCS ≥ 70 (High) and explanation mentions the
   4 real factors.
2. `false_positive_cases.yaml` — Beta-like, copycat-like, shared-hosting cases; tests assert
   RCS < 50 and `band ∈ {weak, low}`.
Reported metrics on these fixtures (not on live data): precision@High, recall@High, FP count.

## 8. Limitations (honest engineering)

- Synthetic data has no real-world noise; production calibration requires access to an
  authorized, ethics-approved evaluation set.
- Stylometry degrades below ~8 posts/800 tokens — the reliability gate enforces honesty.
- Time-of-day features assume normalized clock; spoofed timestamps attack the signal
  (defended only by provenance integrity checks).
- No single method is *proof*; the platform always says "hypothesis" until a human reviews.
