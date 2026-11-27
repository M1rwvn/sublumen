import os, pytest
CSV = "data/dataset_v2/dataset.csv"
pytestmark = pytest.mark.skipif(not os.path.exists(CSV), reason="dataset_v2 not built")

def test_ensemble_trains_and_predicts(tmp_path):
    from sublumen.ml_engine import ensemble, train, covers
    from sublumen.ml_engine.features import POSITION_FREE
    from sublumen.ml_engine.predict import Detector
    m = train.run(CSV, str(tmp_path), 42, "model_v4", POSITION_FREE, ensemble.cands)
    assert set(m["test"]) == {"mlp", "ensemble_soft"}
    d = Detector(str(tmp_path / "model_v4_ensemble_soft.joblib"))
    assert 0 <= d.predict(covers.make_cover("graphic", 4))["score"] <= 1
