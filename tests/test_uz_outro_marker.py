import unittest
from hockey_editor.folder_import import parse_episode
from hockey_editor.model import Project,Block
from hockey_editor.script_sections import repair_premature_outro

class OutroMarkerTests(unittest.TestCase):
 def test_explicit_recap_all_uz_profiles(self):
  for profile in ('uz_football','uz_football_shorts','uz_hockey','uz_hockey_shorts','uz_combat','uz_combat_shorts'):
   for ending in ('Demak, tanlovlarim:', 'Demak, tanlovlarimiz:', 'YAKUNIY XULOSA'):
    text='Salom!\nРазбор1 Arsenal - Chelsea\nDemak, bu jamoa himoyada yaxshi.\nTanlovim — total 2,5 dan ko\'p!\n'+ending+'\nBugun uchrashuvlarni tahlil qildik.'
    intro,blocks,outro=parse_episode(text,profile)
    self.assertEqual(len(blocks),1)
    self.assertTrue(outro.script.startswith(ending),(profile,outro.script))
    self.assertIn('Demak, bu jamoa',blocks[-1].script)
 def test_repair_only_empty_outro(self):
  p=Project();p.profile='uz_football_shorts';p.blocks=[Block(script='Tahlil.\nDemak, tanlovlarim:\nX2!')];p.outro.script=''
  self.assertTrue(repair_premature_outro(p));self.assertEqual(p.blocks[-1].script,'Tahlil.')
  self.assertFalse(repair_premature_outro(p));p.outro.script='Manual ending';p.blocks[-1].script+='\nDemak, tanlovlarim:\nOther'
  self.assertFalse(repair_premature_outro(p));self.assertEqual(p.outro.script,'Manual ending')
