import subprocess
import os
import socket

def is_worker_alive(wallet_id: str) -> bool:
    """
    Ask Celery for all of its registered nodes (with `status`),
    then see if any of them start with "wallet_<id>@".
    """
    queue_prefix = f"wallet_{wallet_id}@"
    try:
        # `status` will list all nodes that have ever joined the cluster
        out = subprocess.check_output(
            ["celery", "-A", "heron_app.workers.worker", "status"],
            stderr=subprocess.DEVNULL
        )
        text = out.decode("utf-8")
        # look for any line like "-> wallet_<id>@<hostname>: OK"
        return any(line.strip().startswith("-> "+queue_prefix) for line in text.splitlines())
    except subprocess.CalledProcessError:
        # if Celery isn't up yet, status will fail; treat that as "no node"
        return False

def start_worker(wallet_id: str):
    """
    Launch exactly one celery worker on queue `wallet_<id>` using
    a unique node name that includes this container's hostname.
    """
    queue_name = f"wallet_{wallet_id}"
    # use the container's hostname so that repeated restarts don't collide
    host = socket.gethostname()
    nodename = f"{queue_name}@{host}"

    if is_worker_alive(wallet_id):
        print(f"[Worker] {nodename} is already running, skipping launch")
        return

    print(f"[Worker] Starting new worker for queue={queue_name} as node={nodename}")
    subprocess.Popen([
        "celery", "-A", "heron_app.workers.worker", "worker",
        "-Q", queue_name,
        "-n", nodename,
        "--concurrency=1",
        "--loglevel=info"
    ])