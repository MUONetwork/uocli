"""Top-level package for uocli."""

__author__ = """Mohit Sharma"""
__email__ = 'mohitsharma44@gmail.com'
__version__ = '0.0.1'

import yaml
import os

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

uoclient_config_file = os.environ.get("UOCLIENT_CONFIG", os.path.join(__location__, "uoclient_config.yaml"))


def read_config():
    with open(os.path.join(uoclient_config_file), 'r') as fh:
        try:
            return yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            print(exc)
        except FileNotFoundError as fnf:
            print("Config file not found")


config = read_config()
