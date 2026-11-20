import unittest
from hockey_editor.speech_cleanup import acoustic_cleanup,remove_retakes
from hockey_editor.model import Block
from hockey_editor.ru_speech import tokens

def segment(text,start):
 words=[dict(word=w,start=start+i*.3,end=start+i*.3+.25) for i,w in enumerate(text.split())]
 return dict(start=start,end=words[-1]['end'],text=text,words=words)
class PauseRecoveryTests(unittest.TestCase):
 def test_stretched_word(self):
  s=segment('Вспомним этот бой',0);s['words'][0]['end']=2.25
  clean,_=acoustic_cleanup([s],[(0,.3),(2,4)],5)
  self.assertEqual(clean[0]['words'][0]['start'],2)
  self.assertEqual(s['words'][0]['start'],0)
 def test_unvoiced_consonant(self):
  s=segment('К',0);s['words'][0]['end']=7.25
  clean,_=acoustic_cleanup([s],[(0,.3),(2,3),(7.6,10)],10)
  self.assertEqual(clean[0]['words'][0]['start'],6.75)
 def test_leading_silence(self):
  s=segment('Добрый',0);s['words'][0]['end']=7.25
  clean,cuts=acoustic_cleanup([s],[(7,9)],10)
  self.assertEqual(clean[0]['words'][0]['start'],7)
  self.assertTrue(any(b>6 for a,b in cuts))
 def test_quiet_words_protected(self):
  s=segment('тихая но важная речь',3);_,cuts=acoustic_cleanup([s],[],8)
  for w in s['words']:
   self.assertFalse(any(a<w['end'] and b>w['start'] for a,b in cuts))
 def test_lexical_equivalence(self):
  self.assertEqual(tokens('Ливерпуль Манчестер Юнайтед'),tokens('Liverpool Manchester United'))
  self.assertEqual(tokens('сороковой'),tokens('40'))
 def test_paused_restart(self):
  block=Block(script='К тому же участие Пау Кубарси пока под вопросом из-за повреждения.')
  old=segment('К тому же участие Пау к Барасе.',0)
  new=segment('К тому же участие Пау к Барсе пока под вопросом и заповреждения.',8)
  clean,cuts=remove_retakes([block],[old,new])
  self.assertEqual(len(cuts),1);self.assertEqual(clean[0]['start'],8)
 def test_partial_restart(self):
  block=Block(script='В противостоянии Динамо Бунёдкор мой выбор один икс.')
  clean,cuts=remove_retakes([block],[segment('Противостояние Динамо.',0),segment('Противостояние Динамо будет кор мой выбор один икс.',8)])
  self.assertEqual(len(cuts),1);self.assertEqual(clean[0]['start'],8)
