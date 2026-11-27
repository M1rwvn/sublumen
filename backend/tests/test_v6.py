import os, numpy as np, pytest
from sublumen.ml_engine.spam import spam_features, NAMES
from sublumen.ml_engine.predict import Detector
from sublumen.stego_core import lsb_matching
from conftest import make_png

def test_spam_features_shape_and_normalised():
    a = np.random.default_rng(0).integers(0, 256, (64, 64, 3), dtype=np.uint8)
    f = spam_features(a); assert f.shape == (len(NAMES),) == (125,) and abs(f.sum() - 1) < 1e-9 and (f >= 0).all()

def test_spam_sees_lsb_matching_noise():
    rng = np.random.default_rng(1)
    base = np.clip(np.cumsum(np.cumsum(rng.normal(0, 1, (96, 96, 3)), 0), 1) * 0.5 + 128, 0, 255).astype(np.uint8)  # smooth cover
    st = lsb_matching.embed_matching(base, rng.integers(0, 2, base.size // 2, dtype=np.uint8), rng)
    assert np.abs(spam_features(base) - spam_features(st)).sum() > 0.01

M = os.path.join(os.path.dirname(__file__), "..", "models", "model_v6_svm_rbf.joblib")
@pytest.mark.skipif(not os.path.exists(M), reason="model_v6 not present")
def test_v6_detector_runs_with_threshold_and_spam_features():
    d = Detector(M)
    assert d.threshold != 0.0 and any(n.startswith("spam_") for n in d.features)
    r = d.predict(make_png(96, 96, seed=4))
    assert 0.0 <= r["score"] <= 1.0 and r["level"] in ("low", "medium", "high")
