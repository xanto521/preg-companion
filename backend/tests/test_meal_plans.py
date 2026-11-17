from unittest import TestCase

from app.domain.meal_plans import MEAL_KEYS, meal_groups, recommended_month


class MealPlansTest(TestCase):
    def test_recommendation_boundaries(self):
        for days, expected in ((None, None), (-1, None), (0, 1), (27, 1), (28, 2), (223, 8), (224, 9), (252, 9), (280, 9)):
            with self.subTest(days=days):
                self.assertEqual(recommended_month(days), expected)

    def test_catalog_serves_four_meals_and_omits_withheld_dishes(self):
        groups = meal_groups()
        self.assertEqual([group.month for group in groups], list(range(1, 10)))
        for group in groups:
            self.assertEqual([menu.day for menu in group.days], list(range(1, 8)))
            for menu in group.days:
                for meal in MEAL_KEYS:
                    self.assertTrue(getattr(menu, meal))

        self.assertNotIn("凉拌豆芽", groups[1].days[1].dinner)
        self.assertNotIn("猪肝枸杞汤", groups[4].days[4].dinner)
        self.assertEqual(groups[7].days[1].breakfast, ["牛奶", "全麦面包"])
