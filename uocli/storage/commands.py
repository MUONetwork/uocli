import os
import sys
import click
import time
import requests
import json
import tempfile
import subprocess
import webbrowser
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn
from rich.console import Console, Text
from rich.table import Table
from rich.traceback import install
from botocore.client import Config as botocoreConfig
from uocli import config
from uocli.auth.minio import MinioAuth
from uocli.storage.session import assumed_session

client_id = config['storage']['client_id']
client_secret = config['storage']['client_secret']
storage_url = config['storage']['url']
storage_ui_url = config['storage']['ui']

# Lets also store the credentials to ~/.aws/credentials file so that we can use aws cli to interact with storage
minio_auth = MinioAuth(client_id=client_id, client_secret=client_secret,
                       minio_endpoint=storage_url)
console = Console(emoji=False)
# install()


class Config(object):
    def __init__(self, **kwargs):
        self.creds_info = minio_auth.get_credentials()
        for key in kwargs:
            setattr(self, key, kwargs[key])
        self.boto3session = assumed_session(client_id=client_id, client_secret=client_secret)


def print_error(msg):
    error_message = Text(f'Error: {msg}')
    error_message.stylize("bold red")
    console.print(error_message)
    sys.exit(1)


@click.group()
@click.pass_context
def storage(ctx):
    """
    Handle Storage related operations \f
    """
    ctx.obj = Config()

@storage.command()
def ui():
    """
    Connect to StorageUI \f
    """
    webbrowser.open_new(url=storage_ui_url)

@storage.command()
@click.option("--bucket", type=str, prompt=True)
@click.pass_obj
def ls(ctx, bucket: str = None, prefix: str = None):
    """
    List files in an S3 bucket \f
    Returns
    -------
    None
    """
    s3 = ctx.boto3session.resource('s3',
                                   endpoint_url=storage_url,
                                   config=botocoreConfig(signature_version='s3v4'),
                                   region_name='us-east-1')
    bucket = s3.Bucket(bucket)
    print([x for x in bucket.objects.filter(Prefix=prefix if prefix else "").limit(10)])
