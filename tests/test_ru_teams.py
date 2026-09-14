"""Russian club names must survive import, source selection and episode framing."""
import unittest

from hockey_editor.event_rules import requests_for, suggested_names, team_position
from hockey_editor.framing import split_full_script, prepared_script, framing_cards
from hockey_editor.model import Block, MatchSource, Project
from hockey_editor.timeline import Line
from hockey_editor.episode import assembly_project


class RussianTeamsTests(unittest.TestCase):
    def test_source_names_in_file_order(self):
        self.assertEqual(suggested_names('Шанхайские Драконы — СКА 74, 6 сентября 2025.mp4'),
                         ['Шанхайские Драконы', 'СКА'])
        self.assertEqual(suggested_names('Нефтехимик — Шанхайские Драконы 45 ОТ, 6 сентября.mp4'),
                         ['Нефтехимик', 'Шанхайские Драконы'])
        self.assertEqual(suggested_names('ЦСКА — Нефтехимик.mp4'), ['ЦСКА', 'Нефтехимик'])

    def test_inflections_and_short_names(self):
        for phrase in ('Шанхайские Драконы', 'с «Шанхайскими Драконами»',
                       'против «Шанхайских Драконов»', '«Шанхай»', 'атака «Драконов»'):
            self.assertIsNotNone(team_position('Шанхайские Драконы', phrase))
            self.assertEqual(suggested_names(phrase), ['Шанхайские Драконы'])
        self.assertIsNotNone(team_position('Шанхай', 'Шанхайские Драконы'))
        self.assertIsNotNone(team_position('Нефтехимик', 'поражение от «Нефтехимика»'))
        self.assertIsNone(team_position('СКА', 'ЦСКА'))
        self.assertIsNone(team_position('Шанхайские Драконы', 'СКА — Лада'))

    def test_script_and_all_intro_outro_cards(self):
        intro=('Всем привет! В Омске «Автомобилист» сыграет с «Авангардом». '
               '«Локомотив» едет в Челябинск. СКА встретится с «Шанхайскими Драконами».')
        titles=['АВАНГАРД — АВТОМОБИЛИСТ', 'ТРАКТОР — ЛОКОМОТИВ', 'СКА — ШАНХАЙСКИЕ ДРАКОНЫ']
        bets=['Поэтому мой основной выбор — «Автомобилист» с форой плюс полторы шайбы.',
              'Основной выбор — «Локомотив» с форой ноль.',
              'Поэтому мой основной выбор — тотал больше пяти шайб.']
        outro=('Итак, повторю.\n«Авангард» — «Автомобилист»: «Автомобилист» с форой плюс полторы.\n'
               '«Трактор» — «Локомотив»: «Локомотив» с форой ноль.\n'
               'СКА — «Шанхайские Драконы»: тотал больше пяти.\nВсем удачи и до встречи!')
        text=intro+'\n\n'+'\n\n'.join(t+'\n'+bet for t,bet in zip(titles,bets))+'\n\n'+outro
        start,blocks,end=split_full_script(text)
        self.assertEqual([t for t,_ in blocks], titles)
        self.assertNotIn(titles[2], blocks[1][1])
        self.assertEqual(start,intro);self.assertEqual(end,outro)
        p=Project(blocks=[Block(title=t,script=s) for t,s in blocks])
        p.intro.script=start;p.outro.script=end
        result=[]
        for block in (p.intro,p.outro):
            lines=[Line(t,i*5,(i+1)*5) for i,t in enumerate(prepared_script(block).splitlines())]
            cards,_=framing_cards(assembly_project(p),block,lines,lines[-1].end)
            result.append(cards)
        self.assertEqual([c.text for c in result[0]],titles)
        self.assertEqual([c.forecast_id for c in result[1]],[b.uid for b in p.blocks])
        self.assertEqual([c.text for c in result[1]],
                         ['Автомобилист\nФора (+1.5)','Локомотив\nФора (0)','Тотал больше (5)'])

    def test_historical_source_and_score_order(self):
        primary=MatchSource('head.mp4','СКА','Шанхайские Драконы')
        other=MatchSource('past.mp4','Нефтехимик','Шанхайские Драконы')
        block=Block(title='СКА — Шанхайские Драконы',match_ids=[primary.id,other.id],
                    script='«Драконы» выиграли 5:4 в овертайме у «Нефтехимика».')
        event=requests_for(block,[primary,other])[0]
        self.assertEqual(event.source_id,other.id)
        self.assertEqual(event.score,[4,5])


if __name__=='__main__':unittest.main()
