import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from dataclasses import asdict
from hockey_editor.model import Project,Block
from hockey_editor.timeline import Plan,Line,Card,Insert
from hockey_editor.review import draft_alignment,attach,resolve,pending,preserve_edits,framing_draft
from hockey_editor.episode import combine,assembly_project,store_episode
from hockey_editor.editing import validate_plan,store_plan,saved_plan
from hockey_editor.ru_speech import tokens,prepare as prepare_ru
from hockey_editor.uz_speech import prepare as prepare_uz
from hockey_editor.uzbek import parse_script
from test_uz_speech import segment


class SpeechReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.host=self.root/'host.mp4';self.host.touch()
        self.block=Block(title='Салават Юлаев — Нефтехимик',script='Мой прогноз — тотал меньше пяти с половиной. Всем удачи и до встречи!')
        self.project=Project(host=str(self.host),blocks=[self.block])
    def tearDown(self):self.temp.cleanup()
    def plan(self):
        p=Plan(10,20,[(0,10)],[Line('Мой прогноз — тотал меньше пяти с половиной.',0,5,1,'Нет совпадения','тотал меньше 5,5'),Line('Пока!',5,10)],[],[Card(0,5,'ПРОГНОЗ','ТМ 5,5',0)],[],10)
        return attach(p,self.block,self.project)
    def test_half_total_normalization(self):
        self.assertEqual(tokens('тотал меньше 5,5'),tokens('тотал меньше пяти с половиной'))
        self.assertNotEqual(tokens('5,5'),tokens('4,5'))
    def test_authored_half_total_is_not_truncated(self):
        from hockey_editor.card_text import summarize_card
        from hockey_editor.framing import forecast_text
        self.assertEqual(summarize_card('ПРОГНОЗ','Тотал меньше пяти с половиной.'),'Тотал меньше (5.5)')
        self.block.script='Основную ставку я уже выбрал.\nТотал меньше пяти с половиной.'
        self.assertEqual(forecast_text(self.block),'Тотал меньше (5.5)')
    def test_explicit_market_conflict_requires_review(self):
        from hockey_editor.review import semantic_conflict
        self.assertTrue(semantic_conflict('Тотал меньше пяти с половиной','тотал больше 5,5'))
        self.assertTrue(semantic_conflict('Тотал меньше пяти с половиной','тотал меньше 4,5'))
        self.assertFalse(semantic_conflict('Тотал меньше пяти с половиной','тотал меньше 5,5'))
    def test_missing_words_keep_script_and_audio(self):
        speech=[segment(2,4,'Совершенно другая речь.')]
        result=draft_alignment([self.block],speech,20,'Фраза не найдена')
        lines=result[self.block.uid][0]
        self.assertEqual(lines[0].start,0);self.assertEqual(lines[-1].end,20)
        self.assertTrue(all(l.review_reason for l in lines));self.assertTrue(all(l.end>l.start for l in lines))
        self.assertIn('пяти с половиной',lines[0].text)
    def test_empty_recognition_builds_reviewable_draft(self):
        lines=draft_alignment([self.block],[],20,'Нет речи')[self.block.uid][0]
        self.assertTrue(all(l.review_reason for l in lines));self.assertEqual(lines[-1].end,20)
    def test_ru_production_fallback_no_abort(self):
        with patch('hockey_editor.ru_speech.transcribe',return_value=[segment(0,20,'Не похожий на сценарий текст.')]),patch('hockey_editor.host_media.sources',return_value=[{'duration':25}]):
            result=prepare_ru(self.project,[self.block],self.root,threading.Event(),lambda _:None)
        self.assertTrue(result[self.block.uid][0][0].review_reason)
        self.assertEqual(result[self.block.uid][0][-1].end,25)
    def test_pending_card_exists_and_decisions_are_reversible(self):
        p=self.plan();ident=pending(p)[0]['id']
        p=resolve(p,ident,'confirmed',text='ТМ 5,5',start=1,end=4,owner=self.block.uid)
        self.assertFalse(pending(p));self.assertEqual(p.cards[0].start,1)
        p=resolve(p,ident,'deleted');self.assertFalse(p.cards)
        p=resolve(p,ident,'pending');self.assertEqual(len(p.cards),1);self.assertEqual(len(pending(p)),1)
    def test_invalid_manual_time_leaves_original_unchanged(self):
        p=self.plan();before=p.to_dict()
        with self.assertRaises(ValueError):resolve(p,pending(p)[0]['id'],'confirmed',start=9,end=15)
        self.assertEqual(before,p.to_dict())
    def test_save_reopen_reuses_decisions(self):
        p=self.plan();p=resolve(p,pending(p)[0]['id'],'confirmed',text='Исправлено',start=1,end=4)
        store_plan(self.project,0,p);path=self.root/'saved.hockeyproj';self.project.save(path)
        restored=Project.load(path);p=saved_plan(restored,0)
        self.assertFalse(pending(p));self.assertEqual(p.cards[0].text,'Исправлено');self.assertEqual(p.cards[0].start,1)
    def test_deletion_and_manual_changes_survive_regeneration(self):
        original=self.plan();ident=pending(original)[0]['id']
        edited=resolve(original,ident,'confirmed',text='Исправлено',start=1,end=4)
        fresh=preserve_edits(edited.to_dict(),self.plan())
        self.assertEqual(fresh.cards[0].text,'Исправлено');self.assertEqual(fresh.cards[0].start,1);self.assertFalse(pending(fresh))
        deleted=resolve(edited,ident,'deleted');fresh=preserve_edits(deleted.to_dict(),self.plan())
        self.assertFalse(fresh.cards);self.assertFalse(pending(fresh))
    def test_changed_recording_does_not_reuse_decision(self):
        p=self.plan();p=resolve(p,pending(p)[0]['id'],'confirmed',text='Старая правка')
        self.host.write_bytes(b'new recording');fresh=preserve_edits(p.to_dict(),self.plan())
        self.assertTrue(pending(fresh));self.assertNotEqual(fresh.cards[0].text,'Старая правка')
    def test_missing_recap_keeps_forecast_card(self):
        outro=Block(uid='outro',kind='outro',script='Итак, повторим. Пока!')
        cards,_=framing_draft(self.project,outro,[Line(outro.script,0,10)],10)
        self.assertTrue(any(c.forecast_id==self.block.uid and c.review_reason for c in cards))
    def test_telegram_without_link_is_reviewable(self):
        self.project.assets={'telegram':str(self.host)}
        b=Block(kind='intro',script='Прогнозы в телеграм-канале.')
        cards,_=framing_draft(self.project,b,[Line(b.script,0,10)],10)
        self.assertTrue(any(c.title=='ТЕЛЕГРАМ' and c.review_reason for c in cards))
    def test_manual_telegram_can_move_without_moving_speech(self):
        p=self.plan();p.cards[0].title='ТЕЛЕГРАМ';p.cards[0].asset=str(self.host)
        edited=resolve(p,pending(p)[0]['id'],'confirmed',start=1,end=3)
        self.assertEqual(edited.lines[0].start,0);validate_plan(edited)
    def test_episode_offsets_and_section_decisions(self):
        b=Block(title='Вторая пара',script='Мой прогноз — победа команды.');self.project.blocks.append(b)
        first=self.plan();second=copy.deepcopy(first);second.source_start=20;second.source_end=30
        second.review_items=[];second.cards[0].review_id='';second=attach(second,b,self.project)
        p=combine(self.project,[first,second]);self.assertEqual(p.review_items[1]['start'],10)
        p=resolve(p,p.review_items[1]['id'],'confirmed',start=11,end=14)
        store_episode(self.project,p)
        restored=Plan.from_dict(b.edit_plan)
        self.assertEqual(restored.review_items[0]['start'],1);self.assertEqual(restored.review_items[0]['status'],'confirmed')
    def uz_project(self):
        p=Project(host=str(self.host),profile='uz_football',full_video=True)
        p.intro=Block(uid='intro',kind='intro',language='uz',script='Salom do‘stlar. Bugun futbol haqida gaplashamiz.')
        p.blocks=[Block(title='Real Madrid — Elche',language='uz',script='Bugun Real Madrid o‘ynaydi. Mening tanlovim — Real Madrid g‘alabasi.')]
        p.outro=Block(uid='outro',kind='outro',language='uz',script='Yakuniy tanlov Real Madrid g‘alabasi. Xayr!')
        return p
    def test_uz_missing_sections_and_contradictions_go_to_review(self):
        for speech in ([segment(0,20,'Real Madrid X2 emas, boshqa variant.')],[]):
            with self.subTest(speech=bool(speech)):
                p=self.uz_project();prepare_uz(p,speech,review=True,duration=30)
                self.assertTrue(all(b.asr_lines for b in [p.intro,*p.blocks,p.outro]))
                self.assertTrue(any(l.get('review_reason') for l in p.blocks[0].asr_lines))
                self.assertIn('g‘alabasi',p.blocks[0].script)
    def test_uz_failed_strict_attempt_is_transactional(self):
        p=self.uz_project();p.blocks[0].edit_plan={'my':'edits'};before=copy.deepcopy(p)
        with self.assertRaises(ValueError):prepare_uz(p,[segment(0,20,'Noma‘lum so‘zlar.')])
        self.assertEqual(asdict(p),asdict(before))
        prepare_uz(p,[segment(0,20,'Noma‘lum so‘zlar.')],review=True,duration=30)
        self.assertEqual(p.blocks[0].edit_plan,{'my':'edits'})
    def test_uz_import_many_analyses(self):
        script='KIRISH\nSalom do‘stlar!\n'+''.join(f'CLUB {i} — TEAM {i}\nBugungi uchrashuv haqida tahlil. Mening tanlovim — g‘alaba.\n' for i in range(20))+'YAKUNIY TANLOVLAR\nTanlovlarni takrorlaymiz. Xayr!'
        _,blocks,_=parse_script(script);self.assertEqual(len(blocks),20)
    def test_uz_large_recap_does_not_enter_exponential_search(self):
        from hockey_editor.uz_forecasts import match_forecasts
        owners=[Block(title=f'Team {i}',uid=str(i)) for i in range(20)]
        refs={b.uid:'winner' for b in owners}
        candidates=[{'start':i*2,'end':i*2+1,'features':{},'text':str(i),'words':[]} for i in range(20)]
        with patch('hockey_editor.uz_forecasts.windows',return_value=candidates),patch('hockey_editor.uz_forecasts.score',side_effect=lambda c,o,r,i,owners,recap:(10,False) if c['text']==str(i) else None):
            picks=match_forecasts([],0,40,owners,refs)
        self.assertEqual(len(picks),20)

if __name__=='__main__':unittest.main()
