import json
import requests

# get connection details from API
def importProductAPI():
    # API token to send in the header
    headers = {
        'AuthenticateApi': '3dm0q4lrfmqf05fcbosv001',
        'Content-Type': 'application/json'
    }
    API_URL = 'https://growth.matridtech.net/api/database-api'
    try:
        # Send the POST request and get the response
        response = requests.get(API_URL, headers=headers)
        # Check if the response is successful
        if response.status_code == 200 or response.status_code == 201:
            try:
                print("Request successful!")
                return response.text  # Exit on success
            except ValueError as ve:
                print(f"Request failed with status code: {response.status_code}, Response: {response.text}")
                return None  # Exit on other HTTP errors
        else:
            print(f"API request failed with status code: {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"Error while making API request: {e}")
        return None

db_connection = importProductAPI()
if db_connection is None:
    print("Failed to connect to the database API.")
    exit(1)
else:
    try:
        # Convert the JSON string to a dictionary
        db_data = json.loads(db_connection)
        
        print("Connected to the database API successfully.")
        
        live_db = db_data.get('live_db', {})
        af_history_db = db_data.get('af_history_db', {})
        other_vendor_history_db = db_data.get('other_vendor_history_db', {})
        
        # Extract values for live_db
        HOST = live_db.get('host', '')
        DB = live_db.get('db_name', '')
        USER = live_db.get('user_name', '')
        PASS = live_db.get('password', '')

        # Extract values for af_history_db
        HOST2 = af_history_db.get('host', '')
        DB2 = af_history_db.get('db_name', '')
        USER2 = af_history_db.get('user_name', '')
        PASS2 = af_history_db.get('password', '')

        # Extract values for other_vendor_history_db
        HOST3 = other_vendor_history_db.get('host', '')
        DB3 = other_vendor_history_db.get('db_name', '')
        USER3 = other_vendor_history_db.get('user_name', '')
        PASS3 = other_vendor_history_db.get('password', '')

    except json.JSONDecodeError:
        print("Failed to decode JSON from API response.")