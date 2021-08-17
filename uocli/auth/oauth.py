import os
import sys
from json import JSONDecodeError
from pathlib import Path
from requests_oauthlib import OAuth2Session
from uocli import config
from uocli.auth.webserver import get_authorization_code
import webbrowser
import requests
import time
import json

#HAS_GUI = 'DISPLAY' in os.environ
HAS_GUI = True if sys.platform == 'win32' else os.environ['DISPLAY']
SUPPORTED_CLIENTS = config['supported_clients']
AUTH_SERVER_URL = config['auth_server']['url']


class ClientNotSupportedException(Exception):
    pass


class OAuth(object):

    def __init__(self, client_id, client_secret, realm=None, username=None, password=None):
        if not HAS_GUI and not (username or password):
            raise ClientNotSupportedException("You must either have an active X-Server session or provide username "
                                              "and password for authentication")
        self.supported_clients = SUPPORTED_CLIENTS
        self.realm = realm if realm else "UO"
        self.muon_path = Path(Path.home() / ".muon")
        self.token_file = Path(self.muon_path / "auth_tokens")
        self.redirect_uri = "http://127.0.0.1:8239"
        self.keycloak_token_url = f"{AUTH_SERVER_URL}/auth/realms/{self.realm}/protocol/openid-connect/token"
        self.keycloak_client_id = client_id
        self.keycloak_client_secret = client_secret
        self.username = username
        self.password = password
        if self.keycloak_client_id not in self.supported_clients:
            raise ClientNotSupportedException

    def authenticate(self, token_info=None):
        post_data = {}
        if token_info and token_info['refresh_expires_in'] > time.time() + 10:
            post_data = {'grant_type': 'refresh_token',
                         'client_id': self.keycloak_client_id,
                         'client_secret': self.keycloak_client_secret,
                         'refresh_token': token_info['refresh_token']}
        else:
            if HAS_GUI:
                oauth_session = OAuth2Session(client_id=self.keycloak_client_id, redirect_uri=self.redirect_uri,
                                              scope="email")
                authorization_url, state = oauth_session.authorization_url(
                    f"{AUTH_SERVER_URL}/auth/realms/{self.realm}/protocol/openid-connect/auth",
                    access_type="offline", )
                webbrowser.open_new(url=authorization_url)
                auth_code = get_authorization_code()
                post_data = {'grant_type': 'authorization_code',
                             'code': auth_code,
                             'redirect_uri': self.redirect_uri}
            else:
                post_data = {'grant_type': 'password',
                             'username': self.username, 'password': self.password}
        token_response = requests.post(self.keycloak_token_url,
                                       data=post_data,
                                       verify=True,
                                       allow_redirects=False,
                                       auth=(self.keycloak_client_id, self.keycloak_client_secret))
        access_token_response = json.loads(token_response.text)
        if 'error' in access_token_response:
            if access_token_response.get('error_description', "") == "Session not active":
                # Lets try full Auth
                self.authenticate()
            else:
                raise ClientNotSupportedException(access_token_response)
        self.save_tokens(access_token_response)

    def get_tokens(self):
        reauth = False
        token_info = None
        if self.token_file.is_file():
            with open(self.token_file, 'r') as fh:
                try:
                    current_token_info = json.load(fh)
                    if self.keycloak_client_id not in current_token_info.keys():
                        reauth = True
                    token_info = current_token_info[self.keycloak_client_id]
                    if float(token_info['expires_in']) < time.time():
                        reauth = True
                except (KeyError, JSONDecodeError):
                    reauth = True
            if reauth:
                self.authenticate(token_info)
                return self.get_tokens()
            return token_info
        else:
            self.authenticate()
            return self.get_tokens()

    def save_tokens(self, token_info):
        current_time = int(time.time())
        Path(self.muon_path).mkdir(parents=True, exist_ok=True)
        self.token_file.touch()
        # Update the expiry timeout to epoch time
        token_info['expires_in'] += current_time - 5  # 5 seconds less just in case we are slow to get this data
        token_info['refresh_expires_in'] += current_time - 5  # 5 seconds less just in case we are slow to get this data
        token_info.pop('scope')
        token_info.pop('session_state')
        token_info = {self.keycloak_client_id: token_info}
        # Update the tokens to file
        current_token_info = {}
        with open(self.token_file, 'r') as fh:
            try:
                current_token_info = json.load(fh)
            except JSONDecodeError:
                pass
        current_token_info.update(token_info)
        with open(Path(self.token_file), 'w', encoding='utf-8') as fh:
            json.dump(current_token_info, fh, ensure_ascii=False, indent=4)
