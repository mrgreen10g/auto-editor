"""Speech/section tests independent of neural weights and user recordings."""
import tempfile,unittest
import threading
from unittest.mock import patch
from pathlib import Path
from hockey_editor.model import Project,Block
from hockey_editor.uz_speech import pair_hits,prepare,speech_key
from hockey_editor.uzbek import asr_framing_cards
from hockey_editor.timeline import Line

def segment(start,end,text):
    tokens=text.split();step=(end-start)/len(tokens)
    return {'start':start,'end':end,'text':text,'words':[{'word':word,'start':start+i*step,'end':start+(i+1)*step} for i,word in enumerate(tokens)]}

def sample():
    return [segment(2,8,'Augsburg Bayer, Borussia Dortmund Padi Boron, Mays Eintraxt.'),
      segment(10,15,'Telegram kanalimizda prognozlar. Havola tavsifida.'),
      segment(30,37,'Demak Augsburg Bayer uchrashuvidan boshlaymiz.'),
      segment(70,77,"Bayer X2 va bir yarimdan ko'p gol variantini qildik."),
      segment(90,97,'Ikkinchi Borussia Paddeboron uchrashuvda vaziyat boshqacha.'),
      segment(110,116,"Borussiya g'alabasi va umumiy golsoni bir yarimdan ko'p variant."),
      segment(130,137,'Va Mays Eintraxt uchrashuvda vaziyat teng.'),
      segment(150,158,"Umumiy golsoni bir yarimdan ko'p variantini qildik."),
      segment(170,180,"Yana qaytaraman Bayer X2 va bir yarimdan ko'p gol variant."),
      segment(180,188,"Ikkinchi Dortmund g'alabasi va bir yarimdan ko'p gol variant."),
      segment(188,194,"Oxirgi o'yinda umumiy golsoni bir yarimdan ko'p variant."),
      segment(195,200,'Telegram kanalimizda yangiliklar. Havola tavsifida.'),
      segment(201,204,"Keyingi videoda ko'rishguncha.")]

def project(host):
    p=Project(profile='uz_football',host=str(host),blocks=[
      Block(title='Augsburg — Bayer',language='uz',script="Mening tanlovim — Bayer X2 va 1,5 tadan ko'p gol."),
      Block(title='Borussiya Dortmund — Paderborn',language='uz',script="Mening tanlovim — Dortmund g'alaba qiladi va 1,5 tadan ko'p gol."),
      Block(title='Mayns — Ayntraxt Frankfurt',language='uz',script="Mening tanlovim — 1,5 tadan ko'p gol.")])
    p.intro.language=p.outro.language='uz';p.assets={'telegram':'tg.mov'}
    return p

class SpeechTests(unittest.TestCase):
    def test_unspoken_subscription_does_not_require_asset(self):
        from hockey_editor.episode import EpisodeEngine
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host.mp4';host.touch();p=project(host)
            p.full_video=True;p.assets={'disclaimer':str(host)}
            engine=EpisodeEngine(p,0,Path(d),threading.Event())
            with patch.object(Project,'validate'):engine.validate_all()
            prepare(p,sample())
            # Telegram is actually spoken and therefore still mandatory.
            with self.assertRaisesRegex(ValueError,'Telegram'):
                asr_framing_cards(p,p.outro,[Line(**l) for l in p.outro.asr_lines],204)
            p.assets['telegram']=str(host)
            cards,_=asr_framing_cards(p,p.outro,[Line(**l) for l in p.outro.asr_lines],204)
            self.assertFalse(any(c.title=='ПОДПИСКА' for c in cards))
            with self.assertRaisesRegex(ValueError,'подписки'):
                asr_framing_cards(p,Block(kind='outro',language='uz'),[Line("Kanalga obuna bo'ling.",1,4)],10)
    def test_split_names_and_transliterations(self):
        self.assertTrue(pair_hits('Borussiya Dortmund — Paderborn',segment(0,3,'Borussia Dortmund Padi Boron')['words']))
        self.assertTrue(pair_hits('Mayns — Ayntraxt Frankfurt',segment(0,3,'Va Mays Eintraxt uchrashuvda')['words']))
        self.assertFalse(pair_hits('Mayns — Ayntraxt Frankfurt',segment(0,3,'Bayer oson g‘alaba qilmaydi')['words']))
    def test_free_speech_overrides_written_times_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host.mp4';host.touch();p=project(host)
            p.blocks[0].source_hint=[60,200];p.blocks[1].source_hint=[200,340]
            bounds=prepare(p,sample())
            self.assertEqual(bounds,[2,30,90,130,170,204])
            self.assertEqual([b.asr_lines[0]['start'] for b in p.blocks],[30,90,130])
            self.assertEqual(p.blocks[0].source_hint,[60,200])
            self.assertTrue(all(b.speech_key==speech_key(p) for b in p.blocks))
            for b in p.blocks:self.assertTrue(any(c['title']=='ПРОГНОЗ' for c in b.speech_cards.values()))
            p.save(Path(d)/'project.json');loaded=Project.load(Path(d)/'project.json')
            self.assertEqual(loaded.blocks[1].speech_cards,p.blocks[1].speech_cards)
            self.assertEqual(loaded.blocks[0].speech_key,speech_key(loaded))
            ls=[Line(**l) for l in loaded.outro.asr_lines]
            # Times are absolute here; rendering normalizes them separately.
            cards,_=asr_framing_cards(loaded,loaded.outro,ls,204)
            self.assertEqual([c.forecast_id for c in cards if c.title=='ПРОГНОЗ'],[b.uid for b in p.blocks])
            self.assertFalse(any(c.title=='ПОДПИСКА' for c in cards))
    def test_missing_spoken_block_does_not_use_script_times(self):
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host.mp4';host.touch();p=project(host);p.blocks[2].title='Sevilla — Barcelona'
            with self.assertRaisesRegex(ValueError,'Sevilla'):prepare(p,sample())
