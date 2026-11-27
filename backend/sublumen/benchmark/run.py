"""M07 Attack & Defense benchmark. Fixed seeds, recorded versions, held-out covers only.
Same command + same seed => same numbers (payload bits come from a seeded RNG, not random salts)."""
import argparse, io, json, os, platform
import joblib, numpy as np, pandas as pd, sklearn
from PIL import Image
from ..ml_engine import covers, features
from ..stego_core import lsb, lsb_matching
from ..forensics_core.analyzer import load_array
from ..forensics_core import stats

EMBEDDERS = ("lsb_replace", "lsb_replace_keyed", "lsb_matching")
CHI_P, RS_T = 0.9, 0.1   # fixed a priori, never tuned on test

def png(arr):
    b = io.BytesIO(); Image.fromarray(arr, "RGB").save(b, "PNG"); return b.getvalue()

def embed(arr, rate, kind, seed):
    rng = np.random.default_rng(seed)
    n = int(arr.size * rate)
    bits = rng.integers(0, 2, n, dtype=np.uint8)
    if kind == "lsb_replace":
        out = arr.reshape(-1).copy(); out[:n] = (out[:n] & 0xFE) | bits; return out.reshape(arr.shape)
    if kind == "lsb_replace_keyed":
        out = arr.reshape(-1).copy(); pos = rng.permutation(out.size)[:n]
        out[pos] = (out[pos] & 0xFE) | bits; return out.reshape(arr.shape)
    return lsb_matching.embed_matching(arr, bits, rng)

def detectors(models_dir, name):
    ds = {}
    for algo in ("random_forest", "svm_rbf"):
        d = joblib.load(os.path.join(models_dir, f"{name}_{algo}.joblib"))
        idx = [features.FEATURE_NAMES.index(n) for n in d["features"]]
        ds[algo] = (lambda X, m=d["model"], idx=idx: m.predict(X[:, idx]))
    names = list(features.FEATURE_NAMES)
    ds["chi_square_rule"] = lambda X: (X[:, [names.index(f"chi_p_{p}") for p in ("10", "25", "50", "100")]].max(axis=1) >= CHI_P).astype(int)
    ds["rs_rule"] = lambda X: (X[:, names.index("rs_mean")] >= RS_T).astype(int)
    return ds

def cm(y, p):
    y, p = np.array(y), np.array(p)
    tp, fn = int(((y == 1) & (p == 1)).sum()), int(((y == 1) & (p == 0)).sum())
    fp, tn = int(((y == 0) & (p == 1)).sum()), int(((y == 0) & (p == 0)).sum())
    f = lambda a, b: a / b if b else 0.0
    prec, rec = f(tp, tp + fp), f(tp, tp + fn)
    return dict(tp=tp, fn=fn, fp=fp, tn=tn, recall=rec, fpr=f(fp, fp + tn), precision=prec,
                f1=f(2 * prec * rec, prec + rec), accuracy=f(tp + tn, tp + tn + fp + fn))

def run(dataset_csv, models_dir, model_name="model_v1", seed=2026, rates=(0.05, 0.10, 0.25, 0.50, 1.0), max_covers_per_type=None):
    df = pd.read_csv(dataset_csv)
    held = df[(df.split == "test") & (df.label == 0)]            # HELD-OUT covers only
    if max_covers_per_type:
        held = held.groupby("cover_type", group_keys=False).head(max_covers_per_type)
    ds = detectors(models_dir, model_name)
    rows, cache = [], {}
    def feats(arr):
        return features.extract_array(arr)
    items = []
    for i, r in enumerate(held.itertuples()):
        arr, _ = load_array(covers.make_cover(r.cover_type, int(r.cover_seed)))
        items.append((r.image_id, r.cover_type, arr, feats(arr)))
    out = {"detectors": {}, "grid": {}, "fpr_by_cover_type": {}}
    results = {d: {e: {"y": [], "p": [], "type": [], "rate": []} for e in EMBEDDERS} for d in ds}
    covers_pred = {d: {"y": [], "p": [], "type": []} for d in ds}
    X0 = np.vstack([it[3] for it in items])
    for d, f in ds.items():
        p0 = f(X0)
        covers_pred[d] = {"y": [0] * len(items), "p": list(map(int, p0)), "type": [it[1] for it in items]}
    for e in EMBEDDERS:
        for rate in rates:
            Xs = np.vstack([feats(embed(it[2], rate, e, seed + 1000 * k + int(rate * 100))) for k, it in enumerate(items)])
            for d, f in ds.items():
                p = f(Xs)
                results[d][e]["y"] += [1] * len(items); results[d][e]["p"] += list(map(int, p))
                results[d][e]["type"] += [it[1] for it in items]; results[d][e]["rate"] += [rate] * len(items)
    for d in ds:
        out["fpr_by_cover_type"][d] = {t: float(np.mean([p for p, ty in zip(covers_pred[d]["p"], covers_pred[d]["type"]) if ty == t]))
                                        for t in sorted(set(covers_pred[d]["type"]))}
        out["detectors"][d] = {}
        for e in EMBEDDERS:
            y = covers_pred[d]["y"] + results[d][e]["y"]; p = covers_pred[d]["p"] + results[d][e]["p"]
            out["detectors"][d][e] = cm(y, p)
            grid = {}
            for t in sorted(set(results[d][e]["type"])):
                for rate in rates:
                    sel = [pp for pp, ty, rr in zip(results[d][e]["p"], results[d][e]["type"], results[d][e]["rate"]) if ty == t and rr == rate]
                    grid[f"{t}@{rate}"] = float(np.mean(sel))
            out["grid"].setdefault(d, {})[e] = grid
    # robustness: replace-embedded 50% stego after JPEG q95 recompression / 90% resize, RF only
    rob = {}
    for label, tf in (("none", lambda im: im), ("jpeg_q95", None), ("resize_90", None)):
        Xr = []
        for k, it in enumerate(items):
            st = embed(it[2], 0.5, "lsb_replace", seed + 7 * k)
            im = Image.fromarray(st, "RGB")
            if label == "jpeg_q95":
                b = io.BytesIO(); im.save(b, "JPEG", quality=95); im = Image.open(io.BytesIO(b.getvalue())).convert("RGB")
            elif label == "resize_90":
                im = im.resize((int(im.width * .9), int(im.height * .9)), Image.BICUBIC)
            Xr.append(feats(np.array(im, dtype=np.uint8)))
        rob[label] = {d: float(ds[d](np.vstack(Xr)).mean()) for d in ("random_forest", "svm_rbf", "chi_square_rule", "rs_rule")}
    out["robustness_recall_at_50pct_replace"] = rob
    out["meta"] = dict(seed=seed, rates=list(rates), n_covers=len(items), covers_per_type={t: sum(1 for it in items if it[1] == t) for t in sorted(set(it[1] for it in items))},
                       model=model_name, thresholds=dict(chi_p=CHI_P, rs=RS_T), numpy=np.__version__, sklearn=sklearn.__version__,
                       python=platform.python_version(),
                       notes=["Held-out test-split covers only; models never saw them.", "lsb_matching and lsb_replace_keyed (keyed order over the whole image) are NOT in the training data: out-of-distribution tests.",
                              "Cover set: see covers_per_type (synthetic, 2-photo crops, and Imagenette real JPEG-derived photos if present); not BOSSBase.", "Payload bits are seeded random (equivalent to ciphertext)."])
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/dataset_v1/dataset.csv"); ap.add_argument("--models-dir", default="models")
    ap.add_argument("--seed", type=int, default=2026); ap.add_argument("--out", default="../docs/benchmark_v1.json")
    ap.add_argument("--max-covers-per-type", type=int, default=None)
    ap.add_argument("--model", default="model_v1")
    a = ap.parse_args()
    res = run(a.dataset, a.models_dir, model_name=a.model, seed=a.seed, max_covers_per_type=a.max_covers_per_type)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(res, open(a.out, "w"), indent=1, sort_keys=True)
    print(json.dumps(res["detectors"], indent=1)[:3000]); print(json.dumps(res["robustness_recall_at_50pct_replace"], indent=1))
