"""Dataset builder: cover + stego copies (via the REAL M01 embedder), group split by cover_id."""
import argparse, json, os, platform, sys
import numpy as np
import pandas as pd
from . import covers, features
from ..stego_core import studio
from ..forensics_core.analyzer import load_array
from ..forensics_core.stats import sha256_hex

RATES = (0.10, 0.25, 0.50)

def group_split(cover_ids, seed, fr=(0.70, 0.15, 0.15)):
    ids = sorted(set(cover_ids))
    rng = np.random.default_rng(seed)
    rng.shuffle(ids)
    n = len(ids); a, b = int(n * fr[0]), int(n * (fr[0] + fr[1]))
    m = {}
    for i, c in enumerate(ids):
        m[c] = "train" if i < a else "val" if i < b else "test"
    return m

def build(n_per_type=75, size=128, seed=1234, out="data/dataset_v1", rates=RATES, types=covers.TYPES, keyed=False):
    os.makedirs(out, exist_ok=True)
    rows, X = [], []
    rng = np.random.default_rng(seed)
    cid = 0
    for t in types:
        for _ in range(n_per_type):
            cseed = int(rng.integers(0, 2**31 - 1))
            cover = covers.make_cover(t, cseed, size)
            cap = studio.capacity_bytes(cover)
            image_id = f"img_{cid:05d}"
            def add(label, rate, data):
                arr, _ = load_array(data)
                rows.append(dict(image_id=image_id, cover_type=t, cover_seed=cseed, label=label,
                                 payload_rate=rate, sha256=sha256_hex(data)))
                X.append(features.extract_array(arr))
            add(0, 0.0, cover)
            if keyed:
                from ..benchmark.run import embed as _emb
                for r in rates:
                    for kind in ("lsb_replace", "lsb_replace_keyed"):
                        arr0, _ = load_array(cover)
                        out_arr = _emb(arr0, r, kind, cseed + int(r * 1000))
                        rows.append(dict(image_id=image_id, cover_type=t, cover_seed=cseed, label=1, payload_rate=r, sha256=kind))
                        X.append(features.extract_array(out_arr))
                cid += 1
                continue
            for r in rates:
                payload_len = int(cap * r)
                msg = np.random.default_rng(cseed + int(r * 1000)).bytes(payload_len)
                st = studio.embed(cover, msg, "dataset-pw", with_ssim=False)
                add(1, round(st["payload_rate"], 4), st["stego_png"])
            cid += 1
    df = pd.DataFrame(rows)
    split = group_split(df.image_id.tolist(), seed)
    df["split"] = df.image_id.map(split)
    feat = pd.DataFrame(np.vstack(X), columns=features.FEATURE_NAMES)
    full = pd.concat([df, feat], axis=1)
    full.to_csv(os.path.join(out, "dataset.csv"), index=False)
    meta = dict(seed=seed, size=size, n_per_type=n_per_type, rates=list(rates), types=list(types),
                rows=len(df), numpy=np.__version__, python=platform.python_version())
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=2)
    return full

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-type", type=int, default=75)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--out", default="data/dataset_v1")
    ap.add_argument("--keyed", action="store_true")
    ap.add_argument("--types", default=",".join(covers.TYPES))
    a = ap.parse_args()
    df = build(a.n_per_type, seed=a.seed, out=a.out, keyed=a.keyed, types=tuple(a.types.split(',')))
    print(df.groupby(["split", "label"]).size())
