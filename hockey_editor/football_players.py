"""Seed name vocabulary, NOT a complete or automatically current squad database.
Names only; no ages, results, injuries, or club affiliations.
Sources checked 2026-09-29:
https://www.uefa.com/european-qualifiers/teams/47--germany/squad/
https://www.uefa.com/european-qualifiers/teams/147--serbia/squad/
https://www.uefa.com/european-qualifiers/teams/35--denmark/squad/
https://www.uefa.com/european-qualifiers/teams/110--portugal/squad/
https://www.uefa.com/european-qualifiers/teams/144--wales/squad/
https://www.uefa.com/european-qualifiers/teams/101/squad/
"""
import re,unicodedata
NAMES='''Oliver Baumann;Alexander Nübel;Antonio Rüdiger;Jonathan Tah;Nico Schlotterbeck;Joshua Kimmich;Leon Goretzka;Florian Wirtz;Leroy Sané;Serge Gnabry;Nick Woltemade;Karim Adeyemi
Predrag Rajković;Djordje Petrović;Strahinja Pavlović;Nikola Milenković;Nemanja Maksimović;Saša Lukić;Filip Kostić;Lazar Samardžić;Luka Jović;Aleksandar Mitrović;Dušan Vlahović;Andrija Živković
Kasper Schmeichel;Mads Hermansen;Joachim Andersen;Andreas Christensen;Joakim Mæhle;Christian Eriksen;Christian Nørgaard;Morten Hjulmand;Pierre-Emile Højbjerg;Rasmus Højlund;Mikkel Damsgaard;Kasper Dolberg
Diogo Costa;Rúben Dias;Diogo Dalot;Nuno Mendes;João Cancelo;Bruno Fernandes;Bernardo Silva;João Neves;Cristiano Ronaldo;Gonçalo Ramos;João Félix;Rafael Leão
Karl Darlow;Danny Ward;Chris Mepham;Neco Williams;Ben Davies;Joe Rodon;Ethan Ampadu;David Brooks;Harry Wilson;Aaron Ramsey;Brennan Johnson;Daniel James
Ørjan Nyland;Leo Østigård;Julian Ryerson;Kristoffer Ajer;Patrick Berg;Sander Berge;Martin Ødegaard;Antonio Nusa;Oscar Bobb;Alexander Sørloth;Erling Haaland;Jørgen Strand Larsen'''
PLAYERS=tuple(v.strip() for v in NAMES.replace('\n',';').split(';') if v.strip())

# Name identities only, not current club membership. PL/UEFA player directories:
# https://www.premierleague.com/en/players
# https://www.uefa.com/uefachampionsleague/clubs/players/
RU_NAMES='''Erling Haaland|Эрлинг Холанд|Холанд|Хааланд
Bukayo Saka|Букайо Сака
Cole Palmer|Коул Палмер
Mohamed Salah|Мохамед Салах|Мохаммед Салах
Martin Ødegaard|Мартин Эдегор|Эдегор|Эдегард
Declan Rice|Деклан Райс
William Saliba|Вильям Салиба|Уильям Салиба
Gabriel Martinelli|Габриэл Мартинелли
Kai Havertz|Кай Хаверц
Gabriel Jesus|Габриэл Жезус
David Raya|Давид Райя
Viktor Gyökeres|Виктор Дьёкереш|Дьекереш|Гьокереш
Bruno Fernandes|Бруну Фернандеш|Бруно Фернандеш
Marcus Rashford|Маркус Рэшфорд|Рашфорд
Amad Diallo|Амад Диалло
Mason Mount|Мейсон Маунт
Harry Maguire|Гарри Магуайр
Lisandro Martínez|Лисандро Мартинес
Matheus Cunha|Матеус Кунья
Bryan Mbeumo|Брайан Мбемо
Benjamin Šeško|Беньямин Шешко
Phil Foden|Фил Фоден
Rodri|Родри
Rúben Dias|Рубен Диаш
Bernardo Silva|Бернарду Силва
Jérémy Doku|Жереми Доку
Omar Marmoush|Омар Мармуш
Virgil van Dijk|Вирджил ван Дейк
Alisson Becker|Алисон Бекер|Алиссон Беккер
Alexis Mac Allister|Алексис Мак Аллистер
Dominik Szoboszlai|Доминик Собослаи
Florian Wirtz|Флориан Вирц
Alexander Isak|Александр Исак
Hugo Ekitiké|Юго Экитике
Anthony Gordon|Энтони Гордон
Bruno Guimarães|Бруно Гимарайнс
Sandro Tonali|Сандро Тонали
Enzo Fernández|Энцо Фернандес
Moisés Caicedo|Мойсес Кайседо
João Pedro|Жоао Педро
Reece James|Рис Джеймс
Micky van de Ven|Микки ван де Вен
James Maddison|Джеймс Мэддисон
Dominic Solanke|Доминик Соланке
Ollie Watkins|Олли Уоткинс
Morgan Rogers|Морган Роджерс
Emiliano Martínez|Эмилиано Мартинес
Chris Wood|Крис Вуд
Morgan Gibbs-White|Морган Гиббс Уайт|Гиббс-Уайт
Elliot Anderson|Эллиот Андерсон
Jarrod Bowen|Джаррод Боуэн
Jean-Philippe Mateta|Жан-Филипп Матета
Eberechi Eze|Эберечи Эзе
João Palhinha|Жоао Пальинья
Kylian Mbappé|Килиан Мбаппе
Lamine Yamal|Ламин Ямаль
Vinícius Júnior|Винисиус Жуниор
Jude Bellingham|Джуд Беллингем
Harry Kane|Гарри Кейн
Robert Lewandowski|Роберт Левандовски
Ousmane Dembélé|Усман Дембеле
Lautaro Martínez|Лаутаро Мартинес
Khvicha Kvaratskhelia|Хвича Кварацхелия
Alexander Golovin|Александр Головин
Aleksey Miranchuk|Алексей Миранчук
Matvey Safonov|Матвей Сафонов
Konstantin Tyukavin|Константин Тюкавин
Sergey Pinyaev|Сергей Пиняев
Maksim Glushenkov|Максим Глушенков
Eduard Spertsyan|Эдуард Сперцян
Eldor Shomurodov|Эльдор Шомуродов
Abdukodir Khusanov|Абдукодир Хусанов
Abbosbek Fayzullaev|Аббосбек Файзуллаев
Oston Urunov|Остон Урунов
Jaloliddin Masharipov|Джалолиддин Машарипов'''
RUSSIAN={r.split('|')[0]:r.split('|')[1] for r in RU_NAMES.splitlines()}
EXTRA={r.split('|')[0]:r.split('|')[1:] for r in RU_NAMES.splitlines()}
PLAYERS=tuple(dict.fromkeys([*PLAYERS,*EXTRA]))

def plain(text):
    text=text.casefold().translate(str.maketrans({'ø':'o','æ':'ae','đ':'d'}))
    return ''.join(c for c in unicodedata.normalize('NFKD',text) if not unicodedata.combining(c))

def mentioned_names(text):
    t=plain(text);hits=[];surnames={}
    for name in PLAYERS:
        for alias in [name,*EXTRA.get(name,[])]:
            surname=plain(alias.split()[-1]);surnames.setdefault(surname,set()).add(name)
    for name in PLAYERS:
        aliases=[name,*EXTRA.get(name,[])]
        aliases += [v.split()[-1] for v in aliases if len(surnames[plain(v.split()[-1])])==1]
        for alias in aliases:
            pattern=re.escape(plain(alias))
            if re.search('[а-я]',pattern):
                if pattern.endswith(('а','я','ь')) and len(pattern)>4:pattern=pattern[:-1]
                suffix=r'[а-я]*'
            else:suffix=r"(?:ning|ni|ga|da|dan)?"
            m=re.search(r'(?<!\w)'+pattern+suffix+r'(?!\w)',t)
            if m:hits.append((m.start(),name));break
    return [n for _,n in sorted(hits)]


def cards(block,lines,existing):
    from .timeline import Card
    if block.kind!='analysis':return []
    result=[];seen={}
    for i,line in enumerate(lines):
        names=mentioned_names(line.text)
        names=[n for n in names if line.start-seen.get(n,-100)>=20]
        if not names or line.end-line.start<.6 or any(c.start<line.end and c.end>line.start for c in existing):continue
        text='\n'.join((RUSSIAN.get(n,n) if block.language=='ru' else n) for n in names[:3])
        result.append(Card(line.start,line.end,'ИГРОКИ',text,i,review_reason=line.review_reason))
        for n in names:seen[n]=line.start
    return result
