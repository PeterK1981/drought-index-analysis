import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from rasterio.transform import from_origin

from drought.analysis import (Climate, bivariate, classify, de_martonne,
                              load_climate, quantile_breaks, smooth_classes)


class AnalysisTests(unittest.TestCase):
    def test_formula_and_invalid_values(self):
        result = de_martonne([600, -1, 600, np.nan], [10, 10, -10, 10])
        self.assertEqual(result[0], 30)
        self.assertTrue(np.isnan(result[1:]).all())

    def test_thresholds_belong_to_upper_class(self):
        np.testing.assert_array_equal(classify([9, 10, 20, 24, 28, 35, 55, np.nan]),
                                      [0, 1, 2, 3, 4, 5, 6, -1])

    def test_majority_is_not_median(self):
        values = np.array([[0, 0, 0], [0, 3, 3], [6, 6, 6]])
        self.assertEqual(smooth_classes(values, 3, "majority")[1, 1], 0)
        self.assertEqual(smooth_classes(values, 3, "median")[1, 1], 3)

    def test_smoothing_does_not_fill_missing_cells(self):
        values = np.array([[-1, -1, -1], [-1, 5, 5], [-1, 5, 5]])
        for method in ("majority", "median"):
            result = smooth_classes(values, 3, method)
            np.testing.assert_array_equal(result[values < 0], -1)
            np.testing.assert_array_equal(result[values == 5], 5)

    def test_tied_quartiles_do_not_split_equal_values(self):
        values = np.full((2, 2), 10.)
        breaks = quantile_breaks(values)
        climate = Climate(values, values, None, (2000, 2000))
        np.testing.assert_array_equal(bivariate(climate, breaks, breaks), 0)

    def test_reference_breaks_are_applied_unchanged(self):
        climate = Climate(np.array([[20., 60.]]), np.array([[5., 15.]]), None, (2000, 2000))
        np.testing.assert_array_equal(bivariate(climate, [25, 50, 75], [6, 10, 14]), [[0, 14]])

    def test_incomplete_year_is_masked_and_temperature_scaled(self):
        transform = from_origin(0, 2, 1, 1)
        arrays = [np.array([[600., 600.]]), np.array([[100., 100.]]),
                  np.array([[800., np.nan]]), np.array([[120., 120.]])]
        with patch("drought.analysis.source_path", return_value=Path("dummy.asc")), \
             patch("drought.analysis.read_grid", side_effect=[(a, transform) for a in arrays]):
            result = load_climate("unused", 2000, 2001)
        self.assertEqual(result.precipitation[0, 0], 700)
        self.assertEqual(result.temperature[0, 0], 11)
        self.assertTrue(np.isnan(result.index[0, 1]))

    def test_misaligned_rasters_rejected(self):
        values = np.ones((2, 2))
        with patch("drought.analysis.source_path", return_value=Path("dummy.asc")), \
             patch("drought.analysis.read_grid", side_effect=[
                 (values, from_origin(0, 2, 1, 1)), (values, from_origin(1, 2, 1, 1))]):
            with self.assertRaisesRegex(ValueError, "deckungsgleich"):
                load_climate("unused", 2000, 2000)


if __name__ == "__main__":
    unittest.main()
