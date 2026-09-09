"""Use display metadata through FFmpeg, then vote on upright presenter faces."""
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
from .media import run, probe, Cancelled


def choose_rotation(votes):
    totals = {angle: sum(row.get(angle, 0.) for row in votes) for angle in (0,90,180,270)}
    ranking=sorted(totals,key=totals.get,reverse=True)
    best,second=ranking[:2]
    support=sum(row.get(best,0)>.5 for row in votes)
    confident=support>=2 and totals[best]>=2 and totals[best]>=totals[second]*1.45+.5
    return (best if confident else 0), confident


def face_votes(image, faces, eyes):
    import cv2
    votes={}
    for angle in (0,90,180,270):
        rotated=np.rot90(image, -angle//90).copy()
        gray=cv2.cvtColor(rotated,cv2.COLOR_RGB2GRAY)
        score=0.
        for x,y,w,h in faces.detectMultiScale(gray,scaleFactor=1.1,minNeighbors=5,minSize=(45,45)):
            upper=gray[y+int(.12*h):y+int(.65*h),x:x+w]
            found=eyes.detectMultiScale(upper,scaleFactor=1.1,minNeighbors=3,minSize=(max(10,w//10),max(10,h//10)))
            eye_score=2 if len(found)>=2 else .6 if len(found)==1 else 0
            score=max(score,.4+eye_score)
        votes[angle]=score
    return votes


def detect_rotation(host, cache, cancel, log=lambda _:None):
    path=Path(host);stat=path.stat()
    signature=hashlib.sha256(json.dumps([str(path.resolve()),stat.st_size,stat.st_mtime_ns,'orientation-1']).encode()).hexdigest()
    folder=Path(cache)/'orientation';folder.mkdir(parents=True,exist_ok=True)
    saved=folder/'result.json'
    if saved.exists():
        data=json.loads(saved.read_text(encoding='utf-8'))
        if data.get('signature')==signature:
            log(data['note']);return data['angle']
    try:
        import cv2
        faces=cv2.CascadeClassifier(str(Path(cv2.data.haarcascades)/'haarcascade_frontalface_default.xml'))
        eyes=cv2.CascadeClassifier(str(Path(cv2.data.haarcascades)/'haarcascade_eye_tree_eyeglasses.xml'))
        if faces.empty() or eyes.empty(): raise ValueError('Модели определения лица не найдены.')
        duration=probe(host)['duration'];votes=[]
        for i, fraction in enumerate((.08,.22,.4,.62,.8)):
            if cancel.is_set(): raise Cancelled('Отменено.')
            target=folder/f'frame-{i}.jpg'
            run(['-y','-ss',max(0,min(duration-.2,duration*fraction)),'-i',host,'-frames:v','1','-vf',
                 'scale=640:640:force_original_aspect_ratio=decrease',target],cancel)
            with Image.open(target) as image: votes.append(face_votes(np.asarray(image.convert('RGB')),faces,eyes))
        angle,confident=choose_rotation(votes)
        note=f'Поворот ведущего определён автоматически: {angle}°.' if confident else 'Поворот: надёжно определить лицо не удалось. Сохранена ориентация файла; доступна ручная настройка.'
    except Cancelled: raise
    except Exception as error:
        angle=0;note='Автоповорот недоступен: '+str(error)+'. Сохранена ориентация файла.'
    saved.write_text(json.dumps({'signature':signature,'angle':angle,'note':note},ensure_ascii=False),encoding='utf-8')
    log(note);return angle
