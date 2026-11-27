#!/usr/bin/env python3
"""Pack the repo (git-tracked files) into ONE text file for chat delivery, and unpack it again.
Text files are stored as-is; binaries (images, models) as base64. Large models other than v8 and v7 are left out (they can be retrained).
  python scripts/make_bundle.py pack out.txt [part_MB]  (parts: out.txt.part1, .part2 ...; rejoin with: cat out.txt.part* > bundle.txt)
  python scripts/make_bundle.py pack out.txt      |      python scripts/make_bundle.py unpack bundle.txt target_dir"""
import sys, os, base64, subprocess, zlib
KEEP_MODELS = ("model_v8_hgb.joblib", "model_v8.metrics.json", "model_v7_svm_rbf.joblib", "model_v7.metrics.json")
M = "=====SUBLUMEN-FILE "
def pack(out):
    files = subprocess.check_output(["git", "ls-files"], text=True).split("\n"); n = 0
    with open(out, "w", encoding="utf-8") as o:
        o.write("SUBLUMEN SOURCE BUNDLE. Unpack: python3 scripts/make_bundle.py unpack bundle.txt NEWDIR (the script is inside this file: copy the block for scripts/make_bundle.py into a file first).\n")
        for f in files:
            if not f or f.startswith("backend/models/") and os.path.basename(f) not in KEEP_MODELS: continue
            b = open(f, "rb").read()
            try:
                t = b.decode("utf-8"); assert "\r" not in t and not t.endswith("\n=====") ; kind = "text"; body = t if t.endswith("\n") else t + "\n#NOEOL\n"
            except Exception: kind = "b64z"; e = base64.b64encode(zlib.compress(b, 9)).decode(); body = "\n".join(e[i:i + 100] for i in range(0, len(e), 100)) + "\n"
            o.write(f"{M}{kind} {f} {len(b)}\n{body}"); n += 1
        o.write("=====SUBLUMEN-END\n")
    print("packed", n, "files")
def unpack(src, dst):
    cur = None; buf = []; n = 0
    def flush():
        nonlocal n
        if cur is None: return
        kind, path, size = cur; p = os.path.join(dst, path); os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        s = "".join(buf)
        if kind == "text": s = s[:-len("#NOEOL\n")][:-1] if s.endswith("#NOEOL\n") else s; data = s.encode("utf-8")
        else: data = zlib.decompress(base64.b64decode(s))
        assert len(data) == int(size), (path, len(data), size)
        open(p, "wb").write(data); n += 1
    for line in open(src, encoding="utf-8"):
        if line.startswith(M) or line.startswith("=====SUBLUMEN-END"):
            flush(); buf = []
            cur = tuple(line[len(M):].split()) if line.startswith(M) else None
        elif cur is not None: buf.append(line)
    print("unpacked", n, "files into", dst)
if __name__ == "__main__":
    if sys.argv[1] == "pack":
        pack(sys.argv[2])
        if len(sys.argv) > 3:  # split at line boundaries so that `cat parts` restores the exact file
            lim = int(float(sys.argv[3]) * 1e6); n = 1; sz = 0; out = open(f"{sys.argv[2]}.part{n}", "w", encoding="utf-8")
            for line in open(sys.argv[2], encoding="utf-8"):
                if sz + len(line) > lim: out.close(); n += 1; sz = 0; out = open(f"{sys.argv[2]}.part{n}", "w", encoding="utf-8")
                out.write(line); sz += len(line)
            out.close(); os.remove(sys.argv[2]); print("parts:", n)
    else: unpack(sys.argv[2], sys.argv[3])
