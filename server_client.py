import json
import os
import time
import asyncssh

HOST = os.environ["SERVER_HOST"]
USER = os.environ["SERVER_USER"]
ACCOUNT = os.environ["SERVER_ACCOUNT"]


async def _run(command: str) -> str:
    async with asyncssh.connect(HOST, username=USER) as conn:
        result = await conn.run(command, check=True)
        return result.stdout


async def get_jobs() -> list[dict]:
    output = await _run(f"squeue -A {ACCOUNT} --json")
    data = json.loads(output)
    jobs = []
    now = int(time.time())
    for j in data.get("jobs", []):
        state = j.get("job_state", ["UNKNOWN"])
        if isinstance(state, list):
            state = state[0]
        start = j.get("start_time", {}).get("number", 0)
        elapsed = (now - start) if start else 0
        limit_minutes = j.get("time_limit", {}).get("number", 0)
        jobs.append({
            "job_id": j.get("job_id", "?"),
            "name": j.get("name", "?"),
            "user": j.get("user_name", "?"),
            "state": state,
            "nodes": j.get("nodes", "?"),
            "elapsed": _fmt_seconds(elapsed),
            "limit": _fmt_seconds(limit_minutes * 60) if limit_minutes else "∞",
        })
    return jobs


async def get_job_info(job_id: int) -> dict | None:
    output = await _run(f"sacct -j {job_id} --json")
    data = json.loads(output)
    jobs = data.get("jobs", [])
    if not jobs:
        return None
    j = jobs[0]
    state = j.get("state", {}).get("current", ["UNKNOWN"])
    if isinstance(state, list):
        state = state[0]
    elapsed = j.get("time", {}).get("elapsed", 0)
    exit_code = j.get("exit_code", {}).get("return_code", {}).get("number", "?")
    return {
        "job_id": j.get("job_id", job_id),
        "name": j.get("name", "?"),
        "user": j.get("user", "?"),
        "state": state,
        "nodes": j.get("nodes", "?"),
        "elapsed": _fmt_seconds(elapsed),
        "exit_code": exit_code,
    }


async def get_balance() -> dict | None:
    output = await _run("sbalance --json")
    entries = json.loads(output)
    for entry in entries:
        if entry.get("account") == ACCOUNT:
            return entry
    return None


def _fmt_seconds(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
