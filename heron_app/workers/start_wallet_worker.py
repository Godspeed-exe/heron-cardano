import subprocess
import sys

def start_worker(wallet_id: str):
    queue_name = f"wallet_{wallet_id}"
    subprocess.Popen([
        "celery", "-A", "heron_app.workers.worker", "worker",
        "-Q", queue_name,
        "-n", f"{queue_name}@%h",
        "--concurrency=1",
        "--loglevel=info"
    ])