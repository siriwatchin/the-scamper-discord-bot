# Scamper Discord Bot

A Discord bot for Kaggle hackathon teams — tracks the competition leaderboard, alerts you when rankings change, and shows compute job status on the team's server.

---

## Setup

### 1. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
DISCORD_TOKEN=<Discord Bot Token>
KAGGLE_USERNAME=<Kaggle username>
KAGGLE_KEY=<Kaggle API key>
OWNER_ID=<Your Discord user ID>

# Optional — required only if using /jobs, /jobinfo, /balance
SERVER_HOST=<Cluster hostname>
SERVER_USER=<Cluster username>
SERVER_ACCOUNT=<Cluster account name>
```

- **Discord Token** — [Discord Developer Portal](https://discord.com/developers/applications) → Bot → Reset Token
- **Kaggle API key** — kaggle.com → Account → API → Create New Token (downloads `kaggle.json` — copy the username and key)
- **Owner ID** — Discord → Settings → Advanced → Enable Developer Mode → right-click your name → Copy User ID
- **SERVER_*** — hostname, username, and account name for SSH access to your compute cluster. If omitted, server commands are disabled automatically.

> The machine running the bot must have its SSH public key already authorized on the server (`~/.ssh/authorized_keys`). Run `ssh-keyscan <SERVER_HOST> >> ~/.ssh/known_hosts` once before starting the bot.

### 3. Run the bot

```bash
python bot.py
```

Stop with `Ctrl+C`.

---

## Commands

### General

| Command | Description |
|---------|-------------|
| `/ping` | Check if the bot is online and show latency |
| `/status` | Show current bot configuration (ephemeral) |

---

### Configuration (owner / Manage Server only)

| Command | Description |
|---------|-------------|
| `/setcompetition <slug>` | Set the Kaggle competition to track |
| `/setchannel` | Set the current channel to receive auto-updates |
| `/setinterval <minutes>` | How often to poll the leaderboard (min 5, default 30) |
| `/setupdates leaderboard rank_changes` | Toggle what the bot posts automatically (both default to on) |

**Example:**
```
/setcompetition titanic
/setchannel
/setinterval 15
/setupdates leaderboard:True rank_changes:False
```

> The slug is the last part of the competition URL:
> `https://www.kaggle.com/competitions/titanic` → slug is `titanic`

---

### Leaderboard

| Command | Description |
|---------|-------------|
| `/leaderboard` | Show the current top 10 with a link to Kaggle (1 request/min per server) |
| `/track <team name>` | Watch a team and get alerted when their rank changes — only you can see the confirmation |
| `/untrack <team name>` | Stop watching a team — only you can see the confirmation |
| `/tracklist` | Show all teams currently being tracked — only you can see the response |

> The team name must match exactly as shown on the Kaggle leaderboard.

---

### Server jobs

> Requires `SERVER_HOST`, `SERVER_USER`, and `SERVER_ACCOUNT` to be set in `.env`.

| Command | Description |
|---------|-------------|
| `/jobs` | Show all running/pending jobs for the configured account |
| `/jobinfo <job_id>` | Show details of a specific job (state, runtime, nodes, exit code) |
| `/balance` | Show compute/GPU/memory allocation balance for the account |

---

## How auto-updates work

1. The bot polls the leaderboard every N minutes (configured with `/setinterval`)
2. If **Auto Leaderboard** is on — posts a refreshed top-10 embed to the configured channel
3. If **Rank Change Alerts** is on — sends a separate alert for any tracked team whose rank changed

Both can be toggled independently with `/setupdates`.

---

## Logs

Logs are written to `logs/bot.log` and rotated daily at midnight. The last 30 days are kept.

```
logs/
  bot.log              — today's log
  bot.log.2026-05-17   — yesterday's log
  ...
```

---

## First-time setup checklist

```
1. Run: python bot.py
2. In your team's Discord channel, run:
   /setcompetition <slug>
   /setchannel
   /setinterval 15
   /track <your team name>
3. Run /leaderboard to confirm Kaggle data is being fetched correctly
4. Run /jobs to confirm server connection is working (if SERVER_* is configured)
```

---

## Project structure

```
bot.py               — entry point + logging setup
cogs/
  leaderboard_cog.py — /leaderboard, /track, /untrack, /tracklist + background poller
  config_cog.py      — /setcompetition, /setchannel, /setinterval, /setupdates, /status
  server_cog.py      — /jobs, /jobinfo, /balance (loaded only if SERVER_* env vars are set)
kaggle_client.py     — Kaggle API wrapper
server_client.py     — SSH client for compute server commands
state.py             — read/write config.json
logs/                — daily rotating log files (not committed)
.env                 — credentials (not committed)
config.json          — bot settings (not committed)
```
