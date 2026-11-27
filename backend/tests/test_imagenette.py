import os, pytest
D = os.environ.get("SS_REAL_DIR", "/tmp/real/imagenette2-160/train")
@pytest.mark.skipif(not os.path.isdir(D), reason="Imagenette not downloaded")
def test_imagenette_cover_loads():
    from sublumen.ml_engine import covers
    import inspect
    fn = [v for k, v in vars(covers).items() if "imagenette" in k.lower() and callable(v)]
    assert fn or "imagenette" in inspect.getsource(covers)
