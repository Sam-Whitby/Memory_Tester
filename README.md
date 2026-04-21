# Memory Tester — MIDI Smith-Waterman Alignment (Proof of Concept)

A proof-of-concept for comparing MIDI recordings of piano improvisation using
**Smith-Waterman local sequence alignment** on chord-event representations.

The intended application is an improvisation-recall trainer: a musician plays a
melody, tries to reproduce it from memory, and the system scores how well the
reconstruction matched the original. This repo demonstrates the core comparison
engine in isolation.

---

## Concept

Each MIDI recording is converted to an ordered sequence of **chord events**:
groups of note-onsets that fall within a configurable time window ε (default
30 ms) are merged into a single simultaneous event carrying a set of MIDI pitch
numbers. Two recordings are then compared as sequences of these events using
Smith-Waterman local alignment.

### Scoring function

Each pair of chord events is scored by **Jaccard similarity** on their pitch sets:

```
Jaccard(A, B) = |A ∩ B| / |A ∪ B|
match_score(A, B) = 2 · Jaccard(A, B) − 1
```

This maps the interval [0, 1] to [−1, +1]:
- Identical chords → +1.0 (strongly reinforces alignment)
- 50 % pitch overlap → 0.0 (neutral)
- No shared pitches → −1.0 (opening a gap is preferred)

The SW recurrence is the standard local-alignment DP:

```
H(i, j) = max(0,
              H(i-1, j-1) + match_score(A_i, B_j),   # match / mismatch
              H(i-1, j)   − gap_penalty,               # gap in B
              H(i,   j-1) − gap_penalty)               # gap in A
```

(default gap penalty = 0.5)

### Normalisation

The raw SW score is normalised against the self-scores of each recording to
produce a value in [0, 1]:

```
sim(A, B) = SW(A, B) / √(SW(A, A) · SW(B, B))
```

Identical sequences score 1.0; completely disjoint sequences score 0.0.
This is equivalent to cosine normalisation in the SW score space and is the
same approach used by normalised sequence identity in bioinformatics.

---

## Repository structure

```
Memory_Tester/
├── align.py               # Main script: loads MIDIs, prints similarity matrix
├── generate_examples.py   # Generates 10 example MIDI files
├── requirements.txt
└── examples/              # Generated .mid files (created by generate_examples.py)
    ├── ex01_A_clean.mid   # C-major folk melody (reference)
    ├── ex02_A_del3.mid    # Same, 3 events deleted
    ├── ex03_A_sub4.mid    # Same, 4 note substitutions
    ├── ex04_A_mixed.mid   # Same, deletions + substitutions
    ├── ex05_B_clean.mid   # Different C-major melody
    ├── ex06_B_var.mid     # Variant of ex05
    ├── ex07_C_clean.mid   # A-minor melody
    ├── ex08_C_var.mid     # Variant of ex07
    ├── ex09_D_clean.mid   # Chromatic melody
    └── ex10_D_var.mid     # Variant of ex09
```

---

## Installation

```bash
pip install -r requirements.txt
```

Requires Python ≥ 3.8.

---

## Usage

```bash
# Generate the 10 example MIDI files
python generate_examples.py

# Run pairwise alignment with default settings (ε = 30 ms, gap = 0.5)
python align.py

# Custom chord-grouping window (milliseconds)
python align.py --epsilon 50

# Custom directory
python align.py path/to/midi/dir --epsilon 30 --gap 0.4
```

### Example output

```
ε = 30.0 ms  |  gap penalty = 0.5
Loading 10 files from 'examples/'

  ex01_A_clean.mid                        28 events
  ex02_A_del3.mid                         25 events
  ...

Pairwise similarity (SW / Jaccard pitch, cosine-normalised):

               ex01  ex02  ex03  ex04  ex05  ex06  ex07  ex08  ex09  ex10
─────────────────────────────────────────────────────────────────────────
ex01_A_clean  1.000 0.888 0.750 0.741 0.491 0.435 0.071 0.073 0.037 0.000
ex02_A_del3   0.888 1.000 0.624 0.608 0.423 0.360 0.076 0.077 0.039 0.000
ex03_A_sub4   0.750 0.624 1.000 0.482 0.309 0.283 0.089 0.091 0.037 0.038
ex04_A_mixed  0.741 0.608 0.482 1.000 0.434 0.431 0.074 0.075 0.038 0.000
ex05_B_clean  0.491 0.423 0.309 0.434 1.000 0.847 0.091 0.111 0.038 0.000
ex06_B_var    0.435 0.360 0.283 0.431 0.847 1.000 0.076 0.096 0.039 0.000
ex07_C_clean  0.071 0.076 0.089 0.074 0.091 0.076 1.000 0.818 0.037 0.038
ex08_C_var    0.073 0.077 0.091 0.075 0.111 0.096 0.818 1.000 0.038 0.038
ex09_D_clean  0.037 0.039 0.037 0.038 0.038 0.039 0.037 0.038 1.000 0.804
ex10_D_var    0.000 0.000 0.038 0.000 0.000 0.000 0.038 0.038 0.804 1.000
```

The matrix is symmetric with 1.0 on the diagonal. Clear block structure is
visible: Groups A (ex01–04), B (ex05–06), C (ex07–08), and D (ex09–10) each
form high-similarity clusters. Cross-group scores reflect genuine harmonic
distance (A/B share C-major material; C is A-minor; D is chromatic).

---

## Why Smith-Waterman?

Standard DTW aligns entire sequences globally, which fails gracefully when a
performer recalls only part of an improvisation correctly. SW **local alignment**
finds the best-matching subsequences, giving partial credit for correctly
recalled passages while ignoring unmatched flanking material. This matches
the use case: a musician might perfectly reconstruct the middle of an
improvisation while blanking on the opening or ending.

SW also naturally handles:
- **Missing notes** (gaps): treated as indels with a fixed penalty rather than
  cascading off-by-one errors
- **Extra notes** (insertions): same gap mechanism
- **Chord approximations**: Jaccard similarity gives partial credit for
  partially correct chords

---

## Limitations of this proof of concept

- **No rhythm scoring**: only pitch content is compared; timing is used only
  for event grouping, not for scoring
- **No velocity scoring**: dynamics are discarded
- **Simple gap model**: a uniform gap penalty does not distinguish grace notes
  from genuinely missing phrases
- **ε is a free parameter**: the chord-grouping window needs tuning for
  different tempos and playing styles
- **O(n²) SW**: adequate for short improvisations (~30 events); would need
  FastDTW-style banding for very long sequences

---

## References

- **Smith, T.F. & Waterman, M.S. (1981).** Identification of common molecular
  subsequences. *Journal of Molecular Biology*, 147(1), 195–197.
  The local sequence alignment algorithm implemented here.

- **[pretty_midi](https://github.com/craffel/pretty-midi)** (Raffel & Ellis,
  2014) — MIDI file I/O and manipulation.

- **[numpy](https://numpy.org/)** — DP matrix computation.

- Related bioinformatics SW implementations consulted for algorithm
  verification: [biopython](https://github.com/biopython/biopython)
  (`Bio.Align.PairwiseAligner`), [swalign](https://github.com/mbreese/swalign).
  A direct implementation was necessary here because the scoring function
  operates on frozensets (chord pitch content) rather than character alphabets.
