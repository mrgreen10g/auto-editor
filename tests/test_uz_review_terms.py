import unittest
from hockey_editor.uz_review_terms import exact_translation


class ReviewTermTests(unittest.TestCase):
    def test_total_direction_is_preserved(self):
        self.assertEqual(exact_translation('Mening tanlovim total 2,5 dan kam.'),'Мой выбор: Тотал меньше 2,5')
        self.assertEqual(exact_translation('Total 1.5 tadan ko‘p.'),'Тотал больше 1,5')

    def test_not_losing_is_not_not_winning(self):
        self.assertEqual(exact_translation("Real Madrid mag'lub bo'lmaydi."),'Real Madrid не проиграет.')

    def test_qualifiers_are_never_silently_removed(self):
        for text in ["Total 2,5 dan kam emas.","Agar Real Madrid mag'lub bo'lmaydi.","Real Madrid g'alaba qozonadi deb o'ylamayman.","Total 2,5 dan ko'p bo'lishi mumkin."]:
            self.assertIsNone(exact_translation(text),text)
