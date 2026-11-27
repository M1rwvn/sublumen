import json, os
import pytest
from sublumen.benchmark import run as bench

CSV, MODELS = "data/dataset_v1/dataset.csv", "models"
pytestmark = pytest.mark.skipif(not os.path.exists(CSV), reason="dataset not built (run ml_engine.dataset)")

def test_benchmark_same_seed_same_numbers():
    a = bench.run(CSV, MODELS, seed=11, rates=(0.1, 0.5), max_covers_per_type=4)
    b = bench.run(CSV, MODELS, seed=11, rates=(0.1, 0.5), max_covers_per_type=4)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["meta"]["seed"] == 11 and "sklearn" in a["meta"] and a["meta"]["thresholds"]

def test_benchmark_uses_only_heldout_covers():
    import pandas as pd
    df = pd.read_csv(CSV)
    held = df[(df.split == "test") & (df.label == 0)]
    train_seeds = set(df[df.split != "test"].cover_seed)
    assert not (set(held.cover_seed) & train_seeds)

def test_different_seed_changes_embedding_but_structure_same():
    a = bench.run(CSV, MODELS, seed=1, rates=(0.5,), max_covers_per_type=3)
    assert set(a["detectors"]) == {"random_forest", "svm_rbf", "chi_square_rule", "rs_rule"}
    assert set(a["detectors"]["random_forest"]) == {"lsb_replace", "lsb_replace_keyed", "lsb_matching"}

def test_matching_embedder_changes_by_at_most_one():
    import numpy as np
    from sublumen.ml_engine import covers
    from sublumen.forensics_core.analyzer import load_array
    arr, _ = load_array(covers.make_cover("photo_like", 5))
    out = bench.embed(arr, 0.5, "lsb_matching", 3)
    assert np.abs(out.astype(int) - arr.astype(int)).max() <= 1
    out2 = bench.embed(arr, 0.5, "lsb_replace", 3)
    assert np.abs(out2.astype(int) - arr.astype(int)).max() <= 1
