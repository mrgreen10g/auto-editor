"""Confirmed footage must survive ASR, edits and an actual final export."""
import copy,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from dataclasses import asdict
from PIL import Image
from hockey_editor.model import Project,Block,MatchSource,EventRequest,EventSelection
from hockey_editor.timeline import Plan,Line,Card,Insert
from hockey_editor.review import attach,preserve_edits
from hockey_editor.editing import validate_plan
from hockey_editor.combat_scan import live_ranges,confident_action,DETECTOR_VERSION
from hockey_editor.goals import propose,source_signature
from hockey_editor.engine import Engine
from hockey_editor.media import run


class RegressionTests(unittest.TestCase):
    def test_football_timed_headings_and_duplicate_empty_intro(self):
        from hockey_editor.uzbek import parse_script
        from hockey_editor.recording_times import recording_ranges
        from test_uz_speech import segment
        text='''O'ZBEKISTON SUPERLIGASI
NEFTCHI — XORAZM URGANCH
PAXTAKOR — BUNYODKOR
KIRISH
KIRISH | 0:00–1:00
Assalomu alaykum. Bugun ikki uchrashuvni ko'ramiz.
NEFTCHI — XORAZM URGANCH | 1:00–4:30
Neftchi g'alabasi mening birinchi tanlovim.
PAXTAKOR — BUNYODKOR | 4:30–8:00
Paxtakor g'alabasi mening ikkinchi tanlovim.
YAKUNIY TANLOVLAR | 8:00–8:30
Ikki tanlovni takrorlaymiz.
YAKUNIY CTA | 8:30–9:00
Obuna bo'ling. Xayr!'''
        for value in (text,text.replace('KIRISH\n','')):
            a,b,z=parse_script(value)
            self.assertEqual([x.title for x in b],['Neftchi — Xorazm Urganch','Paxtakor — Bunyodkor'])
            self.assertNotIn('|',a.script+z.script)
        p=Project(profile='uz_football',intro=a,blocks=b,outro=z,recording_times='00:00 00:33 Интро\n00:34 02:24 Нефтчи Хорезм\n02:35 04:37 Пахтакор Бунёдкор\n04:38 04:40 Последний раз об выбор\n04:41 04:59 Концовка')
        speech=[segment(a,z,'Test gap.') for a,z in [(0,33),(34,144),(155,277),(278,280),(281,299)]]
        ranges=recording_ranges(p,speech)
        self.assertEqual(len(ranges),4);self.assertEqual(ranges[-1],(278,299))
        from hockey_editor.uz_speech import prepare
        with patch('hockey_editor.uz_speech._prepare',side_effect=ValueError('forecast uncertain')):
            prepare(p,speech,review=True,duration=299)
        for block,(lo,hi) in zip([p.intro,*p.blocks,p.outro],ranges):
            self.assertEqual(block.asr_lines[0]['start'],lo)
            self.assertEqual(block.asr_lines[-1]['end'],hi)

    def test_second_choice_inside_second_match_is_not_rejected_as_first(self):
        from hockey_editor.uz_forecasts import match_forecasts
        from test_uz_speech import segment
        b=Block(title='Paxtakor — Bunyodkor',language='uz')
        segments=[segment(160,168,'Ikkinchi tanlovim Paxtakor g‘alabasi.')]
        found=match_forecasts(segments,155,277,[b],{b.uid:'Paxtakor g‘alabasi'},recap=False)
        self.assertEqual(len(found),1)

    def test_two_frame_forecast_remains_reviewable_without_blocking_export(self):
        b=Block(kind='outro',uid='outro');p=Project(outro=b)
        plan=Plan(0,4.7,[(0,4.7)],[],[],[Card(50/30,52/30,'ПРОГНОЗ','Neftchi g‘alabasi',forecast_id='first')],[],4.7)
        attach(plan,b,p);validate_plan(plan,check_files=False)
        self.assertGreaterEqual(plan.cards[0].end-plan.cards[0].start,1)
        self.assertEqual(plan.cards[0].forecast_id,'first');self.assertEqual(len(plan.review_items),1)

    def test_manual_trim_does_not_delete_newly_accepted_insert(self):
        original=Insert('a.mp4',2,5,0,'A',source_max=3)
        old=Plan(0,20,[(0,20)],[],[copy.deepcopy(original)],[],[],20,input_key='same',edit_baseline={'cards':[],'inserts':[asdict(original)]})
        old.inserts[0].end=4
        new=Plan(0,20,[(0,20)],[],[copy.deepcopy(original),Insert('b.mp4',10,13,0,'B',source_max=3)],[],[],20,input_key='same')
        preserve_edits(old.to_dict(),new);validate_plan(new,check_files=False)
        self.assertEqual([(i.path,i.end) for i in sorted(new.inserts,key=lambda i:i.start)],[('a.mp4',4),('b.mp4',13)])
        old.inserts=[];preserve_edits(old.to_dict(),new)
        self.assertEqual([i.path for i in new.inserts],['b.mp4'])

    def test_one_missed_clock_read_does_not_send_continuous_action_to_review(self):
        clock=[[t,60-t,.95] for t in range(0,14,2)];clock[3]=[6,None,0]
        self.assertEqual(live_ranges(clock,14),[[.5,11.5]])
        self.assertTrue(confident_action(4,7.5,clock,[2.]*28,[False]*28))
        frozen=[[t,60,.95] for t in range(0,14,2)]
        self.assertFalse(confident_action(4,7.5,frozen,[2.]*28,[False]*28))
        cuts=[False]*28;cuts[10]=True
        self.assertFalse(confident_action(4,7.5,clock,[2.]*28,cuts))
        self.assertFalse(confident_action(4,7.5,clock,[0.]*28,[False]*28))
        clock[2]=[4,None,0]
        self.assertFalse(confident_action(4,7.5,clock,[2.]*28,[False]*28))

    def test_auto_selection_keeps_accepted_candidate_reserved(self):
        source=MatchSource('a.mp4','','',sport='combat',fighter='ALEKSANDR XALZOV')
        prior=EventRequest(source.id,'Xalzov zarba beradi.','play',selection=EventSelection('one',0,3,1,'sig',True),requested_teams=[source.fighter])
        new=EventRequest(source.id,'Xalzov himoyasi kuchli.','play',requested_teams=[source.fighter])
        data=dict(signature='sig',fighter=source.fighter,detector_version=DETECTOR_VERSION,candidates=[dict(id=k,start=t,end=t+3,time=t+1,kind='play',confidence=.86,note='action') for k,t in [('one',0),('two',5)]])
        propose([new,prior],{source.id:data},[source])
        self.assertTrue(new.selection.accepted);self.assertEqual(new.selection.candidate_id,'two')

    def test_single_ru_analysis_runs_lexical_cleanup_even_without_alignment_failure(self):
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host.mp4';host.touch()
            p=Project(host=str(host),blocks=[Block(script='Сегодня хозяева играют очень уверенно и победили в четырёх матчах.')])
            speech=([Line(p.blocks[0].script,5,12,omit=[(0,4.9)])],[])
            engine=Engine(p,0,Path(d)/'cache',threading.Event())
            with patch('hockey_editor.ru_speech.prepare',return_value={p.blocks[0].uid:speech}) as prepare,patch.object(engine,'_analyze',return_value='ready') as analyze:
                self.assertEqual(engine.analyze(),'ready')
                prepare.assert_called_once();self.assertEqual(analyze.call_args.args[1],speech)

    def test_restart_without_asr_punctuation_and_prefix_correction(self):
        from hockey_editor.speech_cleanup import remove_retakes
        from test_workflow_improvements import segment
        target='Сегодня хозяева играют очень уверенно и победили в четырёх матчах.'
        b=Block(script=target)
        for first in ['Сегодня хозяева играют очень плохо нет','Сегодня гости играют очень плохо.']:
            bad=segment(first);good=segment(target,bad['end']+.12)
            merged=dict(start=0,end=good['end'],text=first+' '+target,words=bad['words']+good['words'])
            cleaned,cuts=remove_retakes([b],[merged])
            self.assertEqual(len(cuts),1);self.assertEqual(cleaned[0]['text'],target)
        # An authored recap is not an accidental second take.
        _,cuts=remove_retakes([b,Block(script=target)],[bad,good]);self.assertFalse(cuts)

    def test_ru_bad_take_is_removed_from_actual_video_keep_ranges(self):
        from test_workflow_improvements import segment
        from hockey_editor.speech_cleanup import remove_retakes
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            run(['-y','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=18','-f','lavfi','-i','sine=f=220:r=48000:d=18','-t',18,'-c:v','libx264','-c:a','aac',d/'host.mp4'])
            first='Сегодня разберём интересный хоккейный матч.'
            target='Сегодня хозяева играют очень уверенно и победили в четырёх матчах.'
            b=Block(title='СКА — Лада',script=first+' '+target)
            speech=[segment(first,0),segment('Сегодня хозяева играют очень плохо нет',3),segment(target,7)]
            _,cuts=remove_retakes([b],speech);self.assertTrue(cuts)
            p=Project(host=str(d/'host.mp4'),blocks=[b]);p.settings.auto_rotate=False
            with patch('hockey_editor.ru_speech.transcribe',return_value=speech):
                plan=Engine(p,0,d/'cache',threading.Event()).analyze()
            for a,z in plan.keep:
                for lo,hi in cuts:
                    self.assertLessEqual(min(plan.source_start+z,hi)-max(plan.source_start+a,lo),.04)
            self.assertLess(plan.duration,plan.source_end-plan.source_start-3)

    def test_confirmed_paraphrased_combat_clips_are_visible_in_final_mp4(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            run(['-y','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=28','-f','lavfi','-i','sine=f=220:r=48000:d=28','-t',28,'-c:v','libx264','-c:a','aac',d/'host.mp4'])
            sources=[]
            for name,color in [('ALEKSANDR XALZOV','red'),('AZAMAT ESPAY','lime')]:
                file=d/(color+'.mp4');run(['-y','-f','lavfi','-i',f'color=c={color}:s=320x180:r=30:d=4','-c:v','libx264',file])
                sources.append(MatchSource(str(file),'','',sport='combat',fighter=name))
            b=Block(title='ALEKSANDR XALZOV — AZAMAT ESPAY',language='uz',sport='combat',script='Xalzov texnik jihatdan yaxshi jangchi. Espay kuchli zarba beradi.',match_ids=[s.id for s in sources])
            b.asr_lines=[asdict(Line(t,a,z,recognized=t)) for t,a,z in [(b.title,0,5),('Xalzovning himoyasi va zarbalari juda yaxshi.',6,10),('Bu jang juda qiziqarli bo‘ladi.',10,20),('Espay hujumda juda kuchli jangchi.',20,24),('Keyingi safar ko‘rishguncha.',24,28)]]
            b.events=[EventRequest(s.id,t,'play',selection=EventSelection('accepted',0,3,1.5,source_signature(s),True),requested_teams=[s.fighter]) for s,t in zip(sources,['Xalzov texnik jihatdan yaxshi jangchi.','Espay kuchli zarba beradi.'])]
            p=Project(host=str(d/'host.mp4'),profile='uz_combat',blocks=[b],matches=sources)
            p.settings.auto_rotate=False;p.settings.cut_pauses=False;p.settings.zoom=False
            engine=Engine(p,0,d/'cache',threading.Event())
            with patch('hockey_editor.uz_speech.synchronize'):
                plan=engine.analyze()
            self.assertEqual(len(plan.inserts),2)
            self.assertEqual([x.path for x in plan.inserts],[s.path for s in sources])
            self.assertEqual(b.events[0].phrase,'Xalzov texnik jihatdan yaxshi jangchi.')
            engine.render(plan,d/'final.mp4')
            for n,clip in enumerate(plan.inserts):
                run(['-y','-ss',(clip.start+clip.end)/2,'-i',d/'final.mp4','-frames:v',1,d/f'{n}.png'])
                with Image.open(d/f'{n}.png') as im:
                    r,g,blue=im.convert('RGB').getpixel((160,500))
                    self.assertLess(blue,40)
                    self.assertGreater(r if n==0 else g,180)

    def test_three_ru_sections_do_not_inherit_previous_forecast(self):
        from hockey_editor.episode import combine,store_episode,saved_episode
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            run(['-y','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=12','-f','lavfi','-i','sine=f=220:r=48000:d=12','-t',12,'-c:v','libx264','-c:a','aac',d/'host.mp4'])
            blocks=[Block(title=t,script='Подробный разбор матча и основной выбор.') for t in ['СКА — ЦСКА','Торпедо — Спартак','Лада — Барыс']]
            p=Project(host=str(d/'host.mp4'),blocks=blocks)
            p.settings.auto_rotate=False;p.settings.zoom=False;p.settings.transitions=False;p.settings.animate_cards=False;p.settings.wobble=False
            parts=[Plan(i*4,i*4+4,[(0,4)],[Line(b.script,0,4)],[],[Card(0,1,'ПРОГНОЗ',b.title,forecast_id=b.uid),Card(2,3,'СТАТИСТИКА','Три победы подряд')],[],4) for i,b in enumerate(blocks)]
            plan=combine(p,parts);store_episode(p,plan)
            self.assertEqual(len(saved_episode(p).sections),3)
            Engine(p,0,d/'cache',threading.Event()).render(plan,d/'final.mp4')
            for t in (1.5,5.5,9.5):
                run(['-y','-ss',t,'-i',d/'final.mp4','-frames:v',1,d/'check.png'])
                with Image.open(d/'check.png') as im:
                    r,g,blue=im.convert('RGB').getpixel((200,600))
                    self.assertGreater(blue,180);self.assertLess(r,40)
            for t in (2.5,6.5,10.5):
                run(['-y','-ss',t,'-i',d/'final.mp4','-frames:v',1,d/'check.png'])
                with Image.open(d/'check.png') as im:
                    r,g,blue=im.convert('RGB').getpixel((200,100))
                    self.assertLess(blue,180)


if __name__=='__main__':unittest.main()
