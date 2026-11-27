"""Train RF + SVM with GroupKFold on train+val, pick by CV F1, evaluate on TEST exactly once, register model."""
import argparse, datetime, json, os, platform
import joblib, numpy as np, pandas as pd, sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, accuracy_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from .features import FEATURE_NAMES, V1_NAMES, POSITION_FREE

def assert_no_leakage(df):
    sp = df.groupby("image_id")["split"].nunique()
    if (sp > 1).any():
        raise AssertionError("LEAKAGE: a cover_id appears in more than one split")

def metrics(y, p):
    tn, fp, fn, tp = confusion_matrix(y, p, labels=[0, 1]).ravel()
    return dict(n=int(len(y)), accuracy=float(accuracy_score(y, p)), precision=float(precision_score(y, p, zero_division=0)),
                recall=float(recall_score(y, p, zero_division=0)), f1=float(f1_score(y, p, zero_division=0)),
                fpr=float(fp / max(1, fp + tn)), tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp))

def candidates(seed):
    return {
        "random_forest": make_pipeline(StandardScaler(), RandomForestClassifier(n_estimators=300, random_state=seed, class_weight="balanced", n_jobs=-1)),
        "svm_rbf": make_pipeline(StandardScaler(), SVC(C=3.0, kernel="rbf", class_weight="balanced", random_state=seed)),
    }

def run(dataset_csv, models_dir, seed=42, name="model_v1", feature_names=None, cands=None):
    cands = cands or candidates
    FEATURE_NAMES = list(feature_names or V1_NAMES)
    df = pd.read_csv(dataset_csv)
    assert_no_leakage(df)
    dev = df[df.split.isin(["train", "val"])].reset_index(drop=True)
    test = df[df.split == "test"].reset_index(drop=True)
    Xd, yd, gd = dev[list(FEATURE_NAMES)].values, dev.label.values, dev.image_id.values
    cv_report, cv = {}, GroupKFold(n_splits=5)
    for mname, pipe in cands(seed).items():
        f1s, fprs = [], []
        for tr, va in cv.split(Xd, yd, gd):
            assert not (set(gd[tr]) & set(gd[va]))
            from sklearn.base import clone
            m = clone(pipe).fit(Xd[tr], yd[tr]); pr = m.predict(Xd[va]); mm = metrics(yd[va], pr)
            f1s.append(mm["f1"]); fprs.append(mm["fpr"])
        cv_report[mname] = dict(cv_f1_mean=float(np.mean(f1s)), cv_f1_std=float(np.std(f1s)), cv_fpr_mean=float(np.mean(fprs)))
    out_models = {}
    best = max(cv_report, key=lambda k: cv_report[k]["cv_f1_mean"])
    # TEST SET USED ONCE: every candidate is refit on train+val and scored a single time.
    all_test = {}
    for mname, pipe in cands(seed).items():
        m = pipe.fit(Xd, yd)
        p = m.predict(test[list(FEATURE_NAMES)].values)
        res = metrics(test.label.values, p)
        t2 = test.assign(pred=p)
        res["recall_by_payload_rate"] = {str(r): float(g.pred.mean()) for r, g in t2[t2.label == 1].groupby("payload_rate")}
        res["recall_by_cover_type"] = {str(c): float(g.pred.mean()) for c, g in t2[t2.label == 1].groupby("cover_type")}
        res["fpr_by_cover_type"] = {str(c): float(g.pred.mean()) for c, g in t2[t2.label == 0].groupby("cover_type")}
        res["errors"] = t2[t2.pred != t2.label][["image_id", "cover_type", "label", "payload_rate"]].to_dict("records")
        all_test[mname] = res
        out_models[mname] = m
    os.makedirs(models_dir, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    meta = dict(name=name, selected=best, trained_at=stamp, seed=seed, features=list(FEATURE_NAMES),
                dataset=dataset_csv, dataset_rows=len(df), train_rows=len(dev), test_rows=len(test),
                split_by="image_id (GroupKFold CV; group split 70/15/15)", cv=cv_report, test=all_test,
                versions=dict(python=platform.python_version(), sklearn=sklearn.__version__, numpy=np.__version__),
                limitations=["Trained on sequential LSB replacement only.", "Cover images are mostly synthetic + 2 real photos (see covers.py).",
                             "Not validated on BOSSBase or any external dataset."])
    for mname, m in out_models.items():
        joblib.dump(dict(model=m, features=list(FEATURE_NAMES), meta=meta, algo=mname), os.path.join(models_dir, f"{name}_{mname}.joblib"))
    joblib.dump(dict(model=out_models[best], features=list(FEATURE_NAMES), meta=meta, algo=best), os.path.join(models_dir, f"{name}.joblib"))
    json.dump(meta, open(os.path.join(models_dir, f"{name}.metrics.json"), "w"), indent=2)
    return meta

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/dataset_v1/dataset.csv")
    ap.add_argument("--models-dir", default="models")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--name", default="model_v1")
    ap.add_argument("--position-free", action="store_true")
    a = ap.parse_args()
    m = run(a.dataset, a.models_dir, a.seed, a.name, POSITION_FREE if a.position_free else None)
    print("selected:", m["selected"]); print(json.dumps(m["cv"], indent=1))
    for k, v in m["test"].items():
        print(k, {x: (round(y, 4) if isinstance(y, float) else y) for x, y in v.items() if x not in ("errors",)})
