# Script to fix web scraping error for away score/result

# Imports for Google Cloud Storage
from google.cloud import storage
import datetime
import json

def get_match_filename(date, hometeam, awayteam):
    match_date = datetime.datetime.strptime(date, '%A %B %d, %Y').strftime('%d%b%Y')
    home_name = hometeam.replace(' ', '_')
    away_name = awayteam.replace(' ', '_')
    return match_date + '_' + home_name + '_vs_' + away_name + '.json'

def store_match_json(match_json):
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

def print_match_result(match_json):
    print('Result: ' + match_json['Result'] + '  ' +
            match_json['HomeStats']['Team'] + ' ' + str(match_json['HomeStats']['Goals']) + '   ' +
            match_json['AwayStats']['Team'] + ' ' + str(match_json['AwayStats']['Goals']))

def convert_player(old_player):
    new_player = {}
    new_player['2CrdY'] = int(old_player['2CrdY'])
    new_player['AstShots'] = int(old_player['AstShots'])
    new_player['Asts'] = int(old_player['Asts'])
    new_player['Blk'] = int(old_player['Blk'])
    new_player['CrdR'] = int(old_player['CrdR'])
    new_player['CrdY'] = int(old_player['CrdY'])
    new_player['Crs'] = int(old_player['Crs'])
    new_player['Fld'] = int(old_player['Fld'])
    new_player['Fls'] = int(old_player['Fls'])
    new_player['Gls'] = int(old_player['Gls'])
    new_player['Int'] = int(old_player['Int'])
    new_player['Min'] = int(old_player['Min'])
    new_player['PK'] = int(old_player['PK'])
    new_player['PKatt'] = int(old_player['PKatt'])
    new_player['Sh'] = int(old_player['Sh'])
    new_player['SoT'] = int(old_player['SoT'])
    new_player['TklW'] = int(old_player['TklW'])
    new_player['Touches'] = int(old_player['Touches'])
    new_player['pAtt'] = int(old_player['pAtt'])
    new_player['pComp'] = int(old_player['pComp'])
    new_player['xA'] = float(old_player['xA'])
    new_player['xG'] = float(old_player['xG'])
    new_player['Name'] = old_player['Name']
    new_player['Pos'] = old_player['Pos']
    return new_player

def convert_keeper(old_keeper):
    new_keeper = {}
    new_keeper['Name'] = old_keeper['Name']
    new_keeper['GA'] = int(old_keeper['GA'])
    new_keeper['Min'] = int(old_keeper['Min'])
    new_keeper['SoTA'] = int(old_keeper['SoTA'])
    new_keeper['PSxG'] = float(old_keeper['PSxG'])
    return new_keeper

def main():
    bucket_name = 'steadfast-tesla-297100_data_bucket'
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blobs = storage_client.list_blobs(bucket_name)

    for blob in blobs:
        file_name = blob.name
        print('Filename: ' + file_name)
        json_string = blob.download_as_string()
        match_json = json.loads(json_string)
        print_match_result(match_json)
        
        # ... Modify ...
        away_goals = 0
        new_away_players = []
        for player in match_json['AwayPlayers']:
            away_goals += int(player['Gls'])
            new_away_players.append(convert_player(player))
        
        match_json['AwayPlayers'] = new_away_players

        match_json['AwayStats']['Goals'] = away_goals

        # Fix match result
        if int(match_json['HomeStats']['Goals']) == away_goals:
            match_json['Result'] = 'Draw'
        elif int(match_json['HomeStats']['Goals']) < away_goals:
            match_json['Result'] = 'Away'
        else:
            match_json['Result'] = 'Home'

        new_home_players = []
        for player in match_json['HomePlayers']:
            new_home_players.append(convert_player(player))
        match_json['HomePlayers'] = new_home_players

        new_home_keepers = []
        for keeper in match_json['HomeKeepers']:
            new_home_keepers.append(convert_keeper(keeper))
        match_json['HomeKeepers'] = new_home_keepers

        new_away_keepers = []
        for keeper in match_json['AwayKeepers']:
            new_away_keepers.append(convert_keeper(keeper))
        match_json['AwayKeepers'] = new_away_keepers

        print_match_result(match_json)
        blob.delete()

        bucket = storage_client.get_bucket(bucket_name)
        new_blob = bucket.blob(file_name)
        new_blob.upload_from_string(
            data=json.dumps(match_json),
            content_type='application/json'
        )

        json_string = new_blob.download_as_string()
        match_json = json.loads(json_string)
        print_match_result(match_json)
        break


if __name__ == "__main__":
    main()
