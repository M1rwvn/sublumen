"""ADVANCED: light neural net (sklearn MLP) and a soft-voting ensemble (RF + SVM + MLP). Not a CNN: no torch in this build."""
import argparse
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from . import train
from .features import POSITION_FREE

def cands(seed):
    rf = RandomForestClassifier(n_estimators=300, random_state=seed, class_weight="balanced", n_jobs=-1)
    svm = SVC(C=3.0, kernel="rbf", class_weight="balanced", probability=True, random_state=seed)
    mlp = MLPClassifier(hidden_layer_sizes=(64, 32), early_stopping=True, max_iter=500, random_state=seed)
    return {
        "mlp": make_pipeline(StandardScaler(), mlp),
        "ensemble_soft": make_pipeline(StandardScaler(), VotingClassifier([("rf", rf), ("svm", svm), ("mlp", mlp)], voting="soft")),
    }

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--dataset", default="data/dataset_v2/dataset.csv")
    ap.add_argument("--models-dir", default="models"); ap.add_argument("--name", default="model_v4")
    a = ap.parse_args()
    m = train.run(a.dataset, a.models_dir, 42, a.name, POSITION_FREE, cands)
    print(m["selected"], m["cv"])
    for k, v in m["test"].items():
        print(k, {x: (round(y, 4) if isinstance(y, float) else y) for x, y in v.items() if x not in ("errors", "recall_by_cover_type", "fpr_by_cover_type")})
