"""M08 upload validation: size cap, magic bytes vs extension, safe decode, pixel cap. Reject early, clear errors."""
import io, os
from PIL import Image

class ValidationError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message); self.code, self.message, self.status = code, message, status

MAGIC = (("PNG", b"\x89PNG\r\n\x1a\n"), ("BMP", b"BM"), ("JPEG", b"\xff\xd8\xff"))
EXT = {"PNG": {".png"}, "BMP": {".bmp"}, "JPEG": {".jpg", ".jpeg"}}

def sniff(data: bytes):
    for name, m in MAGIC:
        if data.startswith(m):
            return name
    return None

def validate_image(data: bytes, filename: str, max_bytes: int, max_pixels: int, allowed=("PNG", "BMP", "JPEG")) -> dict:
    if not data:
        raise ValidationError("empty_file", "File is empty.")
    if len(data) > max_bytes:
        raise ValidationError("too_large", f"File exceeds the {max_bytes} byte limit.", 413)
    kind = sniff(data)
    if kind is None or kind not in allowed:
        raise ValidationError("unsupported_type", "Only real PNG, BMP or JPEG images are accepted.", 415)
    ext = os.path.splitext(filename or "")[1].lower()
    if ext and ext not in EXT[kind]:
        raise ValidationError("extension_mismatch", f"File extension '{ext}' does not match its content ({kind}).", 415)
    try:
        img = Image.open(io.BytesIO(data))
        w, h = img.size  # header only: checked BEFORE decoding pixels (decompression-bomb guard)
        if w * h > max_pixels:
            raise ValidationError("too_many_pixels", f"Image has {w*h} pixels; limit is {max_pixels}.", 413)
        img.verify()
        Image.open(io.BytesIO(data)).convert("RGB").load()
    except ValidationError:
        raise
    except Exception:
        raise ValidationError("corrupt_image", "Image is corrupt or cannot be decoded.", 422)
    return {"format": kind, "width": w, "height": h}

def sanitize_text(s, max_len=200):
    s = "".join(ch for ch in (s or "") if ch.isprintable()).strip()
    return s[:max_len]
