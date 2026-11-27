"""End-to-end reproduction of the model_v8 pipeline (covers -> features -> selection -> training -> locked test -> export).
Run from backend/:  SS_PHOTOS=/path/to/photos [SS_SMOKE=1] [SS_POOL=dir] python -m sublumen.ml_engine.repro all
SS_SMOKE=1 uses a tiny subset: it only proves the pipeline runs end to end, its numbers mean nothing.
Stages: covers, features, assemble, select, train, locked, export (or 'all'). Photos layout: see docs/REPRODUCE.md."""
import os, sys, json, time, numpy as np, joblib
from . import pool
from .pool import ROOT, SMOKE

NSHARDS = 4 if SMOKE else 60
def stage_covers(): pool.build_covers()
def stage_features():
    for e in ("v7", "srmx"):
        for k in range(NSHARDS): pool.featurize(e, k, NSHARDS)
def stage_assemble():
    meta, X, names = pool.load(("v7", "srmx"), NSHARDS)
    meta.to_pickle(f"{ROOT}/meta.pkl"); np.save(f"{ROOT}/X_v7srm.npy", X); json.dump(names, open(f"{ROOT}/names_v7srm.json", "w")); print("assembled", X.shape)
def stage_select(top=700):
    from .loop import data
    meta, X, names = data(); tr = ((meta.split == "train") & (meta.variant == "png")).values; y = meta.label.values[tr]; idx = np.where(tr)[0]; sc = np.zeros(X.shape[1])
    for j in range(0, X.shape[1], 300):
        B = np.asarray(X[:, j:j + 300])[idx]; a, b = B[y == 0], B[y == 1]; sc[j:j + 300] = np.abs(a.mean(0) - b.mean(0)) / np.sqrt(0.5 * (a.var(0) + b.var(0)) + 1e-12)
    order = np.argsort(-sc); sel = list(range(137)) + [int(i) for i in order if i >= 137][:top]
    json.dump(sel, open(f"{ROOT}/sel_v7_srm700.json", "w")); print("selected", len(sel), "(train rows only)")
def stage_train(iters=None, lr=0.1):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from .loop import data, colset, val_summary, save_scores
    iters = iters or (60 if SMOKE else 800); meta, X, names = data(); cols = colset(names, "sel_v7_srm700"); tr = (meta.split == "train").values
    Xt = np.asarray(X[tr][:, cols]); yt = meta.label.values[tr]; w = np.where(yt == 0, (yt == 1).sum() / (yt == 0).sum(), 1.0)
    m = HistGradientBoostingClassifier(max_iter=iters, learning_rate=lr, max_leaf_nodes=31, l2_regularization=1.0, max_features=0.3, random_state=0).fit(Xt, yt, sample_weight=w)
    name = f"hgb_sel_v7_srm700_lr{lr:g}"; joblib.dump(m, f"{ROOT}/model_{name}.joblib")
    s = np.empty(len(meta), dtype=np.float32)
    for i in range(0, len(meta), 20000): s[i:i + 20000] = m.decision_function(np.asarray(X[i:i + 20000][:, cols]))
    save_scores(name, s); print(name, val_summary(meta, s))
def stage_locked():
    from .loop import data, save_scores
    from .lockeval import val_threshold, locked_report, pretty
    meta, X, names = data(); name = "hgb_sel_v7_srm700_lr0.1"; s = np.load(f"{ROOT}/scores_{name}.npy")
    d = joblib.load("models/model_v7_svm_rbf.joblib"); v7 = np.empty(len(meta), dtype=np.float32)
    for i in range(0, len(meta), 10000): v7[i:i + 10000] = d["model"].decision_function(np.asarray(X[i:i + 10000][:, :137]))
    save_scores("v7shipped", v7); res = {}
    for n, sc in (("v7shipped", v7), (name, s)):
        r = locked_report(n, meta, sc, val_threshold(meta, sc), B=200 if SMOKE else 1000); res[n] = r; pretty(r)
    json.dump(res, open(f"{ROOT}/locked_result.json", "w"))
def stage_export():
    from .export_v8 import main
    main(locked_json=f"{ROOT}/locked_result.json")
STAGES = dict(covers=stage_covers, features=stage_features, assemble=stage_assemble, select=stage_select, train=stage_train, locked=stage_locked, export=stage_export)
if __name__ == "__main__":
    for st in (list(STAGES) if sys.argv[1] == "all" else sys.argv[1:]):
        t = time.time(); print("==", st); STAGES[st](); print("== %s done in %.0fs" % (st, time.time() - t))
