"""
generate_examples.py
Generates 10 example MIDI files for Smith-Waterman alignment testing.

Groups:
  A (ex01-ex04): C-major folk melody, progressively corrupted
  B (ex05-ex06): Different C-major melody (moderate similarity to A)
  C (ex07-ex08): A-minor melody (low similarity to A/B)
  D (ex09-ex10): Chromatic melody (very low similarity to others)
"""

import os
import random
import pretty_midi

EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")
TEMPO   = 120           # BPM
BEAT    = 60.0 / TEMPO  # 0.5 s per beat
JITTER  = 0.008         # ±8 ms per-event timing jitter (well within default ε=30 ms)

random.seed(42)


# ── melody definitions ─────────────────────────────────────────────────────────
# (pitches: list[int], start_beat: float, dur_beats: float, velocity: int)

MELODY_A = [
    ([60, 48], 0,  1.0, 82),  # C4+C3
    ([64],     1,  0.5, 74),  # E4
    ([67, 55], 2,  1.0, 78),  # G4+G3
    ([65],     3,  0.5, 70),  # F4
    ([64, 52], 4,  1.0, 76),  # E4+E3
    ([62],     5,  0.5, 68),  # D4
    ([60, 48], 6,  2.0, 84),  # C4+C3  (held)
    ([62],     8,  0.5, 72),  # D4
    ([64, 52], 9,  1.0, 76),  # E4+E3
    ([65],     10, 0.5, 70),  # F4
    ([67, 55], 11, 1.0, 80),  # G4+G3
    ([69],     12, 0.5, 74),  # A4
    ([67, 55], 13, 1.0, 76),  # G4+G3
    ([65],     14, 0.5, 70),  # F4
    ([64, 52], 15, 1.0, 74),  # E4+E3
    ([62],     16, 0.5, 68),  # D4
    ([60, 48], 17, 2.0, 86),  # C4+C3
    ([67, 55], 19, 1.0, 78),  # G4+G3
    ([69],     20, 0.5, 74),  # A4
    ([71],     21, 0.5, 76),  # B4
    ([72, 60], 22, 1.0, 84),  # C5+C4
    ([71],     23, 0.5, 76),  # B4
    ([69],     24, 0.5, 72),  # A4
    ([67, 55], 25, 1.0, 78),  # G4+G3
    ([65],     26, 0.5, 70),  # F4
    ([64, 52], 27, 1.0, 74),  # E4+E3
    ([62],     28, 0.5, 70),  # D4
    ([60, 48], 29, 3.0, 88),  # C4+C3  (final)
]  # 28 events, ~16 s

MELODY_B = [
    ([64, 52], 0,  1.0, 80),  # E4+E3
    ([65],     1,  0.5, 74),  # F4
    ([67, 55], 2,  1.0, 78),  # G4+G3
    ([69],     3,  0.5, 72),  # A4
    ([67, 55], 4,  1.0, 76),  # G4+G3
    ([65],     5,  0.5, 70),  # F4
    ([64, 52], 6,  2.0, 82),  # E4+E3
    ([60, 48], 8,  1.0, 78),  # C4+C3
    ([62],     9,  0.5, 72),  # D4
    ([64, 52], 10, 1.0, 76),  # E4+E3
    ([65],     11, 0.5, 70),  # F4
    ([64, 52], 12, 0.5, 74),  # E4+E3
    ([62],     13, 0.5, 68),  # D4
    ([60, 48], 14, 2.0, 84),  # C4+C3
    ([60],     16, 0.5, 72),  # C4
    ([62],     17, 0.5, 74),  # D4
    ([64, 52], 18, 0.5, 76),  # E4+E3
    ([65],     19, 0.5, 70),  # F4
    ([67, 55], 20, 1.0, 80),  # G4+G3
    ([69],     21, 0.5, 74),  # A4
    ([71],     22, 0.5, 76),  # B4
    ([72, 60], 23, 1.0, 84),  # C5+C4
    ([71],     24, 0.5, 76),  # B4
    ([69],     25, 0.5, 72),  # A4
    ([67, 55], 26, 1.0, 78),  # G4+G3
    ([64, 52], 27, 1.0, 74),  # E4+E3
    ([60, 48], 28, 3.0, 86),  # C4+C3
]  # 27 events, ~15.5 s

MELODY_C = [
    ([69, 57], 0,  1.0, 78),  # A4+A3
    ([67],     1,  0.5, 72),  # G4
    ([65, 53], 2,  1.0, 76),  # F4+F3
    ([64],     3,  0.5, 70),  # E4
    ([62, 50], 4,  1.0, 74),  # D4+D3
    ([60],     5,  0.5, 68),  # C4
    ([59, 47], 6,  2.0, 82),  # B3+B2
    ([60],     8,  0.5, 72),  # C4
    ([62, 50], 9,  1.0, 76),  # D4+D3
    ([64],     10, 0.5, 70),  # E4
    ([65, 53], 11, 1.0, 78),  # F4+F3
    ([67],     12, 0.5, 74),  # G4
    ([69, 57], 13, 2.0, 82),  # A4+A3
    ([72, 60], 15, 0.5, 80),  # C5+C4
    ([71],     16, 0.5, 76),  # B4
    ([69, 57], 17, 0.5, 78),  # A4+A3
    ([67],     18, 0.5, 72),  # G4
    ([65, 53], 19, 0.5, 74),  # F4+F3
    ([64],     20, 0.5, 70),  # E4
    ([62, 50], 21, 0.5, 76),  # D4+D3
    ([60],     22, 0.5, 72),  # C4
    ([59, 47], 23, 1.0, 80),  # B3+B2
    ([57, 45], 24, 1.0, 76),  # A3+A2
    ([55],     25, 0.5, 72),  # G3
    ([53, 41], 26, 0.5, 74),  # F3+F2
    ([52],     27, 0.5, 68),  # E3
    ([50, 38], 28, 0.5, 70),  # D3+D2
    ([45, 33], 29, 3.0, 84),  # A2+A1
]  # 28 events, ~16 s

MELODY_D = [
    ([61, 49], 0,  1.0, 82),  # C#4+C#3
    ([63],     1,  0.5, 76),  # Eb4
    ([66, 54], 2,  1.0, 80),  # F#4+F#3
    ([68],     3,  0.5, 74),  # Ab4
    ([66, 54], 4,  0.5, 78),  # F#4+F#3
    ([63],     5,  0.5, 70),  # Eb4
    ([61, 49], 6,  2.0, 84),  # C#4+C#3
    ([66, 54], 8,  0.5, 78),  # F#4+F#3
    ([68],     9,  0.5, 74),  # Ab4
    ([70, 58], 10, 1.0, 82),  # Bb4+Bb3
    ([71],     11, 0.5, 78),  # B4
    ([70, 58], 12, 0.5, 76),  # Bb4+Bb3
    ([68],     13, 0.5, 72),  # Ab4
    ([66, 54], 14, 0.5, 78),  # F#4+F#3
    ([63],     15, 0.5, 70),  # Eb4
    ([61, 49], 16, 2.0, 86),  # C#4+C#3
    ([54],     18, 0.5, 72),  # F#3
    ([56, 44], 19, 0.5, 76),  # Ab3+Ab2
    ([58],     20, 0.5, 74),  # Bb3
    ([59, 47], 21, 1.0, 80),  # B3+B2
    ([61],     22, 0.5, 76),  # C#4
    ([63, 51], 23, 0.5, 78),  # Eb4+Eb3
    ([66],     24, 0.5, 80),  # F#4
    ([68, 56], 25, 1.0, 84),  # Ab4+Ab3
    ([66],     26, 0.5, 78),  # F#4
    ([61, 49], 27, 3.0, 86),  # C#4+C#3
]  # 26 events, ~15 s


# ── helpers ────────────────────────────────────────────────────────────────────

def vary(melody, delete_indices=(), substitutions=None):
    """Return a modified copy of melody: delete or substitute events by index."""
    substitutions = substitutions or {}
    result = []
    for i, event in enumerate(melody):
        if i in delete_indices:
            continue
        pitches, start, dur, vel = event
        if i in substitutions:
            pitches = substitutions[i]
        result.append((pitches, start, dur, vel))
    return result


def write_midi(note_events, path):
    pm = pretty_midi.PrettyMIDI(initial_tempo=TEMPO)
    piano = pretty_midi.Instrument(program=0, name="Piano")
    for pitches, start_beat, dur_beats, velocity in note_events:
        # Shared per-event jitter: keeps simultaneous notes grouped but adds realism
        ev_jitter = random.uniform(-JITTER, JITTER)
        t0 = max(0.0, start_beat * BEAT + ev_jitter)
        t1 = max(t0 + 0.05, t0 + dur_beats * BEAT * 0.9)
        for pitch in pitches:
            piano.notes.append(pretty_midi.Note(
                velocity=int(min(127, max(1, velocity))),
                pitch=int(pitch),
                start=t0,
                end=t1,
            ))
    pm.instruments.append(piano)
    pm.write(path)


# ── example specifications ─────────────────────────────────────────────────────

EXAMPLES = {
    # ── Group A: same C-major melody, increasingly corrupted ──────────────────
    "ex01_A_clean.mid": MELODY_A,

    # 3 events deleted (minor omissions)
    "ex02_A_del3.mid": vary(MELODY_A, delete_indices={3, 11, 22}),

    # 4 note substitutions (wrong notes played)
    "ex03_A_sub4.mid": vary(MELODY_A, substitutions={
        2:  [66, 54],   # G4+G3 → F#4+F#3
        8:  [64],       # D4 → E4  (one step up)
        15: [65, 53],   # E4+E3 → F4+F3
        23: [65, 53],   # G4+G3 → F4+F3
    }),

    # Mixed: 2 deletions + 3 substitutions
    "ex04_A_mixed.mid": vary(MELODY_A,
        delete_indices={5, 19},
        substitutions={
            0:  [62, 50],   # C4+C3 → D4+D3
            12: [65],       # A4 → F4
            25: [67, 55],   # F4+F3 → G4+G3
        }
    ),

    # ── Group B: different C-major melody (moderate similarity to A) ──────────
    "ex05_B_clean.mid": MELODY_B,

    # 2 deletions + 1 substitution
    "ex06_B_var.mid": vary(MELODY_B,
        delete_indices={4, 15},
        substitutions={9: [60]}   # D4 → C4
    ),

    # ── Group C: A-minor melody (low similarity) ──────────────────────────────
    "ex07_C_clean.mid": MELODY_C,

    # 1 deletion + 2 substitutions
    "ex08_C_var.mid": vary(MELODY_C,
        delete_indices={6},
        substitutions={
            2:  [64, 52],   # F4+F3 → E4+E3
            11: [65],       # G4 → F4
        }
    ),

    # ── Group D: chromatic melody (very low similarity) ───────────────────────
    "ex09_D_clean.mid": MELODY_D,

    # 1 deletion + 2 substitutions
    "ex10_D_var.mid": vary(MELODY_D,
        delete_indices={5},
        substitutions={
            3:  [67],       # Ab4 → G4
            10: [69, 57],   # Bb4+Bb3 → A4+A3
        }
    ),
}


def main():
    os.makedirs(EXAMPLES_DIR, exist_ok=True)
    print(f"Writing MIDI examples to {EXAMPLES_DIR}/\n")
    for fname, events in EXAMPLES.items():
        path = os.path.join(EXAMPLES_DIR, fname)
        write_midi(events, path)
        duration = max(s * BEAT + d * BEAT for _, s, d, _ in events)
        print(f"  {fname:35s}  {len(events):2d} events  {duration:.1f}s")
    print(f"\nGenerated {len(EXAMPLES)} files.")


if __name__ == "__main__":
    main()
