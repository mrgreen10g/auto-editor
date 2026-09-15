import unittest
from test_uz_speech import segment
from hockey_editor.model import Block
from hockey_editor.uz_forecasts import match_forecasts,features
from hockey_editor.uz_speech import contextual_telegram_spans
from hockey_editor.framing import forecast_text

class ContextTests(unittest.TestCase):
 def owners(self):
  return [Block(title='Bavariya — Union Berlin',language='uz',script="Mening tanlovim — Bavariya g'alabasi va 2,5 dan ko‘p gol."),Block(title='Ayntraxt Frankfurt — Frayburg',language='uz',script="Mening tanlovim — Ayntraxt 1X va 1,5 dan ko‘p gol."),Block(title='Borussiya Menxengladbax — Mayns',language='uz',script="Mening tanlovim — 2,5 dan ko‘p gol.")]
 def test_correction_weak_foreign_match_and_different_asr_chunks(self):
  owners=self.owners();refs={b.uid:forecast_text(b) for b in owners}
  data=[segment(10,18,'Ayntraxt 1X va 1,5 dan ko‘p gol variant.'),segment(19,27,'Birinchi Bavariya g‘alabasi va 2,5 dan ko‘p gol.'),segment(28,40,'Oxirgi uchrashuvda Ayntraxt emas, balki Mais. Umumiy 2,5 dan ko‘p gol variyatni qildik.')]
  words=[w for s in data for w in s['words']]
  for groups in ([words],[words[i:i+3] for i in range(0,len(words),3)]):
   segments=[dict(start=g[0]['start'],end=g[-1]['end'],text=' '.join(w['word'] for w in g),words=g) for g in groups]
   picks=match_forecasts(segments,0,45,owners,refs)
   self.assertEqual([v['forecast_id'] for v in sorted(picks,key=lambda v:v['start'])],[owners[i].uid for i in (1,0,2)])
   self.assertGreaterEqual(picks[2]['start'],28)
   self.assertLessEqual(picks[1]['end'],picks[0]['start'])
 def test_missing_pick_is_not_invented(self):
  owners=self.owners();refs={b.uid:forecast_text(b) for b in owners}
  data=[segment(1,8,'Bavariya g‘alabasi va 2,5 dan ko‘p gol.'),segment(10,17,'Ayntraxt 1X va 1,5 dan ko‘p gol.')]
  with self.assertRaises(ValueError):match_forecasts(data,0,20,owners,refs)
 def test_double_chance_identity(self):
  owner=self.owners()[1];refs={owner.uid:forecast_text(owner)}
  self.assertEqual(features('bir iks')['chance'],'1x');self.assertEqual(features('X ikki')['chance'],'x2')
  for chance in ('X2','12'):
   with self.subTest(chance=chance),self.assertRaises(ValueError):match_forecasts([segment(1,8,f'Ayntraxt {chance} va 1,5 dan ko‘p gol.')],0,10,[owner],refs)
 def test_statistics_twelve_is_not_a_market(self):
  self.assertIsNone(features('12 zarba berdi')['chance'])
 def test_contextual_telegram_requires_script_and_channel_information(self):
  b=Block(kind='outro',script='Telegram kanalimizda prognozlar.')
  data=[segment(1,5,'Kanalimizga o‘ting, informatsiyalarni topasiz.'),segment(6,8,'Obuna bo‘ling, xayr!')]
  self.assertEqual(contextual_telegram_spans(b,data,0,10),[(1,5)])
  b.script='Obuna bo‘ling!';self.assertFalse(contextual_telegram_spans(b,data,0,10))
  b.script='Telegram';self.assertFalse(contextual_telegram_spans(b,[segment(1,5,'Informatsiyalar foydali.')],0,10))
 def test_contextual_telegram_stops_before_subscription(self):
  b=Block(kind='outro',script='Telegram kanalimizda prognozlar.')
  s=segment(1,9,'Kanalimizda informatsiyalar bor. Obuna bo‘ling, xayr!')
  result=contextual_telegram_spans(b,[s],0,10)
  self.assertEqual(result,[(1,s['words'][2]['end'])])
