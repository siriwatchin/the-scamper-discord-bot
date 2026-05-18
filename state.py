import asyncio
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

config_lock = asyncio.Lock()


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
