"""Read TXT/DOCX scripts; remove unspoken editorial instructions."""
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

def read_script(path):
    path=Path(path)
    if path.suffix.lower()!='.docx':return path.read_text(encoding='utf-8-sig')
    with zipfile.ZipFile(path) as archive:
        info=archive.getinfo('word/document.xml')
        if info.file_size>20_000_000:raise ValueError('Документ слишком большой для сценария.')
        root=ET.fromstring(archive.read(info))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    def paragraph(p):
        return ''.join((t.text or '') if t.tag.endswith('}t') else '\n' if t.tag.endswith(('}br','}cr')) else '\t' if t.tag.endswith('}tab') else '' for t in p.iter())
    return '\n'.join(paragraph(p) for p in root.findall('.//w:p',ns))

def clean_script(text):
    text=re.sub(r'\[[^\]]*[А-Яа-яЁё][^\]]*\]','',text,flags=re.S)
    text=re.sub(r'https?://\S+|:chatgpt-content-reference\{[^}]*\}|[^]*','',text)
    return '\n'.join(l.strip().lstrip('\ufeff') for l in text.splitlines()
                     if l.strip() and not re.search('[А-Яа-яЁё]',l) and not re.fullmatch(r'[━─═_—–\-\s]+',l))
