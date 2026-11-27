"""Feature extractor registry for the improvement loop. Each entry: names + fn(uint8 HxWx3 array) -> 1-D float array."""
import numpy as np
from . import features
from .features import POSITION_FREE
from .spam import NAMES as SPAM, spam_features

_idx = [features.FEATURE_NAMES.index(n) for n in POSITION_FREE]
def _v7(a): return np.concatenate([features.extract_array(a)[_idx], spam_features(a)])
REGISTRY = {"v7": dict(names=list(POSITION_FREE) + SPAM, fn=_v7)}

from .srm import srm_features, NAMES as SRM
def _srm(a): return np.concatenate([_v7(a), srm_features(a)])
REGISTRY["srmx"] = dict(names=SRM, fn=srm_features, npy=True)   # SRM-lite only (float32 .npy per shard); concatenated with v7 at load time
