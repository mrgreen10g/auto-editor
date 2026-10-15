"""Exact sports phrase translations for review; never infer an omitted claim.

Whole-clause matching is intentional: an added negation or condition must not
be swallowed by a rule that would reverse the meaning of a forecast.
"""
import re
from .uzbek import norm


def exact_translation(text):
    original=text.strip().rstrip('.!')
    t=norm(original)
    pick=re.fullmatch(r"(?:(?:mening|bizning)\s+)?(?:tanlovim|tanlovimiz|tanlov|prognoz)\s*[—–:\-]?\s*(.+)",t)
    prefix='Мой выбор: ' if pick else ''
    body=pick[1] if pick else t
    total=re.fullmatch(r"(?:umumiy\s+)?(?:total|gol soni)\s*[:—\-]?\s*(\d+(?:[,.]\d+)?)\s*(?:ta)?dan\s+(kam|ko'p)(?:\s+gol)?",body)
    if total:return prefix+'Тотал '+('меньше ' if total[2]=='kam' else 'больше ')+total[1].replace('.',',')
    # Preserve the exact original team spelling; translation is not team correction.
    negative=re.fullmatch(r"(.+?)\s+mag'lub\s+bo'lmaydi",t)
    if negative and not re.search(r"\b(?:agar|emas|balki|mumkin|chunki|lekin)\b",negative[1]):
        team=original[:len(negative[1])]
        return team+' не проиграет.'
    positive=re.fullmatch(r"(.+?)\s+g'alaba\s+qozonadi",t)
    if positive and not re.search(r"\b(?:agar|emas|balki|mumkin|chunki|lekin)\b",positive[1]):
        return original[:len(positive[1])]+' победит.'
    return None


def sensitive(text):
    return bool(re.search(r"total|tanlov|mag'lub|bo'lmay|g'alaba|\b(?:1x|x2|fora|emas)\b",norm(text)))
