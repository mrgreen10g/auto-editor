"""Local scoreboard OCR. Models ship with RapidOCR; no uploads or API keys."""
import re
import sys
import numpy as np


def score_text(text):
    text = re.sub(r'\s+', '', text.upper())
    m = re.fullmatch(r'(\d{1,2})[:|IL/\\—–-](\d{1,2})', text)
    if not m and re.fullmatch(r'\d{2}', text):
        return tuple(map(int, text))
    if m:
        value = tuple(map(int, m.groups()))
        return value if max(value) <= 15 else None
    return None


def clock_text(text):
    m = re.search(r'(?<!\d)(\d{1,2})[:.](\d{2})(?!\d)', text)
    if m and int(m[1]) <= 20 and int(m[2]) < 60:
        return int(m[1]) * 60 + int(m[2])
    return None


def overlap(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    return intersection / max(1e-9, min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1])))


class ScoreReader:
    def __init__(self, ocr=None):
        if ocr is None:
            if sys.platform != 'win32':
                raise RuntimeError('Нативный поиск табло проверяется в Windows-сборке.')
            import onnxruntime
            onnxruntime.disable_telemetry_events()
            from rapidocr_onnxruntime import RapidOCR
            ocr = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1,
                           det_limit_type='max', det_limit_side_len=960)
        self.ocr = ocr
        self.box = self.clock_box = self.period_box = None
        self.colors = None

    @staticmethod
    def crop(image, box):
        h, w = image.shape[:2]
        x1, y1, x2, y2 = box
        return image[max(0, int(y1*h)):min(h, int(y2*h)+1), max(0, int(x1*w)):min(w, int(x2*w)+1)]

    def text(self, image):
        if not image.size:
            return '', 0.
        result, _ = self.ocr(image, use_det=False, use_cls=False)
        return (str(result[0][0]), float(result[0][1])) if result else ('', 0.)

    def tokens(self, image, top, bottom):
        h, w = image.shape[:2]
        band = image[int(top*h):int(bottom*h)]
        result, _ = self.ocr(band, use_cls=False)
        tokens = []
        for polygon, text, conf in result or []:
            points = np.asarray(polygon)
            box = [max(0., (points[:, 0].min()-3)/w), max(0., top+(points[:, 1].min()-3)/h),
                   min(1., (points[:, 0].max()+3)/w), min(1., top+(points[:, 1].max()+3)/h)]
            tokens.append((box, str(text), float(conf)))
        return tokens

    def visual_candidates(self, image):
        import cv2
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        boxes = []
        for top, bottom in ((0, .22), (.80, 1)):
            band = gray[int(top*h):int(bottom*h)]
            for mask in ((band < 80), (band > 210)):
                _, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype('uint8'), 8)
                glyphs = []
                for x, y, gw, gh, area in stats[1:]:
                    if .024*h <= gh <= .065*h and .24 <= gw/gh <= 1.2 and .18 <= area/(gw*gh) <= .90:
                        glyphs.append((int(x), int(y), int(gw), int(gh)))
                for a in glyphs:
                    for b in glyphs:
                        x, y, aw, ah = a; bx, by, bw, bh = b
                        gap = bx-x-aw
                        if .35*ah <= gap <= 2.8*ah and abs(y-by) < .25*ah and .75 <= bh/ah <= 1.3:
                            boxes.append([max(0, (x-5)/w), max(top, top+(min(y, by)-5)/h),
                                          min(1, (bx+bw+5)/w), min(bottom, top+(max(y+ah, by+bh)+5)/h)])
        boxes.sort(key=lambda b: b[3]-b[1], reverse=True)
        result = []
        for box in boxes[:16]:
            text, conf = self.text(self.crop(image, box))
            if score_text(text) is not None and conf >= .32:
                result.append((box, conf))
        return result

    def locate(self, images, cancel, log, manual=None):
        from .media import Cancelled
        clusters = []
        all_tokens = []
        for image in images:
            if cancel.is_set():
                raise Cancelled('Отменено.')
            tokens = self.tokens(image, 0, .22) + self.tokens(image, .80, 1)
            all_tokens += tokens
            candidates = [(box, conf) for box, text, conf in tokens
                          if conf >= .65 and score_text(text) is not None
                          and not re.fullmatch(r'\d{2}:\d{2}', text.strip()) and box[3]-box[1] >= .022]
            candidates += self.visual_candidates(image) if manual is None else []
            for box, conf in candidates:
                existing = next((c for c in clusters if overlap(c[0], box) > .6), None)
                if existing:
                    existing[1] += 1
                else:
                    clusters.append([box, 1, conf])
            if manual or any(c[1] >= 4 for c in clusters):
                break
        if manual:
            self.box = manual
        elif clusters:
            self.box = max(clusters, key=lambda c: (c[1], (c[0][3]-c[0][1])*c[2]))[0]
        else:
            raise ValueError('Счёт на табло не найден. Нажмите «Область счёта» и выделите две цифры счёта.')
        same_row = [t for t in all_tokens if abs((t[0][1]+t[0][3]-self.box[1]-self.box[3])/2) < .045 and overlap(t[0], self.box) < .1]
        clocks = [t for t in same_row if clock_text(t[1]) is not None]
        if clocks:
            self.clock_box = min(clocks, key=lambda t: abs(t[0][0]-self.box[0]))[0]
        periods = [t for t in same_row if re.search(r'OT|ОТ|[123](?:ST|ND|RD)|ПЕР', t[1].upper())]
        if periods:
            self.period_box = periods[0][0]
        log('Область счёта найдена. Проверяю изменения по записи…')
        return self.box

    @staticmethod
    def color(image):
        pixels = image.reshape(-1, 3)
        if not len(pixels):
            return np.zeros(3)
        quantized = (pixels // 32).astype(int)
        codes = quantized[:, 0]*64 + quantized[:, 1]*8 + quantized[:, 2]
        mode = np.bincount(codes, minlength=512).argmax()
        return pixels[codes == mode].mean(axis=0)

    def read(self, image, time):
        from .goals import Observation
        text, conf = self.text(self.crop(image, self.box))
        score = score_text(text) if conf >= .32 else None
        if score is None and conf >= .6:
            crop = self.crop(image, self.box); w = crop.shape[1]
            a, ac = self.text(crop[:, :int(.46*w)])
            b, bc = self.text(crop[:, int(.54*w):])
            if a.isdigit() and b.isdigit() and min(ac, bc) >= .75 and max(int(a), int(b)) <= 15:
                score = (int(a), int(b)); conf = min(ac, bc)
        clock = clock_text(self.text(self.crop(image, self.clock_box))[0]) if self.clock_box else None
        period = self.text(self.crop(image, self.period_box))[0] if self.period_box else ''
        banner = False; side = None
        x1, y1, x2, y2 = self.box
        if score is not None:
            self.colors = [self.color(self.crop(image, [max(0, x1-.10), y1, max(.001, x1-.04), y2])),
                           self.color(self.crop(image, [min(.999, x2+.035), y1, min(1, x2+.12), y2]))]
        else:
            band = self.crop(image, [.03, y1, .97, y2])
            text, confidence = self.text(band)
            banner = bool(confidence >= .7 and re.search(r'G[O0]{1,10}[A4][L1I]|Г[ОO]{1,10}Л', text.upper().replace(' ', '')))
            if banner and self.colors is not None:
                color = self.color(band)
                distances = [np.linalg.norm(color-c) for c in self.colors]
                if abs(distances[0]-distances[1]) > 90:
                    side = int(np.argmin(distances))
        mid = image[int(.25*len(image)):int(.75*len(image))].astype(float)
        ice = float(((mid.max(axis=2)-mid.min(axis=2) < 65) & (mid.mean(axis=2) > 150)).mean())
        return Observation(time, score, conf, clock, period, banner, side, ice)
