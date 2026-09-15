import tempfile,threading,unittest
from pathlib import Path
from hockey_editor.model import Project,Block
from hockey_editor.episode import EpisodeEngine,assembly_project,combine,store_episode,saved_episode
from hockey_editor.framing import split_full_script,prepared_script,framing_cards,forecast_text
from hockey_editor.alignment import split_script
from hockey_editor.timeline import Line,Plan,Card
from hockey_editor.card_text import classify_card,summarize_card

PAIRS=['Сибирь — Нефтехимик','Металлург — Спартак','Салават Юлаев — Ак Барс','Лада — Барыс','Сочи — ЦСКА']
PICKS=['Мой основной выбор — победа Нефтехимика с учётом овертайма и буллитов.',
       'Основной выбор — Спартак X2.',
       'Основной прогноз — победа Салавата Юлаева с учётом овертайма и буллитов.',
       'Поэтому основной выбор — Барыс X2.',
       'Мой основной выбор — индивидуальный тотал Сочи меньше двух.']

def project():
    return Project(blocks=[Block(title=t,script=t+'\n'+s) for t,s in zip(PAIRS,PICKS)])

def cards(p,block):
    rows=split_script(prepared_script(block))
    lines=[Line(t,i*5,(i+1)*5) for i,t in enumerate(rows)]
    return framing_cards(p,block,lines,len(rows)*5)

class FiveAnalysisTests(unittest.TestCase):
    def test_import_and_validation_have_no_four_block_cap_for_ru(self):
        for count in (5,8):
            pairs=(PAIRS+['Авангард — Автомобилист','Трактор — Локомотив','Динамо Москва — СКА'])[:count]
            text='Всем привет, сегодня новый выпуск.\n'+'\n'.join(t+'\nПодробно разбираем игру и выбираем прогноз.' for t in pairs)+'\nИтак, повторю. Всем удачи и до встречи!'
            intro,blocks,outro=split_full_script(text)
            self.assertEqual([t for t,s in blocks],pairs)
            with tempfile.TemporaryDirectory() as d:
                host=Path(d)/'host.mp4';host.touch();p=Project(host=str(host),blocks=[Block(title=t,script=s) for t,s in blocks])
                EpisodeEngine(p,0,Path(d)/'cache',threading.Event()).validate_all()
                p.save(Path(d)/'p.hockeyproj');self.assertEqual(len(Project.load(Path(d)/'p.hockeyproj').blocks),count)

    def test_cities_derby_and_unspoken_fifth_intro(self):
        p=project();p.intro.script='Сегодня пять матчей. В Новосибирске я пойду против хозяев, в Магнитогорске — против фаворита, в первом Зелёном дерби важен календарь, а в матче Сочи — ЦСКА не выбираю победителя.'
        found,warnings=cards(p,p.intro)
        self.assertEqual([c.text for c in found if c.title=='РАЗБОР МАТЧА'],[PAIRS[i] for i in (0,1,2,4)])
        self.assertTrue(any(PAIRS[3] in w for w in warnings))

    def test_all_five_recaps_and_comment_question(self):
        p=project();p.outro.script='Итак, повторю.\n'+'\n'.join(t+': '+s for t,s in zip(PAIRS,PICKS))+'\nНапишите в комментариях: переоцениваю форму Спартака или Металлург заслуживает такой коэффициент?\nВсем удачи и до встречи!'
        found,_=cards(p,p.outro);picks=[c for c in found if c.title=='ПРОГНОЗ']
        self.assertEqual([c.forecast_id for c in picks],[b.uid for b in p.blocks])
        self.assertEqual([c.text for c in picks],[forecast_text(b) for b in p.blocks])
        self.assertEqual(len([c for c in found if c.title=='ВОПРОС ЗРИТЕЛЯМ']),1)
        self.assertEqual(picks[-1].text,'Сочи\nИндивидуальный тотал меньше (2)')
        self.assertIn('ОТ и буллитами',picks[2].text)
        self.assertIn('X2',picks[1].text)

    def test_missing_recap_is_still_an_error(self):
        p=project();p.outro.script='Итак, повторю.\n'+'\n'.join(t+': '+s for t,s in zip(PAIRS[:4],PICKS[:4]))+'\nДо встречи!'
        with self.assertRaisesRegex(ValueError,'Сочи'):cards(p,p.outro)

    def test_exact_overtime_win_is_not_changed_to_overall_win(self):
        text='Мой выбор — победа Нефтехимика в овертайме.'
        self.assertNotIn('с ОТ и буллитами',summarize_card('ПРОГНОЗ',text))

    def test_seven_sections_survive_combination_and_reopening(self):
        p=project();p.full_video=True;runtime=assembly_project(p);plans=[]
        for i,b in enumerate(runtime.blocks):
            plans.append(Plan(i*4,i*4+3,[(0,3)],[Line(b.title,0,3)],[],[],[],3))
        merged=combine(runtime,plans)
        self.assertEqual(len(merged.sections),7)
        self.assertEqual([s['title'] for s in merged.sections],[b.title for b in runtime.blocks])
        with tempfile.TemporaryDirectory() as d:
            p.host=str(Path(d)/'host.mp4');Path(p.host).touch();store_episode(p,merged);p.save(Path(d)/'p.hockeyproj')
            self.assertEqual(len(saved_episode(Project.load(Path(d)/'p.hockeyproj')).sections),7)
