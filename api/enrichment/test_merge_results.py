"""Tests for merge_results cross-validation logic."""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure the enrichment module is importable
sys.path.insert(0, os.path.dirname(__file__))

from merge_results import _cross_validate


class TestCrossValidate(unittest.TestCase):

    def test_mismatch_detected(self):
        """Cross-validation returns mismatches when classifier and registration disagree."""
        classifier = {'make': 'Toyota', 'model': 'Camry', 'year': 2020, 'color': 'blue'}
        registration = {'make': 'Honda', 'model': 'Accord', 'year': 2018, 'color': 'red'}

        mismatches = _cross_validate(classifier, registration)

        self.assertTrue(len(mismatches) > 0)
        self.assertTrue(any('make' in m for m in mismatches))
        self.assertTrue(any('model' in m for m in mismatches))
        self.assertTrue(any('color' in m for m in mismatches))
        self.assertTrue(any('year' in m for m in mismatches))

    def test_no_mismatch_when_data_matches(self):
        """Cross-validation returns empty list when classifier and registration agree."""
        classifier = {'make': 'Toyota', 'model': 'Camry', 'year': 2020, 'color': 'blue'}
        registration = {'make': 'Toyota', 'model': 'Camry', 'year': 2020, 'color': 'blue'}

        mismatches = _cross_validate(classifier, registration)

        self.assertEqual(mismatches, [])


if __name__ == '__main__':
    unittest.main()
