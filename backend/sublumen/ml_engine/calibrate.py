"""Probability calibration: fit on TRAIN, calibrate on VAL (sigmoid), report reliability on TEST (used once).
Outputs model_v3_<algo>.joblib + model_v3.metrics.json with ECE/Brier before and after."""
import argparse, datetime, json, os, platform
import joblib, numpy as np, pandas as pd, sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from .features import POSITION_FREE
from .train import metrics, assert_no_leakage

def reliability(y, p, bins=10):
    edges = np.linspace(0, 1, bins + 1); rows, ece = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        if sel.sum():
            conf, acc = float(p[sel].mean()), float(y[sel].mean())
            rows.append(dict(bin=f"{lo:.1f}-{hi:.1f}", n=int(sel.sum()), mean_pred=conf, frac_positive=acc))
            ece += sel.mean() * abs(conf - acc)
    return rows, float(ece)

def run(csv, models_dir, seed=42, name="model_v3"):
    df = pd.read_csv(csv); assert_no_leakage(df)
    F = list(POSITION_FREE)
    tr, va, te = (df[df.split == s] for s in ("train", "val", "test"))
    algos = {"random_forest": make_pipeline(StandardScaler(), RandomForestClassifier(n_estimators=300, random_state=seed, class_weight="balanced", n_jobs=-1)),
             "svm_rbf": make_pipeline(StandardScaler(), SVC(C=3.0, kernel="rbf", class_weight="balanced", random_state=seed))}
    meta = dict(name=name, selected="svm_rbf", trained_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), seed=seed, features=F,
                dataset=csv, method="sigmoid (Platt) calibration fit on val split; base model fit on train split only",
                cv={}, test={}, versions=dict(python=platform.python_version(), sklearn=sklearn.__version__, numpy=np.__version__),
                limitations=["Calibrated on a synthetic + 2-photo dataset: probabilities are only meaningful on similar data.",
                             "Trained on LSB replacement (sequential + keyed) only; LSB matching and JPEG are largely missed."])
    models = {}
    for a, base in algos.items():
        base.fit(tr[F].values, tr.label.values)
        # uncalibrated score for the reliability baseline
        if hasattr(base, "predict_proba"):
            raw = base.predict_proba(te[F].values)[:, 1]
        else:
            raw = 1 / (1 + np.exp(-base.decision_function(te[F].values)))
        cal = CalibratedClassifierCV(FrozenEstimator(base), method="sigmoid").fit(va[F].values, va.label.values)
        pc = cal.predict_proba(te[F].values)[:, 1]
        y = te.label.values
        rr, ece_r = reliability(y, raw); rc, ece_c = reliability(y, pc)
        res = metrics(y, (pc >= 0.5).astype(int))
        res.update(ece_raw=ece_r, ece_calibrated=ece_c, brier_raw=float(brier_score_loss(y, raw)), brier_calibrated=float(brier_score_loss(y, pc)),
                   reliability_calibrated=rc, reliability_raw=rr, errors=[])
        meta["test"][a] = res; meta["cv"][a] = dict(cv_f1_mean=None, cv_f1_std=None, cv_fpr_mean=None)
        models[a] = cal
    os.makedirs(models_dir, exist_ok=True)
    for a, m in models.items():
        joblib.dump(dict(model=m, features=F, meta=meta, algo=a), os.path.join(models_dir, f"{name}_{a}.joblib"))
    json.dump(meta, open(os.path.join(models_dir, f"{name}.metrics.json"), "w"), indent=1)
    joblib.dump(dict(model=models["svm_rbf"], features=F, meta=meta, algo="svm_rbf"), os.path.join(models_dir, f"{name}.joblib"))
    return meta

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--dataset", default="data/dataset_v2/dataset.csv"); ap.add_argument("--models-dir", default="models")
    a = ap.parse_args(); m = run(a.dataset, a.models_dir)
    for k, v in m["test"].items():
        print(k, {x: round(y, 4) for x, y in v.items() if isinstance(y, float)})
