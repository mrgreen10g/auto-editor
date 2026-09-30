"""Offline NHL name vocabulary. Names are not evidence of transfers or injuries."""
import re
import unicodedata
from collections import defaultdict
from functools import lru_cache
from .nhl_roster import ROSTERS

# Broadcast spellings and observed ASR variants. Generic transliteration below
# is only an additional lookup alias, never text asserted on screen.
_RU = '''Pavel Dorofeyev|Павел Дорофеев|дарафеев
Oliver Bjorkstrand|Оливер Бьоркстранд|бьюерк странт|бьеркстранд|бьорк странд
Eeli Tolvanen|Ээли Толванен
Joe Veleno|Джо Велено
Sean Durzi|Шон Дурзи
Marcus Pettersson|Маркус Петтерссон|пейт петерсон|петерсон|петерссон
Elias Pettersson|Элиас Петтерссон|пейт петерсон|петерсон|петерссон
Nikita Kucherov|Никита Кучеров
Brayden Point|Брэйден Пойнт|брейден пойнт
Jake Guentzel|Джейк Гюнцель|джейк генцел
Brandon Hagel|Брэндон Хэйгел|хейгл|хэгел|хейгел
Victor Hedman|Виктор Хедман
Andrei Vasilevskiy|Андрей Василевский
Yanni Gourde|Янни Гурд|янни горд|я не гурт
Dominic James|Доминик Джеймс
Igor Shesterkin|Игорь Шестёркин|шестеркин
Connor Bedard|Коннор Бедард|бедарда
Bowen Byram|Боуэн Байрэм|байрам
Patrick Kane|Патрик Кейн|кэйн
Teuvo Teravainen|Теуво Терявяйнен|теравайнен
Frank Nazar|Фрэнк Назар
Spencer Knight|Спенсер Найт
Vincent Trocheck|Винсент Трочек|троучек
Anders Lee|Андерс Ли
Clayton Keller|Клейтон Келлер
Logan Cooley|Логан Кули
Dylan Guenther|Дилан Гюнтер
Nick Schmaltz|Ник Шмальц
Mikhail Sergachev|Михаил Сергачёв|сергачев
Anthony Mantha|Энтони Манта
Evan Rodrigues|Эван Родригес
Luke Evangelista|Люк Евангелиста
Jack Hughes|Джек Хьюз
Luke Hughes|Люк Хьюз
Quinn Hughes|Куинн Хьюз
Nico Hischier|Нико Хишир|хишер
Jesper Bratt|Йеспер Братт|еспер братт
Timo Meier|Тимо Майер|майер
Dougie Hamilton|Дуги Хэмилтон|хэмилтон
Arseny Gritsyuk|Арсений Грицюк
Matvei Michkov|Матвей Мичков
Travis Konecny|Трэвис Конекны|конекни
Sean Couturier|Шон Кутюрье
Trevor Zegras|Тревор Зеграс
Owen Tippett|Оуэн Типпетт
Connor McDavid|Коннор Макдэвид|макдевид
Leon Draisaitl|Леон Драйзайтль|драйзайтл
Nathan MacKinnon|Натан Маккиннон|маккиннон
Cale Makar|Кейл Макар|кэйл макар
Mikko Rantanen|Микко Рантанен
Sidney Crosby|Сидни Кросби
Evgeni Malkin|Евгений Малкин
Alex Ovechkin|Александр Овечкин|алекс овечкин
Kirill Kaprizov|Кирилл Капризов
Artemi Panarin|Артемий Панарин
David Pastrnak|Давид Пастрняк|пастрнак
Auston Matthews|Остон Мэттьюс|остон мэтьюс|мэттьюс|мэтьюс
William Nylander|Вильям Нюландер|ньюландер
Mitch Marner|Митч Марнер
John Tavares|Джон Таварес
Jack Eichel|Джек Айкел|айкел|айхел
Mark Stone|Марк Стоун
Sam Reinhart|Сэм Райнхарт|райнхарт|рейнхарт
Aleksander Barkov|Александр Барков
Matthew Tkachuk|Мэттью Ткачук
Brady Tkachuk|Брэди Ткачук
Sergei Bobrovsky|Сергей Бобровский
Brad Marchand|Брэд Маршан
Sebastian Aho|Себастьян Ахо
Andrei Svechnikov|Андрей Свечников
Seth Jarvis|Сет Джарвис
Pyotr Kochetkov|Пётр Кочетков
Ilya Sorokin|Илья Сорокин
Semyon Varlamov|Семён Варламов
Alexander Romanov|Александр Романов
Mathew Barzal|Мэтью Барзал
Bo Horvat|Бо Хорват
Mika Zibanejad|Мика Зибанежад
J.T. Miller|Джей Ти Миллер
Adam Fox|Адам Фокс
Vladislav Gavrikov|Владислав Гавриков
Alexis Lafreniere|Алекси Лафреньер
Igor Chernyshov|Игорь Чернышов
Macklin Celebrini|Маклин Селебрини|селебрини
Will Smith|Уилл Смит
Yaroslav Askarov|Ярослав Аскаров
Ivan Demidov|Иван Демидов
Nick Suzuki|Ник Сузуки
Cole Caufield|Коул Кофилд|кауфилд
Juraj Slafkovsky|Юрай Слафковски
Lane Hutson|Лэйн Хатсон
Filip Forsberg|Филип Форсберг
Roman Josi|Роман Йози
Juuse Saros|Юусе Сарос
Steven Stamkos|Стивен Стэмкос|стамкос
Jason Robertson|Джейсон Робертсон
Wyatt Johnston|Уайатт Джонстон
Jake Oettinger|Джейк Эттингер
Miro Heiskanen|Миро Хейсканен
Roope Hintz|Роопе Хинц
Kyle Connor|Кайл Коннор
Mark Scheifele|Марк Шайфли
Josh Morrissey|Джош Моррисси
Gabriel Vilardi|Габриэль Виларди
Vladislav Namestnikov|Владислав Наместников
Tim Stutzle|Тим Штюцле
Drake Batherson|Дрейк Батерсон
Claude Giroux|Клод Жиру
Artem Zub|Артём Зуб
Dylan Larkin|Дилан Ларкин
Lucas Raymond|Лукас Рэймонд|реймонд
Moritz Seider|Мориц Зайдер
Alex DeBrincat|Алекс Дебринкэт|дебринкат
Tage Thompson|Тейдж Томпсон
Rasmus Dahlin|Расмус Далин
Zach Werenski|Зак Веренски
Adam Fantilli|Адам Фантилли
Dmitri Voronkov|Дмитрий Воронков
Ivan Provorov|Иван Проворов
Valeri Nichushkin|Валерий Ничушкин
Martin Necas|Мартин Нечас
Devon Toews|Девон Тэйвз|тэйвз
Gabriel Landeskog|Габриэль Ландеског
Pavel Buchnevich|Павел Бучневич
Robert Thomas|Роберт Томас
Jordan Kyrou|Джордан Кайру
Jordan Binnington|Джордан Биннингтон
Tom Wilson|Том Уилсон
Dylan Strome|Дилан Строум
Aliaksei Protas|Алексей Протас
Ilya Protas|Илья Протас
Nikita Zadorov|Никита Задоров
Jeremy Swayman|Джереми Свейман
Charlie McAvoy|Чарли Макэвой
Marat Khusnutdinov|Марат Хуснутдинов
Leo Carlsson|Лео Карлссон
Cutter Gauthier|Каттер Готье
Pavel Mintyukov|Павел Минтюков
Nikita Nesterenko|Никита Нестеренко
Beckett Sennecke|Беккет Сеннеке
Lukas Dostal|Лукаш Достал
Kirill Marchenko|Кирилл Марченко
Mats Zuccarello|Матс Цуккарелло
Adrian Kempe|Адриан Кемпе
Quinton Byfield|Куинтон Байфилд
Drew Doughty|Дрю Даути
Kevin Fiala|Кевин Фиала
Matty Beniers|Мэтти Бенирс
Jared McCann|Джаред Макканн
Shane Wright|Шейн Райт
Vince Dunn|Винс Данн
Jonathan Huberdeau|Джонатан Юбердо
Nazem Kadri|Назем Кадри
Dustin Wolf|Дастин Вольф
Yegor Sharangovich|Егор Шарангович
Maxim Tsyplakov|Максим Цыплаков
Daniil But|Даниил Бут
Dmitri Simashev|Дмитрий Симашев
Danila Yurov|Данила Юров
Roman Kantserov|Роман Канцеров'''


def plain(text):
    # Strip Latin accents without turning Cyrillic й into и (team names use й).
    return ''.join(''.join(v for v in unicodedata.normalize('NFKD',c) if not unicodedata.combining(v))
                   if 'LATIN' in unicodedata.name(c,'') else c
                   for c in text.lower().replace('ё','е'))


def translit(text):
    text=plain(text)
    for a,b in [('shch','щ'),('sh','ш'),('ch','ч'),('kh','х'),('zh','ж'),('th','т'),
                ('ph','ф'),('oo','у'),('ee','и'),('ya','я'),('yu','ю'),('yo','е')]:text=text.replace(a,b)
    return text.translate(str.maketrans(dict(zip('abcdefghijklmnopqrstuvwxyz',
        ['а','б','к','д','е','ф','г','х','и','дж','к','л','м','н','о','п','к','р','с','т','у','в','в','кс','и','з']))))


PLAYERS=tuple(sorted(set(n for team in ROSTERS.values() for n in team)))
_IDS={name:'pl'+''.join(chr(97+(i//26**k)%26) for k in (3,2,1,0)) for i,name in enumerate(PLAYERS)}
RUSSIAN={};EXTRA={}
for row in _RU.splitlines():
    name,ru,*aliases=row.split('|');RUSSIAN[name]=ru;EXTRA[name]=aliases


@lru_cache(maxsize=1)
def vocabulary():
    aliases=defaultdict(set)
    first_names={plain(n.split()[0]) for n in PLAYERS}
    first_names|={plain(n.split()[0]) for n in RUSSIAN.values()}
    blocked=first_names|{'back','power','white','brown','young'}
    for name in PLAYERS:
        variants=[name,translit(name)]
        last=name.split()[-1]
        if len(last)>=4:variants.extend([last,translit(last)])
        if name in RUSSIAN:
            variants.append(RUSSIAN[name]);surname=RUSSIAN[name].split()[-1]
            if len(surname)>=4:variants.append(surname)
            variants.extend(EXTRA[name])
        for v in variants:
            v=plain(v).strip()
            if v in blocked:continue
            aliases[v].add(name)
            # Russian noun cases, without broad prefix matching.
            if re.fullmatch('[а-я -]+',v) and v[-1] not in 'аеёиоуыэюяьй':
                for ending in ('а','у','ом','е'):aliases[v+ending].add(name)
    pattern=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(s) for s in sorted(aliases,key=lambda s:(-len(s),s)))+r')(?!\w)',re.I)
    return aliases,pattern


def mentions(text):
    aliases,pattern=vocabulary();out=[]
    for m in pattern.finditer(plain(text)):
        candidates=aliases[m[0]]
        # A shared surname identifies a family name, not an invented full name.
        name=next(iter(candidates)) if len(candidates)==1 else None
        label=RUSSIAN.get(name,name) if name else text[m.start():m.end()].strip()
        out.append((m.start(),m.end(),label,name))
    return out


@lru_cache(maxsize=8192)
def normalize_speech(text):
    aliases,pattern=vocabulary()
    # Six-letter tokens stay intact in ru_speech.tokens. Ambiguous surnames
    # remain lexical words and never select a particular player.
    def replace(m):
        names=aliases[m[0]]
        if len(names)>1 and all(n.endswith('Pettersson') for n in names):return 'петтерссон'
        return _IDS[next(iter(names))] if len(names)==1 else m[0]
    return pattern.sub(replace,plain(text))


def prompt_names(text):
    return list(dict.fromkeys(name for _,_,_,name in mentions(text) if name))


def cards(block,lines,existing):
    """Group spoken name lists; retain facts already covered by other cards."""
    from .timeline import Card,frame
    if block.kind!='analysis':return []
    out=[];last={};i=0
    while i<len(lines):
        line=lines[i];found=mentions(line.text)
        if not found or any(c.line==i for c in existing):i+=1;continue
        names=list(dict.fromkeys(x[2] for x in found));end=line.end;j=i+1
        residual=line.text
        for a,z,_,_ in reversed(found):residual=residual[:a]+residual[z:]
        bare=not re.sub(r'[\s.,;:!?—–-]|\bи\b','',residual,flags=re.I)
        if bare:
            while j<len(lines) and len(names)<3:
                nxt=mentions(lines[j].text);rest=lines[j].text
                for a,z,_,_ in reversed(nxt):rest=rest[:a]+rest[z:]
                if not nxt or any(c.line==j for c in existing) or re.sub(r'[\s.,;:!?—–-]|\bи\b','',rest,flags=re.I):break
                names=list(dict.fromkeys(names+[x[2] for x in nxt]));end=lines[j].end;j+=1
        # A mention with analysis context, or an explicitly spoken name list.
        useful=bare or bool(re.search(r'приш[её]л|добав|состав|сезон|гол|шайб|очк|бомбард|готов|здоров|основной вариант|лидер|возвращ|атак|защит|вратар|забил|набрал|без\b|есть\b|hujum|himoya|gol|jarohat|tarkib|keldi|kuchli|ochko',line.text,re.I))
        names=[n for n in names if line.start-last.get(n,-100)>=20]
        if useful and names and end-line.start>=.6 and not any(c.start<end and c.end>line.start for c in existing):
            text='\n'.join(names[:3]);reason=next((l.review_reason for l in lines[i:j] if l.review_reason),'')
            out.append(Card(frame(line.start),frame(end),'ИГРОКИ NHL',text,i,review_reason=reason))
            for name in names:last[name]=line.start
        i=j
    return out
