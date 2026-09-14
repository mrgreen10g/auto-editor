"""Cases from the multi-league author corpus, plus ambiguous-name counterexamples."""
import json
from pathlib import Path
import unittest
from hockey_editor.team_names import ru_file_names, football_names, football_positions
from hockey_editor.event_rules import team_position, suggested_names, topic_for_phrase, requests_for
from hockey_editor.framing import split_full_script, pair_matches
from hockey_editor.uzbek import parse_script, mentions
from hockey_editor.uz_speech import pair_hits, name_hits
from hockey_editor.model import Block, MatchSource

def words(text):return [{'word':w} for w in text.split()]

class TeamCatalogTests(unittest.TestCase):
    def test_all_corpus_headings_import_in_order(self):
        samples=json.loads((Path(__file__).parent/'fixtures'/'team_headings.json').read_text(encoding='utf-8'))
        self.assertEqual(len(samples),26)
        self.assertEqual(sum(len(s['headings']) for s in samples),80)
        for sample in samples:
            titles=sample['headings']
            with self.subTest(sample=sample['file'],profile=sample['profile']):
                if sample['profile']=='ru':
                    script='Всем привет!\n'+'\n'.join(t+'\nТекст разбора.' for t in titles)+'\nИтак, повторю. До встречи!'
                    _,blocks,_=split_full_script(script)
                    self.assertEqual([t for t,_ in blocks],titles)
                    self.assertTrue(all(len(ru_file_names(t+'.mp4'))==2 for t in titles))
                else:
                    script='Лига | LONG SSENARIY\n8–10 daqiqa\n'+'\n'.join(titles)+'\nKIRISH\nSalom.\n'
                    script+='\n'.join(t+'\n1:00–2:00\nMening tanlovim — 1,5 tadan ko\'p gol.' for t in titles)
                    script+='\nYAKUNIY EKSPRESS\n'+titles[0]+'\nTakrorlayman.\nYAKUNIY CTA\nKo\'rishguncha.'
                    _,blocks,end=parse_script(script)
                    self.assertEqual([b.title.casefold() for b in blocks],[t.casefold() for t in titles])
                    self.assertIn('Takrorlayman',end.script)
                    for b in blocks:
                        self.assertTrue(pair_hits(b.title,words(b.title.replace(' — ',' va '))))

    def test_hockey_cities_and_inflections(self):
        examples=[('Металлург','Магнитка забрасывала три шайбы.'),('Торпедо','Нижегородцы начали с победы.'),
                  ('Амур','Хабаровчане сравняли счёт.'),('Салават Юлаев','Уфа проиграла.'),
                  ('Сибирь','Новосибирцы выиграли.'),('Барыс','Астанчане уступили.'),
                  ('Нефтехимик','Нижнекамцы выиграли.'),('Локомотив','У ярославцев победа.'),
                  ('Лада','Тольяттинцы не проиграли.'),('Адмирал','Владивосток не проигрывает.'),
                  ('Автомобилист','Екатеринбуржцы выиграли.'),('Авангард','Омичи победили.'),
                  ('Трактор','Челябинцы проиграли.'),('Ак Барс','Победа Казани.'),('Северсталь','Череповец не проиграл.')]
        for club,phrase in examples:self.assertIsNotNone(team_position(club,phrase),(club,phrase))
        self.assertEqual(topic_for_phrase('Амур','Магнитка прибавила.','Металлург — Амур'),'Металлург')
        self.assertEqual(suggested_names('На Кубке Минска победили Сибирь 3:1.'),['Сибирь'])
        self.assertIsNone(team_position('Динамо Минск','Матч прошёл в Минске.'))

    def test_distinct_dynamo_and_contextual_cities(self):
        self.assertIsNone(team_position('Динамо Москва','минское «Динамо»'))
        self.assertIsNone(team_position('Динамо Минск','московское «Динамо»'))
        self.assertEqual(ru_file_names('Динамо Минск — Динамо Москва 3-1.mp4'),['Динамо Минск','Динамо Москва'])
        self.assertFalse(pair_matches('московское Динамо',Block(title='Динамо Москва — Динамо Минск')))
        self.assertTrue(pair_matches('Москва сыграет с Минском',Block(title='Динамо Москва — Динамо Минск')))
        self.assertFalse(pair_matches('Москва сыграет в Москве',Block(title='ЦСКА — Спартак')))
        self.assertIsNone(team_position('СКА','Армейцы победили.'))
        self.assertIsNotNone(team_position('ЦСКА','Армейцы победили.',('ЦСКА','Спартак')))
        self.assertIsNone(team_position('ЦСКА','Армейцы победили.',('ЦСКА','СКА')))
        self.assertEqual(ru_file_names('СКА-ВМФ — Нефтяник.mp4'),['СКА-ВМФ','Нефтяник'])

    def test_transliterations_suffixes_and_short_names(self):
        pairs=[('Liverpool — Fulham','Liverpul Fulhem'),('Chelsea — Hull','Chelsi Hall'),
               ('Coventry City — Brighton','Koventri Siti Brayton'),('Tottenham — Everton','Tottenxemning Everton'),
               ('PSG — Monaco','PSJ Monako'),("Xorazm Urganch — So'g'diyona","Xorazm So‘g‘diyonaning"),
               ("Lokomotiv Toshkent — Mash'al","Lokomotiv Mash’alga"),('OKMK — Paxtakor','AGMK Pakhtakor'),
               ('Rayo Vallecano — Espanyol','Rayo Valyekano Espanyol')]
        for title,text in pairs:
            self.assertTrue(pair_hits(title,words(text)),(title,text))
            self.assertTrue(mentions(title,text),(title,text))
        self.assertEqual(football_names('Liverpool — Fulham 2-0 highlights.mp4'),['Liverpool','Fulham'])
        self.assertEqual(football_names('Манчестер Юнайтед — Манчестер Сити.mp4'),['Manchester United','Manchester City'])

    def test_shared_football_words_do_not_make_a_pair(self):
        title='Manchester United — Manchester City'
        for text in ('Manchester Manchester','Manchester United va Ipswich Town','Koventri Siti Brayton'):
            self.assertFalse(pair_hits(title,words(text)),text)
            self.assertFalse(mentions(title,text),text)
        self.assertTrue(pair_hits(title,words('Manchester Yunayted va Manchester Siti')))
        self.assertFalse(name_hits('PSG',words('pas')))
        self.assertFalse(football_positions('Real Madrid','Madrid London'))

    def test_city_reference_uses_the_right_historical_match(self):
        a=MatchSource('one.mp4','Металлург','Амур');b=MatchSource('two.mp4','Лада','Амур')
        block=Block(title='Металлург — Амур',match_ids=[a.id,b.id],script='Хабаровчане уступили «Ладе» 1:3.')
        event=requests_for(block,[a,b])[0]
        self.assertEqual(event.source_id,b.id);self.assertEqual(event.score,[3,1])
