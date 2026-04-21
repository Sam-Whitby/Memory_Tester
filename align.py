"""
align.py
Compute pairwise Smith-Waterman similarity between MIDI files.

Each MIDI file is represented as a sequence of chord events (epsilon-grouped
note onsets). Events are compared using an octave-aware soft chord similarity
and the SW gap penalty is scaled by each event's duration weight, so that
short ornamental notes are cheap to skip and long structural notes are not.

The score is normalised by the geometric mean of each file's self-score,
giving a value in [0, 1] where 1 = identical sequence.

Usage:
    python align.py                              # uses ./examples/, ε=30 ms
    python align.py path/to/dir                  # custom directory
    python align.py --epsilon 50                 # 50 ms grouping window
    python align.py --epsilon 50 --gap 0.4
    python align.py --octave-weight 0.8          # less credit for octave errors
"""

import os
import glob
import argparse
import numpy as np
import pretty_midi


# ── tuneable constants ─────────────────────────────────────────────────────────

OCTAVE_WEIGHT = 0.9   # similarity credit for same pitch class, different octave
WEIGHT_FLOOR  = 0.05  # minimum event weight (grace notes are cheap, not free)


# ── pitch / chord similarity ───────────────────────────────────────────────────

def pitch_sim(p: int, q: int, octave_weight: float = OCTAVE_WEIGHT) -> float:
    """
    Similarity between two MIDI note numbers.
      1.0           exact match
      octave_weight same pitch class, different octave (e.g. C4 vs C5)
      0.0           different pitch class
    """
    if p == q:
        return 1.0
    if p % 12 == q % 12:
        return octave_weight
    return 0.0


def _max_assignment(sim_mat: np.ndarray) -> float:
    """
    Maximum-weight bipartite matching via brute-force permutation for
    chord sizes ≤ 5; falls back to scipy for anything larger.
    """
    n, m = sim_mat.shape
    if n == 0 or m == 0:
        return 0.0
    if n == 1 or m == 1:
        return float(sim_mat.max())
    if max(n, m) <= 5:
        from itertools import permutations
        k, big = min(n, m), max(n, m)
        best = 0.0
        for perm in permutations(range(big), k):
            t = (sum(sim_mat[i, perm[i]] for i in range(k)) if n <= m
                 else sum(sim_mat[perm[j], j] for j in range(k)))
            if t > best:
                best = t
        return best
    from scipy.optimize import linear_sum_assignment
    r, c = linear_sum_assignment(-sim_mat)
    return float(sim_mat[r, c].sum())


def chord_sim(pitches_a: frozenset, pitches_b: frozenset,
              octave_weight: float = OCTAVE_WEIGHT) -> float:
    """
    Soft chord similarity in [0, 1].

    Builds an element-wise pitch-similarity matrix, finds the optimal
    note-to-note assignment, then normalises by max(|A|, |B|) so that
    extra or missing notes are penalised.

    Examples
    --------
    chord_sim({60}, {60})     → 1.0   (exact)
    chord_sim({60}, {72})     → 0.9   (C4 vs C5, same pitch class)
    chord_sim({60}, {62})     → 0.0   (C vs D, different pitch class)
    chord_sim({60,64},{60,65})→ 0.5   (one exact, one miss; max chord = 2)
    """
    a, b = list(pitches_a), list(pitches_b)
    na, nb = len(a), len(b)
    if na == 0 and nb == 0:
        return 1.0
    if na == 0 or nb == 0:
        return 0.0
    sim_mat = np.array([[pitch_sim(p, q, octave_weight) for q in b] for p in a],
                       dtype=np.float64)
    return _max_assignment(sim_mat) / max(na, nb)


# ── MIDI → event sequence ──────────────────────────────────────────────────────

def midi_to_events(filepath, epsilon_ms=30.0):
    """
    Parse a MIDI file into an ordered list of chord events.

    Note-ons within epsilon_ms of each other are merged into a single event.
    Each event dict carries:
        pitches     : frozenset of MIDI note numbers
        onset_ms    : time of first note in the group (ms)
        duration_ms : longest note duration in the chord (ms), from MIDI note-off
        weight      : duration_ms / median(duration_ms), floored at WEIGHT_FLOOR
    """
    pm = pretty_midi.PrettyMIDI(filepath)

    raw = []
    for instrument in pm.instruments:
        for note in instrument.notes:
            dur_ms = (note.end - note.start) * 1000.0
            raw.append((note.start * 1000.0, note.pitch, dur_ms))
    raw.sort(key=lambda x: x[0])

    if not raw:
        return []

    events = []
    i = 0
    while i < len(raw):
        anchor = raw[i][0]
        pitches, durs = set(), []
        j = i
        while j < len(raw) and raw[j][0] - anchor < epsilon_ms:
            pitches.add(raw[j][1])
            durs.append(raw[j][2])
            j += 1
        events.append({
            "pitches":     frozenset(pitches),
            "onset_ms":    anchor,
            "duration_ms": max(durs),   # sustain = longest note in chord
        })
        i = j

    # Normalise durations to per-recording weights
    median_dur = float(np.median([e["duration_ms"] for e in events]))
    for ev in events:
        ev["weight"] = max(WEIGHT_FLOOR,
                           ev["duration_ms"] / median_dur if median_dur > 0 else 1.0)
    return events


# ── scoring ────────────────────────────────────────────────────────────────────

def sw_score(seq_a, seq_b, gap_penalty=0.5, octave_weight=OCTAVE_WEIGHT):
    """
    Raw Smith-Waterman local alignment score.

    Match score:  2 * chord_sim(A_i, B_j) - 1
        +1.0  identical chords
        +0.8  all notes in correct pitch class but wrong octave  (OCTAVE_WEIGHT=0.9)
         0.0  50% soft chord overlap
        -1.0  no pitch-class overlap  (SW resets; opening a gap is preferred)

    Gap cost: gap_penalty × event.weight
        Long structural notes are expensive to skip.
        Short grace notes are cheap to skip (weight ≈ WEIGHT_FLOOR).

    Follows: Smith & Waterman (1981), J. Mol. Biol. 147:195-197.
    Duration weighting follows the spirit of parangonar (Nakamura et al. 2015),
    which scales note-deletion probabilities by note duration.
    """
    n, m = len(seq_a), len(seq_b)
    if n == 0 or m == 0:
        return 0.0

    H = np.zeros((n + 1, m + 1), dtype=np.float64)

    for i in range(1, n + 1):
        a_i = seq_a[i - 1]
        for j in range(1, m + 1):
            b_j   = seq_b[j - 1]
            s     = 2.0 * chord_sim(a_i["pitches"], b_j["pitches"],
                                    octave_weight) - 1.0
            gap_a = gap_penalty * a_i.get("weight", 1.0)
            gap_b = gap_penalty * b_j.get("weight", 1.0)
            H[i, j] = max(0.0,
                          H[i - 1, j - 1] + s,
                          H[i - 1, j    ] - gap_a,
                          H[i,     j - 1] - gap_b)

    return float(H.max())


def normalised_similarity(seq_a, seq_b, gap_penalty=0.5,
                          octave_weight=OCTAVE_WEIGHT):
    """
    Similarity in [0, 1] via cosine-style normalisation over SW scores:
        sim(A, B) = sw(A, B) / sqrt(sw(A, A) * sw(B, B))
    Diagonal entries (self-comparison) are exactly 1.0.
    """
    s_ab = sw_score(seq_a, seq_b, gap_penalty, octave_weight)
    s_aa = sw_score(seq_a, seq_a, gap_penalty, octave_weight)
    s_bb = sw_score(seq_b, seq_b, gap_penalty, octave_weight)
    denom = (s_aa * s_bb) ** 0.5
    if denom == 0.0:
        return 0.0
    return min(1.0, s_ab / denom)


# ── display ────────────────────────────────────────────────────────────────────

def print_matrix(labels, matrix):
    short = [os.path.splitext(os.path.basename(p))[0] for p in labels]
    # Use a compact 4-char abbreviation (ex01, ex02, …) for column headers
    abbrev = [s[:4] for s in short]
    col_w = 6
    row_w = max(len(s) for s in short) + 1

    header = " " * row_w + "".join(f"{a:>{col_w}}" for a in abbrev)
    print(header)
    print("─" * len(header))
    for i, label in enumerate(short):
        row = f"{label:<{row_w}}"
        for j in range(len(short)):
            row += f"{matrix[i, j]:>{col_w}.3f}"
        print(row)


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Smith-Waterman pairwise similarity matrix for MIDI files."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default="examples",
        help="Directory of .mid files (default: examples/)",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=30.0,
        metavar="MS",
        help="Chord-grouping window in ms (default: 30)",
    )
    parser.add_argument(
        "--gap",
        type=float,
        default=0.5,
        metavar="G",
        help="SW gap penalty (default: 0.5)",
    )
    parser.add_argument(
        "--octave-weight",
        type=float,
        default=OCTAVE_WEIGHT,
        metavar="W",
        help=f"Similarity credit for same pitch class, different octave (default: {OCTAVE_WEIGHT})",
    )
    args = parser.parse_args()

    midi_files = sorted(glob.glob(os.path.join(args.directory, "*.mid")))
    if not midi_files:
        print(f"No .mid files found in '{args.directory}'")
        return

    print(f"\nε = {args.epsilon} ms  |  gap penalty = {args.gap}  |  octave weight = {args.octave_weight}")
    print(f"Loading {len(midi_files)} files from '{args.directory}/'\n")

    sequences = []
    for f in midi_files:
        evs = midi_to_events(f, epsilon_ms=args.epsilon)
        sequences.append(evs)
        print(f"  {os.path.basename(f):38s} {len(evs):3d} events")

    n = len(midi_files)
    matrix = np.zeros((n, n))
    print("\nComputing similarity matrix …")
    for i in range(n):
        for j in range(i, n):
            sim = normalised_similarity(sequences[i], sequences[j], args.gap, args.octave_weight)
            matrix[i, j] = sim
            matrix[j, i] = sim

    print("\nPairwise similarity (SW / Jaccard pitch, cosine-normalised):\n")
    print_matrix(midi_files, matrix)
    print()


if __name__ == "__main__":
    main()
