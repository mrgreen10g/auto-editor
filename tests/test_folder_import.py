import copy,tempfile,unittest
from pathlib import Path
from hockey_editor.model import Project,Block
from hockey_editor.folder_import import root_files,build_import,unresolved_sources,pair_key,parse_episode
from hockey_editor.material_folder import candidates,resolve,save_kit,load_kit

SCRIPT="""Всем привет! Сегодня разберём два матча. Переходим к разбору.
АМУР — СПАРТАК
Амур играет дома. Мой прогноз — тотал больше 4,5 шайб в матче.
САЛАВАТ ЮЛАЕВ — СИБИРЬ
Сибирь играет в гостях. Мой прогноз — победа хозяев в основное время.
Итак, повторю два выбора. Тотал больше и победа хозяев. Подписывайтесь, до встречи!
"""

def setup(root):
    host=root/'any-camera.MOV';host.write_bytes(b'host')
    script=root/'text.txt';script.write_text(SCRIPT,encoding='utf-8-sig')
    for folder,file in [('АМУР — СПАРТАК','Амур - ЦСКА 2026-10-12.mp4'),('САЛАВАТ — СИБИРЬ','Сибирь - Трактор.MP4')]:
        d=root/folder;d.mkdir();(d/file).write_bytes(b'match')
    short=root/'shorts';short.mkdir();(short/'host.mp4').write_bytes(b'ignore');(short/'text.txt').write_text('ignore')
    return host,script

class FolderImportTests(unittest.TestCase):
    def test_new_folder_each_time_and_archives_keep_real_opponents(self):
        original=Project(host='old',blocks=[Block(title='Old')]);original.settings.noise_reduction=14;original.music='music.mp3'
        before=copy.deepcopy(original)
        with tempfile.TemporaryDirectory() as d:
            for n in ['release-a','release-b']:
                root=Path(d).resolve()/n;root.mkdir();host,script=setup(root)
                hosts,scripts=root_files(root);self.assertEqual(hosts,[host]);self.assertEqual(scripts,[script])
                draft,mapping,notes=build_import(original,root,host,script)
                self.assertEqual(len(mapping),2);self.assertEqual(len(draft.matches),2)
                self.assertEqual(draft.host,str(host.resolve()));self.assertEqual(draft.music,'music.mp3')
                self.assertEqual(draft.settings.noise_reduction,14);self.assertTrue(draft.full_video and draft.whole_episode)
                self.assertEqual(draft.blocks[0].title,'АМУР — СПАРТАК')
                self.assertEqual(draft.matches[0].away,'ЦСКА')
                self.assertFalse(unresolved_sources(draft));self.assertFalse(any('shorts' in x for x in notes))
                self.assertEqual(original,before)

    def test_unknown_footage_not_labeled_as_forecast_pair(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();host,script=setup(root)
            (root/'АМУР — СПАРТАК'/'recording.mp4').write_bytes(b'unknown')
            draft,_,_=build_import(Project(),root,host,script)
            unknown=unresolved_sources(draft);self.assertEqual(len(unknown),1)
            self.assertEqual((unknown[0].home,unknown[0].away),('',''))

    def test_ambiguity_and_missing_folder_are_visible(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();host,script=setup(root)
            alt=root/'Спартак — Амур';alt.mkdir();(alt/'Амур - Спартак.mp4').write_bytes(b'v')
            draft,mapping,notes=build_import(Project(),root,host,script)
            self.assertNotIn(0,mapping);self.assertTrue(any('несколько' in x for x in notes))
            draft,mapping,_=build_import(Project(),root,host,script,{0:str(alt)})
            self.assertIn(0,mapping);self.assertEqual(len(draft.matches),2)
            (root/'other.MP4').write_bytes(b'v');self.assertEqual(len(root_files(root)[0]),2)

    def test_unknown_football_pair_and_script_error_leave_original_intact(self):
        from test_shorts import SCRIPT as UZ
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();host=root/'host.mp4';host.write_bytes(b'v');script=root/'text.txt';script.write_text(UZ,encoding='utf-8')
            p=Project(profile='uz_football_shorts');draft,_,notes=build_import(p,root,host,script)
            self.assertEqual(len(draft.blocks),2);self.assertEqual(len(notes),2)
            before=copy.deepcopy(p);script.write_text('invalid')
            with self.assertRaises(ValueError):build_import(p,root,host,script)
            self.assertEqual(p,before)
        self.assertEqual(pair_key('Amur — Spartak','uz_hockey'),pair_key('СПАРТАК — АМУР','uz_hockey'))

    def test_materials_folder_relocates_and_preserves_legacy_kit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();folder=root/'materials';folder.mkdir()
            for name in ['Дисклеймер.mov','ТГ.mp4','Подписка.MOV']:(folder/name).write_bytes(b'v')
            choices=candidates(folder);self.assertTrue(all(len(v)==1 for v in choices.values()))
            assets={k:str(v[0]) for k,v in choices.items()};kit=root/'kit.json';save_kit(kit,str(folder),assets)
            self.assertEqual(load_kit(kit),(str(folder),assets))
            new=root/'moved';folder.rename(new)
            resolved=resolve(str(new),assets);self.assertTrue(all(Path(p).is_file() for p in resolved.values()))
            p=Project(asset_folder=str(new),assets=resolved);project=root/'project.hockeyproj';p.save(project)
            q=Project.load(project);self.assertEqual(q.asset_folder,str(new));self.assertEqual(q.assets,resolved)
            import json
            kit.write_text(json.dumps(resolved));self.assertEqual(load_kit(kit),('',resolved))
            (new/'Telegram other.mp4').write_bytes(b'v')
            self.assertEqual(len(candidates(new)['telegram']),2)
            self.assertNotIn('telegram',resolve(str(new),{}))

if __name__=='__main__':unittest.main()
