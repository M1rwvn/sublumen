"""Candidate training/selection helpers for the improvement loop. Selection uses VAL only; scores for ALL rows (incl. locked test) are saved to
data/pool/scores_<name>.npy but never printed here: the locked test is read only through lockeval.locked_report (which logs)."""
import json, time, numpy as np, pandas as pd, joblib
from sklearn.metrics import roc_auc_score
from .pool import ROOT
def data():
    meta = pd.read_pickle(f"{ROOT}/meta.pkl"); X = np.load(f"{ROOT}/X_v7srm.npy", mmap_mode="r"); names = json.load(open(f"{ROOT}/names_v7srm.json")); return meta, X, names
def colset(names, which):
    if which == "v7": return np.arange(137)
    if which == "srm": return np.arange(137, len(names))
    if which.startswith("sel_"): return np.array(json.load(open(f"{ROOT}/{which}.json")))
    if which == "all": return np.arange(len(names))
    raise KeyError(which)
def val_summary(meta, score):
    v = (meta.split == "val").values; m = meta[v].assign(s=score[v]); png = m[m.variant == "png"]
    thr = float(np.quantile(png[png.label == 0].s, 0.95)); out = {"val_auc_png": round(float(roc_auc_score(png.label, png.s)), 4), "thr": thr}
    for e, r in (("lsb_replace", .1), ("lsb_matching", .1), ("lsb_matching", .25), ("lsb_matching", .5), ("adaptive_matching", .25), ("adaptive_matching", .5)):
        g = png[(png.embedder == e) & (png.payload_rate == r)]; out[f"{e}{r}"] = round(float((g.s >= thr).mean()), 3)
    jc = m[(m.label == 0) & (m.variant == "jpeg95")]; out["jpeg_clean_fpr"] = round(float((jc.s >= thr).mean()), 3)
    js = m[(m.label == 1) & (m.variant == "jpeg95")]; out["jpeg_stego_recall"] = round(float((js.s >= thr).mean()), 3)
    return out
def save_scores(name, score): np.save(f"{ROOT}/scores_{name}.npy", score.astype(np.float32))
