"""NHL identities, official English names and Russian broadcast spellings.

Club names checked against https://www.nhl.com/info/teams/ (2026-09-24).
Cities shared by clubs (New York) are never independent aliases.
"""
import re

# English canonical | distinctive English short name | Russian aliases (regex).
_DATA = '''Anaheim Ducks|Anaheim|анахайм\\w*|анахейм\\w*|дакс
Boston Bruins|Boston|бостон\\w*|брюинз|брюинс
Buffalo Sabres|Buffalo|баффало|сейбрз|сэйбрз
Calgary Flames|Calgary|калгари|флэймз|флеймз
Carolina Hurricanes|Carolina|каролин\\w*|харрикейнз|харрикейнс
Chicago Blackhawks|Chicago|чикаго|блэкхокс|блэкхоукс
Colorado Avalanche|Colorado|колорадо|эвеланш|аваланш
Columbus Blue Jackets|Columbus|коламбус\\w*|блю\\s+джекетс|блю\\s+джэкетс
Dallas Stars|Dallas|даллас\\w*|старз
Detroit Red Wings|Detroit|детройт\\w*|рэд\\s+уингз|ред\\s+уингз
Edmonton Oilers|Edmonton|эдмонтон\\w*|ойлерз|ойлерс
Florida Panthers|Florida|флорид\\w*|пантерз
Los Angeles Kings|Los Angeles|лос[- ]анджелес\\w*|кингз|кингс
Minnesota Wild|Minnesota|миннесот\\w*|уайлд|вайлд
Montreal Canadiens|Montreal|монреал\\w*|канадиенс|канадиенс\\w*
Nashville Predators|Nashville|нэшвилл\\w*|нешвилл\\w*|предаторз
New Jersey Devils|New Jersey|нью[- ]джерси|девилз
New York Islanders|Islanders|нью[- ]йорк\\s+айлендерс|айлендерс\\w*
New York Rangers|Rangers|нью[- ]йорк\\s+рейнджерс|рейнджерс\\w*|рэйнджерс\\w*
Ottawa Senators|Ottawa|оттав\\w*|сенаторз
Philadelphia Flyers|Philadelphia|филадельфи\\w*|флайерз|флайерс
Pittsburgh Penguins|Pittsburgh|питтсбург\\w*|питсбург\\w*|пингвинз
San Jose Sharks|San Jose|сан[- ]хосе|шаркс
Seattle Kraken|Seattle|сиэтл\\w*|сиетл\\w*|кракен\\w*
St. Louis Blues|St Louis|сент[- ]луис\\w*|блюз
Tampa Bay Lightning|Tampa Bay|тамп\\w*(?:[- ]бэй)?|лайтнинг
Toronto Maple Leafs|Toronto|торонто|мейпл\\s+лифс
Utah Mammoth|Utah|юта|юты|юте|маммот
Vancouver Canucks|Vancouver|ванкувер\\w*|кэнакс|канакс
Vegas Golden Knights|Vegas|вегас\\w*|голден\\s+найтс
Washington Capitals|Washington|вашингтон\\w*|кэпиталз|кэпиталс
Winnipeg Jets|Winnipeg|виннипег\\w*|виннипэг\\w*|джетс'''

NHL = {}
for row in _DATA.splitlines():
    canonical,short,*russian=row.split('|')
    english=[re.escape(canonical),re.escape(short)]
    # Distinctive two-word nicknames are safe too; single generic "Stars" isn't.
    if canonical=='Montreal Canadiens':english.append('montréal canadiens')
    if canonical=='St. Louis Blues':english.extend([r'st\.?\s*louis(?:\s+blues)?',r'saint\s+louis(?:\s+blues)?'])
    NHL[canonical]=(('|'.join(english+russian)).lower(),)

# Club nicknames used on their own in mixed Russian/English scripts.
NICKNAMES = {
 'Anaheim Ducks':'Ducks', 'Boston Bruins':'Bruins', 'Buffalo Sabres':'Sabres',
 'Calgary Flames':'Flames', 'Carolina Hurricanes':'Hurricanes', 'Chicago Blackhawks':'Blackhawks',
 'Colorado Avalanche':'Avalanche', 'Columbus Blue Jackets':'Blue Jackets', 'Dallas Stars':'Stars',
 'Detroit Red Wings':'Red Wings', 'Edmonton Oilers':'Oilers', 'Florida Panthers':'Panthers',
 'Los Angeles Kings':'Kings', 'Minnesota Wild':'Wild', 'Montreal Canadiens':'Canadiens|Habs',
 'Nashville Predators':'Predators', 'New Jersey Devils':'Devils', 'New York Islanders':'Islanders',
 'New York Rangers':'Rangers', 'Ottawa Senators':'Senators', 'Philadelphia Flyers':'Flyers',
 'Pittsburgh Penguins':'Penguins', 'San Jose Sharks':'Sharks', 'Seattle Kraken':'Kraken',
 'St. Louis Blues':'Blues', 'Tampa Bay Lightning':'Lightning', 'Toronto Maple Leafs':'Maple Leafs|Leafs',
 'Utah Mammoth':'Mammoth', 'Vancouver Canucks':'Canucks', 'Vegas Golden Knights':'Golden Knights',
 'Washington Capitals':'Capitals|Caps', 'Winnipeg Jets':'Jets',
}
for club,names in NICKNAMES.items():NHL[club]=(NHL[club][0]+'|'+names.lower(),)
# Alternative phonetic spellings and declined forms attested in Russian scripts.
NHL['Calgary Flames']=(NHL['Calgary Flames'][0]+r'|калгар+и\w*',)
NHL['Seattle Kraken']=(NHL['Seattle Kraken'][0]+r'|сеттл\w*|сеттал\w*',)
for club in NHL:NHL[club]=(NHL[club][0].replace('[- ]',r'\s*[- ]\s*'),)
NHL['Vegas Golden Knights']=(NHL['Vegas Golden Knights'][0]+r'|лас[- ]вегас\w*',)
NHL['Toronto Maple Leafs']=(NHL['Toronto Maple Leafs'][0]+r'|мэйпл\s+лифс|лифс',)
NHL['New Jersey Devils']=(NHL['New Jersey Devils'][0]+r'|дэвилз|девилс',)

# Broadcast/scoreboard abbreviations. NY alone deliberately remains ambiguous.
CODES='ANA BOS BUF CGY CAR CHI COL CBJ DAL DET EDM FLA LAK MIN MTL NSH NJD NYI NYR OTT PHI PIT SJS SEA STL TBL TOR UTA VAN VGK WSH WPG'.split()
for club,code in zip(NHL,CODES):
    NHL[club]=(NHL[club][0]+'|'+code.lower(),)


def speech_names(text):
    # Stable lexical identity bridges English scripts and Russian ASR. Longest
    # full aliases first; prefix boundaries prevent matching inside a word.
    for i,(club,patterns) in enumerate(NHL.items()):
        token='nhl'+chr(97+i//26)+chr(97+i%26)
        pattern=r'(?<!\w)(?:'+patterns[0]+r')(?!\w)'
        text=re.sub(pattern,token,text,flags=re.I)
    return text
