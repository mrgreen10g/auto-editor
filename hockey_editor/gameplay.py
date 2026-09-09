"""Select moving rink footage independently of scoreboard recognition."""
import numpy as np
from PIL import Image
from .media import Cancelled


def frame_features(path):
    with Image.open(path) as image:
        rgb = np.asarray(image.convert('RGB').resize((160, 90)), dtype=float)
    middle = rgb[20:72]
    gray = rgb.mean(axis=2)
    ice = float(((middle.max(axis=2)-middle.min(axis=2) < 70) & (middle.mean(axis=2) > 145)).mean())
    usable = gray.mean() > 20 and gray.std() > 7
    return gray, ice, usable


def gameplay_candidates(files, duration, cancel, step=2):
    from .goals import Candidate
    features = []
    previous = None
    for i, file in enumerate(files):
        if cancel.is_set(): raise Cancelled('Отменено.')
        gray, ice, usable = frame_features(file)
        motion = float(np.abs(gray-previous).mean()/255) if previous is not None else 0.
        features.append((ice, motion, usable)); previous = gray
    windows = []
    count = max(2, min(4, len(files)))
    length = min(8., duration)
    for i in range(max(1, len(files)-count+1)):
        start = min(i*step, max(0, duration-length))
        samples = features[i:i+count]
        if not samples or not all(f[2] for f in samples): continue
        ice = float(np.mean([f[0] for f in samples]))
        motion = float(np.mean([f[1] for f in samples]))
        quality = ice*.7 + min(.2, motion)*1.5
        windows.append((quality, start, ice, motion))
    # Prefer ice + movement. If the rink is dark or obscured, retain the best nonblank scene.
    strong = [w for w in windows if w[2] >= .18 and w[3] >= .006]
    pool = strong or [w for w in windows if w[3] >= .006] or windows
    pool.sort(reverse=True)
    chosen = []
    for quality, start, ice, motion in pool:
        if any(abs(start-c.start) < length+3 for c in chosen): continue
        confident = ice >= .18 and motion >= .006
        chosen.append(Candidate(f'broll-{len(chosen)}', None, None, start+length/2, start, start+length,
                                .82 if confident else .4,
                                'Игровая сцена по изображению, без привязки к счёту.' if confident else 'Резервная сцена: желательно просмотреть качество.', '', 'play'))
        if len(chosen) >= 60: break
    return chosen
