"""Main module."""
import time
from proxmoxer import ProxmoxAPI
from rich.progress import Progress


proxmox = ProxmoxAPI('192.168.41.44', user='root@pam', password='', verify_ssl=False)

with Progress() as progress:
    upid = sorted(proxmox.cluster.tasks.get(), key=lambda x: x['starttime'], reverse=True)[0]['upid']
    task1 = progress.add_task("[red]Cloning...", total=100)
    while not progress.finished:
        try:
            completed = proxmox.nodes.pve.get('tasks/{}/log?limit=500'.format(upid))[-1]['t'].split(':')[-1].strip().strip(' %')
            if completed == "TASK OK":
                completed = 100
            progress.update(task1, completed=float(completed))
        except:
            break
        time.sleep(0.5)
