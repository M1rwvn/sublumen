import joblib, numpy as np
from .features import extract_bytes

class Detector:
    def __init__(self, path):
        d = joblib.load(path)
        self.model, self.features, self.meta, self.algo = d["model"], d["features"], d["meta"], d["algo"]
        self.threshold = float(d.get("threshold", 0.0))  # decision-function threshold chosen on validation data (v6+)
        import os
        self.name = os.path.basename(path)[:-len(".joblib")]

    def predict(self, data: bytes) -> dict:
        if self.algo == "hgb":
            return self._predict_tiles(data)
        return self._predict_one(data)

    def _predict_tiles(self, data: bytes, max_tiles=8) -> dict:
        """The v8 model was trained on 128x128 crops: score evenly spaced 128px tiles and average the logits."""
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(data)); im.load(); im = im.convert("RGB"); a = np.asarray(im); h, w = a.shape[:2]
        if h < 128 or w < 128:
            r = self._predict_one(data); r["note"] = "Image smaller than 128px: score from a single full-image pass, less reliable."; return r
        ys, xs = list(range(0, h - 127, 128)) or [0], list(range(0, w - 127, 128)) or [0]
        pos = [(y, x) for y in ys for x in xs]; step = max(1, len(pos) // max_tiles); pos = pos[::step][:max_tiles]
        zs = []
        for y, x in pos:
            b = io.BytesIO(); Image.fromarray(a[y:y + 128, x:x + 128]).save(b, "PNG"); zs.append(np.log(max(self._predict_one(b.getvalue())["score"], 1e-6) / max(1 - self._predict_one(b.getvalue())["score"], 1e-6)) if False else self._logit(b.getvalue()))
        z = float(np.mean(zs)); score = float(1 / (1 + np.exp(-z)))
        lvl = "high" if score >= 0.85 else "medium" if score >= 0.5 else "low"
        return {"model": self.name, "algo": self.algo, "score": score, "level": lvl, "label": "suspected" if score >= 0.5 else "not_suspected", "tiles": len(pos),
                "note": "Mean evidence over up to 8 evenly spaced 128px tiles; 0.5 is the validation threshold (5% clean false alarms on photo-disjoint validation). A score, not proof."}

    def tile_grid(self, data: bytes, max_tiles=36) -> dict:
        """Per-tile model score on a grid of 128px tiles (same scoring as predict). For the evidence overlay; 0.5 = validation threshold."""
        import io
        from PIL import Image
        a = np.asarray(Image.open(io.BytesIO(data)).convert("RGB")); h, w = a.shape[:2]
        if h < 128 or w < 128: return {"tile": 128, "tiles": [], "h": h, "w": w}
        step = 128
        while (len(range(0, h - 127, step)) * len(range(0, w - 127, step))) > max_tiles: step += 128
        out = []
        for y in range(0, h - 127, step):
            for x in range(0, w - 127, step):
                b = io.BytesIO(); Image.fromarray(a[y:y + 128, x:x + 128]).save(b, "PNG")
                z = self._logit(b.getvalue()); out.append({"y": y, "x": x, "score": float(1 / (1 + np.exp(-z)))})
        return {"tile": 128, "step": step, "h": h, "w": w, "tiles": out}

    def _logit(self, data):
        s = min(max(self._predict_one(data)["score"], 1e-6), 1 - 1e-6); return float(np.log(s / (1 - s)))

    def _predict_one(self, data: bytes) -> dict:
        from .features import FEATURE_NAMES
        full = extract_bytes(data)
        spam = None
        cols = []
        srm = None
        for n in self.features:
            if n.startswith(("srm4_", "srmx_")):
                if srm is None:
                    from .srm import srm_features, NAMES as SRM_NAMES
                    from ..forensics_core.analyzer import load_array
                    srm = srm_features(load_array(data)[0]); self._srm_pos = {k: i for i, k in enumerate(SRM_NAMES)}
                cols.append(srm[self._srm_pos[n]])
            elif n.startswith("spam_"):
                if spam is None:
                    from .spam import spam_features
                    from ..forensics_core.analyzer import load_array
                    spam = spam_features(load_array(data)[0])
                cols.append(spam[int(n.split("_")[1])])
            else:
                cols.append(full[FEATURE_NAMES.index(n)])
        x = np.array(cols, dtype=float).reshape(1, -1)
        if self.threshold != 0.0:
            score = float(1 / (1 + np.exp(-(self.model.decision_function(x)[0] - self.threshold))))
        elif hasattr(self.model, "predict_proba"):
            score = float(self.model.predict_proba(x)[0, 1])
        else:
            score = float(1 / (1 + np.exp(-self.model.decision_function(x)[0])))
        lvl = "high" if score >= 0.85 else "medium" if score >= 0.5 else "low"
        return {"model": self.name, "algo": self.algo, "score": score, "level": lvl,
                "label": "suspected" if score >= 0.5 else "not_suspected",
                "note": ("Calibrated on a dataset where ~86% of images are stego; real-world prevalence differs, so treat as a score, not the true probability. Not proof." if "method" in self.meta else "Model score is an indicator, not a calibrated probability or proof.")}
