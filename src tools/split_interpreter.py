#!/usr/bin/env python3
"""
split_interpreter.py

Splits an interpreter.py that already contains "## NN -- filename -- description"
marker comments (one per split point) into that many chunk files, plus a
manifest.txt listing them in order.

Markers look like:
    ## 07 -- 07_interp_core.py -- Interpreter core: init/run/execute/eval/call

The double-hash makes them easy to grep/search for on their own
(e.g. `grep -n "^## " interpreter.py`), and this script drives the split off
the markers themselves rather than hardcoded line numbers -- so re-splitting
still works after you've edited the file, as long as the markers stay in
place at the top of each section.

Usage:
    python3 split_interpreter.py interpreter.py split_out/
"""
import sys
import os
import re

MARKER_RE = re.compile(r"^## (\d+) -- (\S+) -- (.*)$")

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 split_interpreter.py interpreter.py split_out/")
        sys.exit(1)

    src_path, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    with open(src_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find every marker line and its position.
    markers = []  # (line_index, num, fname, desc)
    for i, line in enumerate(lines):
        m = MARKER_RE.match(line.rstrip("\n"))
        if m:
            markers.append((i, m.group(1), m.group(2), m.group(3)))

    if not markers:
        print("No '## NN -- filename -- description' markers found. "
              "Add them first (see interpreter_marked.py), or edit this "
              "script to fall back to fixed line ranges.")
        sys.exit(1)

    manifest = []
    for idx, (start_i, num, fname, desc) in enumerate(markers):
        end_i = markers[idx + 1][0] if idx + 1 < len(markers) else len(lines)
        chunk_lines = lines[start_i:end_i]  # includes the marker line itself
        out_path = os.path.join(out_dir, fname)
        with open(out_path, "w", encoding="utf-8") as f:
            f.writelines(chunk_lines)
        manifest.append(fname)
        print(f"wrote {fname}: {len(chunk_lines)} lines ({desc})")

    with open(os.path.join(out_dir, "manifest.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(manifest) + "\n")

    print(f"\nDone. {len(manifest)} chunks written to {out_dir}/")

if __name__ == "__main__":
    main()
