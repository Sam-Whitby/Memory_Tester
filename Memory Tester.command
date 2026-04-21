#!/bin/bash
# Memory Tester — double-click this file in Finder to launch.
# Requires a MIDI keyboard connected before launch.

cd "$(dirname "$0")"

# Locate a Python 3 that has tkinter + mido (prefer Anaconda, then Homebrew)
find_python() {
    for py in \
        "$HOME/opt/anaconda3/bin/python3" \
        "$HOME/anaconda3/bin/python3"     \
        "$HOME/miniconda3/bin/python3"    \
        /usr/local/bin/python3            \
        /opt/homebrew/bin/python3         \
        python3
    do
        if "$py" -c "import tkinter, mido" 2>/dev/null; then
            echo "$py"
            return
        fi
    done
}

PY=$(find_python)
if [ -z "$PY" ]; then
    echo "ERROR: No suitable Python found."
    echo "Install Anaconda or run:  pip install mido python-rtmidi matplotlib"
    read -r -p "Press Enter to exit..." _
    exit 1
fi

echo "Using Python: $PY"
"$PY" -m pip install -q -r requirements.txt 2>/dev/null
"$PY" memory_tester.py
