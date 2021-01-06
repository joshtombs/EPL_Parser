# Note, run with -b flag to suppress output
import unittest

import main
from main import (ASSIGN_OR_RAISE, get_match_filename, match_is_valid,
                print_run_statistics, extract_one_match_team)

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

class TestMatchIsValid(unittest.TestCase):
    def setUp(self):
        # Instead of actually populating stats, it is enough just to have array elements
        self.test_match = {
            'Date': 'Tuesday January 05, 2021',
            'Result': 'Draw',
            'HomeStats': {
                'Team': 'TeamA',
                'Goals': 5
            },
            'AwayStats': {
                'Team': 'TeamB',
                'Goals': 5
            },
            'HomePlayers': [0,1,2,3,4,5,6,7,8,9,10],
            'AwayPlayers': [0,1,2,3,4,5,6,7,8,9,10],
            'HomeKeepers': [0],
            'AwayKeepers': [0]
        }
    def test_match_is_valid_with_none(self):
        """
        Test that match_is_valid handles None for an input
        """
        self.assertEqual(match_is_valid(None), False)
    def test_match_is_valid_with_empty(self):
        """
        Test that match_is_valid handles an empty object as input
        """
        self.assertEqual(match_is_valid({}), False)
    def test_match_is_valid_with_good_match(self):
        """
        Test that match_is_valid asserts true when the input criteria is satisfied
        """
        self.assertEqual(match_is_valid(self.test_match), True)
    def test_match_is_valid_with_too_few_home_players(self):
        """
        Test that match_is_valid asserts false when too few home players
        """
        self.test_match['HomePlayers'] = [0,1,2,3]
        self.assertEqual(match_is_valid(self.test_match), False)
    def test_match_is_valid_with_too_few_away_players(self):
        """
        Test that match_is_valid asserts false when too few away players
        """
        self.test_match['AwayPlayers'] = []
        self.assertEqual(match_is_valid(self.test_match), False)
    def test_match_is_valid_with_too_few_home_players(self):
        """
        Test that match_is_valid asserts false when too few home keepers
        """
        self.test_match['HomeKeepers'] = []
        self.assertEqual(match_is_valid(self.test_match), False)
    def test_match_is_valid_with_too_few_away_players(self):
        """
        Test that match_is_valid asserts false when too few away keepers
        """
        self.test_match['AwayKeepers'] = []
        self.assertEqual(match_is_valid(self.test_match), False)
    def test_match_is_valid_with_bad_input(self):
        """
        Test that match_is_valid asserts false when a field is the wrong type
        """
        self.test_match = 'string'
        self.assertEqual(match_is_valid(self.test_match), False)
    def test_match_is_valid_with_no_date(self):
        """
        Test that match_is_valid asserts false when the date field is missing
        """
        self.test_match.pop('Date', None)
        self.assertEqual(match_is_valid(self.test_match), False)
    def test_match_is_valid_with_bad_date(self):
        """
        Test that match_is_valid asserts false when the date field is invalid
        """
        self.test_match['Date'] = 'Tuesday May 35, 2010'
        self.assertEqual(match_is_valid(self.test_match), False)
    def test_match_is_valid_with_no_result(self):
        """
        Test that match_is_valid asserts false when the result field is missing
        """
        self.test_match.pop('Result', None)
        self.assertEqual(match_is_valid(self.test_match), False)
    def test_match_is_valid_with_wrong_result(self):
        """
        Test that match_is_valid asserts false when the result field is incorrect
        """
        self.test_match['Result'] = 'Away'
        self.assertEqual(match_is_valid(self.test_match), False)
    def test_match_is_valid_with_no_home_score(self):
        """
        Test that match_is_valid asserts false when the home goal field is missing
        """
        self.test_match['HomeStats'].pop('Goals', None)
        self.assertEqual(match_is_valid(self.test_match), False)
    def test_match_is_valid_with_no_away_score(self):
        """
        Test that match_is_valid asserts false when the away goal field is missing
        """
        self.test_match['AwayStats'].pop('Goals', None)
        self.assertEqual(match_is_valid(self.test_match), False)

class TestPrintRunStatistics(unittest.TestCase):
    def setUp(self):
        self.stats = {
            'total': 100,
            'new': 60,
            'old': 40,
            'skipped': 5,
            'bucket': 95,
        }
    def test_print_run_statistics_with_valid(self):
        """
        Test that print_run_statistics succeeds with valid input
        """
        try:
            print_run_statistics(self.stats)
        except:
            self.fail('print_run_statistics failed unexpectedly')
    def test_print_run_statistics_with_none(self):
        """
        Test that print_run_statistics succeeds with None as an input
        """
        self.stats = None
        try:
            print_run_statistics(self.stats)
        except:
            self.fail('print_run_statistics failed unexpectedly')
    def test_print_run_statistics_with_invalid(self):
        """
        Test that print_run_statistics succeeds with valid input
        """
        self.stats = None
        try:
            print_run_statistics(self.stats)
        except:
            self.fail('print_run_statistics failed unexpectedly')

class TestExtractOneMatchTeam(unittest.TestCase):
    def setUp(self):
        self.match = {
            'Date': 'Saturday January 02, 2021',
            'Result': 'Away',
            'HomeStats': {
                'Team': 'TeamA',
                'Record': '0-4-1',
                'Goals': 2,
                'Possession': '51%'
            },
            'AwayStats': {
                'Team': 'TeamB & Spaces',
                'Record': '17-4-0',
                'Goals': 4,
                'Possession': '49%'
            },
            'HomeKeepers': [
                {
                    'Name': 'KeeperA'
                }
            ],
            'AwayKeepers': [
                {
                    'Name': 'KeeperB'
                }
            ],
            'HomePlayers': [0,1,2,3,4,5,6,7,8,9,10,11,12,13],
            'AwayPlayers': [0,1,2,3,4,5,6,7,8,9,10,11]
        }

    def test_extract_one_match_with_home(self):
        new_json = extract_one_match_team(self.match, self.match['HomeStats']['Team'])
        self.assertEqual(new_json['Team'], self.match['HomeStats']['Team'])
        self.assertEqual(new_json['Date'], self.match['Date'])
        self.assertEqual(new_json['Result'], 'Loss')
        self.assertEqual(new_json['Opponent'], self.match['AwayStats']['Team'])
        self.assertEqual(new_json['OppRecord'], self.match['AwayStats']['Record'])
        self.assertEqual(new_json['GlsFor'], self.match['HomeStats']['Goals'])
        self.assertEqual(new_json['GlsAgainst'], self.match['AwayStats']['Goals'])
        self.assertEqual(new_json['Possession'], self.match['HomeStats']['Possession'])
        self.assertEqual(new_json['Keepers'], self.match['HomeKeepers'])
        self.assertEqual(new_json['Players'], self.match['HomePlayers'])

    def test_extract_one_match_with_away(self):
        new_json = extract_one_match_team(self.match, self.match['AwayStats']['Team'])
        self.assertEqual(new_json['Team'], self.match['AwayStats']['Team'])
        self.assertEqual(new_json['Date'], self.match['Date'])
        self.assertEqual(new_json['Result'], 'Win')
        self.assertEqual(new_json['Opponent'], self.match['HomeStats']['Team'])
        self.assertEqual(new_json['OppRecord'], self.match['HomeStats']['Record'])
        self.assertEqual(new_json['GlsFor'], self.match['AwayStats']['Goals'])
        self.assertEqual(new_json['GlsAgainst'], self.match['HomeStats']['Goals'])
        self.assertEqual(new_json['Possession'], self.match['AwayStats']['Possession'])
        self.assertEqual(new_json['Keepers'], self.match['AwayKeepers'])
        self.assertEqual(new_json['Players'], self.match['AwayPlayers'])

    def test_extract_one_match_with_bad_team(self):
        new_json = extract_one_match_team(self.match, 'TeamC')
        self.assertIsNone(new_json)

    def test_extract_one_match_with_none_match(self):
        new_json = extract_one_match_team(None, self.match['AwayStats']['Team'])
        self.assertIsNone(new_json)

    def test_extract_one_match_with_missing_team(self):
        self.match['HomeStats'].pop('Team', None)
        new_json = extract_one_match_team(self.match, self.match['AwayStats']['Team'])
        self.assertIsNone(new_json)

if __name__ == '__main__':
    unittest.main()