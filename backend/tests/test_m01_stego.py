import io, os
import numpy as np
import pytest
from PIL import Image
from sublumen.stego_core import studio
from sublumen.stego_core.crypto import StegoError
from conftest import make_png

def test_roundtrip_100_random_messages():
    rng = np.random.default_rng(1)
    cover = make_png(96, 96, seed=5)
    cap = studio.capacity_bytes(cover)
    for i in range(100):
        n = int(rng.integers(0, min(cap, 400)))
        msg = bytes(rng.integers(0, 256, n, dtype=np.uint8))
        pw = f"pw-{i}-" + os.urandom(4).hex()
        out = studio.embed(cover, msg, pw, with_ssim=False)
        assert studio.extract(out["stego_png"], pw) == msg

def test_unicode_message(cover_png):
    msg = "رسالة سرية 🔒 secret".encode()
    out = studio.embed(cover_png, msg, "كلمة-سر")
    assert studio.extract(out["stego_png"], "كلمة-سر") == msg

def test_wrong_password_always_fails(cover_png):
    out = studio.embed(cover_png, b"hello", "right")
    for pw in ["wrong", "Right", "right ", "x"]:
        with pytest.raises(StegoError) as e:
            studio.extract(out["stego_png"], pw)
        assert e.value.code == "auth_failed"

def test_tampered_bit_fails(cover_png):
    out = studio.embed(cover_png, b"hello world", "pw")
    arr = np.array(Image.open(io.BytesIO(out["stego_png"])).convert("RGB"))
    flat = arr.reshape(-1)
    for pos in [5 * 8 + 3, 40 * 8 + 1, 50 * 8 + 2]:  # salt / header, ciphertext, tag region
        f2 = flat.copy(); f2[pos] ^= 1
        b = io.BytesIO(); Image.fromarray(f2.reshape(arr.shape)).save(b, format="PNG")
        with pytest.raises(StegoError):
            studio.extract(b.getvalue(), "pw")

def test_capacity_rejected_cleanly(cover_png):
    cap = studio.capacity_bytes(cover_png)
    studio.embed(cover_png, b"a" * cap, "pw", with_ssim=False)  # exactly fits
    with pytest.raises(StegoError) as e:
        studio.embed(cover_png, b"a" * (cap + 1), "pw")
    assert e.value.code == "capacity"

def test_clean_image_has_no_payload(cover_png):
    with pytest.raises(StegoError) as e:
        studio.extract(cover_png, "pw")
    assert e.value.code == "no_payload"

def test_jpeg_rejected_and_jpeg_recompress_destroys():
    jpg = make_png(64, 64, fmt="JPEG")
    with pytest.raises(StegoError) as e:
        studio.embed(jpg, b"x", "pw")
    assert e.value.code == "lossy_format"
    out = studio.embed(make_png(), b"secret", "pw")
    b = io.BytesIO(); Image.open(io.BytesIO(out["stego_png"])).save(b, format="JPEG", quality=95)
    with pytest.raises(StegoError):
        studio.extract(Image.open(io.BytesIO(b.getvalue())).convert("RGB") and _to_png(b.getvalue()), "pw")

def _to_png(jpg_bytes):
    b = io.BytesIO(); Image.open(io.BytesIO(jpg_bytes)).convert("RGB").save(b, format="PNG"); return b.getvalue()

def test_bmp_supported():
    bmp = make_png(64, 64, fmt="BMP")
    out = studio.embed(bmp, b"bmp ok", "pw")
    assert studio.extract(out["stego_png"], "pw") == b"bmp ok"

def test_garbage_file_is_clean_error():
    with pytest.raises(StegoError) as e:
        studio.extract(b"not an image", "pw")
    assert e.value.code == "bad_image"

def test_psnr_matches_theory_for_full_embed():
    cover = make_png(128, 128, seed=3)
    cap = studio.capacity_bytes(cover)
    out = studio.embed(cover, os.urandom(cap), "pw")
    # half of the LSBs flip by 1 => MSE ~ 0.5 => PSNR ~ 51.1 dB
    assert 50.5 < out["psnr_db"] < 51.7
    assert 0.95 < out["ssim"] <= 1.0

def test_nonce_and_salt_not_reused(cover_png):
    a = studio.embed(cover_png, b"same", "pw", with_ssim=False)["stego_png"]
    b = studio.embed(cover_png, b"same", "pw", with_ssim=False)["stego_png"]
    assert a != b
