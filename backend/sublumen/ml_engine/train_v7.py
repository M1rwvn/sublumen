"""model_v7: same features and SVM as v6, trained on dataset_v4 (Imagenette 160px crops + synthetic) PLUS dataset_v5full
(128px crops of full-size decoded Imagenette JPEG photos, 2400 covers, source photos disjoint across train/val/test).
Threshold = 95th percentile of clean-PNG validation scores over BOTH datasets (target 5% false alarms). Test metrics: both test splits pooled.
Run from backend/: python -m sublumen.ml_engine.train_v7  (needs data/dataset_v4 and data/dataset_v5full, see dataset_v4.build)."""
import json, datetime, platform, joblib, numpy as np, pandas as pd, sklearn
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from .features import POSITION_FREE
from .spam import NAMES

def main(models_dir="models"):
    cols = list(POSITION_FREE) + NAMES
    a = pd.read_csv("data/dataset_v4/dataset.csv"); b = pd.read_csv("data/dataset_v5full/dataset.csv"); a["src"] = "v4"; b["src"] = "full"
    al = pd.concat([a, b], ignore_index=True)
    tr, va, te = (al[al.split == s] for s in ("train", "val", "test"))
    m = make_pipeline(StandardScaler(), SVC(C=3.0, kernel="rbf", gamma="scale", class_weight="balanced")).fit(tr[cols].values, tr.label.values)
    sv = m.decision_function(va[cols].values); thr = float(np.quantile(sv[((va.label == 0) & (va.variant == "png")).values], 0.95))
    d = te.assign(p=(m.decision_function(te[cols].values) >= thr).astype(int)); y, p = d.label.values, d.p.values
    tp, fn, fp, tn = int(((y == 1) & (p == 1)).sum()), int(((y == 1) & (p == 0)).sum()), int(((y == 0) & (p == 1)).sum()), int(((y == 0) & (p == 0)).sum())
    cov = d[(d.label == 0) & (d.variant == "png")]
    test = dict(n=len(d), accuracy=(tp + tn) / len(d), precision=tp / max(tp + fp, 1), recall=tp / (tp + fn), f1=2 * tp / (2 * tp + fp + fn), fpr=fp / (fp + tn), tn=tn, fp=fp, fn=fn, tp=tp,
                fpr_png_covers=float(cov.p.mean()), fpr_png_covers_v4_imagenette160=float(cov[(cov.src == "v4") & (cov.cover_type == "imagenette")].p.mean()),
                fpr_png_covers_fullsize_crops=float(cov[cov.src == "full"].p.mean()), n_test_png_covers=int(len(cov)),
                fpr_jpeg95_covers=float(d[(d.label == 0) & (d.variant == "jpeg95")].p.mean()), by_embedder_and_variant={})
    for (e, v, r, s), g in d[d.label == 1].groupby(["embedder", "variant", "payload_rate", "src"]): test["by_embedder_and_variant"][f"{e}|{v}|{r}|{s}"] = float(g.p.mean())
    meta = dict(name="model_v7", selected="svm_rbf", trained_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), seed=0, features=cols,
                dataset="data/dataset_v4 + data/dataset_v5full", cv={"svm_rbf": {"note": "no CV; source-photo-disjoint train/val/test; threshold chosen on val"}}, test={"svm_rbf": test}, threshold=thr,
                versions=dict(python=platform.python_version(), sklearn=sklearn.__version__, numpy=np.__version__),
                limitations=["Same features as v6; trained on Imagenette 160px crops, 128px crops of full-size decoded Imagenette JPEGs, and synthetic covers.",
                             "Recompressed (JPEG q95) stego is mostly missed (recall below v6), but false alarms on recompressed clean covers are lower.",
                             "Still not validated on BOSSBase or camera RAW; one photo family. Single split, no cross-validation."])
    joblib.dump(dict(model=m, features=cols, threshold=thr, meta=meta, algo="svm_rbf"), f"{models_dir}/model_v7_svm_rbf.joblib")
    json.dump(meta, open(f"{models_dir}/model_v7.metrics.json", "w"), indent=2)
    print(json.dumps({k: v for k, v in test.items() if k != "by_embedder_and_variant"}, indent=1))
if __name__ == "__main__": main()
