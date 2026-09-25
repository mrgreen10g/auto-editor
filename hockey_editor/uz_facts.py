"""Compact Uzbek claims, grounded in the supplied spoken sentence.

No generic keyword-to-subtitle fallback. Negated/conditional arguments are
kept verbatim as a short clause, never inverted into an asserted advantage.
"""
import re
from .uzbek import norm

ARGUMENTS=(
 (r'ufc',r'debyut|tajrib|oktagon.*ko.rgan'),
 (r'parter|stoyka|jiu.jitsu',r'xavf|ideal|kerak|daraja|ushla|asosiy'),
 (r'raqib\w*',r'almashtir|almashgan|qisqa muddat'),
 (r'ketma.ket',r'g.alaba|mag.lub'),
 (r'masofa\w*',r'nazorat|ushla|saqla|qisqartir|ishla'),
 (r'bosim\w*',r'ber|qil|oshir|chid|javob|muammo'),
 (r'temp\w*|sur.at\w*',r'oshir|yuqori|pasay|ushla'),
 (r'himoya\w*',r'kuchli|zaif|muammo|xato|ishonch'),
 (r'almashinuv\w*',r'qochma|kuchli|xavf|tort'),
 (r'tajriba\w*',r'ustun|katta|ko.p|kam|yetar|yuqori'),
 (r'kurash\w*|parter\w*|grappling\w*',r'ustun|kuchli|yaxshi|zaif|olib|o.tkaz'),
 (r'hujum\w*',r'kuchli|xavfli|tez|samarali|muammo'),
 (r'pressing\w*',r'yuqori|kuchli|faol|qil'),
 (r'qarshi hujum\w*',r'xavfli|kuchli|tez|yaxshi'),
 (r'jarohat\w*|diskvalifik\w*|safdan chiq\w*',r'.'),
)

def argument(text):
    clauses=[]
    for sentence in re.split(r'[.!?;]',text):
        clauses.extend([sentence] if len(sentence.split())<=22 else re.split(r',|\s+[—–]\s+',sentence))
    for clause in clauses:
        t=norm(clause).strip(' ,:')
        if not 3<=len(t.split())<=22:continue
        if any(re.search(a,t) and re.search(b,t) for a,b in ARGUMENTS):
            # Preserve the actual claim and its qualifiers, not a manufactured
            # two-word summary that could reverse a negation.
            if not re.search(r'agar|emas|maydi|yo.q',t):
                if 'mumkin' not in t and re.search(r'tajriba\w*\s+(?:ancha\s+)?(?:yuqori|katta|ko.p)|katta\s+tajriba',t):return 'Katta tajriba'
                if 'mumkin' not in t and 'bosim' in t and re.search(r'javob bera ol(?:adi|aydi)|javob beradi',t):return 'Bosimga javob bera oladi'
                if 'bosim' in t and 'temp' in t and 'muammo' in t:
                    return 'Bosim va temp raqibga muammo yaratishi mumkin' if 'mumkin' in t else 'Bosim va temp raqibga muammo yaratadi'
                if 'mumkin' not in t and 'temp' in t and 'oshir' in t and 'seriya' in t and re.search(r'ishla|shiloli',t):return 'Tempni oshirib, seriyalar bilan ishlaydi'
            # Keep qualifiers and negations in the clause. Trimming a prefix
            # containing them could turn an uncertain claim into an assertion.
            if re.search(r'agar|emas|maydi|yo.q|mumkin',t):
                return re.sub(r'\s+va jang$','',clause.strip(' ,:'))
            start=min((m.start() for a,b in ARGUMENTS if re.search(b,t) for m in [re.search(a,t)] if m),default=0)
            return re.sub(r'\s+va jang$','',clause.strip(' ,:')[start:])
    return ''

def combat_facts(text):
    from .combat_cards import numbers
    t=norm(text);facts=[]
    # Outcome values are tied to their nouns, not the first number in a line
    # (which may be an event number, weight or age).
    outcomes={}
    for key,pattern in [('w',r"[gq]'?alab\w*"),('l',r"ma[gq]'?lub\w*"),('d',r'durr?ang\w*')]:
        for m in re.finditer(pattern,t):
            prefix=t[:m.start()].rstrip(' ,:')
            nearby=' '.join(prefix.split()[-3:]);values=numbers(nearby)
            if key not in outcomes and values and re.search(r"(?:\d|ta|bitta|biti|ikki|uch|to.rt|besh|olti|yett?i|sakkiz|to.qqiz|o.n)\W*$",nearby):outcomes[key]=values[-1]
    if 'w' in outcomes and 'l' in outcomes:
        facts.append('REKORD: '+'–'.join(str(outcomes[k]) for k in ('w','l','d') if k in outcomes))
    for m in re.finditer(r'\byosh\w*',t):
        v=numbers(' '.join(t[:m.start()].split()[-4:]))
        if v:
            tail=t[m.end():m.end()+25]
            facts.append(f'{v[-1]} YOSH'+(' KICHIK' if 'kichik' in tail else ' KATTA' if 'katta' in tail else ''))
    for m in re.finditer(r'\b(?:cm|santimetr)\b',t):
        pre=t[:m.start()];v=numbers(' '.join(pre.split()[-5:]))
        if not v:continue
        label="QO‘L UZUNLIGI" if re.search(r"qo.l|quloch",pre[-65:]) else 'FARQ' if re.search(r'farq|baland|past|^yana ',t) else "BO‘Y"
        facts.append(f'{label}: {v[-1]} CM')
    # Counts require an explicit finish-result relation. "Every second seeks
    # a knockout" and "one dangerous punch" must never become "1 KO".
    for m in re.finditer(r'\bn(?:(?:ok|ak)aut|akod)\w*|\b(?:sabmishn|submission|sabmishen)\w*',t):
        context=t[max(0,m.start()-70):m.end()+40]
        if re.search(r'har bir|soniya|izla|agar|xavf|emas',context):continue
        pre=t[:m.start()];v=numbers(' '.join(pre.split()[-6:]))
        if v and (re.search(r'g.alaba|yakun|tugat|ta\b|tasi\b|orqali',context) or len(t.split())<=3):facts.append(f'{v[-1]} '+('SUB' if re.match('s',m.group()) else 'KO'))
    if re.search(r'bazasi|asosiy baza',t):
        for pattern,label in [(r'\bboks\b','BOKS'),(r'muay|moytay|moitay','MUAY THAI'),(r'jiu|jiu-jitsu','JIU-JITSU'),(r'kurash','KURASH')]:
            if re.search(pattern,t):facts.append('BAZA: '+label);break
    for clause in re.split(r'[;]|(?<!\d),(?!\d)',t):
        for m in re.finditer(r'foiz|%',clause):
            v=numbers(' '.join(clause[:m.start()].split()[-4:]))
            if not v or not 0<=v[-1]<=100:continue
            if re.search(r'takedown|teykdaun',clause):label='TAKEDOWN HIMOYASI' if 'himoya' in clause else 'TAKEDOWN'
            elif 'himoya' in clause:label='ZARBA HIMOYASI'
            elif re.search(r'tik turgan|standing|stoyka',clause):label='TIK HOLATDAGI ZARBALAR'
            elif re.search(r'aniq|zarba',clause):label='ZARBA ANIQLIGI'
            else:continue
            facts.append(f'{label}: {v[-1]}%')
        rate=re.search(r'(\d+[,.]\d+)\s*(?:ta\s+)?(?:muhim\s+)?zarba',clause)
        if rate and re.search(r'daqiqa|minut',clause):facts.append('ZARBA / MIN: '+rate[1].replace(',','.'))
    if re.search(r'birinchi raund',t) and re.search(r'finish|yakunlan',t):
        before=re.split(r'birinchi raund',t)[0];v=numbers(before)
        if v:facts.append(f'1-RAUNDDA YAKUN: {v[-1]}')
    if not outcomes.get('l') and len(outcomes)==1 and 'w' in outcomes:
        m=re.search(r'(.{0,35})jang(?:da|dan)?\s',t)
        if m:
            v=numbers(m[1])
            if v and v[-1]==outcomes['w']:facts.append(f"{v[-1]} JANG · {outcomes['w']} G‘ALABA")
    return list(dict.fromkeys(facts))

COMBAT_TERMS={
 'nokaut':('KO','knockout','nakaut','nakod'),
 'texnik nokaut':('TKO','technical knockout'),
 'nokdaun':('knockdown',),
 'sabmishn':('submission','sabmishen','bo‘g‘ish','og‘ritish'),
 'klinch':('clinch',), 'parter':('ground','grappling'),
 'teykdaun':('takedown','yiqitish'), 'jab':('jeb',),
 'revansh':('rematch','revanj'), 'qaror':('decision','ochkolar'),
 'yalang‘och musht':('bare-knuckle','кулачный бой'),
}
