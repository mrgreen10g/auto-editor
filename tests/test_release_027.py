import tempfile
import unittest
from pathlib import Path
from hockey_editor.model import Project,Block,MatchSource
from hockey_editor.timeline import Line,Card,Plan
from hockey_editor.speech_cleanup import remove_retakes
from hockey_editor.uz_structure import parse
from hockey_editor.uz_speech import make_lines

def segment(text,start=0):
    words=[dict(word=w,start=start+i*.3,end=start+i*.3+.23) for i,w in enumerate(text.split())]
    return dict(text=text,start=start,end=words[-1]['end'],words=words)

class ReleaseTests(unittest.TestCase):
    def test_two_sentence_restart_keeps_complete_later_take(self):
        text='Сегодня хозяева активно идут вперед и контролируют мяч. Их соперник часто теряет мяч в опасной зоне.'
        bad=segment('Сегодня хозяева активно идут вперед и контролируют мяч. Их соперник часто теряет нет заново.')
        good=segment(text,12)
        clean,cuts=remove_retakes([Block(script=text)],[bad,good])
        self.assertEqual(len(cuts),1)
        self.assertEqual(clean[0]['words'][0]['start'],12)
        self.assertEqual(clean[-1]['text'],text)

    def test_wrong_number_or_negation_is_not_successful_retake(self):
        text='Хозяева в этом матче не пропустили три мяча.'
        for later in ['Хозяева в этом матче пропустили три мяча.', 'Хозяева в этом матче не пропустили два мяча.']:
            _,cuts=remove_retakes([Block(script=text)],[segment('Хозяева в этом матче нет.'),segment(later,5)])
            self.assertFalse(cuts)

    def test_authored_repeat_and_distant_recap_survive(self):
        text='Хозяева в этом матче уверенно играют в атаке.'
        self.assertFalse(remove_retakes([Block(script=text+'\n'+text)],[segment(text),segment(text,8)])[1])
        self.assertFalse(remove_retakes([Block(script=text)],[segment(text),segment(text,100)])[1])

    def test_oral_uz_fixture_has_no_intro_words(self):
        a,blocks,z=parse('Salom do‘stlar.\nBirinchi uchrashuv — Surxon va Xorazm\nSurxon uyda kuchli.\nMening tanlovim total 2,5 dan kam.','football')
        self.assertEqual([b.title for b in blocks],['Surxon — Xorazm'])
        self.assertIn('Birinchi uchrashuv',blocks[0].script)

    def test_heard_words_survive_annotation(self):
        from hockey_editor.review import heard_context
        data=segment('Surxon uyda juda kuchli himoya qiladi.',2)
        rows,_=make_lines([data],0,5,[(2,4,'СТАТИСТИКА','Script card')])
        self.assertTrue(all(r['recognized'] and r['words'] for r in rows))
        from types import SimpleNamespace
        plan=SimpleNamespace(lines=[Line(**r) for r in rows])
        self.assertIn('Surxon',heard_context(plan,2,4))
        self.assertNotIn('Script card',heard_context(plan,2,4))

    def test_ru_football_parser_and_archive_ownership(self):
        from hockey_editor.ru_football import parse_script
        from hockey_editor.event_rules import requests_for
        text='Всем привет. Сегодня футбол.\nНачинаем с «Ноттингем Форест» — «Арсенал».\nАрсенал уверенно контролирует мяч и создает много опасных моментов.\nОсновной прогноз — победа Арсенала.\nПо счёту жду 0:2.\nИтак, повторю два выбора. До встречи.'
        a,b,z=parse_script(text)
        self.assertEqual(b[0].title,'Ноттингем Форест — Арсенал')
        m=MatchSource('match.mp4','Arsenal','Chelsea',sport='football');b[0].match_ids=[m.id]
        events=requests_for(b[0],[m]);self.assertTrue(events)
        self.assertTrue(all(e.source_id==m.id and e.kind=='play' for e in events))
        self.assertFalse(any('прогноз' in e.phrase or 'жду' in e.phrase for e in events))

    def test_shorts_folder_uses_child_host_and_parent_matches(self):
        from hockey_editor.folder_import import build_import,presenter_folder
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);short=root/'shorts';short.mkdir()
            (root/'long.mp4').touch();(root/'text.txt').write_text('wrong long text')
            host=short/'any.MOV';host.touch();script=short/'text.txt'
            script.write_text('Salom do‘stlar.\nBirinchi o‘yin — Arsenal va Chelsea.\nArsenal uyda kuchli. Mening tanlovim Arsenal g‘alabasi.\nDemak: Arsenal g‘alabasi.',encoding='utf-8')
            match=root/'Arsenal — Chelsea';match.mkdir();(match/'Arsenal — Chelsea.mp4').touch()
            p=Project(profile='uz_football_shorts')
            result,_,_=build_import(p,root,host,script)
            self.assertEqual(result.host,str(host.resolve()));self.assertEqual(len(result.matches),1)
            self.assertEqual(presenter_folder(root,p.profile),short)
            with self.assertRaises(ValueError):build_import(p,root,root/'long.mp4',root/'text.txt')

    def test_mirror_setting_roundtrip_and_profile_groups(self):
        from hockey_editor.profiles import apply_profile,PROFILES
        p=Project();p.settings.mirror_host=True;apply_profile(p,'ru_football')
        self.assertEqual(p.blocks[0].sport,'football');self.assertEqual(p.blocks[0].language,'ru')
        self.assertTrue(all(key.startswith(lang+'_') for lang,values in PROFILES.items() for key,_ in values))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'p.json';p.save(path);self.assertTrue(Project.load(path).settings.mirror_host)

    def test_football_names_in_russian_and_ambiguous_players(self):
        from hockey_editor.team_names import football_positions
        from hockey_editor.football_players import mentioned_names
        self.assertTrue(football_positions('Arsenal','победа Арсенала'))
        self.assertTrue(football_positions('Leeds United','матч с Лидсом'))
        self.assertIn('Erling Haaland',mentioned_names('У Холанда три гола.'))
        self.assertEqual(mentioned_names('Мартинес вернулся.'),[])
