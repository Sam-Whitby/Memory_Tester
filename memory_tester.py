#!/usr/bin/env python3
"""
memory_tester.py — MIDI improvisation recall trainer.

Phase 1 : Play a melody (recording starts on first note, Space to stop).
Phase 2+ : Attempt to recreate it from memory (same start/stop logic).
           Similarity vs the original is scored and shown after each attempt.
Double Space (no notes between the two presses) → end session.

During recording phases no pitch information is displayed.
"""

import sys
import time
import queue
import threading
import tkinter as tk
from tkinter import ttk

import numpy as np
import mido
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ── Smith-Waterman alignment (inline — no dependency on align.py at runtime) ───

EPSILON_MS  = 30.0
GAP_PENALTY = 0.5


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def _sw_raw(seq_a, seq_b) -> float:
    """Raw Smith-Waterman score using Jaccard pitch similarity."""
    n, m = len(seq_a), len(seq_b)
    if n == 0 or m == 0:
        return 0.0
    H = np.zeros((n + 1, m + 1))
    for i in range(1, n + 1):
        pi = seq_a[i - 1]["pitches"]
        for j in range(1, m + 1):
            s = 2.0 * _jaccard(pi, seq_b[j - 1]["pitches"]) - 1.0
            H[i, j] = max(0.0,
                          H[i - 1, j - 1] + s,
                          H[i - 1, j    ] - GAP_PENALTY,
                          H[i,     j - 1] - GAP_PENALTY)
    return float(H.max())


def _similarity(seq_a, seq_b) -> float:
    """Cosine-normalised SW similarity in [0, 1]."""
    s_ab = _sw_raw(seq_a, seq_b)
    denom = (_sw_raw(seq_a, seq_a) * _sw_raw(seq_b, seq_b)) ** 0.5
    return min(1.0, s_ab / denom) if denom > 0.0 else 0.0


def _to_events(raw_notes, epsilon_ms=EPSILON_MS):
    """[(onset_ms, pitch), …] → ordered chord-event list."""
    if not raw_notes:
        return []
    raw = sorted(raw_notes, key=lambda x: x[0])
    events, i = [], 0
    while i < len(raw):
        anchor = raw[i][0]
        pitches = set()
        j = i
        while j < len(raw) and raw[j][0] - anchor < epsilon_ms:
            pitches.add(raw[j][1])
            j += 1
        events.append({"pitches": frozenset(pitches), "onset_ms": anchor})
        i = j
    return events


# ── MIDI listener (background thread) ─────────────────────────────────────────

class MidiListener(threading.Thread):
    def __init__(self, port_name: str, q: queue.Queue):
        super().__init__(daemon=True)
        self.port_name = port_name
        self._q = q
        self._stop = threading.Event()

    def run(self):
        try:
            with mido.open_input(self.port_name) as port:
                self._q.put(("midi_ready", self.port_name))
                while not self._stop.is_set():
                    for msg in port.iter_pending():
                        if msg.type == "note_on" and msg.velocity > 0:
                            self._q.put(("note", (time.time() * 1000.0, msg.note)))
                    time.sleep(0.004)
        except Exception as exc:
            self._q.put(("midi_error", str(exc)))

    def stop(self):
        self._stop.set()


# ── colours & fonts ────────────────────────────────────────────────────────────

BG     = "#1a1a2e"
PANEL  = "#0d0d1a"
FG     = "#e0e0e0"
ACCENT = "#4cc9f0"
GOOD   = "#06d6a0"
WARN   = "#ffd166"
BAD    = "#ef476f"
GREY   = "#666688"

F_BIG    = ("Helvetica Neue", 24, "bold")
F_STATUS = ("Helvetica Neue", 13)
F_MONO   = ("Courier New", 12)
F_HEAD   = ("Helvetica Neue", 11, "bold")


# ── application ────────────────────────────────────────────────────────────────

class App(tk.Tk):

    # ── state IDs ──
    S_CONNECTING  = "connecting"
    S_WAIT_PLAY   = "wait_play"      # prompt: play the original melody
    S_REC_MELODY  = "rec_melody"     # recording original
    S_WAIT_RECALL = "wait_recall"    # prompt: attempt reconstruction
    S_REC_RECALL  = "rec_recall"     # recording an attempt
    S_DONE        = "done"

    def __init__(self):
        super().__init__()
        self.title("Memory Tester")
        self.configure(bg=BG)
        self.geometry("760x720")
        self.resizable(True, True)

        # ── app state ──
        self._state    = self.S_CONNECTING
        self._q        = queue.Queue()
        self._listener = None

        self._rec_start  = 0.0   # onset of first note in current recording (ms)
        self._raw        = []    # [(onset_ms_relative, pitch)]
        self._notes_flag = False # any notes since last Space?

        self._original = []   # chord events for the original melody
        self._scores   = []   # float scores per attempt
        self._n        = 0    # attempt counter

        self._build_ui()
        self._connect_midi()
        self.bind("<space>", self._on_space)
        self.focus_set()
        self.after(50, self._poll)

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── status panel ──
        self._panel = tk.Frame(self, bg=PANEL, height=155)
        self._panel.pack(fill=tk.X, padx=20, pady=(20, 8))
        self._panel.pack_propagate(False)

        self._lbl_main = tk.Label(
            self._panel, text="Connecting to MIDI keyboard…",
            font=F_BIG, bg=PANEL, fg=ACCENT,
            wraplength=720, justify=tk.CENTER,
        )
        self._lbl_main.pack(expand=True)

        self._lbl_sub = tk.Label(
            self._panel, text="",
            font=F_STATUS, bg=PANEL, fg=FG,
            wraplength=720, justify=tk.CENTER,
        )
        self._lbl_sub.pack(pady=(0, 14))

        # ── accent line ──
        tk.Frame(self, bg=ACCENT, height=2).pack(fill=tk.X, padx=20)

        # ── scores table ──
        tbl = tk.Frame(self, bg=BG)
        tbl.pack(fill=tk.X, padx=20, pady=(12, 0))

        tk.Label(tbl, text="Scores", font=F_HEAD,
                 bg=BG, fg=ACCENT).pack(anchor=tk.W, pady=(0, 4))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("MT.Treeview",
                        background=BG, foreground=FG,
                        fieldbackground=BG, rowheight=24, font=F_MONO)
        style.configure("MT.Treeview.Heading",
                        background=PANEL, foreground=ACCENT, font=F_HEAD)
        style.map("MT.Treeview", background=[("selected", "#2a2a4a")])

        self._tree = ttk.Treeview(
            tbl, columns=("attempt", "score", "bar"),
            show="headings", style="MT.Treeview", height=5,
        )
        self._tree.heading("attempt", text="Attempt")
        self._tree.heading("score",   text="Similarity")
        self._tree.heading("bar",     text="")
        self._tree.column("attempt", width=110, anchor=tk.CENTER)
        self._tree.column("score",   width=110, anchor=tk.CENTER)
        self._tree.column("bar",     width=460, anchor=tk.W)
        self._tree.pack(fill=tk.X)

        # ── graph ──
        gf = tk.Frame(self, bg=BG)
        gf.pack(fill=tk.BOTH, expand=True, padx=20, pady=(14, 16))

        self._fig = Figure(figsize=(7, 3.2), dpi=100, facecolor=BG)
        self._ax  = self._fig.add_subplot(111)
        self._refresh_graph()

        self._canvas = FigureCanvasTkAgg(self._fig, master=gf)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _refresh_graph(self):
        ax = self._ax
        ax.clear()
        ax.set_facecolor(BG)
        ax.tick_params(colors=FG, labelsize=9)
        for sp in ax.spines.values():
            sp.set_edgecolor("#444466")
        ax.set_xlabel("Attempt", color=FG, fontsize=10)
        ax.set_ylabel("Similarity to original", color=FG, fontsize=10)
        ax.set_ylim(-0.03, 1.07)
        ax.set_title("Reconstruction similarity vs. original melody",
                     color=FG, fontsize=11, pad=8)
        ax.grid(True, color="#2a2a44", linewidth=0.6, linestyle="--")

        if self._scores:
            xs = list(range(1, len(self._scores) + 1))
            ys = self._scores
            if len(xs) > 1:
                ax.plot(xs, ys, color=ACCENT, linewidth=1.8, zorder=3, alpha=0.7)
            dot_colours = [
                GOOD if s >= 0.75 else WARN if s >= 0.45 else BAD
                for s in ys
            ]
            ax.scatter(xs, ys, color=dot_colours, s=80, zorder=5)
            # annotate each point
            for x, y in zip(xs, ys):
                ax.annotate(f"{y:.2f}", (x, y),
                            textcoords="offset points", xytext=(0, 9),
                            ha="center", fontsize=8, color=FG)
            ax.set_xlim(0.5, max(xs) + 0.5)
            ax.set_xticks(xs)
            ax.axhline(y=max(ys), color=GOOD, linewidth=0.8,
                       linestyle=":", alpha=0.5)

        self._fig.tight_layout(pad=1.4)
        self._canvas.draw()

    # ─────────────────────────────────────────────────────────────────────────
    # MIDI connection
    # ─────────────────────────────────────────────────────────────────────────

    def _connect_midi(self):
        ports = mido.get_input_names()
        if not ports:
            self._show("No MIDI input found.",
                       "Connect a MIDI keyboard and restart the app.")
            return
        # Prefer a port that looks like a physical keyboard
        port = next(
            (p for p in ports if "iac" not in p.lower() and "bus" not in p.lower()),
            ports[0],
        )
        self._listener = MidiListener(port, self._q)
        self._listener.start()

    # ─────────────────────────────────────────────────────────────────────────
    # Event dispatch
    # ─────────────────────────────────────────────────────────────────────────

    def _poll(self):
        try:
            while True:
                self._dispatch(*self._q.get_nowait())
        except queue.Empty:
            pass
        self.after(50, self._poll)

    def _dispatch(self, kind, data):
        if kind == "midi_ready":
            self._goto(self.S_WAIT_PLAY, port=data)

        elif kind == "midi_error":
            self._show("MIDI error", str(data))

        elif kind == "note":
            onset_ms, pitch = data
            s = self._state

            if s == self.S_WAIT_PLAY:
                self._rec_start = onset_ms
                self._raw = [(0.0, pitch)]
                self._notes_flag = True
                self._goto(self.S_REC_MELODY)

            elif s == self.S_REC_MELODY:
                self._raw.append((onset_ms - self._rec_start, pitch))
                self._notes_flag = True
                self._flash()

            elif s == self.S_WAIT_RECALL:
                self._rec_start = onset_ms
                self._raw = [(0.0, pitch)]
                self._notes_flag = True
                self._goto(self.S_REC_RECALL)

            elif s == self.S_REC_RECALL:
                self._raw.append((onset_ms - self._rec_start, pitch))
                self._notes_flag = True
                self._flash()

    def _on_space(self, _=None):
        # Flush MIDI queue before acting so no note is lost to a race
        try:
            while True:
                self._dispatch(*self._q.get_nowait())
        except queue.Empty:
            pass

        s = self._state

        if s == self.S_REC_MELODY:
            evs = _to_events(self._raw)
            if not evs:
                self._lbl_sub.config(text="No notes recorded — play something first.")
                return
            self._original = evs
            self._notes_flag = False
            self._goto(self.S_WAIT_RECALL)

        elif s == self.S_WAIT_RECALL:
            if not self._notes_flag:
                self._goto(self.S_DONE)
            # (notes already being recorded → we are in S_REC_RECALL, not here)

        elif s == self.S_REC_RECALL:
            evs = _to_events(self._raw)
            score = _similarity(self._original, evs) if evs else 0.0
            self._n += 1
            self._scores.append(score)
            self._notes_flag = False
            self._add_row(self._n, score)
            self._refresh_graph()
            self._goto(self.S_WAIT_RECALL)

    # ─────────────────────────────────────────────────────────────────────────
    # State transitions
    # ─────────────────────────────────────────────────────────────────────────

    def _goto(self, state, **kw):
        self._state = state

        if state == self.S_WAIT_PLAY:
            self._show(
                "Play your melody.",
                f"MIDI: {kw.get('port', '…')}   ·   "
                "Recording starts on first note   ·   Space to stop",
            )

        elif state == self.S_REC_MELODY:
            self._show("● Recording original melody…",
                       "Space to stop")

        elif state == self.S_WAIT_RECALL:
            n = self._n + 1
            hint = (
                "Recording starts on first note   ·   Space to stop   ·   "
                "Two Spaces (no notes between) to end session"
            )
            self._show(f"Attempt {n} — play your reconstruction.", hint)

        elif state == self.S_REC_RECALL:
            self._show(f"● Recording attempt {self._n + 1}…",
                       "Space to stop")

        elif state == self.S_DONE:
            n = len(self._scores)
            best = f"{max(self._scores):.3f}" if self._scores else "—"
            self._show(
                "Session complete.",
                f"{n} attempt{'s' if n != 1 else ''}   ·   "
                f"Best similarity: {best}   ·   Close window to exit",
            )
            if self._listener:
                self._listener.stop()

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _show(self, main: str, sub: str = ""):
        self._lbl_main.config(text=main)
        self._lbl_sub.config(text=sub)

    def _flash(self):
        """Brief colour pulse on the status label to confirm a note arrived."""
        self._lbl_main.config(fg=GOOD)
        self.after(110, lambda: self._lbl_main.config(fg=ACCENT))

    def _bar(self, score: float, width: int = 40) -> str:
        filled = round(score * width)
        return "█" * filled + "░" * (width - filled)

    def _row_colour(self, score: float) -> str:
        return GOOD if score >= 0.75 else WARN if score >= 0.45 else BAD

    def _add_row(self, n: int, score: float):
        colour = self._row_colour(score)
        tag = f"r{n}"
        self._tree.insert(
            "", tk.END,
            values=(f"Attempt {n}", f"{score:.3f}", self._bar(score)),
            tags=(tag,),
        )
        self._tree.tag_configure(tag, foreground=colour)
        kids = self._tree.get_children()
        if kids:
            self._tree.see(kids[-1])


# ── entry point ────────────────────────────────────────────────────────────────

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
