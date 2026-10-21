"""Validated, non-overwriting logo uploads to an owner-selected local folder."""
import base64,binascii,io,re
from pathlib import Path
from PIL import Image,ImageOps,UnidentifiedImageError
from .mini_export import folder
from .mini_server import RemoteError

MAX_BYTES=8*1024*1024

def save_upload(data):
    root=folder(data.get('upload_folder',''))
    name=str(data.get('file_name','')).strip()
    if not name or len(name)>120 or re.search(r'[<>:"/\\|?*\x00-\x1f]',name) or name.endswith(('.', ' ')):
        raise RemoteError('Укажите имя логотипа без пути и символов <>:"/\\|?*.')
    if Path(name).suffix.lower() in ('.png','.jpg','.jpeg','.webp'):name=name.rsplit('.',1)[0]
    if not name or name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        raise RemoteError('Выберите другое имя логотипа.')
    raw=data.get('image','')
    if not isinstance(raw,str) or len(raw)>4*((MAX_BYTES+2)//3):raise RemoteError('Логотип должен быть не больше 8 МБ.')
    try:content=base64.b64decode(raw,validate=True)
    except (ValueError,binascii.Error):raise RemoteError('Не удалось прочитать изображение. Выберите файл заново.') from None
    if not content or len(content)>MAX_BYTES:raise RemoteError('Логотип должен быть не больше 8 МБ.')
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in ('PNG','JPEG','WEBP') or image.width*image.height>16000000:raise RemoteError('Нужен PNG, JPEG или WebP, не более 16 миллионов пикселей.')
            image.load();normalized=ImageOps.exif_transpose(image).convert('RGBA')
            out=io.BytesIO();normalized.save(out,format='PNG');payload=out.getvalue()
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError):
        raise RemoteError('Изображение повреждено или имеет неподдерживаемый формат.') from None
    target=root/(name+'.png')
    try:stream=target.open('xb')
    except FileExistsError:raise RemoteError('В этой папке уже есть '+target.name+'. Выберите другое имя или назначьте существующий файл.') from None
    except OSError:raise RemoteError('Не удалось сохранить логотип в выбранную папку.') from None
    try:
        with stream:stream.write(payload)
    except Exception:
        target.unlink(missing_ok=True);raise
    return target
