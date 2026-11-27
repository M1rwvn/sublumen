"""model_v6 experiments on dataset_v4 (source-photo-disjoint test split). Threshold is chosen on VAL only (target FPR on val covers),
then everything is scored once on TEST. Prints / saves per-embedder recall and FPR on PNG and JPEG-recompressed covers."""
import json, sys, time, joblib, numpy as np, pandas as pd, sklearn
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from .features import POSITION_FREE
from .spam import NAMES as SPAM

def fit(df, cols, C=3.0, gamma="scale"):
    return make_pipeline(StandardScaler(), SVC(C=C, kernel="rbf", gamma=gamma, class_weight="balanced")).fit(df[cols].values, df.label.values)

def pick_threshold(m, val, cols, target_fpr):
    s = m.decision_function(val[cols].values); c = np.sort(s[(val.label == 0) & (val.variant == "png")])
    return float(np.quantile(c, 1 - target_fpr))

def evaluate(m, test, cols, thr):
    s = m.decision_function(test[cols].values); t = test.assign(pred=(s >= thr).astype(int))
    out = {"fpr_png_all": float(t[(t.label == 0) & (t.variant == "png")].pred.mean()),
           "fpr_png_imagenette": float(t[(t.label == 0) & (t.variant == "png") & (t.cover_type == "imagenette")].pred.mean()),
           "fpr_jpeg95_covers": float(t[(t.label == 0) & (t.variant == "jpeg95")].pred.mean()),
           "n_test_covers": int(t[(t.label == 0) & (t.variant == "png")].shape[0]),
           "n_test_imagenette_covers": int(t[(t.label == 0) & (t.variant == "png") & (t.cover_type == "imagenette")].shape[0]), "recall": {}}
    for (e, v, r), g in t[t.label == 1].groupby(["embedder", "variant", "payload_rate"]):
        out["recall"][f"{e}|{v}|{r}"] = float(g.pred.mean())
    return out

def main(name, cols, include_jpeg, target_fpr, C, df):
    tr = df[df.split == "train"]
    if not include_jpeg: tr = tr[tr.variant == "png"]
    val, test = df[df.split == "val"], df[df.split == "test"]
    t0 = time.time(); m = fit(tr, cols, C)
    thr = pick_threshold(m, val, cols, target_fpr)
    res = evaluate(m, test, cols, thr); res.update(name=name, threshold=thr, target_val_fpr=target_fpr, C=C, n_features=len(cols), jpeg_in_training=include_jpeg, fit_s=round(time.time() - t0, 1))
    return m, res

if __name__ == "__main__":
    df = pd.read_csv("data/dataset_v4/dataset.csv")
    which = sys.argv[1]
    PF, PS = list(POSITION_FREE), list(POSITION_FREE) + SPAM
    cfg = {"pf_png": (PF, False), "pf_all": (PF, True), "spam_png": (PS, False), "spam_all": (PS, True)}[which]
    m, res = main(which, cfg[0], cfg[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.05, 3.0, df)
    joblib.dump(dict(model=m, features=cfg[0], threshold=res["threshold"], meta=res), f"/tmp/exp_{which}.joblib")
    json.dump(res, open(f"/tmp/exp_{which}.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "recall"}))
    for k, v in sorted(res["recall"].items()): print(" ", k, round(v, 3))
