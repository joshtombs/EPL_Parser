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
CLOUD_STORAGE_BUCKET = os.environ['CLOUD_STORAGE_BUCKET']

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
    return resp_page.content

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
    sbm = soup.find('div', {'class': 'scorebox_meta'})
    if sbm is None:
        raise ValueError('Error parsing page')

    date_el = sbm.find('strong')
    if date_el is None:
        raise ValueError('Error parsing page')
    match['Date'] = date_el.text

    sb = soup.find('div', {'class': 'scorebox'})
    if sb is None:
        raise ValueError('Error parsing page')

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

def get_match_filename(date, hometeam, awayteam):
    match_date = datetime.datetime.strptime(date, '%A %B %d, %Y').strftime('%d%b%Y')
    home_name = hometeam.replace(' ', '_')
    away_name = awayteam.replace(' ', '_')
    return match_date + '_' + home_name + '_vs_' + away_name + '.json'

def store_match_json(match_json):
    bucket_name = os.environ.get('CLOUD_STORAGE_BUCKET')
    file_name = get_match_filename(match_json['Date'], match_json['HomeStats']['Team'], match_json['AwayStats']['Team'])

    storage_client = storage.Client()
    try:
        bucket = storage_client.get_bucket(bucket_name)
    except exceptions.NotFound:
        raise NameError("Bucket does not exist")
    
    try:
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

def print_run_statistics(run_stats):
    print('Run statistics:')
    print('   Total Matches: ', run_stats['total'])
    print('   New Matches: ', run_stats['new'])
    print('   Old Matches: ', run_stats['old'])
    print('   Skipped Matches: ', run_stats['skipped'])
    print('   --------------------------')
    print('   Bucket should have: ', run_stats['bucket'], ' matches')

@app.route("/")
def hello_world():
    return render_template('index.html')

@app.route("/test/<path:url>")
def test_pyppeteer(url):
    print("Got request to collect", url)
    # First collect the site from the url
    try:
        page_content = asyncio.run(get_page(url))
    except:
        return "Error retrieving match content from URL"
    soup = BeautifulSoup(page_content, 'html.parser')
    return "Success."

@app.route("/collectmatch/<path:url>")
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

@app.route("/findmatches")
def find_new_matches():
    url = "http://fbref.com/en/comps/9/schedule/Premier-League-Scores-and-Fixtures"

    # First collect the site from the url
    try:
        page_content = asyncio.run(get_page(url))
    except:
        return "Error retrieving fixture content from URL"

    # Then parse the HTML on the site
    soup = BeautifulSoup(page_content, 'html.parser')

    caption_el = soup.find('caption')
    if caption_el is None:
        raise ValueError('Error parsing page')

    match_table = caption_el.parent
    if match_table is None:
        raise ValueError('Error parsing page')

    match_tbody = match_table.find('tbody')
    if match_table is None:
        raise ValueError('Error parsing page')

    # Setup cloud storage checking
    bucket_name = os.environ.get('CLOUD_STORAGE_BUCKET')
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
        date_td = row.find('td', {'data-stat': 'date'})
        if date_td is None:
            raise ValueError('Error parsing page')

        try:
            match_date = datetime.datetime.strptime(date_td.text, '%Y-%m-%d').strftime('%A %B %d, %Y')
        except:
            raise ValueError('Error parsing page')

        squad_link_pattern =  '^/en\/squads\/(.+)\/(.+)-Stats'

        home_team_td = row.find('td', {'data-stat': 'squad_a'})
        if home_team_td is None:
            raise ValueError('Error parsing page')

        home_team_a = home_team_td.find('a', href=True)
        if home_team_a is None:
            raise ValueError('Error parsing page')
        ht = re.search(squad_link_pattern, home_team_a['href'])
        home_team = ht.group(2)
        if home_team is None:
            raise ValueError('Error parsing page')
        home_name = home_team.replace('-', ' ').replace(' and ', ' & ')

        away_team_td = row.find('td', {'data-stat': 'squad_b'})
        if away_team_td is None:
            raise ValueError('Error parsing page')

        away_team_a = away_team_td.find('a', href=True)
        if away_team_a is None:
            raise ValueError('Error parsing page')
        at = re.search(squad_link_pattern, away_team_a['href'])
        away_team = at.group(2)
        if away_team is None:
            raise ValueError('Error parsing page')
        away_name = away_team.replace('-', ' ').replace(' and ', ' & ')

        match_file_name = get_match_filename(match_date, home_name, away_name)

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
        match_report_td = row.find('td', {'data-stat': 'match_report'})
        if match_report_td is None:
            raise ValueError('Error parsing page')

        link = match_report_td.find('a')
        if link is not None:
            match_url = 'http://fbref.com' + link['href']

            pattern = re.compile(r'^http:\/\/fbref\.com\/en\/matches\/(.+)Premier\-League')
            if pattern.match(match_url) is None:
                print('URL doesnt match pattern... quitting')
                print(match_url)
                num_skipped_matches += 1
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
    bucket_name = os.environ.get('CLOUD_STORAGE_BUCKET')
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(bucket_name)

    bucket_blobs = []
    for blob in blobs:
        bucket_blobs.append(blob)

    return render_template('storage.html', bucket_blobs=bucket_blobs)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
