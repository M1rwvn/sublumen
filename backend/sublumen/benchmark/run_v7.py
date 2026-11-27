"""Benchmark for model_v6 on the source-photo-disjoint TEST split of dataset_v4, with cluster-bootstrap 95% CIs
(resampling covers: a cover and all its stego/recompressed variants move together). Same data, same seed => same numbers.
Baselines (chi-square rule, RS rule) use the fixed a-priori thresholds from run.py. v5 SVM is scored on the same rows."""
import argparse, json, os, platform
import joblib, numpy as np, pandas as pd, sklearn
from ..ml_engine import features
from ..ml_engine.spam import NAMES as SPAM
from .run import CHI_P, RS_T

def load(models_dir, name):
    d = joblib.load(os.path.join(models_dir, f"{name}.joblib"))
    cols = list(d["features"]); thr = float(d.get("threshold", 0.0)); m = d["model"]
    return lambda df: (m.decision_function(df[cols].values) >= thr).astype(int) if thr != 0.0 else m.predict(df[cols].values).astype(int)

def rules(df):
    return {"chi_square_rule": (df[[f"chi_p_{p}" for p in ("10", "25", "50", "100")]].max(axis=1) >= CHI_P).astype(int).values,
            "rs_rule": (df["rs_mean"] >= RS_T).astype(int).values}

def boot(ids, pred, mask, B, rng):
    """Cluster bootstrap of mean(pred[mask]) over covers."""
    u = np.unique(ids); idx = {c: np.where(mask & (ids == c))[0] for c in u}
    s = np.array([pred[idx[c]].sum() for c in u], float); n = np.array([len(idx[c]) for c in u], float)
    keep = n > 0; s, n = s[keep], n[keep]
    pt = s.sum() / n.sum(); r = rng.integers(0, len(s), (B, len(s)))
    bs = s[r].sum(1) / n[r].sum(1)
    return float(pt), [float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], int(n.sum())

def run(dataset, models_dir, models, seed=2026, B=2000):
    """dataset: one csv path, or a list of (label, path); with a list the rows are pooled but every measure is reported per set."""
    sets = [("", dataset)] if isinstance(dataset, str) else dataset
    parts = []
    for lab_, path in sets:
        d_ = pd.read_csv(path); d_ = d_[d_.split == "test"].copy(); d_["set"] = lab_; d_["image_id"] = lab_ + d_.image_id; parts.append(d_)
    df = pd.concat(parts, ignore_index=True)
    rng = np.random.default_rng(seed); ids = df.image_id.values
    preds = {m: load(models_dir, m)(df) for m in models}; preds.update(rules(df))
    out = {"detectors": {}, "meta": dict(seed=seed, bootstrap=B, n_test_covers=int(df[(df.label == 0) & (df.variant == "png")].shape[0]), rows=len(df),
           models=models, thresholds=dict(chi_p=CHI_P, rs=RS_T), sklearn=sklearn.__version__, numpy=np.__version__, python=platform.python_version(),
           notes=["Test split uses source photos never used for train/val (v6). v5/v2 may have seen some of these photos in dataset_v3 (favours them).",
                  "CIs: cluster bootstrap over covers, 2.5-97.5 percentiles. Single split, no cross-validation.",
                  "Imagenette 160px crops, JPEG-derived ImageNet photos; not BOSSBase, not camera RAW. Payload bits seeded random."])}
    for d, p in preds.items():
        r = {}
        for sl in sorted(df.set.unique()):
            S = (df.set == sl).values; pre = (sl + ":") if sl else ""
            cov = (df.label == 0) & (df.variant == "png"); cj = (df.label == 0) & (df.variant == "jpeg95"); im = cov & (df.cover_type == "imagenette")
            for k, mk in ((pre + "fpr_png_all", cov), (pre + "fpr_png_real_photos", im), (pre + "fpr_jpeg95_covers", cj)):
                v, ci, n = boot(ids, p, mk.values & S, B, rng); r[k] = dict(value=v, ci95=ci, n=n)
            for (e, var, rate) in sorted(set(map(tuple, df[(df.label == 1) & S][["embedder", "variant", "payload_rate"]].values.tolist()))):
                mk = ((df.embedder == e) & (df.variant == var) & (df.payload_rate == rate) & (df.label == 1)).values & S
                v, ci, n = boot(ids, p, mk, B, rng); r[f"{pre}recall|{e}|{var}|{rate}"] = dict(value=v, ci95=ci, n=n)
        out["detectors"][d] = r
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--dataset", default="data/dataset_v4/dataset.csv"); ap.add_argument("--models-dir", default="models")
    ap.add_argument("--out", default="../docs/benchmark_v7.json"); a = ap.parse_args()
    res = run([("imagenette160", a.dataset), ("fullsize", "data/dataset_v5full/dataset.csv")], a.models_dir, ["model_v7_svm_rbf", "model_v6_svm_rbf", "model_v5_svm_rbf"])
    res["meta"]["notes"] = ["Two held-out sets, source photos never used for train/val: imagenette160 (128px crops of 160px Imagenette + synthetic covers) and fullsize (128px crops of full-size decoded Imagenette JPEGs, real photos only).",
        "v5 and v6 never saw full-size crops in training; v7 did (train split only). v5/v2 may have seen some imagenette160 test photos in dataset_v3 (favours them).",
        "CIs: cluster bootstrap over covers, 2.5-97.5 percentiles. Single split, no cross-validation. Not BOSSBase, not camera RAW. Payload bits seeded random."]
    json.dump(res, open(a.out, "w"), indent=1, sort_keys=True)
    for d, r in res["detectors"].items():
        print(d)
        for k, v in sorted(r.items()): print("  %-40s %.3f [%.3f, %.3f] n=%d" % (k, v["value"], v["ci95"][0], v["ci95"][1], v["n"]))
