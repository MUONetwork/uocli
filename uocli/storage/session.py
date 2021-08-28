import os
import getpass
from botocore.credentials import RefreshableCredentials
from botocore.session import get_session

### Temporary hack
# try:
#     from ..auth.oauth import OAuth
# except ImportError:
#     import sys
#
#     sys.path.append("/Users/mohitsharma44/devel/uo/uocli/uocli/")
#     sys.path.append("/Users/mohitsharma44/devel/uo/uocli/uocli/auth")
#     from auth.oauth import OAuth
###
from uocli import config
from uocli.auth.oauth import OAuth

from botocore.client import Config
from boto3 import Session

client_id = config['storage']['client_id']
client_secret = config['storage']['client_secret']
storage_url = config['storage']['url']

class AuthenticationError(Exception):
    pass


def assumed_session(session=None,
                    username=None, password=None,
                    client_id=None, client_secret=None):
    """
    Assume a boto3.Session with automatic credential renewal.
    The credentials will automatically be rotated if they're about to
    expire in the next 15 mins

    Notes: We have to poke at botocore internals a few times
    Parameters
    ----------
    session
    username
    password
    client_id
    client_secret

    Returns
    -------
    session: boto3.session
    """
    if username is None:
        username = getpass.getuser()
        username = input("Enter your username") if username == "jovyan" else username
    if password is None and 'DISPLAY' not in os.environ:
        password = getpass.getpass(f"Enter the password for {username}: ")

    if session is None:
        session = Session()

    def refresh(username=None, password=None,
                client_id=None, client_secret=None):
        oauth = OAuth(client_id=client_id, client_secret=client_secret)
        access_token = oauth.get_tokens()["access_token"]

        sts_client = session.client('sts',
                                    region_name='us-east-1',
                                    use_ssl=True,
                                    endpoint_url=storage_url)
        credentials = sts_client.assume_role_with_web_identity(
            RoleArn='arn:aws:iam::123456789012:user/svc-internal-api',  # This is ignored by Minio
            RoleSessionName='test',  # This is ignored by Minio
            WebIdentityToken=access_token,
            DurationSeconds=3600,
        )['Credentials']

        return {'access_key': credentials['AccessKeyId'],
                'secret_key': credentials['SecretAccessKey'],
                'token': credentials['SessionToken'],
                'expiry_time': credentials['Expiration'].isoformat()}

    session_credentials = RefreshableCredentials.create_from_metadata(
        metadata=refresh(username=username, password=password, client_id=client_id, client_secret=client_secret),
        refresh_using=refresh,
        method='sts-assume-role')

    s = get_session()
    s._credentials = session_credentials
    region = session._session.get_config_variable('region') or 'us-east-1'
    s.set_config_variable('region', region)
    return Session(botocore_session=s)


if __name__ == "__main__":
    sess = assumed_session(client_id=client_id, client_secret=client_secret)
    s3 = sess.resource('s3',
                       endpoint_url=storage_url,
                       config=Config(signature_version='s3v4'),
                       region_name='us-east-1')
    print([x for x in s3.buckets.all()])
