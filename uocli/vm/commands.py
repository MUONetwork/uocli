import os
import sys
import sys
import click
import time
import requests
import json
import tempfile
import subprocess
from pathlib import Path
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn
from rich.console import Console, Text
from rich.table import Table
from rich.traceback import install

from uocli import config
from uocli.auth.oauth import OAuth

client_id = config['uoserver']['client_id']
client_secret = config['uoserver']['client_secret']

oauth = OAuth(client_id=client_id, client_secret=client_secret)
console = Console(emoji=False)
# install()

uoserver_url = config['uoserver']['url']
remote_viewer_path = sorted(Path("c:\Program Files").glob("**/remote-viewer.exe"))[0] if sys.platform == 'win32' \
    else "/usr/local/bin/remote-viewer"


def retry(times):
    """
    Retry Decorator
    Retries the wrapped function/method `times`
    """

    def decorator(func):
        def newfn(self, *args, **kwargs):
            attempt = 0
            while attempt < times:
                try:
                    return func(self, *args, **kwargs)
                except Exception as ex:
                    attempt += 1
            return func(*args, **kwargs)

        return newfn

    return decorator


class Config(object):
    def __init__(self, **kwargs):
        self.token_info = oauth.get_tokens()
        for key in kwargs:
            setattr(self, key, kwargs[key])
        self.access_token = self.token_info['access_token']


class Mutex(click.Option):
    def __init__(self, *args, **kwargs):
        self.not_required_if: list = kwargs.pop("not_required_if")

        assert self.not_required_if, "'not_required_if' parameter required"
        kwargs["help"] = (kwargs.get("help", "") + "Option is mutually exclusive with " + ", ".join(
            self.not_required_if) + ".").strip()
        super(Mutex, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        current_opt: bool = self.name in opts
        for mutex_opt in self.not_required_if:
            if mutex_opt in opts:
                if current_opt:
                    raise click.UsageError(
                        "Illegal usage: '" + str(self.name) + "' is mutually exclusive with " + str(mutex_opt) + ".")
                else:
                    self.prompt = None
        return super(Mutex, self).handle_parse_result(ctx, opts, args)


def print_error(msg):
    error_message = Text(f'Error: {msg}')
    error_message.stylize("bold red")
    console.print(error_message)
    sys.exit(1)


def post(ctx, uri, data, addnl_headers=None):
    """
    Send POST request to serverr
    Parameters
    ----------
    headers
    data

    Returns
    -------

    """
    headers = {"Authorization": f"Bearer {ctx.access_token}", 'Content-type': 'application/json'}
    if addnl_headers:
        headers.update(addnl_headers)
    resp = requests.post(f'{uoserver_url}{uri}', headers=headers, json=data)
    if resp.status_code not in range(200, 400):
        try:
            print_error(resp.json().get("detail", f"Improper detail of the error returned: {resp.text}"))
        except json.JSONDecodeError:
            print_error(f"Error returned from the server: {resp.text}")
    return resp.json()


def get(ctx, uri, addnl_headers=None, params=None):
    """
    Get data from server
    Parameters
    ----------
    headers

    Returns
    -------

    """
    headers = {"Authorization": f"Bearer {ctx.access_token}"}
    if addnl_headers:
        headers.update(addnl_headers)
    resp = requests.get(f'{uoserver_url}{uri}', headers=headers, params=params)
    if resp.status_code not in range(200, 400):
        try:
            print_error(
                resp.json().get("detail", f"Improper detail of the error returned: {resp.text}"))
            sys.exit(1)
        except json.JSONDecodeError:
            print_error(f"Error returned from the server: {resp.text}")
            sys.exit(1)
    return resp.json()


@click.group()
@click.pass_context
def vm(ctx):
    """
    Handle VM related operations \f
    """
    ctx.obj = Config()


def get_task_status(ctx, upid: str = None):
    return get(ctx=ctx, uri=f"/vm/upid/status/{upid}")


def get_task_log(ctx, upid: str = None):
    return get(ctx=ctx, uri=f"/vm/upid/log/{upid}")


def track_status(ctx, upid: str = None, message: str = None, transient: bool = False):
    """
    For a given upid, track status of the task and present it
    as a progress bar to the user
    Parameters
    ----------
    upid: str

    """
    if upid:
        clone_complete = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=transient,
        ) as progress:
            task = progress.add_task(f"[cyan]{message}", total=100)
            while not progress.finished:
                try:
                    if clone_complete != 100:
                        json_resp = get_task_log(ctx, upid)
                        if 'TASK ERROR' in json_resp['t']:
                            # Hacky way to see for no-op. Need to improve this
                            if 'already' in json_resp['t']:
                                clone_complete = 100
                            else:
                                print_error("Task Error.. Contact system admin")
                                sys.exit(2)
                            # clone_complete = json_resp['t'].split(':')[-1].strip().strip(' %')
                        elif "TASK OK" in json_resp['t']:
                            clone_complete = 100
                        else:
                            clone_complete = json_resp['t'].split(' ')[-1].strip('(').strip(')').strip('%')
                        try:
                            clone_complete = float(clone_complete)
                            progress.update(task, completed=clone_complete)
                        except ValueError:
                            pass
                        time.sleep(1)
                except Exception as ex:
                    print(f"Exception occurred: {ex}")
                    break
        if clone_complete == 100:
            with console.status(f"[cyan]Waiting for {message} to complete...",
                                spinner="bouncingBar", spinner_style="cyan") as status:
                # Most often the cloning is reported as completed but there are still a few tasks
                # that continue to run. The only option is for us to track when status of task is
                # reported as stopped
                task_status = get_task_status(ctx, upid)['status']
                while task_status == "running":
                    task_status_json = get_task_status(ctx, upid)
                    task_status = task_status_json['status']
                    # We'll only get this once task's status is stopped
                    exitstatus = task_status_json.get('exitstatus')
                    if task_status == "stopped":
                        if exitstatus == "OK":
                            console.log(f"✓ {message} Completed")
                        else:
                            console.log(f"[bold red]{message} Errored. Contact system admin")
                            sys.exit(1)
                    time.sleep(2)


@vm.command()
@click.option("--vmname", type=str, prompt=True)
@click.option("--template", type=str, prompt=True, prompt_required=False, default="linux-mint-201-template")
@click.option("--storage", type=str, prompt=True, prompt_required=False, default="luna")
@click.option("--sshkey", type=str, prompt=True)
@click.pass_obj
def new(ctx, vmname: str = None, template: str = None, storage: str = None, sshkey: str = None):
    """
    Create a New VM \f
    Parameters
    ----------
    sshkey: str
        Path to your public ssh key (id_rsa.pub)
    vmname: str
        Name for your VM. Try to keep this as unique as possible
    template: str, Optional
        Template to clone from.
    storage: str, Optional
        Backend block storage to use for this VM

    Returns
    -------
    vmid: int
        Unique id for this VM
    """
    headers = {"Authorization": f"Bearer {ctx.access_token}", 'Content-type': 'application/json'}
    create_vm_data = {
        "name": vmname,
        "template_name": template,
        "storage_dev": storage
    }
    upid = None
    with console.status(f"[bold green]Creating new VM...") as status:
        resp = post(ctx=ctx, uri=f"/vm/clone_vm", data=create_vm_data)
        upid = resp['upid']
    track_status(ctx=ctx, upid=upid, message="Copying data from template", transient=True)
    # Get newly created VM's ID
    vm_id = json.loads(get_vmid(ctx, vmname=vmname, tojson=True))['vm_id']
    provision_vm(ctx, vmid=vm_id, sshkey=sshkey)


@retry(3)
def _provision_ssh(ctx, vmid: int, sshkey: str):
    ssh_public_key_content = None
    with open(sshkey, 'r') as fh:
        ssh_public_key_content = fh.read()
    ssh_data = {
        "vm_id": vmid,
        "ssh_public_key": ssh_public_key_content
    }
    post(ctx=ctx, uri=f"/vm/provision/ssh", data=ssh_data)


@retry(3)
def _update_vm_resources(ctx, vmid: int, instancetype: str = None):
    edit_data = {
        "vm_id": vmid,
        "vcpus": 4,
        "cores": 4,
        "sockets": 1,
        "description": "",
        "memory": 16384,
        "restart": False
    }
    post(ctx=ctx, uri=f"/vm/edit", data=edit_data)


@retry(3)
def provision_vm(ctx, vmid: int, sshkey: str):
    # Lets provision the VM
    provisioning_data = {
        "vm_id": vmid
    }
    with console.status(f"[bold cryan]Provisioning your new VM...") as status:
        time.sleep(2)
        _update_vm_resources(ctx, vmid)
        console.log("✓ Updated guest VM resources successfully")
        time.sleep(5)
    # Start VM if its not already running
    change_vm_state(ctx=ctx, vmid=vmid, state="start", progressbar=False)
    console.log("✓ Started VM successfully")
    with console.status(f"[bold cryan]Waiting for VM to boot...") as status:
        # Wait for addntl 40 secs for VM to be ready. Is there a better way to get this info??
        time.sleep(40)
    with console.status(f"[bold cryan]Provisioning your user in your new VM...") as status:
        temp_pwd = post(ctx=ctx, uri=f"/vm/provision/user", data=provisioning_data)["temporary_ssh_password"]
        time.sleep(5)
        console.log(f"✓ User provisioned successfully. Temporary password: {temp_pwd}")
    with console.status(f"[bold cryan]Provisioning ssh in your new VM...") as status:
        _provision_ssh(ctx, vmid, sshkey)
        time.sleep(5)
        console.log("✓ SSH provisioned successfully")
    with console.status(f"[bold cryan]Expanding disk and Updating guest VM hostname...") as status:
        post(ctx=ctx, uri=f"/vm/provision/vm", data=provisioning_data)
        time.sleep(5)
        console.log("✓ Updated guest VM network and remote display successfully")
        console.log(f"[bold cryan]You can now login to your VM with vmid: {vmid}. "
                    f"For more info, run `uocli vm --connect --help`")
    change_vm_state(ctx=ctx, vmid=vmid, state="start", progressbar=False)



@vm.command()
@click.option("--vmid", type=int, prompt=True)
@click.option("--username", type=str, default=lambda: os.environ.get("USER", "uouser"))
@click.option("--sshkey", type=str, prompt=True)
@click.pass_obj
def provision(ctx, vmid: int, username: str, sshkey: str):
    """
    Provision VM with user and ssh public key \f
    Parameters
    ----------
    vmid: int
        ID of the VM to provision
    username: str
        Optional, Username for the authorized user to provision on the VM.
        If not passed, we will infer from $USER env var else fallback on uouser
    sshkey: str
        Path to your public ssh key (id_rsa.pub)

    """
    return provision_vm(ctx, vmid, sshkey)


#     headers = {"Authorization": f"Bearer {ctx.access_token}", 'Content-type': 'application/json'}
#     ssh_public_key_content = ""
#     with open(sshkey, 'r') as fh:
#         ssh_public_key_content = fh.read()
#     provision_data = {
#         "vm_id": vmid,
#         "user": username,
#         "ssh_public_key": ssh_public_key_content
#     }
#     with console.status(f"[bold cyan]Provisioning VM...") as status:
#         resp = requests.post(f'http://localhost:8000/vm/provision', headers=headers, json=provision_data)
#         if resp.status_code not in range(200, 400):
#             try:
#                 print_error(resp.json().get("detail", f"Improper detail of the error returned: {resp.text}"))
#             except json.JSONDecodeError:
#                 print_error(f"Error returned from the server: {resp.text}")
#         edit_data = {
#             "vm_id": vmid,
#             "vcpus": 4,
#             "cores": 4,
#             "sockets": 1,
#             "description": "",
#             "memory": 16384,
#             "restart": True
#         }
#         resp2 = requests.post(f'http://localhost:8000/vm/edit/', headers=headers, json=edit_data)
#         print(resp2.text)
#         if resp.status_code not in range(200, 400):
#             try:
#                 print_error(resp.json().get("detail", f"Improper detail of the error returned: {resp.text}"))
#             except json.JSONDecodeError:
#                 print_error(f"Error returned from the server: {resp.text}")
#         table = Table(title=f"VM Provision Status")
#         table.add_column("Attribute", style="cyan", no_wrap=True)
#         table.add_column("Value", style="green")
#         for k, v in resp.json().items():
#             table.add_row(f"{k}", f"{v}")
#         console.print(table, justify="left")


@vm.command()
@click.option("--tojson", default=False, is_flag=True)
@click.pass_obj
def list(ctx, tojson: bool = False):
    """
    List all the VMs owned by the user \f
    Returns
    -------
    VMStatus: table/ json
        Status of the VM
    """
    with console.status(f"[bold cyan]Looking up all your VMs...") as status:
        vmstatuses = get(ctx=ctx, uri="/vm/list")
    if tojson:
        print(json.dumps(vmstatuses, indent=4))
    else:
        for vmstatus in vmstatuses:
            table = Table(title=f"VM {vmstatus['vm_id']}'s Status")
            table.add_column("Attribute", style="cyan", no_wrap=True)
            table.add_column("Value", style="green")
            for k, v in vmstatus.items():
                table.add_row(f"{k}", f"{v}")
            console.print(table, justify="left")


@vm.command()
@click.option("--tojson", default=False, is_flag=True)
@click.pass_obj
def list_templates(ctx, tojson: bool = False):
    """
    List all VM templates \f

    Returns
    -------
    VMTemplates: table/ json
        Templates that can be used to clone the VMs
    """
    vmtemplates = get(ctx=ctx, uri="/vm/templates/list")
    if tojson:
        print(json.dumps(vmtemplates, indent=4))
    else:
        table = Table(title=f"VM Templates")
        table.add_column("Names", style="cyan", no_wrap=True)
        for vmtemplate in vmtemplates['templates']:
            table.add_row(vmtemplate)
        console.print(table, justify="left")


def get_vmstatus(ctx, vmid: int = None, tojson: bool = True):
    return get(ctx=ctx, uri=f"/vm/{vmid}/status")


@vm.command()
@click.option("--vmid", type=int, prompt=True)
@click.option("--tojson", default=False, is_flag=True)
@click.pass_obj
def status(ctx, vmid: int = None, tojson: bool = False):
    """
    Given the ID or Name for the VM, query the status of the VM\f
    Parameters
    ----------
    vmid: int
        VMID of the VM

    Returns
    -------
    VMStatus: table/ json
        Status of the VM
    """
    vmstatus = {}
    with console.status(f"[bold green]Obtaining VM {vmid}'s Status...") as cstatus:
        vmstatus = get_vmstatus(ctx, vmid, tojson=True)
    if tojson:
        print(json.dumps(vmstatus, indent=4))
    else:
        table = Table(title="VM Status")
        table.add_column("Attribute", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        for k, v in vmstatus.items():
            table.add_row(f"{k}", f"{v}")
        console.print(table, justify="left")


@vm.command()
@click.option("--vmid", type=int, prompt=True)
@click.pass_obj
def start(ctx, vmid: int = None):
    """
    Start the VM \f
    Parameters
    ----------
    vmid: int
        VMID of the VM

    """
    change_vm_state(ctx, vmid, "start")


@vm.command()
@click.option("--vmid", type=int, prompt=True)
@click.pass_obj
def stop(ctx, vmid: int = None):
    """
    Stop the VM \f
    Parameters
    ----------
    vmid: int
        VMID of the VM

    """
    change_vm_state(ctx, vmid, "stop")


@vm.command()
@click.option("--vmid", type=int, prompt=True)
@click.pass_obj
def shutdown(ctx, vmid: int = None):
    """
    Shutdown the VM \f
    Parameters
    ----------
    vmid: int
        VMID of the VM

    """
    change_vm_state(ctx, vmid, "shutdown")


@vm.command()
@click.option("--vmid", type=int, prompt=True)
@click.pass_obj
def reboot(ctx, vmid: int = None):
    """
    Reboot the VM \f
    Parameters
    ----------
    vmid: int
        VMID of the VM

    """
    change_vm_state(ctx, vmid, "reboot")


@vm.command()
@click.option("--vmid", type=int, prompt=True)
@click.pass_obj
def reset(ctx, vmid: int = None):
    """
    Reset the VM \f
    Parameters
    ----------
    vmid: int
        VMID of the VM

    """
    change_vm_state(ctx, vmid, "reset")


@vm.command()
@click.option("--vmid", type=int, prompt=True)
@click.pass_obj
def suspend(ctx, vmid: int = None):
    """
    Suspend the VM \f
    Parameters
    ----------
    vmid: int
        VMID of the VM

    """
    change_vm_state(ctx, vmid, "suspend")


@vm.command()
@click.option("--vmid", type=int, prompt=True)
@click.pass_obj
def resume(ctx, vmid: int = None):
    """
    Resume the VM \f
    Parameters
    ----------
    vmid: int
        VMID of the VM

    """
    change_vm_state(ctx, vmid, "resume")


def change_vm_state(ctx, vmid: int = None, state: str = None, progressbar: bool = True):
    resp = post(ctx=ctx, uri=f"/vm/{vmid}/{state}", data=None)
    if resp:
        track_status(ctx=ctx, upid=resp['upid'], message=f"VM {vmid} {state}", transient=not progressbar)


@vm.command()
@click.option("--vmname", prompt=True)
@click.option("--tojson", default=False, is_flag=True)
@click.pass_obj
def get_id(ctx, vmname: str = None, tojson: bool = False):
    get_vmid(ctx, vmname, tojson)


def get_vmid(ctx, vmname: str = None, tojson: bool = False):
    """
    Given a VM Name, obtain its ID\f
    Parameters
    ----------
    vmname: str
        Name of the VM
    tojson: bool
        Format the output in json

    Returns
    -------
    VMID: table/json
    """
    headers = {"Authorization": f"Bearer {ctx.access_token}"}
    resp = None
    with console.status(f"[bold green]Obtaining VM {vmname}'s ID...") as status:
        resp = get(ctx=ctx, uri="/vm/vm_id", params={"vm_name": vmname})
    vmid = resp
    if tojson:
        return json.dumps(vmid, indent=4)
    else:
        table = Table(title=f"VM ID")
        table.add_column("VMName", style="cyan", no_wrap=True)
        table.add_column("VMID", style="green")

        for k, v in vmid.items():
            table.add_row(f"{k}", f"{v}")
        console.print(table, justify="left")


@vm.command()
@click.option("--vmid", type=int, prompt=True)
@click.option("--spice", prompt=False, is_flag=True, cls=Mutex, not_required_if=["vnc", "ssh"])
@click.option("--vnc", prompt=False, is_flag=True, cls=Mutex, not_required_if=["spice", "ssh"])
@click.option("--ssh", prompt=False, is_flag=True, cls=Mutex, not_required_if=["vnc", "spice"])
@click.pass_obj
def connect(ctx, vmid: int = None, spice: bool = True, vnc: bool = False, ssh: bool = False):
    """
    Connect to the remote VM via spice proxy, vnc or ssh \f
    Parameters
    ----------
    vmid: str
        VMID of the VM
    spice: bool
        To connect using spice protocol (select this for best graphics performance)
    vnc: bool
        To connect using vnc protocol (less color accurate, for high latency networks)
    ssh: bool
        To connect to vm via web console

    """
    headers = {"Authorization": f"Bearer {ctx.access_token}"}
    resp = None
    if not (spice or ssh):
        print_error("Only spice proxy and ssh are currently supported")
        sys.exit(1)
    if spice:
        with console.status(f"[bold cyan]Connecting to VM via spice...") as cstatus:
            resp = requests.get(f'{uoserver_url}/vm/{vmid}/spiceproxy', headers=headers)
            if resp.status_code in range(500, 600):
                print_error(f"VM {vmid} is not configrured to use spice proxy: {resp.text}")
            if resp.status_code not in range(200, 400):
                try:
                    print_error(resp.json().get("detail", f"Improper detail of the error returned: {resp.text}"))
                except json.JSONDecodeError:
                    print_error(f"Error returned from the server: {resp.text}")
            spiceproxy = resp.json()
            spiceproxy_file = ""
            with tempfile.TemporaryDirectory() as td:
                spiceproxy_file = os.path.join(td, f'{vmid}.spiceproxy')
                with open(spiceproxy_file, 'w') as fh:
                    fh.write("[virt-viewer]\n")
                    for k, v in spiceproxy.items():
                        fh.write(f'{k}={v}\n')
                if spiceproxy_file:
                    cstatus.update("[bold green]Active Spice session in another window")
                    # Open remote viewer
                    subprocess.run([remote_viewer_path, spiceproxy_file])  # , "--debug"])
                else:
                    print_error("Something's messed up")
    elif ssh:
        with console.status(f"[bold green]Connecting to VM via ssh...") as cstatus:
            # Obtain ip address for the vm
            ip_address = get_vmstatus(ctx, vmid, tojson=True)["ifaces"][0]["ip"]
        os.system(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {ip_address}')
