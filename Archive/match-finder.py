# Imports for web scraping
from requests_html import HTMLSession
from bs4 import BeautifulSoup
import pyppeteer
import re
import time
import datetime
import os
from google.cloud import storage

def get_match_filename(date, hometeam, awayteam):
    match_date = datetime.datetime.strptime(date, '%A %B %d, %Y').strftime('%d%b%Y')
    home_name = hometeam.replace(' ', '_')
    away_name = awayteam.replace(' ', '_')
    return match_date + '_' + home_name + '_vs_' + away_name + '.json'

def get_page(url):
    session = HTMLSession()
    print("Launched browser...")
    resp_page = session.get(url)
    print("Got response from page...")
    return resp_page

def get_page_content(url):
    page_resp = get_page(url)
    page_resp.html.render()
    print("Rendered page...")
    return page_resp.content

def get_page_json(url):
    return get_page(url).json

def print_run_statistics(run_stats):
    print('Run statistics:')
    print('   Total Matches: ', run_stats['total'])
    print('   New Matches: ', run_stats['new'])
    print('   Old Matches: ', run_stats['old'])
    print('   Skipped Matches: ', run_stats['skipped'])
    print('   --------------------------')    
    print('   Bucket should have: ', run_stats['bucket'], ' matches')

def find_new_matches():
    url = "http://fbref.com/en/comps/9/schedule/Premier-League-Scores-and-Fixtures"

    # First collect the site from the url
    try:
        page_content = get_page_content(url)
    except:
        print("Error retrieving fixture content from URL")
        exit()

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

            collect_url = "http://epl-data-w2aw2gorcq-ue.a.run.app/collectmatch/" + match_url
            print("Requested: " + collect_url)
            num_new_matches += 1
            # print(get_page(collect_url))
            # time.sleep(45)
        else:
            num_skipped_matches += 1

    run_stats = {}
    run_stats['total'] = num_total_matches
    run_stats['new'] = num_new_matches
    run_stats['old'] = num_already_collected_matches
    run_stats['skipped'] = num_skipped_matches
    run_stats['bucket'] = num_total_matches - num_skipped_matches
    return run_stats

if __name__ == "__main__":
    stats = find_new_matches()
    print_run_statistics(stats)