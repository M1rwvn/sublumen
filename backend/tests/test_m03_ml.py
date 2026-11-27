import json, os
import numpy as np, pandas as pd, pytest
from sublumen.ml_engine import dataset, train, features, covers
from sublumen.ml_engine.predict import Detector
from sublumen.stego_core import studio
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold, cross_val_score

@pytest.fixture(scope="module")
def small(tmp_path_factory):
    d = tmp_path_factory.mktemp("ds")
    df = dataset.build(n_per_type=14, seed=7, out=str(d))
    return df, str(d / "dataset.csv"), tmp_path_factory

def test_no_cover_id_shared_between_splits(small):
    df, _, _ = small
    train.assert_no_leakage(df)
    assert (df.groupby("image_id").split.nunique() == 1).all()
    assert set(df.split) == {"train", "val", "test"}

def test_leakage_guard_actually_fires(small):
    df, _, _ = small
    bad = df.copy()
    first = bad.image_id.iloc[0]
    idx = bad.index[bad.image_id == first]
    bad.loc[idx[0], "split"] = "test"; bad.loc[idx[1], "split"] = "train"
    with pytest.raises(AssertionError):
        train.assert_no_leakage(bad)

def test_dataset_is_deterministic():
    a = dataset.build(n_per_type=3, seed=5, out="/tmp/dsa")
    b = dataset.build(n_per_type=3, seed=5, out="/tmp/dsb")
    # cover rows (every 4th) are fully deterministic; stego bytes differ per run because salt/nonce are random
    assert a.sha256.tolist()[::4] == b.sha256.tolist()[::4]
    assert np.allclose(a[list(features.FEATURE_NAMES)].values[::4], b[list(features.FEATURE_NAMES)].values[::4])

def test_training_deterministic_and_registered(small, tmp_path):
    _, csv, _ = small
    m1 = train.run(csv, str(tmp_path / "m1"), seed=3)
    m2 = train.run(csv, str(tmp_path / "m2"), seed=3)
    assert m1["test"] == m2["test"]
    assert m1["seed"] == 3 and m1["features"] and "trained_at" in m1
    assert os.path.exists(tmp_path / "m1" / "model_v1.joblib")

def test_shuffled_labels_collapse_to_chance(small):
    df, _, _ = small
    dev = df[df.split != "test"]
    X, g = dev[list(features.FEATURE_NAMES)].values, dev.image_id.values
    y = np.random.default_rng(0).permutation(dev.label.values)
    acc = cross_val_score(RandomForestClassifier(100, random_state=0), X, y, groups=g, cv=GroupKFold(4)).mean()
    base = max(y.mean(), 1 - y.mean())
    assert acc < base + 0.08   # no better than majority guess => pipeline is not leaking labels

def test_serving_matches_training_features(small):
    df, _, _ = small
    cover = covers.make_cover("graphic", 99)
    assert np.allclose(features.extract_bytes(cover), features.extract_bytes(cover))

def test_detector_predicts(small, tmp_path):
    _, csv, _ = small
    train.run(csv, str(tmp_path), seed=1)
    det = Detector(str(tmp_path / "model_v1.joblib"))
    cover = covers.make_cover("photo_like", 123)
    st = studio.embed(cover, os.urandom(studio.capacity_bytes(cover) // 2), "pw", with_ssim=False)["stego_png"]
    assert det.predict(st)["score"] > det.predict(cover)["score"]
    assert det.predict(cover)["model"] == "model_v1"
