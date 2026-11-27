"""Large multi-family photo pool with a LOCKED test set (model-improvement loop).
Families: imagenette (ImageNet, full-size decoded JPEG), pets (Oxford-IIIT Pets, Flickr/web JPEG), synthetic (covers.make_cover),
flowers (Oxford 102 Flowers, web JPEG), kodak (24 lossless film-scan PNGs). Splits are by SOURCE PHOTO:
  train/val: imagenette, pets (hash split), synthetic        LOCKED TEST: pets-test photos, ALL flowers, ALL kodak (families never seen in training).
Cover crops are stored once (data/pool/covers.npz + covers.csv); stego/recompressed variants are derived deterministically from cover_id,
so any feature extractor can be run later on exactly the same images. `photo_id` is the bootstrap cluster (crops of one photo move together).
Run from backend/: python -m sublumen.ml_engine.pool covers"""
import glob, hashlib, io, os, sys
import numpy as np, pandas as pd
from PIL import Image
from ..stego_core import lsb_matching

ROOT = os.environ.get("SS_POOL", "data/pool"); S = 128; PHOTOS = os.environ.get("SS_PHOTOS", "/tmp/real"); SMOKE = bool(os.environ.get("SS_SMOKE"))
def _h(s, m=1000): return int(hashlib.sha256(s.encode()).hexdigest(), 16) % m

def sources():
    out = []  # (family, split, photo_id, path, n_crops)
    for f in sorted(glob.glob(PHOTOS + "/full_big/train/all/*.JPEG")):
        b = os.path.basename(f); h = _h(b)
        out.append(("imagenette", "train" if h < 850 else "val", b, f, 1))
    for f in sorted(glob.glob(PHOTOS + "/pets/images/*.jpg")):
        b = os.path.basename(f); h = _h(b)
        out.append(("pets", "train" if h < 650 else "val" if h < 800 else "test", b, f, 1))
    for f in sorted(glob.glob(PHOTOS + "/flowers/jpg/*.jpg")): out.append(("flowers", "test", os.path.basename(f), f, 1))
    for f in sorted(glob.glob(PHOTOS + "/kodak/*.png")): out.append(("kodak", "test", os.path.basename(f), f, 20))
    return out

QUOTA = {("imagenette", "train"): 1800, ("imagenette", "val"): 360, ("pets", "train"): 900, ("pets", "val"): 240, ("pets", "test"): 600, ("flowers", "test"): 800, ("kodak", "test"): 24}

if SMOKE:  # tiny subset: checks that the whole pipeline runs end to end, NOT for results
    QUOTA = {k: (3 if k[0] == "kodak" else 10) for k in QUOTA}

def build_covers():
    os.makedirs(ROOT, exist_ok=True); rows, X = [], []
    by = {}
    for fam, sp, pid, path, nc in sources(): by.setdefault((fam, sp), []).append((pid, path, nc))
    for (fam, sp), q in QUOTA.items():
        lst = by[(fam, sp)]; rng = np.random.default_rng(_h(fam + sp, 10**6))
        pick = [lst[i] for i in sorted(rng.permutation(len(lst))[:q])]
        for pid, path, nc in pick:
            im = Image.open(path).convert("RGB")
            if min(im.size) < 160: continue
            a = np.asarray(im, dtype=np.uint8)
            for k in range(nc):
                r = np.random.default_rng(_h(pid + str(k), 10**9)); y = int(r.integers(0, a.shape[0] - S + 1)); x = int(r.integers(0, a.shape[1] - S + 1))
                rows.append(dict(cover_id=f"{fam}:{pid}:{k}", family=fam, split=sp, photo_id=f"{fam}:{pid}")); X.append(a[y:y + S, x:x + S].copy())
    from . import covers
    from ..forensics_core.analyzer import load_array
    for sp, n in ((("train", 6), ("val", 3)) if SMOKE else (("train", 300), ("val", 80))):
        for i in range(n):
            t = ("graphic", "texture", "photo_like")[i % 3]; arr, _ = load_array(covers.make_cover(t, 7000 + i + (0 if sp == "train" else 5000)))
            rows.append(dict(cover_id=f"synthetic:{t}{i}:{sp}", family="synthetic", split=sp, photo_id=f"synthetic:{t}{i}:{sp}")); X.append(np.ascontiguousarray(arr[:S, :S]) if arr.shape[0] >= S and arr.shape[1] >= S else np.asarray(Image.fromarray(arr).resize((S, S))))
    df = pd.DataFrame(rows); np.savez_compressed(f"{ROOT}/covers.npz", x=np.stack(X)); df.to_csv(f"{ROOT}/covers.csv", index=False)
    print(df.groupby(["family", "split"]).agg(covers=("cover_id", "size"), photos=("photo_id", "nunique")))

def adaptive_matching(arr, bits_rate, seed):
    """Content-adaptive +-1 embedding: payload goes to the most textured samples (3x3 neighbourhood residual energy), +-1 only where the LSB must change."""
    rng = np.random.default_rng(seed); x = arr.astype(np.int16); n = int(arr.size * bits_rate)
    pad = np.pad(x, ((1, 1), (1, 1), (0, 0)), mode="edge"); nb = sum(pad[i:i + x.shape[0], j:j + x.shape[1]] for i in range(3) for j in range(3) if (i, j) != (1, 1)) / 8.0
    cost = np.abs(x - nb).reshape(-1) + rng.random(x.size) * 1e-3
    pos = np.argsort(-cost)[:n]; bits = rng.integers(0, 2, n); flat = x.reshape(-1).copy()
    ch = (flat[pos] & 1) != bits; step = np.where(rng.random(n) < 0.5, 1, -1); step = np.where(flat[pos] == 0, 1, np.where(flat[pos] == 255, -1, step))
    flat[pos[ch]] += step[ch]; return np.clip(flat, 0, 255).astype(np.uint8).reshape(arr.shape)

def jpeg95(a):
    b = io.BytesIO(); Image.fromarray(a, "RGB").save(b, "JPEG", quality=95); return np.asarray(Image.open(io.BytesIO(b.getvalue())).convert("RGB"), dtype=np.uint8)

def variants(cid, arr):
    """Yield (meta, array) for one cover: clean PNG, clean JPEG95, 8 PNG stego variants, 3 JPEG95 stego variants."""
    from ..benchmark.run import embed
    s0 = _h(cid, 10**8)
    yield dict(label=0, variant="png", embedder="none", payload_rate=0.0), arr
    yield dict(label=0, variant="jpeg95", embedder="none", payload_rate=0.0), jpeg95(arr)
    for kind, rates in (("lsb_replace", (0.10, 0.25, 0.50)), ("lsb_replace_keyed", (0.25,)), ("lsb_matching", (0.10, 0.25, 0.50))):
        for r in rates: yield dict(label=1, variant="png", embedder=kind, payload_rate=r), embed(arr, r, kind, s0 + int(r * 100))
    for r in (0.25, 0.50): yield dict(label=1, variant="png", embedder="adaptive_matching", payload_rate=r), adaptive_matching(arr, r, s0 + 7 + int(r * 100))
    yield dict(label=1, variant="jpeg95", embedder="lsb_replace", payload_rate=0.5), jpeg95(embed(arr, 0.5, "lsb_replace", s0 + 1))
    yield dict(label=1, variant="jpeg95", embedder="lsb_matching", payload_rate=0.5), jpeg95(embed(arr, 0.5, "lsb_matching", s0 + 2))

def featurize(extractor, shard, nshards, out=None):
    """Compute features for covers with index % nshards == shard; resumable (skips existing files)."""
    import importlib, time
    out = out or f"{ROOT}/feats_{extractor}"; os.makedirs(out, exist_ok=True); fn = f"{out}/shard_{shard:03d}_of_{nshards:03d}.csv"
    if os.path.exists(fn): return fn
    ex = importlib.import_module(f"sublumen.ml_engine.extractors").REGISTRY[extractor]
    df = pd.read_csv(f"{ROOT}/covers.csv"); X = np.load(f"{ROOT}/covers.npz")["x"]; rows, F = [], []
    for i in range(shard, len(df), nshards):
        c = df.iloc[i]
        for meta, a in variants(c.cover_id, X[i]):
            rows.append(dict(cover_id=c.cover_id, family=c.family, split=c.split, photo_id=c.photo_id, **meta)); F.append(ex["fn"](a))
    if ex.get("npy"):
        np.save(fn[:-4] + ".npy", np.vstack(F).astype(np.float32)); pd.DataFrame(rows).to_csv(fn + ".tmp", index=False); os.replace(fn + ".tmp", fn); return fn
    d = pd.concat([pd.DataFrame(rows), pd.DataFrame(np.vstack(F), columns=ex["names"])], axis=1); d.to_csv(fn + ".tmp", index=False); os.replace(fn + ".tmp", fn); return fn

def load(extractors=("v7",), nshards=60):
    """Load metadata + concatenated features. Returns (meta DataFrame, float32 matrix, feature names). Shards must exist for every extractor."""
    from .extractors import REGISTRY
    metas, mats = [], []
    for k in range(nshards):
        parts = []
        for e in extractors:
            fn = f"{ROOT}/feats_{e}/shard_{k:03d}_of_{nshards:03d}.csv"
            if REGISTRY[e].get("npy"): m = pd.read_csv(fn); parts.append((m, np.load(fn[:-4] + ".npy")))
            else: d = pd.read_csv(fn); m = d.iloc[:, :8]; parts.append((m, d.iloc[:, 8:].values.astype(np.float32)))
        m0 = parts[0][0]
        for m, _ in parts[1:]: assert (m.cover_id.values == m0.cover_id.values).all() and (m.variant.values == m0.variant.values).all() and (m.embedder.values == m0.embedder.values).all()
        metas.append(m0); mats.append(np.hstack([x for _, x in parts]))
    names = sum([REGISTRY[e]["names"] for e in extractors], [])
    return pd.concat(metas, ignore_index=True), np.vstack(mats), names

if __name__ == "__main__":
    if sys.argv[1] == "covers": build_covers()
