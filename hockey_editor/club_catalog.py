"""Multilingual club identities; not season membership or current squads.

Canonical identities checked against league club directories. Transliteration
variants are editorial aliases, not separate teams.
Sources: premierleague.com/en/clubs, laliga.com/en-GB/laliga-easports/clubs,
bundesliga.com/en/bundesliga/clubs, en.legaseriea.it/team, ligue1.com/fr,
premierliga.ru/clubs, mlssoccer.com/clubs. Uzbek aliases also cover supplied scripts.
"""
ROWS = '''
Kattaqo'rg'on|Каттакурган
Metallurg|Металлург Бекабад|Металлург
Aral|Арал
TerDU|ТерДУ
G'azalkent|Газалкент
Paxtakor II|Пахтакор II|Пахтакор 2
BuxDU|БухДУ
Lochin|Лочин
Olimpik MobiUz|Олимпик МобиУз|Олимпик
FarDU|ФарДУ
Sho'rtan|Шуртан
QMU Jayxun|КМУ Джайхун|Джайхун
PSG|Paris Saint-Germain|Parij Sen Jermen|Пари Сен-Жермен|Пари Сен Жермен
Inter|Internazionale|Интернационале
Tottenham|Tottenham Hotspur|Тоттенхэм Хотспур
Athletic|Athletic Club|Атлетик Бильбао
Bayer|Bayer Leverkuzen|Байер Леверкузен
Leeds United|Leeds|Lids|Лидс|Лидс Юнайтед
Burnley|Bernli|Byornli|Бернли
Brentford|Брентфорд
Crystal Palace|Kristal Pelas|Kristal Peles|Кристал Пэлас
West Ham United|West Ham|Vest Hem|Vest Xem|Вест Хэм
Wolverhampton Wanderers|Wolverhampton|Wolves|Vulverhempton|Вулверхэмптон
Leicester City|Leicester|Lester|Лестер
Southampton|Sautgempton|Sauthempton|Саутгемптон
Sheffield United|Sheffild Yunayted|Шеффилд Юнайтед
Atletico Madrid|Atlético Madrid|Atletiko Madrid|Atletiko|Атлетико Мадрид|Атлетико
Real Sociedad|Real Sosedad|Реал Сосьедад
Real Betis|Betis|Бетис|Реал Бетис
Villarreal|Vilyarreal|Вильярреал
Sevilla|Sevilya|Севилья
Girona|Jirona|Жирона
Mallorca|Malyorka|Мальорка
Real Oviedo|Oviedo|Ovyedo|Реал Овьедо|Овьедо
Levante|Леванте
Las Palmas|Лас-Пальмас|Лас Пальмас
Real Valladolid|Valladolid|Valyadolid|Вальядолид
Leganes|Leganés|Леганес
Deportivo La Coruna|Deportivo La Coruña|Deportivo|Депортиво
Bayern Munich|Bayern Munchen|Bayern München|Bavariya|Bayern|Бавария
RB Leipzig|Leipzig|Leypsig|Leyptsig|РБ Лейпциг|Лейпциг
VfB Stuttgart|Stuttgart|Shtutgart|Shtuttgart|Штутгарт
Borussia Monchengladbach|Borussia Mönchengladbach|Borussiya Menxengladbax|Gladbach|Боруссия Менхенгладбах|Боруссия Мёнхенгладбах
Hoffenheim|Xoffenxaym|Hoffenhaym|Хоффенхайм
Freiburg|Frayburg|Фрайбург
Werder Bremen|Werder|Verder|Verder Bremen|Вердер
Wolfsburg|Volfsburg|Вольфсбург
Hamburg|Hamburger SV|Gamburg|Гамбург
Cologne|Koln|Köln|Kyoln|Кельн|Кёльн
Heidenheim|Haydenhaym|Xaydenxaym|Хайденхайм
St. Pauli|St Pauli|Sankt Pauli|Санкт-Паули|Санкт Паули
Elversberg|Elversberq|Эльверсберг
Juventus|Yuventus|Ювентус
Milan|AC Milan|Милан
Napoli|Наполи
Atalanta|Аталанта
Bologna|Bolonya|Болонья
Fiorentina|Florentina|Фиорентина
Lazio|Latsio|Лацио
Genoa|Jenoa|Дженоа
Cagliari|Kalyari|Кальяри
Lecce|Lechche|Лечче
Sassuolo|Сассуоло
Cremonese|Kremoneze|Кремонезе
Pisa|Пиза
Empoli|Эмполи
Monza|Montsa|Монца
Venezia|Venetsiya|Венеция
Frosinone|Frozinone|Фрозиноне
Marseille|Olympique Marseille|Marsel|Марсель
Nice|Nitsa|Nitstsa|Ницца
Lens|Lans|Ланс
Rennes|Renn|Ренн
Strasbourg|Strasbur|Страсбур
Brest|Stade Brestois|Брест
Nantes|Nant|Нант
Le Havre|Gavr|Гавр
Lorient|Loryan|Лорьян
Metz|Mets|Мец
Angers|Anje|Анже
Paris FC|Paris FK|Париж ФК|Париж
Reims|Reyms|Реймс
Saint Etienne|Saint-Étienne|Sent Etyen|Сент-Этьен
Montpellier|Monpelye|Монпелье
Zenit|Zenit Saint Petersburg|Zenit Sankt Peterburg|Зенит
Spartak Moscow|Spartak Moskva|Спартак Москва|Спартак-Москва
CSKA Moscow|CSKA Moskva|SSKA Moskva|ЦСКА Москва|ПФК ЦСКА
Dynamo Moscow|Dinamo Moskva|Динамо Москва|Динамо-Москва
Dynamo Makhachkala|Dinamo Maxachqala|Динамо Махачкала
Lokomotiv Moscow|Lokomotiv Moskva|Локомотив Москва
Krasnodar|Краснодар
Rostov|Ростов
Rubin Kazan|Rubin|Рубин
Krylya Sovetov|Krilya Sovetov|Крылья Советов
Akhmat Grozny|Axmat|Akhmat|Ахмат
Orenburg|Оренбург
Akron Tolyatti|Akron|Акрон
Baltika Kaliningrad|Baltika|Балтика
Pari Nizhny Novgorod|Pari NN|Pari Nijniy Novgorod|Пари НН
Sochi|Сочи
Fakel Voronezh|Fakel|Факел
Rodina Moscow|Rodina Moskva|Родина
Khimki|Ximki|Химки
Ural|Урал
Qo'qon-1912|Qo'qon|Qoqon|Kokand 1912|Коканд-1912|Коканд
Andijon|Andijan|Андижан
Dinamo Samarqand|Dinamo Samarkand|Динамо Самарканд
Qizilqum|Kyzylkum|Кызылкум
Atlanta United|Atlanta Yunayted|Атланта Юнайтед
Austin FC|Ostin|Остин
Charlotte FC|Sharlott|Шарлотт
Chicago Fire|Chikago Fayr|Чикаго Файр
FC Cincinnati|Cincinnati|Sinsinnati|Цинциннати
Colorado Rapids|Kolorado Rapids|Колорадо Рэпидз
Columbus Crew|Kolambus Kryu|Коламбус Крю
FC Dallas|Dallas|Даллас
DC United|D.C. United|Di Si Yunayted|Ди Си Юнайтед
Houston Dynamo|Xyuston Dinamo|Хьюстон Динамо
Sporting Kansas City|Sporting Kanzas Siti|Спортинг Канзас-Сити
LA Galaxy|Los Angeles Galaxy|Los Anjeles Gelaksi|Лос-Анджелес Гэлакси
Los Angeles FC|LAFC|Los Anjeles FK|Лос-Анджелес ФК
Inter Miami|Inter Mayami|Интер Майами
Minnesota United|Minnesota Yunayted|Миннесота Юнайтед
CF Montreal|CF Montréal|Monreal|КФ Монреаль|Монреаль
Nashville SC|Nashville|Neshvill|Нэшвилл
New England Revolution|Nyu Ingland Revolyushn|Нью-Инглэнд Революшн
New York Red Bulls|Nyu York Red Bulls|Нью-Йорк Ред Буллз
New York City FC|Nyu York Siti|Нью-Йорк Сити
Orlando City|Orlando Siti|Орландо Сити
Philadelphia Union|Filadelfiya Yunion|Филадельфия Юнион
Portland Timbers|Portlend Timbers|Портленд Тимберс
Real Salt Lake|Real Solt Leyk|Реал Солт-Лейк
San Diego FC|San Diego|Сан-Диего
San Jose Earthquakes|San Xose Ertqueyks|Сан-Хосе Эртквейкс
Seattle Sounders|Sietl Saunders|Сиэтл Саундерс
St. Louis City|Sent Luis Siti|Сент-Луис Сити
Toronto FC|Toronto|Торонто
Vancouver Whitecaps|Vankuver Uaytkeps|Ванкувер Уайткэпс
Benfica|Benfika|Бенфика
Porto|Порту
Sporting CP|Sporting Lisbon|Sporting Lissabon|Спортинг Лиссабон
Ajax|Ayaks|Аякс
PSV Eindhoven|PSV|PSV Eyndxoven|ПСВ
Feyenoord|Feyenoord Rotterdam|Фейеноорд
Celtic|Seltik|Селтик
Rangers|Glasgow Rangers|Reynjers|Рейнджерс
Galatasaray|Galatasaroy|Галатасарай
Fenerbahce|Fenerbahçe|Fenerbaxche|Фенербахче
Besiktas|Beşiktaş|Beshiktosh|Бешикташ
Salzburg|Red Bull Salzburg|Zalzburg|Zalsburg|Зальцбург
Slovan Bratislava|Slovan|Слован Братислава
Bodo Glimt|Bodø/Glimt|Bodo/Glimt|Bude Glimt|Будё-Глимт|Буде-Глимт
Lech Poznan|Lech Poznań|Lex Poznan|Лех Познань
'''


def extend(catalog, normalize):
    for row in ROWS.strip().splitlines():
        aliases=tuple(dict.fromkeys(row.split('|')))
        keys={normalize(a) for a in aliases}
        existing=[name for name,values in catalog.items() if keys.intersection(normalize(v) for v in values)]
        if len(existing)>1:raise ValueError('Ambiguous club catalog row: '+aliases[0])
        name=existing[0] if existing else aliases[0]
        catalog[name]=tuple(dict.fromkeys((*catalog.get(name,()),*aliases)))
