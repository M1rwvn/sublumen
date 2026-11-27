"""dataset_v4: bigger real-photo set, source-photo-disjoint test split, 3 embedders (+ JPEG q95 recompression variants).
Rows carry the 28 original features plus 125 SPAM features. The test split uses ONLY source photos never used for train/val."""
import argparse, glob, hashlib, io, json, os
import numpy as np, pandas as pd
from PIL import Image
from . import covers, features
from .spam import spam_features, NAMES as SPAM
from ..benchmark.run import embed
from ..stego_core import lsb_matching  # noqa: F401 (used via embed)

def photo_split(path):  # deterministic by file name: ~25% of source photos are test-only
    h = int(hashlib.sha256(os.path.basename(path).encode()).hexdigest(), 16) % 100
    return "test" if h < 25 else ("val" if h < 37 else "train")

def crop(path, rng, s=128):
    im = np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)
    if im.shape[0] < s or im.shape[1] < s:
        im = np.asarray(Image.fromarray(im).resize((max(s, im.shape[1]), max(s, im.shape[0]))), dtype=np.uint8)
    y = int(rng.integers(0, im.shape[0] - s + 1)); x = int(rng.integers(0, im.shape[1] - s + 1))
    return im[y:y + s, x:x + s].copy()

def jpeg95(arr):
    b = io.BytesIO(); Image.fromarray(arr, "RGB").save(b, "JPEG", quality=95)
    return np.asarray(Image.open(io.BytesIO(b.getvalue())).convert("RGB"), dtype=np.uint8)

def feats(arr):
    return np.concatenate([features.extract_array(arr), spam_features(arr)])

def build(out, n_real=1200, n_other=200, seed=99, src="/tmp/real/imagenette2-160/train", part=0, parts=1):
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(seed)
    files = sorted(glob.glob(os.path.join(src, "*", "*.JPEG")))
    by = {"train": [], "val": [], "test": []}
    for f in files: by[photo_split(f)].append(f)
    rows, X = [], []
    plan = []  # (cover_type, split, maker)
    shares = {"train": 0.63, "val": 0.12, "test": 0.25}
    for sp, sh in shares.items():
        for _ in range(int(n_real * sh)):
            plan.append(("imagenette", sp, by[sp][int(rng.integers(len(by[sp])))]))
    for t in ("graphic", "texture", "photo_like"):
        for i in range(n_other):
            sp = "train" if i < 0.63 * n_other else "val" if i < 0.75 * n_other else "test"
            plan.append((t, sp, int(rng.integers(0, 2**31 - 1))))
    for cid, (t, sp, src_) in enumerate(plan):
        if cid % parts != part: continue
        if t == "imagenette":
            arr = crop(src_, np.random.default_rng(seed * 100003 + cid))
        else:
            arr, _ = __import__("sublumen.forensics_core.analyzer", fromlist=["x"]).load_array(covers.make_cover(t, src_))
        iid = f"v4_{cid:05d}"
        def add(label, variant, kind, rate, a):
            rows.append(dict(image_id=iid, split=sp, cover_type=t, label=label, variant=variant, embedder=kind, payload_rate=rate)); X.append(feats(a))
        add(0, "png", "none", 0.0, arr); add(0, "jpeg95", "none", 0.0, jpeg95(arr))
        for kind, rates in (("lsb_replace", (0.10, 0.25, 0.50)), ("lsb_replace_keyed", (0.25,)), ("lsb_matching", (0.25, 0.50))):
            for r in rates:
                st = embed(arr, r, kind, seed + cid * 7 + int(r * 100))
                add(1, "png", kind, r, st)
        add(1, "jpeg95", "lsb_replace", 0.5, jpeg95(embed(arr, 0.5, "lsb_replace", seed + cid)))
        add(1, "jpeg95", "lsb_matching", 0.5, jpeg95(embed(arr, 0.5, "lsb_matching", seed + cid + 1)))
    df = pd.DataFrame(rows)
    feat = pd.DataFrame(np.vstack(X), columns=list(features.FEATURE_NAMES) + SPAM)
    full = pd.concat([df, feat], axis=1); full.to_csv(os.path.join(out, f"part{part}.csv" if parts > 1 else "dataset.csv"), index=False)
    json.dump(dict(seed=seed, n_real=n_real, n_other=n_other, rows=len(full), source_photo_disjoint_test=True,
                   source_files={k: len(v) for k, v in by.items()}), open(os.path.join(out, "meta.json"), "w"), indent=1)
    print(full.groupby(["split", "cover_type", "label"]).size().unstack())

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="data/dataset_v4"); ap.add_argument("--n-real", type=int, default=1200)
    ap.add_argument("--n-other", type=int, default=200); ap.add_argument('--part', type=int, default=0); ap.add_argument('--parts', type=int, default=1)
    a = ap.parse_args(); build(a.out, a.n_real, a.n_other, part=a.part, parts=a.parts)
