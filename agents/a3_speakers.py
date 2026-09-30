"""a3_speakers.py - Phân cụm 14 file thành 2 người ngâm bằng âm sắc (MFCC) + pitch."""
import glob
import json
from pathlib import Path

import librosa
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

files = sorted(glob.glob("data/style_refs/*.mp3"))
X, names = [], []
for f in files:
    y, sr = librosa.load(f, sr=16000, mono=True)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
    f0, _, _ = librosa.pyin(y, fmin=70, fmax=400, sr=sr)
    f0 = f0[~np.isnan(f0)]
    X.append(np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1), [np.median(f0) / 50]]))
    names.append(Path(f).name)
    print("Đã đo", Path(f).name, flush=True)

Xs = StandardScaler().fit_transform(np.array(X))
km = KMeans(n_clusters=2, n_init=20, random_state=0).fit(Xs)
print("Silhouette:", round(silhouette_score(Xs, km.labels_), 3))

result = {n: int(l) for n, l in zip(names, km.labels_)}
for n, l in result.items():
    print(f"  Người {l}: {n}")
Path("profiles/speakers.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")