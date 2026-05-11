import requests

ACCESS_TOKEN = "YOUR_META_ACCESS_TOKEN"

def fetch_meta_lead(leadgen_id):

    url = f"https://graph.facebook.com/v23.0/{leadgen_id}"

    params = {
        "access_token": ACCESS_TOKEN
    }

    response = requests.get(url, params=params)

    return response.json()