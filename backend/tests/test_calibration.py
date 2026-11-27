import json, os, pytest
CSV = "data/dataset_v2/dataset.csv"
pytestmark = pytest.mark.skipif(not os.path.exists(CSV), reason="dataset_v2 not built")

def test_calibration_reduces_svm_ece_and_brier(tmp_path):
    from sublumen.ml_engine import calibrate
    m = calibrate.run(CSV, str(tmp_path))
    s = m["test"]["svm_rbf"]
    assert s["ece_calibrated"] < s["ece_raw"] and s["brier_calibrated"] < s["brier_raw"]
    assert sum(b["n"] for b in s["reliability_calibrated"]) == 630
    from sublumen.ml_engine.predict import Detector
    d = Detector(str(tmp_path / "model_v3_svm_rbf.joblib"))
    from sublumen.ml_engine import covers
    r = d.predict(covers.make_cover("photo_like", 3))
    assert 0 <= r["score"] <= 1 and "prevalence" in r["note"]
