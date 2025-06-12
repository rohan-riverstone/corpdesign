import requests
import json
import logging 
from requests_oauthlib import OAuth1
from requests.exceptions import ConnectionError, Timeout

class Netsuit_SO:
    
    def so_creation(pdf_request_json : json, config: dict) -> json:

        try:
            url = config['netsuite_endpoint_url']
            consumer_key = config['netsuite_consumer_key']
            consumer_secret = config['netsuite_consumer_secret']
            access_token = config['netsuite_access_token']
            access_token_secret = config['netsuite_access_token_secret']
            realm = config['netsuite_realm']
 
            # Custom OAuth1 parameters
            oauth_signature_method = config['netsuite_oauth_sign_method']
             
            auth = OAuth1(
                consumer_key,
                consumer_secret,
                access_token,
                access_token_secret,
                signature_method=oauth_signature_method,
                realm=realm
            ) 
            headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
            }

            response = requests.request("POST", url, auth=auth, headers=headers, data=pdf_request_json, timeout=150)
            if response.status_code == 200 and (response.text == None or response.text ==""):
                response.text = "No response text from Netsuite API"
            print("response.text :", response.text)
            return response.text
        except(ConnectionError, Timeout) as ex:
            logging.info(f"failed: {ex}")
