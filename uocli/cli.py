"""Console script for uocli."""
import click
import webbrowser
import uocli
from uocli.vm.commands import vm
from uocli.storage.commands import storage


@click.group()
@click.version_option(uocli.__version__)
def cli(json=False):
    """
    Commandline interface to interact with the UO backend infrastructure
    """
    pass


cli.add_command(vm)
cli.add_command(storage)

### Temporary Hack until we have a dashboard/ landing page
### with these links
@cli.command()
def jupyterhub():
    """
    Connect to Jupyterhub \f
    """
    webbrowser.open_new(url="https://jhub.nyc01.cuspuo.org")

# This is added in storage module. Remove it once we have dashboad/landing page
# @cli.command()
# def storageui():
#     """
#     Connect to StorageUI \f
#     """
#     webbrowser.open_new(url="https://storage01.nyc01.cuspuo.org")

###
