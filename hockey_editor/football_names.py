"""National-team names, not current squads or results.
Association names: https://www.uefa.com/nationalassociations/ (2026-09-29).
Player vocabulary comes from the user's cleaned script, without transferring
numbers, results or assertions into the speech decoder prompt.
"""
ROWS='''Albaniya|Albania|Албания
Andorra|Andorra|Андорра
Armaniston|Armenia|Армения
Avstriya|Austria|Австрия
Ozarbayjon|Azerbaijan|Азербайджан
Belarus|Belarus|Беларусь
Belgiya|Belgium|Бельгия
Bosniya va Gersegovina|Bosnia and Herzegovina|Босния и Герцеговина
Bolgariya|Bulgaria|Болгария
Xorvatiya|Croatia|Хорватия
Kipr|Cyprus|Кипр
Chexiya|Czechia|Czech Republic|Чехия
Daniya|Denmark|Дания
Angliya|England|Англия
Estoniya|Estonia|Эстония
Farer orollari|Faroe Islands|Фарерские острова
Finlyandiya|Finland|Финляндия
Fransiya|France|Франция
Gruziya|Georgia|Грузия
Germaniya|Germany|Deutschland|Германия|Nemislar
Gibraltar|Gibraltar|Гибралтар
Gretsiya|Greece|Yunoniston|Греция
Vengriya|Hungary|Венгрия
Islandiya|Iceland|Исландия
Isroil|Israel|Израиль
Italiya|Italy|Италия
Qozog'iston|Kazakhstan|Казахстан
Kosovo|Kosovo|Косово
Latviya|Latvia|Латвия
Lixtenshteyn|Liechtenstein|Лихтенштейн
Litva|Lithuania|Литва
Lyuksemburg|Luxembourg|Люксембург
Malta|Malta|Мальта
Moldova|Moldova|Молдова
Chernogoriya|Montenegro|Черногория
Niderlandiya|Netherlands|Holland|Gollandiya|Нидерланды|Голландия
Shimoliy Makedoniya|North Macedonia|Северная Македония
Shimoliy Irlandiya|Northern Ireland|Северная Ирландия
Norvegiya|Norway|Норвегия
Polsha|Poland|Польша
Portugaliya|Portugal|Португалия
Irlandiya|Republic of Ireland|Ireland|Ирландия
Ruminiya|Romania|Румыния
Rossiya|Russia|Россия
San Marino|San Marino|Сан-Марино
Shotlandiya|Scotland|Шотландия
Serbiya|Serbia|Сербия
Slovakiya|Slovakia|Словакия
Sloveniya|Slovenia|Словения
Ispaniya|Spain|Испания
Shvetsiya|Sweden|Швеция
Shveysariya|Switzerland|Shveytsariya|Швейцария
Turkiya|Türkiye|Turkey|Турция
Ukraina|Ukraine|Украина
Uels|Wales|Уэльс'''
NATIONAL={row.split('|')[0]:tuple(dict.fromkeys(row.split('|'))) for row in ROWS.splitlines()}
NATIONAL["O'zbekiston"]=("O'zbekiston",'Uzbekistan','Узбекистан')

NATIONAL['Norvegiya']+=('Norvega','Narvega','Narviga')
NATIONAL['Uels']+=('Uils','Uylas','Vels','Uyels')
NATIONAL['Portugaliya']+=('Portugiya','Portugaliy')
NATIONAL['Serbiya']+=('Serbiyo',)
