#!/usr/bin/env python3
"""
join_interpreter.py

Reassembles interpreter.py from the ordered chunk files listed in
split_out/manifest.txt. This is the counterpart to split_interpreter.py.

Usage:
    python3 join_interpreter.py split_out/ interpreter.py
"""
import sys
import os

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 join_interpreter.py split_out/ interpreter.py")
        sys.exit(1)

    in_dir, out_path = sys.argv[1], sys.argv[2]
    manifest_path = os.path.join(in_dir, "manifest.txt")

    with open(manifest_path, "r", encoding="utf-8") as f:
        filenames = [line.strip() for line in f if line.strip()]

    pieces = []
    for fname in filenames:
        chunk_path = os.path.join(in_dir, fname)
        with open(chunk_path, "r", encoding="utf-8") as f:
            pieces.append(f.read())

    result = "".join(pieces)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"Reassembled {len(filenames)} chunks -> {out_path} ({len(result.splitlines())} lines)")

if __name__ == "__main__":
    main()
