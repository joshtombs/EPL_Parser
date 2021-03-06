# main.py

# Imports for web server
import os
from flask import Flask, render_template, json, jsonify

# Imports for web scraping
from requests_html import AsyncHTMLSession
from bs4 import BeautifulSoup
import asyncio
import pyppeteer
import re
import time

# Imports for Google Cloud Storage
from google.cloud import storage
import datetime

app = Flask(__name__)

# Configure this environment variable via app.yaml
bucket_name = os.environ.get('CLOUD_STORAGE_BUCKET')

analysis_file_names = ["todays_analysis.json", "tomorrows_analysis.json"]

# Helper function to avoid calling methods on empty objects
def ASSIGN_OR_RAISE(expr):
    if expr is None:
        raise ValueError('Error parsing page')
    return expr

async def get_page(url):
    new_loop=asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    session = AsyncHTMLSession()
    print("Launching browser...")
    browser = await pyppeteer.launch({
        'executablePath': 'google-chrome-unstable',
        'ignoreHTTPSErrors':True,
        'dumpio':True,
        'headless':True,
        'handleSIGINT':False,
        'handleSIGTERM':False,
        'handleSIGHUP':False
    })
    print("Launched browser...")
    session._browser = browser
    resp_page = await session.get(url)
    print("Got response from page...")
    await resp_page.html.arender()
    print("Rendered page...")
    content = resp_page.content

    await browser.close()

    return content

def build_empty_json_obj():
    match = {}
    match['Date'] = ""
    match['Result'] = ""
    match['HomeStats'] = {}
    match['HomeStats']['Team'] = ""
    match['HomeStats']['Record'] = ""
    match['HomeStats']['Formation'] = ""
    match['HomeStats']['Possession'] = ""
    match['HomePlayers'] = []
    match['HomeKeepers'] = []
    match['AwayStats'] = {}
    match['AwayStats']['Team'] = ""
    match['AwayStats']['Record'] = ""
    match['AwayStats']['Formation'] = ""
    match['AwayStats']['Possession'] = ""
    match['AwayPlayers'] = []
    match['AwayKeepers'] = []
    return match

def parse_header(soup, match):
    sbm = ASSIGN_OR_RAISE(soup.find('div', {'class': 'scorebox_meta'}))
    date_el = ASSIGN_OR_RAISE(sbm.find('strong'))
    match['Date'] = date_el.text

    sb = ASSIGN_OR_RAISE(soup.find('div', {'class': 'scorebox'}))
    
    team_names = sb.findAll('a', {'itemprop': 'name'})
    if len(team_names) < 2:
        raise ValueError('Error parsing page')
    match['HomeStats']['Team'] = team_names[0].text
    match['AwayStats']['Team'] = team_names[1].text

    scores_el = sb.find_all('div', {'class':'score'})
    if len(scores_el) < 2:
        raise ValueError('Error parsing page')
    match['HomeStats']['Goals'] = int(scores_el[0].text)
    match['AwayStats']['Goals'] = int(scores_el[1].text)

    if match['HomeStats']['Goals'] == match['AwayStats']['Goals']:
        match['Result'] = 'Draw'
    elif match['HomeStats']['Goals'] > match['AwayStats']['Goals']:
        match['Result'] = 'Home'
    else:
        match['Result'] = 'Away'

    scores_divs = sb.findAll('div', {'class': 'scores'})
    if len(scores_divs) >= 2:
        match['HomeStats']['Record'] = scores_divs[0].nextSibling.text
        match['AwayStats']['Record'] = scores_divs[1].nextSibling.text

    lineup_el = soup.find_all('div', {'class': 'lineup'})
    if len(lineup_el) >= 2:
        home_formation_el = lineup_el[0].find('th')
        if home_formation_el is not None:
            match['HomeStats']['Formation'] = re.findall(r'\(.*?\)', home_formation_el.text)[0]
        away_formation_el = lineup_el[1].find('th')
        if away_formation_el is not None:
            match['AwayStats']['Formation'] = re.findall(r'\(.*?\)', away_formation_el.text)[0]

    possession_text = soup.find(text="Possession")
    if possession_text is not None:
        possession_tr = possession_text.parent
        if possession_tr is not None:
            # TODO: refactor for error checking
            strong_el = possession_tr.findNext('tr').find('strong')
            match['HomeStats']['Possession'] = strong_el.text
            match['AwayStats']['Possession'] = strong_el.findNext('strong').text

    return match

def parse_players(soup, match):
    summary_tables = soup.findAll('table', {'id': re.compile(r'stats_(.+)_summary')})
    misc_tables = soup.findAll('table', {'id': re.compile(r'stats_(.+)_misc')})
    pass_tables = soup.findAll('table', {'id': re.compile(r'stats_(.+)_passing\b')})
    for tbl_num, (summary_table, misc_table, pass_table) in enumerate(zip(summary_tables, misc_tables, pass_tables), start=1):
        summary_rows = summary_table.find('tbody').findAll('tr')
        misc_rows = misc_table.find('tbody').findAll('tr')
        pass_rows = pass_table.find('tbody').findAll('tr')
        for (summary_row, misc_row, pass_row) in zip(summary_rows, misc_rows, pass_rows):
            player = {}

            name_el = summary_row.find('th')
            if name_el is None:
                continue
            player['Name'] = name_el.text.strip()

            pos_el = summary_row.find('td', {'data-stat': 'position'})
            if pos_el is None:
                continue
            player['Pos'] = pos_el.text.strip()

            min_el = summary_row.find('td', {'data-stat': 'minutes'})
            if min_el is not None:
                player['Min'] = int(min_el.text.strip())

            gls_el = summary_row.find('td', {'data-stat': 'goals'})
            if gls_el is not None:
                player['Gls'] = int(gls_el.text.strip())

            asts_el = summary_row.find('td', {'data-stat': 'assists'})
            if asts_el is not None:
                player['Asts'] = int(asts_el.text.strip())

            pk_el = summary_row.find('td', {'data-stat': 'pens_made'})
            if pk_el is not None:
                player['PK'] = int(pk_el.text.strip())

            pkatt_el = summary_row.find('td', {'data-stat': 'pens_att'})
            if pkatt_el is not None:
                player['PKatt'] = int(pkatt_el.text.strip())

            shots_el = summary_row.find('td', {'data-stat': 'shots_total'})
            if shots_el is not None:
                player['Sh'] = int(shots_el.text.strip())

            sot_el = summary_row.find('td', {'data-stat': 'shots_on_target'})
            if sot_el is not None:
                player['SoT'] = int(sot_el.text.strip())

            crdY_el = summary_row.find('td', {'data-stat': 'cards_yellow'})
            if crdY_el is not None:
                player['CrdY'] = int(crdY_el.text.strip())

            crdR_el = summary_row.find('td', {'data-stat': 'cards_red'})
            if crdR_el is not None:
                player['CrdR'] = int(crdR_el.text.strip())

            crdYR_el = misc_row.find('td', {'data-stat': 'cards_yellow_red'})
            if crdYR_el is not None:
                player['2CrdY'] = int(crdYR_el.text.strip())

            touches_el = summary_row.find('td', {'data-stat': 'touches'})
            if touches_el is not None:
                player['Touches'] = int(touches_el.text.strip())

            int_el = summary_row.find('td', {'data-stat': 'interceptions'})
            if int_el is not None:
                player['Int'] = int(int_el.text.strip())

            block_el = summary_row.find('td', {'data-stat': 'blocks'})
            if block_el is not None:
                player['Blk'] = int(block_el.text.strip())

            pcomp_el = summary_row.find('td', {'data-stat': 'passes_completed'})
            if pcomp_el is not None:
                player['pComp'] = int(pcomp_el.text.strip())

            passatt_el = summary_row.find('td', {'data-stat': 'passes'})
            if passatt_el is not None:
                player['pAtt'] = int(passatt_el.text.strip())

            xa_el = summary_row.find('td', {'data-stat': 'xa'})
            if xa_el is not None:
                player['xA'] = float(xa_el.text.strip())

            xg_el = summary_row.find('td', {'data-stat': 'xg'})
            if xg_el is not None:
                player['xG'] = float(xg_el.text.strip())

            crs_el = misc_row.find('td', {'data-stat': 'crosses'})
            if crs_el is not None:
                player['Crs'] = int(crs_el.text.strip())

            tklw_el = misc_row.find('td', {'data-stat': 'tackles_won'})
            if tklw_el is not None:
                player['TklW'] = int(tklw_el.text.strip())

            fouls_el = misc_row.find('td', {'data-stat': 'fouls'})
            if fouls_el is not None:
                player['Fls'] = int(fouls_el.text.strip())

            fouled_el = misc_row.find('td', {'data-stat': 'fouled'})
            if fouled_el is not None:
                player['Fld'] = int(fouled_el.text.strip())

            astshots_el = pass_row.find('td', {'data-stat': 'assisted_shots'})
            if astshots_el is not None:
                player['AstShots'] = int(astshots_el.text.strip())

            if tbl_num == 1:
                match['HomePlayers'].append(player)
            elif tbl_num == 2:
                match['AwayPlayers'].append(player)

    return match

def parse_keepers(soup, match):
    keeper_tables = soup.findAll('table', {'id': re.compile(r'keeper_stats_(.+)')})
    for tbl_num, keeper_table in enumerate(keeper_tables, start=1):
        rows = keeper_table.find('tbody').findAll('tr')
        for row in rows:
            player = {}

            name_el = row.find('th')
            if name_el is None:
                continue
            player['Name'] = name_el.text.strip()

            minutes_el = row.find('td', {'data-stat': 'minutes'})
            if minutes_el is not None:
                player['Min'] = int(minutes_el.text.strip())

            sota_el = row.find('td', {'data-stat': 'shots_on_target_against'})
            if sota_el is not None:
                player['SoTA'] = int(sota_el.text.strip())

            ga_el = row.find('td', {'data-stat': 'goals_against_gk'})
            if ga_el is not None:
                player['GA'] = int(ga_el.text.strip())

            psxg_el = row.find('td', {'data-stat': 'psxg_gk'})
            if psxg_el is not None:
                player['PSxG'] = float(psxg_el.text.strip())

            if tbl_num == 1:
                match['HomeKeepers'].append(player)
            elif tbl_num == 2:
                match['AwayKeepers'].append(player)

    return match

def parse_page_to_json(soup):
    match = build_empty_json_obj()
    match = parse_header(soup, match)
    match = parse_players(soup, match)
    match = parse_keepers(soup, match)
    return match

# Helper function to construct a JSON filename for a match. Inputs are strings
# for date (format WEEKDAY MONTH DAY, YEAR ex. Tuesday January 05, 2021), and
# home & away team names. If an invalid input is detected, None is returned
def get_match_filename(date, hometeam, awayteam):
    try:
        match_date = datetime.datetime.strptime(date, '%A %B %d, %Y').strftime('%d%b%Y')
    except:
        print('Error parsing match_date')
        return None

    if type(hometeam) == str and type(awayteam) == str:
        home_name = hometeam.replace(' ', '_')
        away_name = awayteam.replace(' ', '_')
        return match_date + '_' + home_name + '_vs_' + away_name + '.json'
    else:
        print('Team names must be strings')
        return None

# Helper function to validate whether a match has proper information. Returns
# True if the match looks valid, and False if something doesn't look right
def match_is_valid(match_json):
    try:
        if len(match_json['HomePlayers']) < 11:
            return False
        if len(match_json['AwayPlayers']) < 11:
            return False
        if len(match_json['HomeKeepers']) < 1:
            return False
        if len(match_json['AwayKeepers']) < 1:
            return False
        if datetime.datetime.strptime(match_json['Date'], '%A %B %d, %Y') is None:
            return False
        if match_json['HomeStats']['Goals'] < 0:
            return False
        if match_json['AwayStats']['Goals'] < 0:
            return False
        if match_json['Result'] == 'Draw' and (match_json['HomeStats']['Goals'] != match_json['AwayStats']['Goals']):
            return False
        elif match_json['Result'] == 'Home' and (match_json['HomeStats']['Goals'] <= match_json['AwayStats']['Goals']):
            return False
        elif match_json['Result'] == 'Away' and (match_json['HomeStats']['Goals'] >= match_json['AwayStats']['Goals']):
            return False
    except:
        return False
    return True

# Helper function to convert a match JSON object (data collected from parsing
# one match) into one stored for analysis (which only really cares about one
# team in the match)
def extract_one_match_team(match_json, team):
    new_match_json = {}
    try:
        new_match_json['Date'] = match_json['Date']
        if team == match_json['HomeStats']['Team']:
            team_stats = match_json['HomeStats']
            opp_stats = match_json['AwayStats']
            new_match_json['Keepers'] = match_json['HomeKeepers']
            new_match_json['Players'] = match_json['HomePlayers']
            if match_json['Result'] == 'Home':
                new_match_json['Result'] = 'Win'
            elif match_json['Result'] == 'Away':
                new_match_json['Result'] = 'Loss'
            else:
                new_match_json['Result'] = 'Draw'
        elif team == match_json['AwayStats']['Team']:
            team_stats = match_json['AwayStats']
            opp_stats = match_json['HomeStats']
            new_match_json['Keepers'] = match_json['AwayKeepers']
            new_match_json['Players'] = match_json['AwayPlayers']
            if match_json['Result'] == 'Away':
                new_match_json['Result'] = 'Win'
            elif match_json['Result'] == 'Home':
                new_match_json['Result'] = 'Loss'
            else:
                new_match_json['Result'] = 'Draw'
        else:
            return None

        new_match_json['Team'] = team_stats['Team']
        new_match_json['Opponent'] = opp_stats['Team']
        new_match_json['OppRecord'] = opp_stats['Record']
        new_match_json['GlsFor'] = team_stats['Goals']
        new_match_json['GlsAgainst'] = opp_stats['Goals']
        new_match_json['Possession'] = team_stats['Possession']
    except:
        return None

    return new_match_json

def store_match_json(match_json):
    if not match_is_valid(match_json):
        print('Skipped storing json file because match is not valid')
        return

    file_name = get_match_filename(match_json['Date'], match_json['HomeStats']['Team'], match_json['AwayStats']['Team'])

    storage_client = storage.Client()
    try:
        bucket = storage_client.get_bucket(bucket_name)
    except exceptions.NotFound:
        raise NameError("Bucket does not exist")

    try:
        if file_name is None:
            raise NameError("Error generating filename from match")
        if storage.Blob(bucket=bucket, name=file_name).exists(storage_client):
            raise NameError("File for match already exists")
    except:
        raise NameError("Error checking if file exists")

    try:
        blob = bucket.blob(file_name)
        blob.upload_from_string(
            data=json.dumps(match_json),
            content_type='application/json'
        )
    except:
        raise ValueError("Error writing JSON file to bucket")

# Helper method to print statistics from the find_new_matches function
def print_run_statistics(run_stats):
    def object_or_empty_string(obj, key):
        try:
            val = obj[key]
        except (KeyError, TypeError):
            val = ''
        return val

    print('Run statistics:')
    print('   Total Matches: ', object_or_empty_string(run_stats, 'total'))
    print('   New Matches: ', object_or_empty_string(run_stats, 'new'))
    print('   Old Matches: ', object_or_empty_string(run_stats, 'old'))
    print('   Skipped Matches: ', object_or_empty_string(run_stats, 'skipped'))
    print('   --------------------------')
    print('   Bucket should have: ', object_or_empty_string(run_stats, 'bucket'))

def extract_team_names_from_links(parent_el):
    squad_link_pattern =  '^/en\/squads\/(.+)\/(.+)-Stats'

    home_team_td = ASSIGN_OR_RAISE(parent_el.find('td', {'data-stat': 'squad_a'}))
    home_team_a = ASSIGN_OR_RAISE(home_team_td.find('a', href=True))
    ht = re.search(squad_link_pattern, home_team_a['href'])
    home_team = ASSIGN_OR_RAISE(ht.group(2))
    home_name = home_team.replace('-', ' ').replace(' and ', ' & ')

    away_team_td = ASSIGN_OR_RAISE(parent_el.find('td', {'data-stat': 'squad_b'}))
    away_team_a = ASSIGN_OR_RAISE(away_team_td.find('a', href=True))
    at = re.search(squad_link_pattern, away_team_a['href'])
    away_team = ASSIGN_OR_RAISE(at.group(2))
    away_name = away_team.replace('-', ' ').replace(' and ', ' & ')

    return [home_name, away_name]

def get_matches_for_date(date, storage_client):
    # Get past match data
    blobs = storage_client.list_blobs(bucket_name)
    url = "http://fbref.com/en/comps/9/schedule/Premier-League-Scores-and-Fixtures"

    # First collect the site from the url
    try:
        page_content = asyncio.run(get_page(url))
    except:
        return "Error retrieving fixture content from URL"

    # Then parse the HTML on the site
    soup = BeautifulSoup(page_content, 'html.parser')
    match_els = soup.find_all('td', {'csk': date})
    matches = []
    for match_el in match_els:
        parent_el = match_el.parent
        team_names = extract_team_names_from_links(parent_el)

        match = {}
        match['HomeTeam'] = {}
        match['HomeTeam']['Name'] = team_names[0]
        match['HomeTeam']['PastMatches'] = []
        match['AwayTeam'] = {}
        match['AwayTeam']['Name'] = team_names[1]
        match['AwayTeam']['PastMatches'] = []
        match['History'] = []

        # TODO follow link to get match history b/t teams w/ a cutoff date

        matches.append(match)

    # Parse past matches for the teams
    for blob in blobs:
        for match in matches:
            home_pattern = re.compile(r'.*(%s).*'%match['HomeTeam']['Name'].replace(' ', '_'))
            away_pattern = re.compile(r'.*(%s).*'%match['AwayTeam']['Name'].replace(' ', '_'))
            if home_pattern.match(blob.name) is not None:
                match_json_str = blob.download_as_string()
                match['HomeTeam']['PastMatches'].append(extract_one_match_team(json.loads(match_json_str), match['HomeTeam']['Name']))
            if away_pattern.match(blob.name) is not None:
                match_json_str = blob.download_as_string()
                match['AwayTeam']['PastMatches'].append(extract_one_match_team(json.loads(match_json_str), match['AwayTeam']['Name']))

    # Sort PastMatches by date in reverse order, and keep only 10 most recent
    for match in matches:
        match['HomeTeam']['PastMatches'] = sorted(
            match['HomeTeam']['PastMatches'], key = lambda item: datetime.datetime.strptime(
                item['Date'], '%A %B %d, %Y'), reverse=True)[0:10]
        match['AwayTeam']['PastMatches'] = sorted(
            match['AwayTeam']['PastMatches'], key = lambda item: datetime.datetime.strptime(
                item['Date'], '%A %B %d, %Y'), reverse=True)[0:10]

    # TODO: Get odds?

    return matches

@app.route("/")
def hello_world():
    return render_template('index.html')

# @app.route("/collectmatch/<path:url>")
def collect_match(url):
    print("Got request to collect", url)
    # Check URL against fbref pattern
    pattern = re.compile(r'^http:\/\/fbref\.com\/en\/matches\/(.+)Premier\-League')
    if pattern.match(url) is None:
        return "Url does not match expected pattern"

    # First collect the site from the url
    try:
        page_content = asyncio.run(get_page(url))
    except:
        return "Error retrieving match content from URL"

    # Then parse the HTML on the site
    soup = BeautifulSoup(page_content, 'html.parser')
    match_json = parse_page_to_json(soup)

    # Then store the file on Google Cloud Storage
    try:
        store_match_json(match_json)
    except:
        return "Error storing the json file"

    return jsonify(match_json)

@app.route("/forcefindmatches", defaults={'force': True})
@app.route("/findmatches", defaults={'force': False})
# Force is a boolean that specifies whether to force saving data even if there are
# more than 100 fixtures to collect. Not forcing, protects the app from automatically
# storing too many files at once (which would likely be a bug, because there are not
# hundreds of new matches per day)
def find_new_matches(force):
    url = "http://fbref.com/en/comps/9/schedule/Premier-League-Scores-and-Fixtures"

    # First collect the site from the url
    try:
        page_content = asyncio.run(get_page(url))
    except:
        return "Error retrieving fixture content from URL"

    # Then parse the HTML on the site
    soup = BeautifulSoup(page_content, 'html.parser')

    caption_el = ASSIGN_OR_RAISE(soup.find('caption'))
    match_table = ASSIGN_OR_RAISE(caption_el.parent)
    match_tbody = ASSIGN_OR_RAISE(match_table.find('tbody'))

    # Setup cloud storage checking
    storage_client = storage.Client()
    try:
        bucket = storage_client.get_bucket(bucket_name)
    except exceptions.NotFound:
        raise NameError("Bucket does not exist")

    # Collect statistics
    num_total_matches = 0
    num_already_collected_matches = 0
    num_new_matches = 0
    num_skipped_matches = 0

    # Iterate through each match
    match_rows = match_tbody.find_all('tr', {'class': None})
    for row in match_rows:
        num_total_matches += 1
        date_td = ASSIGN_OR_RAISE(row.find('td', {'data-stat': 'date'}))

        try:
            match_date = datetime.datetime.strptime(date_td.text, '%Y-%m-%d').strftime('%A %B %d, %Y')
        except:
            raise ValueError('Error parsing page')

        team_names = extract_team_names_from_links(row)
        match_file_name = get_match_filename(match_date, team_names[0], team_names[1])
        if match_file_name is None:
            continue    # Error parsing filename from match info provided

        # Check for file in bucket
        try:
            print('Checking bucket for file: ' + match_file_name)
            if storage.Blob(bucket=bucket, name=match_file_name).exists(storage_client):
                print("File for match already exists")
                num_already_collected_matches += 1
                continue
        except:
            raise NameError("Error checking if file exists")

        # Get link for match report
        match_report_td = ASSIGN_OR_RAISE(row.find('td', {'data-stat': 'match_report'}))

        link = match_report_td.find('a')
        if link is not None:
            match_url = 'http://fbref.com' + link['href']

            pattern = re.compile(r'^http:\/\/fbref\.com\/en\/matches\/(.+)Premier\-League')
            if pattern.match(match_url) is None:
                print('URL doesnt match pattern... quitting')
                print(match_url)
                num_skipped_matches += 1
                break

            if num_new_matches > 99 and not force:
                print('Hit an upper limit for number of games per day - this is likely a bug')
                break
            collect_match(match_url)
            time.sleep(15)  # Sleep 15 seconds as to not overload host server
            num_new_matches += 1
        else:
            num_skipped_matches += 1

    run_stats = {}
    run_stats['total'] = num_total_matches
    run_stats['new'] = num_new_matches
    run_stats['old'] = num_already_collected_matches
    run_stats['skipped'] = num_skipped_matches
    run_stats['bucket'] = num_total_matches - num_skipped_matches

    return render_template('findmatches.html', stats=run_stats)

@app.route("/storage", defaults={'filename': 'file1.json'})
@app.route("/storage/<string:filename>")
def see_storage(filename):
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(bucket_name)

    bucket_blobs = []
    for blob in blobs:
        bucket_blobs.append(blob)

    return render_template('storage.html', bucket_blobs=bucket_blobs)

@app.route("/run-analysis")
def run_analysis():
    # Get matches for today and tomorrow
    todays_date = datetime.datetime.today().strftime('%Y%m%d')
    tomorrows_date = (datetime.datetime.today() + datetime.timedelta(days=1)).strftime('%Y%m%d')
    storage_client = storage.Client()
    todays_matches = get_matches_for_date(todays_date, storage_client)
    tomorrows_matches = get_matches_for_date(tomorrows_date, storage_client)

    # Store analysis JSON in bucket
    try:
        bucket = storage_client.get_bucket(bucket_name)
    except exceptions.NotFound:
        raise NameError("Bucket does not exist")

    # Delete old analysis files (if they exists)
    for analysis_file_name in analysis_file_names:
        blob = bucket.get_blob(analysis_file_name)
        if blob is not None:
            blob.delete()

    # Create the new analysis files
    try:
        blob = bucket.blob(analysis_file_names[0])
        blob.upload_from_string(
            data=json.dumps(todays_matches),
            content_type='application/json'
        )
        blob = bucket.blob(analysis_file_names[1])
        blob.upload_from_string(
            data=json.dumps(tomorrows_matches),
            content_type='application/json'
        )
    except:
        raise ValueError("Error writing JSON file to bucket")

    return "Success running analysis"

@app.route("/view-analysis")
def view_analysis():
    storage_client = storage.Client()
    try:
        bucket = storage_client.get_bucket(bucket_name)
    except exceptions.NotFound:
        raise NameError("Bucket does not exist")

    # Check for file in bucket
    try:
        if not storage.Blob(bucket=bucket, name=analysis_file_names[0]).exists(storage_client):
            return "Todays anaylsis file does not exist"
        if not storage.Blob(bucket=bucket, name=analysis_file_names[1]).exists(storage_client):
            return "Tomorrows anaylsis file does not exist"
    except:
        raise NameError("Error checking if file exists")

    # Get todays analysis object
    blob = bucket.get_blob(analysis_file_names[0])
    json_string = blob.download_as_string()
    todays_matches = json.loads(json_string)

    # Get todays analysis object
    blob = bucket.get_blob(analysis_file_names[1])
    json_string = blob.download_as_string()
    tomorrows_matches = json.loads(json_string)

    return render_template('view_analysis.html', todays_matches=todays_matches, tomorrows_matches=tomorrows_matches)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
