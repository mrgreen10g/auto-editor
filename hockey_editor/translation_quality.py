"""Reject unsupported additions; never turn translation into authored speech."""
import re
from collections import Counter

def issue(source,result):
    if not result.strip():return 'пустой результат'
    a=source.casefold();b=result.casefold()
    if re.search(r'аллах|всевышн|милосердн|посланник|коран|пророк|богослов',b) and not re.search(r'alloh|allah|xudo|qur.?on|payg.ambar|rasul|аллах|коран|пророк',a):return 'посторонняя тема'
    numbers=lambda s:Counter(re.sub(r'\s','',v).replace(',','.') for v in re.findall(r'\d+(?:\s*[:.,]\s*\d+)?',s))
    if numbers(a)!=numbers(b):return 'изменились числа или счёт'
    words=re.findall(r'\w+',b)
    if len(words)>max(25,len(a.split())*3):return 'необоснованное расширение текста'
    grams=Counter(tuple(words[i:i+5]) for i in range(len(words)-4))
    if any(n>=3 for n in grams.values()):return 'повторяющийся текст'
    return ''

def chunks(text,tokenizer,limit=160):
    text=text.translate(str.maketrans({c:"'" for c in '’‘ʻʼ`'}))
    for sentence in re.split(r'(?<=[.!?;])\s+|\n+',text.strip()):
        current=[]
        for word in sentence.split():
            if current and len(tokenizer.encode('<2ru> '+' '.join(current+[word]),add_special_tokens=False).tokens)>limit:
                yield ' '.join(current);current=[]
            current.append(word)
        if current:yield ' '.join(current)

def translate_piece(text,model,tokenizer,cancel):
    for beam in (2,4):
        if cancel.is_set():raise InterruptedError('Перевод отменён.')
        # Tokenize language prefix and sentence together, matching model usage.
        source=tokenizer.encode('<2ru> '+text,add_special_tokens=False).tokens+['</s>']
        out=model.translate_batch([source],beam_size=beam,max_decoding_length=384,repetition_penalty=1.1,no_repeat_ngram_size=4)[0].hypotheses[0]
        ids=[tokenizer.token_to_id(t) for t in out]
        if len(out)>=384 or any(i is None for i in ids):continue
        value=tokenizer.decode(ids,skip_special_tokens=True).strip()
        if not issue(text,value):return value
    return None
