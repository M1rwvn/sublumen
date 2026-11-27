"""C2PA / Content Credentials presence check (c2pa-python). Only reports what the library returns.
Absence of a manifest proves nothing about authenticity; presence is not proof either unless validation passes."""
import io, json

MIME = {"PNG": "image/png", "JPEG": "image/jpeg", "BMP": "image/bmp"}

def check_c2pa(data: bytes, fmt: str) -> dict:
    try:
        import c2pa
    except Exception:
        return {"available": False, "present": None, "note": "c2pa library not installed; provenance not checked."}
    try:
        r = c2pa.Reader(MIME.get(fmt, "image/png"), io.BytesIO(data))
        j = json.loads(r.json())
        errs = (j.get("validation_status") or [])
        untrusted = any(e.get("code") == "signingCredential.untrusted" for e in errs)
        return {"signer_trusted": not untrusted, "available": True, "present": True, "active_manifest": j.get("active_manifest"),
                "validation_state": j.get("validation_state"), "validation_errors": errs[:5],
                "note": "A manifest is present. Only a passing validation state supports provenance claims; it still does not prove the depicted event is real."}
    except Exception as e:
        if "ManifestNotFound" in type(e).__name__ or "no JUMBF" in str(e):
            return {"available": True, "present": False, "note": "No C2PA manifest found. This does not mean the image is fake or edited."}
        return {"available": True, "present": None, "note": "C2PA check failed: " + type(e).__name__}
