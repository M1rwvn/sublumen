"""Locked-test evaluation for the improvement loop. The LOCKED test = pool rows with split == 'test' (pets-test photos, all flowers, all kodak).
Rules: never used for training, threshold choice, hyper-parameter or feature selection; every scoring is appended to data/pool/LOCKED_LOG.md.
Thresholds are chosen on VAL (95th percentile of clean-PNG val scores, i.e. 5% target false alarms) before the test rows are touched."""
import json, time, numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from .pool import ROOT

def boot_mean(clusters, v, B, rng):
    u, inv = np.unique(clusters, return_inverse=True); s = np.bincount(inv, weights=v); n = np.bincount(inv).astype(float)
    pt = s.sum() / n.sum(); r = rng.integers(0, len(u), (B, len(u))); bs = s[r].sum(1) / n[r].sum(1)
    return float(pt), [float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], int(n.sum())

def val_threshold(meta, score, target=0.05):
    m = ((meta.split == "val") & (meta.label == 0) & (meta.variant == "png")).values
    return float(np.quantile(score[m], 1 - target))

def locked_report(name, meta, score, thr, B=1000, seed=0, log=True, note=""):
    t = meta[meta.split == "test"].copy(); t["s"] = score[(meta.split == "test").values]; t["p"] = (t.s >= thr).astype(float)
    rng = np.random.default_rng(seed); out = {"name": name, "threshold": thr, "families": {}}
    for fam in sorted(t.family.unique()):
        f = t[t.family == fam]; d = {}
        c = f[(f.label == 0) & (f.variant == "png")]; v, ci, n = boot_mean(c.photo_id.values, c.p.values, B, rng); d["fpr_png"] = dict(value=v, ci95=ci, n=n)
        c = f[(f.label == 0) & (f.variant == "jpeg95")]; v, ci, n = boot_mean(c.photo_id.values, c.p.values, B, rng); d["fpr_jpeg95"] = dict(value=v, ci95=ci, n=n)
        for (e, var, rate), g in f[f.label == 1].groupby(["embedder", "variant", "payload_rate"]):
            v, ci, n = boot_mean(g.photo_id.values, g.p.values, B, rng); d[f"recall|{e}|{var}|{rate}"] = dict(value=v, ci95=ci, n=n)
        png = f[f.variant == "png"]; d["auc_png_all_embedders"] = float(roc_auc_score(png.label, png.s))
        for e in ("lsb_matching", "adaptive_matching"):
            x = png[(png.embedder == e) | (png.label == 0)]; d[f"auc|{e}"] = float(roc_auc_score(x.label, x.s))
        # recall at matched 5% false alarms (threshold from this family's own clean test scores: comparison only, not a shippable operating point)
        t5 = float(np.quantile(png[png.label == 0].s, 0.95)); d["recall_at_5pct_fpr_matched"] = {f"{e}|{r}": float((g.s >= t5).mean()) for (e, r), g in png[png.label == 1].groupby(["embedder", "payload_rate"])}
        out["families"][fam] = d
    if log:
        with open(f"{ROOT}/LOCKED_LOG.md", "a") as fh:
            fh.write(f"- {time.strftime('%Y-%m-%d %H:%M')} locked test scored for `{name}` (threshold from val {thr:.4f}) {note}\n")
    return out

def pretty(out):
    for fam, d in out["families"].items():
        print(f"  [{fam}] fpr_png {d['fpr_png']['value']:.3f} [{d['fpr_png']['ci95'][0]:.3f},{d['fpr_png']['ci95'][1]:.3f}]  jpeg_fpr {d['fpr_jpeg95']['value']:.3f}  AUC all {d['auc_png_all_embedders']:.3f} match {d['auc|lsb_matching']:.3f} adapt {d['auc|adaptive_matching']:.3f}")
        print("     recall own thr:", {k.split('|', 1)[1]: round(v['value'], 3) for k, v in d.items() if k.startswith('recall|') and 'png' in k})
        print("     recall @5%FPR matched:", {k: round(v, 3) for k, v in d['recall_at_5pct_fpr_matched'].items()})
