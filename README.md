# Memory Tester — MIDI Improvisation Recall Trainer

An ear-training tool for piano improvisers. Play a melody on a connected MIDI
keyboard, then try to reconstruct it from memory as many times as you like.
Each attempt is scored against the original using **Smith-Waterman local
sequence alignment** on chord-event representations. Results are shown in a
live table and graph.

---

## Quick start

Connect a MIDI keyboard, then **double-click `Memory Tester.command`** in
Finder. Terminal opens, the app launches, and the GUI appears.

Or from a terminal:

```bash
python3 memory_tester.py
```

### Workflow

| Step | Action |
|------|--------|
| 1 | App connects to your MIDI keyboard automatically |
| 2 | Play your improvisation — recording starts on the **first note** |
| 3 | Press **Space** to stop the original recording |
| 4 | Attempt to reconstruct it from memory — recording starts on first note |
| 5 | Press **Space** to stop; score is added to the table and graph |
| 6 | Repeat step 4–5 as many times as you like |
| 7 | Press **Space twice** (no notes between the two presses) to end the session |

During recording phases **no pitch or note information is shown** — only a
colour pulse confirms that notes are being captured.  Recordings are held in
memory only and are discarded when the window closes.

---

## Repository structure

```
Memory_Tester/
├── Memory Tester.command  # Double-click launcher (macOS)
├── memory_tester.py       # GUI application
├── align.py               # Batch pairwise similarity matrix (CLI tool)
├── generate_examples.py   # Generates 10 example MIDI files
├── requirements.txt
└── examples/              # Generated .mid files
```

## Installation

```bash
pip install -r requirements.txt
```

Requires Python ≥ 3.8 with tkinter (Anaconda distributions include this).
On macOS the `Memory Tester.command` launcher auto-installs dependencies.

---

## Batch alignment tool (CLI)

To compute a pairwise similarity matrix over a directory of MIDI files:

```bash
python align.py                    # default: examples/, ε = 30 ms
python align.py --epsilon 50       # custom chord-grouping window
```

---

## Concept

Each MIDI recording is converted to an ordered sequence of **chord events**:
groups of note-onsets that fall within a configurable time window ε (default
30 ms) are merged into a single simultaneous event carrying a set of MIDI pitch
numbers. Two recordings are then compared as sequences of these events using
Smith-Waterman local alignment.

### Chord similarity

Each pair of chord events is compared using **octave-aware soft Jaccard similarity**.
For every pair of notes across the two chords a pitch similarity is computed:

```
pitch_sim(p, q) = 1.0   if p == q            (exact match)
                  0.9   if p % 12 == q % 12  (same pitch class, different octave)
                  0.0   otherwise
```

The maximum-weight bipartite matching over all note pairs is found, then
normalised by the larger chord size:

```
chord_sim(A, B) = max_matching(sim_matrix) / max(|A|, |B|)
```

This gives a value in [0, 1] with partial credit for chords that share pitch
classes but differ in octave, and a penalty for extra or missing notes.

The SW match score maps chord similarity to [−1, +1]:

```
match_score(A, B) = 2 · chord_sim(A, B) − 1
```

- Identical chords → +1.0
- All notes in the correct pitch class but wrong octave → +0.8
- 50 % soft chord overlap → 0.0 (neutral)
- No pitch-class overlap → −1.0 (opening a gap is preferred)

### Duration-weighted gap penalties

Each chord event is assigned a **weight** proportional to its duration:

```
weight(event) = max(WEIGHT_FLOOR, duration(event) / median_duration)
gap_cost(event) = gap_penalty × weight(event)
```

Long structural notes are expensive to skip; short grace notes are cheap.
The SW recurrence becomes:

```
H(i, j) = max(0,
              H(i-1, j-1) + match_score(A_i, B_j),
              H(i-1, j)   − gap_penalty × weight(A_i),
              H(i,   j-1) − gap_penalty × weight(B_j))
```

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

## Comparison with parangonar

[parangonar](https://github.com/CPJKU/parangonar) is a state-of-the-art MIDI
**score-to-performance** alignment tool (Nakamura et al. 2015, Foscarin et al.
2020). The two systems solve related but distinct problems:

| Dimension | This tool | parangonar |
|-----------|-----------|------------|
| **Task** | Compare two *performances* of the same improvisation | Align a *performance* to a notated *score* |
| **Algorithm** | Smith-Waterman local sequence alignment | HMM or DTW over note-event sequences |
| **Pitch matching** | Octave-aware (same pitch class = 0.9 credit) | Exact MIDI pitch match |
| **Gap / deletion cost** | Scales with note duration (`weight = dur / median`) | Deletion probability scales with note duration (Nakamura 2015) |
| **Polyphony** | Chord-event grouping (ε window) + bipartite matching | Note-by-note matching with instrument track separation |
| **Rhythm** | Duration used only for gap weighting; timing not scored | Full onset-time alignment is the primary output |
| **Output** | Single similarity score in [0, 1] | Correspondence table: which score note maps to which performed note |

**Shared inspiration**: the duration-weighted gap penalty used here is directly
inspired by parangonar's core insight — that deleting a long note is a more
significant alignment event than deleting a short grace note, and the model
should reflect this. Both approaches scale the cost of skipping a note by its
duration relative to surrounding notes.

**Key divergence**: parangonar is designed for score-to-performance alignment,
where a ground-truth note sequence exists and the goal is precise correspondence.
This tool is designed for *performance-to-performance* comparison with no ground
truth, so a single normalised similarity score is more informative than a note
correspondence table. SW local alignment is preferred over global DTW because it
gives partial credit for a correctly recalled passage even when the performer
blanks on the opening or ending.

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

# Reduce octave similarity credit (penalise wrong-octave notes more)
python align.py --octave-weight 0.5
```

### Example output

```
ε = 30.0 ms  |  gap penalty = 0.5  |  octave weight = 0.9
Loading 10 files from 'examples/'

  ex01_A_clean.mid                        28 events
  ex02_A_del3.mid                         25 events
  ...

Pairwise similarity (SW / soft chord sim, cosine-normalised):

               ex01  ex02  ex03  ex04  ex05  ex06  ex07  ex08  ex09  ex10
─────────────────────────────────────────────────────────────────────────
ex01_A_clean  1.000 0.907 0.762 0.757 0.509 0.454 0.071 0.073 0.037 0.000
ex02_A_del3   0.907 1.000 0.658 0.667 0.462 0.400 0.076 0.077 0.039 0.000
ex03_A_sub4   0.762 0.658 1.000 0.513 0.297 0.290 0.089 0.091 0.037 0.038
ex04_A_mixed  0.757 0.667 0.513 1.000 0.462 0.402 0.074 0.075 0.038 0.000
ex05_B_clean  0.509 0.462 0.297 0.462 1.000 0.828 0.091 0.074 0.038 0.000
ex06_B_var    0.454 0.400 0.290 0.402 0.828 1.000 0.076 0.077 0.039 0.000
ex07_C_clean  0.071 0.076 0.089 0.074 0.091 0.076 1.000 0.764 0.037 0.038
ex08_C_var    0.073 0.077 0.091 0.075 0.074 0.077 0.764 1.000 0.038 0.038
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
