import os, numpy as np, pytest
from sublumen.stego_core import studio
from sublumen.stego_core.crypto import StegoError
from sublumen.forensics_core import stats
from sublumen.forensics_core.analyzer import load_array
from conftest import make_png

def test_keyed_roundtrip_and_wrong_password():
    c = make_png(96, 96, seed=8)
    for i in range(20):
        msg = os.urandom(50 + i)
        out = studio.embed(c, msg, f"pw{i}", with_ssim=False, keyed=True)["stego_png"]
        assert studio.extract(out, f"pw{i}") == msg
    with pytest.raises(StegoError):
        studio.extract(out, "bad")

def test_sequential_still_works_and_keyed_spreads_changes():
    c = make_png(128, 128, seed=2); cap = studio.capacity_bytes(c)
    msg = os.urandom(cap // 4)
    seq = studio.embed(c, msg, "pw", with_ssim=False)["stego_png"]
    key = studio.embed(c, msg, "pw", with_ssim=False, keyed=True)["stego_png"]
    assert studio.extract(seq, "pw") == msg and studio.extract(key, "pw") == msg
    A, _ = load_array(c); S, _ = load_array(seq); K, _ = load_array(key)
    rows = lambda X: np.any(X != A, axis=(1, 2))
    assert rows(S)[-40:].sum() == 0          # sequential: tail untouched
    assert rows(K)[-40:].sum() > 20          # keyed: changes spread over the whole image
