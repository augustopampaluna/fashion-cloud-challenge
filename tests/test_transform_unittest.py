# Run:
#   python -m unittest -v

import json
import os
import tempfile
import textwrap
import unittest

from src.transform import (
    load_mappings_index,
    row_to_variation,
    build_catalog_from_pricat,
)


def write_file(path: str, content: str) -> None:
    """
    Helper to write test CSV fixtures to disk with clean indentation.
    """
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(textwrap.dedent(content).lstrip())


class TestTransform(unittest.TestCase):
    def test_row_to_variation_combined_mapping_consumes_fields(self) -> None:
        """
        Combined mapping example:
          size_group_code|size_code  EU|38  -> size = "European size 38"

        Expectations:
        - Output contains the mapped destination field ("size")
        - Input fields used by the combined mapping are NOT copied as raw fields
        - Other raw fields remain
        - 'brand' is never part of variation
        """
        mappings_idx = {
            ("size_group_code", "size_code"): {
                "EU|38": ("size", "European size 38"),
            }
        }

        row = {
            "brand": "Via Vai",
            "article_number": "15189-02",
            "size_group_code": "EU",
            "size_code": "38",
            "ean": "123",
        }

        variation = row_to_variation(row, mappings_idx)

        self.assertEqual(variation["size"], "European size 38")
        self.assertNotIn("size_group_code", variation)
        self.assertNotIn("size_code", variation)
        self.assertEqual(variation["ean"], "123")
        self.assertNotIn("brand", variation)

    def test_row_to_variation_simple_mapping(self) -> None:
        """
        Simple mapping example:
          season  winter -> season = "Winter"

        Expectations:
        - Output contains mapped season value
        - brand is excluded
        """
        mappings_idx = {
            ("season",): {
                "winter": ("season", "Winter"),
            }
        }

        row = {
            "brand": "Via Vai",
            "article_number": "15189-02",
            "season": "winter",
        }

        variation = row_to_variation(row, mappings_idx)

        self.assertEqual(variation["season"], "Winter")
        self.assertNotIn("brand", variation)

    def test_row_to_variation_numeric_conversion(self) -> None:
        """
        Known numeric fields should be converted to float when present and parseable.
        This assumes you defined NUMERIC_FIELDS at module level in src/transform.py
        and implemented float conversion in row_to_variation().
        """
        mappings_idx = {}

        row = {
            "brand": "Via Vai",
            "article_number": "15189-02",
            "price_buy_net": "58.5",
            "price_sell": "139.95",
            "discount_rate": "0.10",
            "currency": "EUR",
        }

        variation = row_to_variation(row, mappings_idx)

        self.assertIsInstance(variation["price_buy_net"], float)
        self.assertIsInstance(variation["price_sell"], float)
        self.assertIsInstance(variation["discount_rate"], float)

        self.assertEqual(variation["price_buy_net"], 58.5)
        self.assertEqual(variation["price_sell"], 139.95)
        self.assertEqual(variation["discount_rate"], 0.10)
        self.assertEqual(variation["currency"], "EUR")

    def test_build_catalog_e2e_counts_variations_and_structure(self) -> None:
        """
        End-to-end test:
        - Create tiny pricat + mappings CSV files (semicolon-delimited)
        - Build catalog
        - Verify:
          * row count == total variations count
          * correct catalog structure
          * grouping by article_number
          * mappings applied
          * numeric conversion applied (if enabled)
          * output is JSON-serializable
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            pricat_path = os.path.join(tmpdir, "pricat.csv")
            mappings_path = os.path.join(tmpdir, "mappings.csv")

            write_file(
                pricat_path,
                """
                ean;supplier;brand;catalog_code;collection;season;article_structure_code;article_number;size_group_code;size_code;currency;price_buy_net;price_sell
                111;Rupesco BV;Via Vai;;NW 17-18;winter;10;15189-02;EU;38;EUR;58.5;139.95
                222;Rupesco BV;Via Vai;;NW 17-18;winter;10;15189-02;EU;39;EUR;58.5;139.95
                """,
            )

            write_file(
                mappings_path,
                """
                source_type;source;destination_type;destination
                season;winter;season;Winter
                collection;NW 17-18;collection;Winter Collection 2017/2018
                article_structure_code;10;article_structure;Pump
                size_group_code|size_code;EU|38;size;European size 38
                size_group_code|size_code;EU|39;size;European size 39
                """,
            )

            mappings_idx = load_mappings_index(mappings_path)
            result, rows_processed = build_catalog_from_pricat(pricat_path, mappings_idx)

            self.assertEqual(rows_processed, 2)
            self.assertIn("catalog", result)
            self.assertEqual(result["catalog"]["brand"], "Via Vai")
            self.assertIsInstance(result["catalog"]["articles"], list)
            self.assertEqual(len(result["catalog"]["articles"]), 1)  # same article_number

            article = result["catalog"]["articles"][0]
            self.assertEqual(article["article_number"], "15189-02")

            variations = article["variations"]
            self.assertEqual(len(variations), 2)

            # brand must not be present inside variations
            self.assertTrue(all("brand" not in v for v in variations))

            # mappings were applied
            self.assertEqual(variations[0]["season"], "Winter")
            self.assertEqual(variations[0]["article_structure"], "Pump")
            self.assertEqual(variations[0]["collection"], "Winter Collection 2017/2018")

            # numeric conversion (only if you implemented it)
            self.assertIsInstance(variations[0]["price_buy_net"], float)
            self.assertIsInstance(variations[0]["price_sell"], float)

            # ensure JSON-serializable
            json.dumps(result)

    def test_build_catalog_inconsistent_brand_raises(self) -> None:
        """
        The challenge implies brand is consistent across all pricat rows.
        If brand changes across rows, we raise an error to avoid inconsistent output.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            pricat_path = os.path.join(tmpdir, "pricat.csv")
            mappings_path = os.path.join(tmpdir, "mappings.csv")

            write_file(
                pricat_path,
                """
                ean;brand;article_number
                111;Via Vai;15189-02
                222;Other Brand;15189-02
                """,
            )

            # Minimal mappings file with only headers (no rules)
            write_file(
                mappings_path,
                """
                source_type;source;destination_type;destination
                """,
            )

            mappings_idx = load_mappings_index(mappings_path)

            with self.assertRaises(ValueError):
                build_catalog_from_pricat(pricat_path, mappings_idx)


if __name__ == "__main__":
    unittest.main()