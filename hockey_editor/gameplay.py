"""Conservative, continuous rink shots. Never fall back to a non-game scene."""
import numpy as np
from PIL import Image
from .media import Cancelled


def frame_features(path):
    with Image.open(path) as image:
        rgb = np.asarray(image.convert('RGB').resize((160, 90)), dtype=float)
    middle = rgb[24:75, 8:152]
    gray = rgb.mean(axis=2)
    light = middle.mean(axis=2)
    ice = (middle.max(axis=2)-middle.min(axis=2) < 65) & (light > 145)
    # Ice must extend in both directions; boards, shirts and faces are insufficient.
    rink = (ice.mean() >= .56 and (ice.mean(axis=1) > .55).mean() >= .48
            and (ice.mean(axis=0) > .4).mean() >= .78
            and .003 <= (light < 110).mean() <= .28 and gray.std() > 9)
    return gray, float(ice.mean()), bool(rink)


def gameplay_ranges(files, duration, cancel, step=.5):
    features = []; previous = None
    for file in files:
        if cancel.is_set(): raise Cancelled('Отменено.')
        gray, ice, rink = frame_features(file)
        motion = float(np.abs(gray-previous).mean()/255) if previous is not None else 0.
        features.append((rink, motion)); previous = gray
    ranges = []; begin = None
    for i in range(len(features)+1):
        valid = i < len(features) and features[i][0]
        if valid and begin is None: begin = i
        if not valid and begin is not None:
            # Guard both ends; never merge across a crowd shot or replay bumper.
            start = begin*step+step
            end = min(duration, (i-1)*step)-step
            motion = np.mean([f[1] for f in features[begin+1:i]]) if i-begin > 1 else 0
            if end-start >= 2.5 and motion >= .0025:
                ranges.append([round(start,3),round(end,3)])
            begin = None
    return ranges


def candidates_from_ranges(ranges):
    from .goals import Candidate
    result = []
    for lo, hi in ranges:
        start = lo
        while hi-start >= 2.5:
            end = min(hi, start+8)
            result.append(Candidate(f'broll-{len(result)}',None,None,(start+end)/2,
                                    start,end,.86,'Непрерывная игровая сцена, проверена по изображению.','','play'))
            start = end+1
    return result


def gameplay_candidates(files, duration, cancel, step=2):
    return candidates_from_ranges(gameplay_ranges(files,duration,cancel,step))


def bound_goal(candidate, ranges):
    """Keep the attack and goal within one rink shot, without celebrations."""
    nearby = [(a,b) for a,b in ranges if a <= candidate.time <= b+2.5]
    if not nearby: return False
    a,b = min(nearby,key=lambda span:abs(min(candidate.time,span[1])-candidate.time))
    when = min(candidate.time,b-.1)
    candidate.start = max(a,when-7)
    candidate.end = min(b,when+2)
    candidate.time = max(candidate.start,min(when,candidate.end))
    return candidate.end-candidate.start >= 2.5
