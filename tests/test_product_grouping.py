import unittest
from types import SimpleNamespace

from app.api.crud import ProductCRUD


class ProductGroupingTests(unittest.TestCase):
    def test_group_product_rows_keeps_one_card_per_product_id(self):
        rows = [
            (SimpleNamespace(id='game-1', region='UA', name='Valentine Revolution', main_name='Valentine Revolution'), None),
            (SimpleNamespace(id='game-1', region='TR', name='Valentine Revolution', main_name='Valentine Revolution'), None),
            (SimpleNamespace(id='game-1', region='IN', name='Valentine Revolution', main_name='Valentine Revolution'), None),
            (SimpleNamespace(id='game-2', region='UA', name='Unusual Findings', main_name='Unusual Findings'), None),
            (SimpleNamespace(id='game-2', region='TR', name='Unusual Findings', main_name='Unusual Findings'), None),
        ]

        grouped = ProductCRUD._group_product_rows(rows)

        self.assertEqual(len(grouped), 2)
        self.assertEqual([product.id for product, _ in grouped], ['game-2', 'game-1'])
        self.assertEqual(grouped[0][0].region, 'TR')
        self.assertEqual(grouped[1][0].region, 'TR')

    def test_group_product_rows_prefers_user_region_when_available(self):
        rows = [
            (SimpleNamespace(id='game-1', region='TR', name='Valentine Revolution', main_name='Valentine Revolution'), None),
            (SimpleNamespace(id='game-1', region='UA', name='Valentine Revolution', main_name='Valentine Revolution'), None),
        ]

        user = SimpleNamespace(preferred_region='UA')

        grouped = ProductCRUD._group_product_rows(rows, user=user)

        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0][0].region, 'UA')


if __name__ == '__main__':
    unittest.main()
