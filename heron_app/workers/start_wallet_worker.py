import subprocess
import sys
import json
import os

def is_worker_alive(wallet_id: str) -> bool:
    queue_name = f"wallet_{wallet_id}"
    nodename_prefix = f"{queue_name}@"

    try:
        output = subprocess.check_output([
            "celery", "-A", "heron_app.workers.worker", "inspect", "ping", "--timeout=2", "--destination", nodename_prefix + "%h"
        ], stderr=subprocess.DEVNULL)
        
        if nodename_prefix in output.decode():
            return True
    except subprocess.CalledProcessError:
        pass

    return False

def start_worker(wallet_id: str):
    queue_name = f"wallet_{wallet_id}"
    nodename = f"{queue_name}@{os.getenv('HOSTNAME', 'default')}-{wallet_id[:8]}"  # ensure unique nodename across restarts

    if is_worker_alive(wallet_id):
        print(f"[Worker] {nodename} is already running.")
        return

    print(f"[Worker] Starting new worker for {queue_name}")
    subprocess.Popen([
        "celery", "-A", "heron_app.workers.worker", "worker",
        "-Q", queue_name,
        "-n", nodename,
        "--concurrency=1",
        "--loglevel=info"
    ])