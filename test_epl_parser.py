# Note, run with -b flag to suppress output
import unittest

import main
from main import ASSIGN_OR_RAISE, get_match_filename

class TestAssignOrRaise(unittest.TestCase):
    def test_assign_or_raise_with_none(self):
        """
        Test to ensure ASSIGN_OR_RAISE raises when an expression evaluates
        to none
        """
        self.assertRaises(ValueError, lambda: ASSIGN_OR_RAISE(None))
    def test_assign_or_raise_with_string(self):
        """
        Test to ensure ASSIGN_OR_RAISE returns a string when passed a string
        """
        self.assertEqual(ASSIGN_OR_RAISE('6'), '6')
    def test_assign_or_raise_with_object(self):
        """
        Test to ensure ASSIGN_OR_RAISE returns an object when passed the object
        """
        obj = type('obj', (object,), {'propertyName' : 'propertyValue'})
        self.assertEqual(ASSIGN_OR_RAISE(obj), obj)
        self.assertEqual(ASSIGN_OR_RAISE(obj.propertyName), 'propertyValue')

class TestGetMatchFilename(unittest.TestCase):
    def test_get_match_filename_no_date(self):
        """
        Test that get_match_filename handles None for a date
        """
        expected_name = None
        self.assertEqual(get_match_filename(None, 'TeamA', 'TeamB'), expected_name)
    def test_get_match_filename_no_teams(self):
        """
        Test that get_match_filename handles None for a team
        """
        expected_name = None
        self.assertEqual(get_match_filename('Sunday January 03, 2021', None, None), expected_name)
    def test_get_match_filename_simple(self):
        """
        Test that match filename generated correctly in base case
        """
        expected_name = '03Jan2021_TeamA_vs_TeamB.json'
        self.assertEqual(get_match_filename('Sunday January 03, 2021', 'TeamA', 'TeamB'), expected_name)
    def test_get_match_filename_with_spaces(self):
        """
        Test that match filename with spaces is generated correctly
        """
        expected_name = '05Jan2021_Team_with_Spaces_vs_Team_with_&_symbol.json'
        self.assertEqual(get_match_filename('Tuesday January 05, 2021', 'Team with Spaces', 'Team with & symbol'), expected_name)
    def test_get_match_filename_with_bad_date(self):
        """
        Test that match filename returns None for an invalid date
        """
        expected_name = None
        self.assertEqual(get_match_filename('Monday February 32, 2021', 'TeamA', 'TeamB'), expected_name)
        self.assertEqual(get_match_filename('Something January 5, 2021', 'TeamA', 'TeamB'), expected_name)
        self.assertEqual(get_match_filename('Tuesday January 5, -5', 'TeamA', 'TeamB'), expected_name)
    def test_get_match_filename_with_wrong_weekday(self):
        """
        Test that match filename ignores the weekday being wrong
        """
        expected_name = expected_name = '05Jan2021_TeamA_vs_TeamB.json'
        self.assertEqual(get_match_filename('Tuesday January 05, 2021', 'TeamA', 'TeamB'), expected_name)
        self.assertEqual(get_match_filename('Thursday January 05, 2021', 'TeamA', 'TeamB'), expected_name)

if __name__ == '__main__':
    unittest.main()