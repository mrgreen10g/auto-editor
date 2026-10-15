import re
import unittest
from hockey_editor.team_names import FOOTBALL,football_identity,football_positions,football_names
from hockey_editor.hockey_names import identity


class ClubCatalogTests(unittest.TestCase):
    def test_all_catalog_clubs_have_russian_aliases(self):
        for name,aliases in FOOTBALL.items():
            self.assertTrue(any(re.search('[А-Яа-яЁё]',a) for a in aliases),name)
            for alias in aliases:self.assertEqual(football_identity(alias),name,alias)

    def test_latin_and_russian_variants_across_leagues(self):
        for a,b in [('Бавария','Bayern Munich'),('Фиорентина','Fiorentina'),('Кристал Пэлас','Crystal Palace'),('Фенербахче','Fenerbahçe'),('Пари Сен-Жермен','PSG'),('Коканд-1912',"Qo'qon"),('Лос-Анджелес Гэлакси','LA Galaxy'),('Ланс','Lens'),('Реал Сосьедад','Real Sociedad'),('ЦСКА Москва','SSKA Moskva')]:
            self.assertIsNotNone(football_identity(a));self.assertEqual(football_identity(a),football_identity(b))

    def test_inter_miami_does_not_become_milan_inter(self):
        self.assertEqual(football_positions('Inter','Inter Miami hujum qiladi.'),[])
        self.assertEqual(football_names('Inter Miami — Toronto FC'),['Inter Miami','Toronto FC'])

    def test_shared_cities_stay_ambiguous(self):
        for name in ('Manchester','New York','Moskva','Madrid'):
            self.assertIsNone(football_identity(name))
        self.assertNotEqual(football_identity('Dynamo Moscow'),football_identity('Dynamo Makhachkala'))

    def test_hockey_qualified_uzbek_names(self):
        self.assertEqual(identity('Spartak Moskva'),'Спартак')
        self.assertEqual(identity('Shanxay Dragons'),'Шанхайские Драконы')
        self.assertEqual(identity('SSKA'),'ЦСКА')
        for text in ('ЦСКА Москва','CSKA Moscow','SSKA Moskva'):
            self.assertEqual(identity(text),'ЦСКА')
        self.assertEqual(identity('СКА Санкт-Петербург'),'СКА')

    def test_full_russian_nhl_names(self):
        examples={'Бостон Брюинз':'Boston Bruins','Торонто Мейпл Лифс':'Toronto Maple Leafs','Вашингтон Кэпиталз':'Washington Capitals','Нью-Йорк Рейнджерс':'New York Rangers','Лос-Анджелес Кингз':'Los Angeles Kings'}
        for text,want in examples.items():self.assertEqual(identity(text),want,text)

    def test_reserve_team_does_not_match_senior(self):
        self.assertEqual(football_positions('Paxtakor','Paxtakor II o‘ynaydi'),[])
        self.assertTrue(football_positions('Paxtakor II','Paxtakor II o‘ynaydi'))
        self.assertTrue(football_positions('Paxtakor','Paxtakor 2 gol urdi'))
        self.assertFalse(football_positions('Paxtakor II','Paxtakor 2 gol urdi'))

    def test_real_requires_unique_fixture_context(self):
        self.assertFalse(football_positions('Real Madrid','Real hujum qiladi',('Real Madrid','Real Betis')))
        self.assertTrue(football_positions('Real Madrid','Real hujum qiladi',('Real Madrid','Arsenal')))
