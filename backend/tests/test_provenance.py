from sublumen.forensics_core.provenance import check_c2pa
from conftest import make_png

def test_unsigned_png_reports_no_manifest():
    r = check_c2pa(make_png(), "PNG")
    assert r["available"] and r["present"] is False and "does not mean" in r["note"]

def test_garbage_does_not_crash():
    r = check_c2pa(b"\x89PNG not really", "PNG")
    assert r["present"] in (False, None)


import io, shutil, subprocess, pytest

def _signed_png(tmp_path):
    import c2pa
    from PIL import Image
    run = lambda *a: subprocess.run(a, cwd=tmp_path, check=True, capture_output=True)
    run("openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", "ca.key")
    run("openssl", "req", "-x509", "-new", "-key", "ca.key", "-sha256", "-days", "30", "-subj", "/CN=Test CA/O=Test",
        "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign", "-out", "ca.pem")
    run("openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", "l.key")
    run("openssl", "pkcs8", "-topk8", "-nocrypt", "-in", "l.key", "-out", "l8.key")
    run("openssl", "req", "-new", "-key", "l.key", "-subj", "/CN=Test Signer/O=Test", "-out", "l.csr")
    (tmp_path / "ext.cnf").write_text("basicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=emailProtection\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n")
    run("openssl", "x509", "-req", "-in", "l.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial", "-days", "30", "-sha256", "-extfile", "ext.cnf", "-out", "l.pem")
    chain = (tmp_path / "l.pem").read_bytes() + (tmp_path / "ca.pem").read_bytes()
    info = c2pa.C2paSignerInfo(c2pa.C2paSigningAlg.ES256, chain, (tmp_path / "l8.key").read_bytes(), None)
    signer = c2pa.Signer.from_info(info)
    b = io.BytesIO(); Image.new("RGB", (64, 64), (120, 40, 200)).save(b, "PNG"); b.seek(0)
    man = {"claim_generator_info": [{"name": "sublumen-test", "version": "1"}], "assertions": [{"label": "c2pa.actions", "data": {"actions": [{"action": "c2pa.created", "digitalSourceType": "http://cv.iptc.org/newscodes/digitaltype/trainedAlgorithmicMedia"}]}}]}
    out = io.BytesIO(); c2pa.Builder(man).sign(signer, "image/png", b, out)
    return out.getvalue()

@pytest.mark.skipif(shutil.which("openssl") is None, reason="needs openssl")
def test_signed_manifest_positive_and_tamper(tmp_path):
    d = _signed_png(tmp_path)
    r = check_c2pa(d, "PNG")
    assert r["present"] is True and r["validation_state"] == "Valid"
    assert r["signer_trusted"] is False  # self-made test CA is not on the C2PA trust list
    b = bytearray(d); b[-40] ^= 0xFF
    r2 = check_c2pa(bytes(b), "PNG")
    assert r2["present"] is True and r2["validation_state"] == "Invalid"
