"""
align.py
Compute pairwise Smith-Waterman similarity between MIDI files.

Each MIDI file is represented as a sequence of chord events (epsilon-grouped
note onsets). Events are compared using Jaccard similarity on their pitch sets.
The SW score is normalised by the geometric mean of each file's self-score,
giving a value in [0, 1] where 1 = identical sequence.

Usage:
    python align.py                        # uses ./examples/, epsilon=30 ms
    python align.py path/to/dir            # custom directory
    python align.py --epsilon 50           # 50 ms grouping window
    python align.py --epsilon 50 --gap 0.4
"""

import os
import glob
import argparse
import numpy as np
import pretty_midi


# ── MIDI → event sequence ──────────────────────────────────────────────────────

def midi_to_events(filepath, epsilon_ms=30.0):
    """
    Parse a MIDI file into an ordered list of chord events.

    Note-ons within epsilon_ms of each other are merged into a single event
    (representing a chord or near-simultaneous cluster). Each event is a dict:
        pitches  : frozenset of MIDI note numbers
        onset_ms : float, time of first note in the group

    Args:
        filepath   : path to .mid file
        epsilon_ms : grouping window in milliseconds
    """
    pm = pretty_midi.PrettyMIDI(filepath)

    raw = []
    for instrument in pm.instruments:
        for note in instrument.notes:
            raw.append((note.start * 1000.0, note.pitch))
    raw.sort(key=lambda x: x[0])

    if not raw:
        return []

    events = []
    i = 0
    while i < len(raw):
        anchor = raw[i][0]
        pitches = set()
        j = i
        while j < len(raw) and raw[j][0] - anchor < epsilon_ms:
            pitches.add(raw[j][1])
            j += 1
        events.append({
            "pitches": frozenset(pitches),
            "onset_ms": anchor,
        })
        i = j

    return events


# ── scoring ────────────────────────────────────────────────────────────────────

def jaccard(a, b):
    """Jaccard similarity between two frozensets."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def sw_score(seq_a, seq_b, gap_penalty=0.5):
    """
    Raw Smith-Waterman local alignment score.

    Match score:  2 * Jaccard(pitches_a, pitches_b) - 1
        +1.0  identical chords
         0.0  50% pitch overlap
        -1.0  no shared pitches  (SW prefers to open a gap instead)

    Follows: Smith & Waterman (1981), J. Mol. Biol. 147:195-197.
    """
    n, m = len(seq_a), len(seq_b)
    if n == 0 or m == 0:
        return 0.0

    H = np.zeros((n + 1, m + 1), dtype=np.float64)

    for i in range(1, n + 1):
        pi = seq_a[i - 1]["pitches"]
        for j in range(1, m + 1):
            pj = seq_b[j - 1]["pitches"]
            match  = H[i - 1, j - 1] + 2.0 * jaccard(pi, pj) - 1.0
            delete = H[i - 1, j    ] - gap_penalty
            insert = H[i,     j - 1] - gap_penalty
            H[i, j] = max(0.0, match, delete, insert)

    return float(H.max())


def normalised_similarity(seq_a, seq_b, gap_penalty=0.5):
    """
    Similarity in [0, 1] via cosine-style normalisation over SW scores:
        sim(A, B) = sw(A, B) / sqrt(sw(A, A) * sw(B, B))
    Diagonal entries (self-comparison) are exactly 1.0.
    """
    s_ab = sw_score(seq_a, seq_b, gap_penalty)
    s_aa = sw_score(seq_a, seq_a, gap_penalty)
    s_bb = sw_score(seq_b, seq_b, gap_penalty)
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
    args = parser.parse_args()

    midi_files = sorted(glob.glob(os.path.join(args.directory, "*.mid")))
    if not midi_files:
        print(f"No .mid files found in '{args.directory}'")
        return

    print(f"\nε = {args.epsilon} ms  |  gap penalty = {args.gap}")
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
            sim = normalised_similarity(sequences[i], sequences[j], args.gap)
            matrix[i, j] = sim
            matrix[j, i] = sim

    print("\nPairwise similarity (SW / Jaccard pitch, cosine-normalised):\n")
    print_matrix(midi_files, matrix)
    print()


if __name__ == "__main__":
    main()
