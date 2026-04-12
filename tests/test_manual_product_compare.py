from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.manual_product_compare import (  # noqa: E402
    GameGroup,
    parse_grouped_text,
    record_signature,
    region_from_url,
)


class ManualProductCompareTests(unittest.TestCase):
    def test_parse_grouped_text_dedupes_urls_and_ignores_extra_sections(self) -> None:
        raw_text = """
        Сверху разбиты по названиям игр. Снизу ссылки подряд.

        Outlast
        https://store.playstation.com/ru-ua/product/EP4467-CUSA00409_00-OUTLAST000000000
        https://store.playstation.com/ru-ua/product/EP4467-CUSA00409_00-OUTLAST000000000

        Только ссылки:
        https://store.playstation.com/en-tr/product/EP3969-PPSA01769_00-0000000000000WOA
        https://store.playstation.com/en-tr/product/EP3969-PPSA01769_00-0000000000000WOA
        """

        groups = parse_grouped_text(raw_text)

        self.assertGreaterEqual(len(groups), 2)
        self.assertEqual(groups[0], GameGroup(title="Outlast", urls=["https://store.playstation.com/ru-ua/product/EP4467-CUSA00409_00-OUTLAST000000000"]))
        self.assertTrue(any(url.endswith("0000000000000WOA") for group in groups for url in group.urls))

    def test_region_from_url_supports_ukraine_alias(self) -> None:
        self.assertEqual(
            region_from_url("https://store.playstation.com/uk-ua/product/EP0002-CUSA05380_00-CODMWRTHEGAME001"),
            "UA",
        )

    def test_record_signature_rounds_numeric_fields(self) -> None:
        signature = record_signature(
            {
                "id": "EP1",
                "region": "TR",
                "name": "Sample",
                "edition": "Deluxe",
                "localization": "subtitles",
                "price_rub": 123.4567,
                "price_old_rub": "250.009",
                "ps_plus": 1,
                "ps_plus_collection": "Extra",
                "ea_play_price": None,
            },
        )

        self.assertIn('"price_rub": 123.46', signature)
        self.assertIn('"price_old_rub": 250.01', signature)
        self.assertIn('"ps_plus": 1', signature)


if __name__ == "__main__":
    unittest.main()
