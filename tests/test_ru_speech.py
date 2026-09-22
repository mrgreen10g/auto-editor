"""Continuous Russian speech must not map an intro onto repeated closing words."""
import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from hockey_editor.alignment import AlignmentError
from hockey_editor.ru_speech import align_episode,recording_key,transcribe
from hockey_editor.model import Block,Project
from hockey_editor.episode import EpisodeEngine
from hockey_editor.engine import Engine

def segment(start,text):
    words=[{'word':w,'start':start+i*.4,'end':start+(i+1)*.4} for i,w in enumerate(text.split())]
    return {'text':text,'start':start,'end':words[-1]['end'],'words':words}

def sample():
    intro='Всем привет, сегодня разберём три хоккейных матча. Дополнительные ставки публикую в телеграм канале.'
    body=['После поражения Авангард уверенно победил соперника. Мой выбор — Автомобилист с форой плюс полторы.',
          'Ярославль начал сезон четырьмя победами подряд. Основной выбор — Локомотив с форой ноль.',
          'Шанхай уже дважды забросил минимум четыре шайбы. Мой выбор — тотал больше пяти шайб.']
    outro='Итак, повторю сегодняшние варианты. Автомобилист с форой плюс полторы. Локомотив с форой ноль. Тотал больше пяти шайб. Дополнительные ставки публикую в телеграм канале. Всем удачи и до встречи!'
    blocks=[Block(title='Начало',kind='intro',uid='intro',script=intro)]
    for i,(title,script) in enumerate(zip(['Авангард — Автомобилист','Трактор — Локомотив','СКА — Шанхайские Драконы'],body)):
        blocks.append(Block(title=title,uid=str(i),script=title+'\n'+script))
    blocks.append(Block(title='Итоги',kind='outro',uid='outro',script=outro))
    speech=[segment(1,intro),segment(32,body[0]),segment(152,body[1]),segment(265,body[2]),segment(387,outro)]
    return blocks,speech

class RussianSpeechTests(unittest.TestCase):
    def test_continuous_episode_and_repeated_telegram(self):
        blocks,speech=sample();result=align_episode(blocks,speech)
        self.assertLess(result['intro'][0][0].start,5)
        self.assertEqual(result['intro'][0][-1].end,32)
        self.assertAlmostEqual(result['0'][0][0].start,32)
        self.assertAlmostEqual(result['1'][0][0].start,152)
        self.assertAlmostEqual(result['2'][0][0].start,265)
        self.assertAlmostEqual(result['outro'][0][0].start,387)
        self.assertTrue(any('Заголовок' in w for w in result['0'][1]))
        self.assertEqual(result['outro'][0][-1].end,speech[-1]['end'])

    def test_chunking_does_not_change_mapping(self):
        blocks,speech=sample();joined=[{'words':[w for s in speech for w in s['words']]}]
        a=align_episode(blocks,speech);b=align_episode(blocks,joined)
        self.assertEqual({k:[vars(l) for l in v[0]] for k,v in a.items()},
                         {k:[vars(l) for l in v[0]] for k,v in b.items()})

    def test_short_spoken_farewell_is_kept(self):
        blocks,speech=sample();end=speech[-1]['end']
        speech.append(segment(end+.2,'Пока!'))
        self.assertAlmostEqual(align_episode(blocks,speech)['outro'][0][-1].end,end+.6)

    def test_intro_late_and_missing_analysis_are_rejected(self):
        blocks,speech=sample()
        late=copy.deepcopy(speech)
        for s in late:
            for w in s['words']:w['start']+=150;w['end']+=150
        with self.assertRaisesRegex(AlignmentError,'двух минут'):align_episode(blocks,late)
        with self.assertRaises(AlignmentError):align_episode(blocks,speech[:2]+speech[3:])

    def test_whole_recording_key_and_cached_words_reused(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);host=d/'host.mp4';host.touch();p=Project(host=str(host))
            folder=d/'ru-speech';folder.mkdir();key=recording_key(p)
            payload=[{'words':[{'word':'привет','start':1,'end':2}]}]
            (folder/(key+'.json')).write_text(json.dumps(payload),encoding='utf-8')
            with patch('hockey_editor.ru_speech.model_path',side_effect=AssertionError('must reuse cache')):
                self.assertEqual(transcribe(p,d,threading.Event(),lambda _:None),payload)
            p.blocks[0].script='Изменён текст.';self.assertEqual(recording_key(p),key)
            host.write_bytes(b'changed');self.assertNotEqual(recording_key(p),key)

    def test_fallback_once_and_failed_partial_plan_rolled_back(self):
        p=Project(full_video=True);p.intro.edit_plan={'accepted':True};p.intro.edit_key='accepted'
        with tempfile.TemporaryDirectory() as d:
            engine=EpisodeEngine(p,0,Path(d),threading.Event());calls=[]
            def assemble(runtime,speech=None):
                calls.append(speech)
                if speech is None:
                    p.intro.edit_plan={'bad':True};raise AlignmentError('unstable')
                self.assertEqual(p.intro.edit_plan,{'accepted':True})
                return 'ready'
            with patch.object(engine,'validate_all'),patch('hockey_editor.episode.saved_episode',return_value=None),patch.object(engine,'_assemble',side_effect=assemble),patch('hockey_editor.ru_speech.prepare',return_value={'checked':True}) as prepare:
                self.assertEqual(engine.analyze(),'ready');self.assertEqual(prepare.call_count,1)
                self.assertEqual(calls,[None,{'checked':True}])

    def test_other_errors_do_not_start_model_download(self):
        p=Project(full_video=True)
        with tempfile.TemporaryDirectory() as d:
            engine=EpisodeEngine(p,0,Path(d),threading.Event())
            with patch.object(engine,'validate_all'),patch('hockey_editor.episode.saved_episode',return_value=None),patch.object(engine,'_assemble',side_effect=ValueError('missing asset')),patch('hockey_editor.ru_speech.prepare') as prepare:
                with self.assertRaisesRegex(ValueError,'missing asset'):engine.analyze()
                prepare.assert_not_called()

    def test_late_saved_intro_is_recomputed_with_two_minute_limit(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);host=d/'host.mp4';host.touch()
            p=Project(host=str(host));p.blocks=[Block(title='Начало',kind='intro',script='Всем привет, сегодня разберём три матча.')]
            engine=Engine(p,0,d,threading.Event())
            (d/'alignment.json').write_text(json.dumps({'key':'old-acoustic-version','lines':[]}),encoding='utf-8')
            late=SimpleNamespace(source_start=387.07,source_end=428.33)
            with patch('hockey_editor.editing.saved_plan',return_value=late),patch('hockey_editor.goals.montage_block',return_value=p.blocks[0]),patch('hockey_editor.host_media.analysis_source',return_value=(str(host),431.33,[])),patch('hockey_editor.engine.run') as run,patch('hockey_editor.engine.align',side_effect=AlignmentError('retry words')):
                with self.assertRaises(AlignmentError):engine.analyze(recover=False)
                command=run.call_args.args[0]
                self.assertEqual(command[command.index('-t')+1],120)
                self.assertEqual(command[command.index('-ss')+1],0)

