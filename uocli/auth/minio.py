import json
import os
import time
from pathlib import Path
import requests
from .oauth import OAuth
import defusedxml.ElementTree as et
import configparser
from datetime import datetime


class AuthError(Exception):
    pass


class MinioAuth(object):

    def __init__(self, client_id, client_secret, minio_endpoint, realm=None, username=None, password=None):
        self.aws_path = Path(Path.home() / ".aws")
        self.minio_url = minio_endpoint
        self.config_file = Path(self.aws_path / "config")
        self.token_file = Path(self.aws_path / "credentials")
        self.credential_section = minio_endpoint.split("//")[1]
        self.storage_client_id = client_id
        self.storage_client_secret = client_secret
        self.realm = realm
        self.username = username
        self.password = password

    def authenticate(self):
        storage_oauth = OAuth(client_id=self.storage_client_id,
                              client_secret=self.storage_client_secret,
                              realm=self.realm, username=self.username, password=self.password)
        tokens = storage_oauth.get_tokens()
        token_validity_seconds = 31536000
        params = params = (
            ('Action', 'AssumeRoleWithWebIdentity'),
            ('DurationSeconds', f"{token_validity_seconds}"),
            ('WebIdentityToken', tokens['access_token']),
            ('Version', '2011-06-15'),
        )
        resp = requests.post(self.minio_url, params=params)
        if resp.status_code == 200:
            element = et.fromstring(resp.text)
            access_key_id = [x for x in element.iter() if 'AccessKeyId' in x.tag][0].text
            secret_access_key = [x for x in element.iter() if 'SecretAccessKey' in x.tag][0].text
            session_token = [x for x in element.iter() if 'SessionToken' in x.tag][0].text
            expiry = [x for x in element.iter() if 'Expiration' in x.tag][0].text
            credentials = {"minio_access_key_id": access_key_id,
                           "minio_secret_access_key": secret_access_key,
                           "minio_session_token": session_token,
                           "expiry": f"{datetime.strptime(expiry, '%Y-%m-%dT%H:%M:%S%z').timestamp()}"}
            self.save_credentials(credentials)
        else:
            raise AuthError(resp.text)

    def get_credentials(self):
        current_credentials = configparser.ConfigParser()
        current_credentials.read(self.token_file)
        if self.credential_section not in current_credentials:
            self.authenticate()
            return self.get_credentials()
        else:
            if float(current_credentials[self.credential_section]['expiry']) < time.time():
                self.authenticate()
                return self.get_credentials()
        token_info = {
            "minio_access_key_id": current_credentials[self.credential_section]["aws_access_key_id"],
            "minio_secret_access_key": current_credentials[self.credential_section]["aws_secret_access_key"],
            "minio_session_token": current_credentials[self.credential_section]["aws_session_token"],
            "expiry": current_credentials[self.credential_section]["expiry"]
        }
        return token_info

    def save_credentials(self, credentials):
        Path(self.aws_path).mkdir(parents=True, exist_ok=True)
        self.token_file.touch()
        self.config_file.touch()
        current_credentials = configparser.ConfigParser()
        current_credentials.read(self.token_file)
        if not self.credential_section in current_credentials:
            current_credentials[self.credential_section] = {}
        current_credentials.set(self.credential_section, "aws_access_key_id", credentials["minio_access_key_id"])
        current_credentials.set(self.credential_section, "aws_secret_access_key", credentials["minio_secret_access_key"])
        current_credentials.set(self.credential_section, "aws_session_token", credentials["minio_session_token"])
        current_credentials.set(self.credential_section, "expiry", credentials["expiry"])
        with open(self.token_file, "w") as fh:
            current_credentials.write(fh)
