"""Export the selected improvement-loop candidate as a registered model (model_v8). Selection and threshold use TRAIN/VAL only.
Usage (backend/): python -m sublumen.ml_engine.export_v8  (needs data/pool + the fitted candidate from the loop; see docs/REPRODUCE.md)."""
import json, datetime, platform, joblib, numpy as np, sklearn
from .loop import data, colset, ROOT
from .lockeval import val_threshold

def main(models_dir=None, cand="hgb_sel_v7_srm700_lr0.1", locked_json="../docs/locked_eval_v8.json"):
    import os; models_dir = models_dir or os.environ.get("SS_MODELS_OUT", "models")
    meta, X, names = data(); cols = colset(names, "sel_v7_srm700"); fnames = [names[i] for i in cols]
    m = joblib.load(f"{ROOT}/model_{cand}.joblib"); s = np.load(f"{ROOT}/scores_{cand}.npy"); thr = val_threshold(meta, s)
    locked = json.load(open(locked_json)) if locked_json and __import__("os").path.exists(locked_json) else None
    v = meta[meta.split == "val"]; sv = s[(meta.split == "val").values]; vm = v.assign(p=(sv >= thr).astype(int))
    test = dict(n=int(len(vm)), split="validation (locked test results: docs/locked_eval_v8.json)", fpr=float(vm[(vm.label == 0) & (vm.variant == "png")].p.mean()), recall=float(vm[vm.label == 1].p.mean()),
                accuracy=float((vm.p == vm.label).mean()), precision=float(vm[vm.p == 1].label.mean()), f1=0.0)
    p, r = test["precision"], test["recall"]; test["f1"] = 2 * p * r / max(p + r, 1e-9)
    meta_out = dict(name="model_v8", selected="hgb", trained_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), seed=0, features=fnames, dataset="data/pool (train split)",
                    cv={"hgb": {"note": "no CV; photo-disjoint train/val; locked test = unseen photos and two unseen families"}}, test={"hgb": test}, threshold=thr,
                    versions=dict(python=platform.python_version(), sklearn=sklearn.__version__, numpy=np.__version__), locked=locked,
                    limitations=["Gradient boosting on 137 LSB/SPAM statistics + 700 SRM-lite residual co-occurrence features (selected by a train-only univariate score).",
                                 "Trained and tested on 128x128 crops with synthetic random-payload LSB embedders (replace, keyed, +-1 matching, texture-adaptive +-1); not validated against third-party stego tools or camera RAW.",
                                 "JPEG-recompressed stego is mostly missed (the hidden bits are destroyed or masked)."])
    joblib.dump(dict(model=m, features=fnames, threshold=thr, meta=meta_out, algo="hgb"), f"{models_dir}/model_v8_hgb.joblib")
    json.dump(meta_out, open(f"{models_dir}/model_v8.metrics.json", "w"), indent=1); print("exported, val threshold", thr, test)
if __name__ == "__main__": main()
