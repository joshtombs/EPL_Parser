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
    match['Date'] = sbm.find('strong').text
    
    sb = soup.find('div', {'class': 'scorebox'})
    team_names = sb.findAll('a', {'itemprop': 'name'})
    match['HomeStats']['Team'] = team_names[0].text
    match['AwayStats']['Team'] = team_names[1].text

    scores_el = sb.find_all('div', {'class':'score'})
    match['HomeStats']['Goals'] = int(scores_el[0].text)
    match['AwayStats']['Goals'] = int(scores_el[0].text)

    if match['HomeStats']['Goals'] == match['AwayStats']['Goals']:
        match['Result'] = 'Draw'
    elif match['HomeStats']['Goals'] > match['AwayStats']['Goals']:
        match['Result'] = 'Home'
    else:
        match['Result'] = 'Away'

    scores_divs = sb.findAll('div', {'class': 'scores'})
    match['HomeStats']['Record'] = scores_divs[0].nextSibling.text
    match['AwayStats']['Record'] = scores_divs[1].nextSibling.text

    lineup_el = soup.find_all('div', {'class': 'lineup'})
    match['HomeStats']['Formation'] = re.findall(r'\(.*?\)', lineup_el[0].find('th').text)[0]
    match['AwayStats']['Formation'] = re.findall(r'\(.*?\)', lineup_el[1].find('th').text)[0]

    possession_text = soup.find(text="Possession")
    possession_tr = possession_text.parent
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
            player['Name'] = summary_row.find('th').text.strip()
            player['Pos'] = summary_row.find('td', {'data-stat': 'position'}).text.strip()
            player['Min'] = summary_row.find('td', {'data-stat': 'minutes'}).text.strip()
            player['Gls'] = summary_row.find('td', {'data-stat': 'goals'}).text.strip()
            player['Asts'] = summary_row.find('td', {'data-stat': 'assists'}).text.strip()
            player['PK'] = summary_row.find('td', {'data-stat': 'pens_made'}).text.strip()
            player['PKatt'] = summary_row.find('td', {'data-stat': 'pens_att'}).text.strip()
            player['Sh'] = summary_row.find('td', {'data-stat': 'shots_total'}).text.strip()
            player['SoT'] = summary_row.find('td', {'data-stat': 'shots_on_target'}).text.strip()
            player['CrdY'] = summary_row.find('td', {'data-stat': 'cards_yellow'}).text.strip()
            player['CrdR'] = summary_row.find('td', {'data-stat': 'cards_red'}).text.strip()
            player['2CrdY'] = misc_row.find('td', {'data-stat': 'cards_yellow_red'}).text.strip()
            player['Touches'] = summary_row.find('td', {'data-stat': 'touches'}).text.strip()
            player['Int'] = summary_row.find('td', {'data-stat': 'interceptions'}).text.strip()
            player['Blk'] = summary_row.find('td', {'data-stat': 'blocks'}).text.strip()
            player['pComp'] = summary_row.find('td', {'data-stat': 'passes_completed'}).text.strip()
            player['pAtt'] = summary_row.find('td', {'data-stat': 'passes'}).text.strip()
            player['xA'] = summary_row.find('td', {'data-stat': 'xa'}).text.strip()
            player['xG'] = summary_row.find('td', {'data-stat': 'xg'}).text.strip()
            player['Crs'] = misc_row.find('td', {'data-stat': 'crosses'}).text.strip()
            player['TklW'] = misc_row.find('td', {'data-stat': 'tackles_won'}).text.strip()
            player['Fls'] = misc_row.find('td', {'data-stat': 'fouls'}).text.strip()
            player['Fld'] = misc_row.find('td', {'data-stat': 'fouled'}).text.strip()
            player['AstShots'] = pass_row.find('td', {'data-stat': 'assisted_shots'}).text.strip()

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
            player['Name'] = row.find('th').text.strip()
            player['Min'] = row.find('td', {'data-stat': 'minutes'}).text.strip()
            player['SoTA'] = row.find('td', {'data-stat': 'shots_on_target_against'}).text.strip()
            player['GA'] = row.find('td', {'data-stat': 'goals_against_gk'}).text.strip()
            player['PSxG'] = row.find('td', {'data-stat': 'psxg_gk'}).text.strip()

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
    pattern = re.compile(r'http:\/\/fbref\.com\/en\/matches\/(.+)Premier\-League')
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
