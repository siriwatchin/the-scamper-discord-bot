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

# Optional — required only if using /server_jobs, /server_jobinfo, /server_balance, /server_usage
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

> Each Discord server the bot is in has its own independent configuration. Run the setup commands separately in each server.

---

## Commands

### General

| Command | Description |
|---------|-------------|
| `/ping` | Check if the bot is online and show latency |
| `/status` | Show current configuration for this server (only you can see) |

---

### Configuration (owner / Manage Server only)

| Command | Description |
|---------|-------------|
| `/setcompetition <slug>` | Set the Kaggle competition to track |
| `/clearcompetition` | Clear the competition for this server |
| `/setchannel` | Set the current channel for all bot notifications (leaderboard, rank alerts, job completion) |
| `/setleaderboardinterval <minutes>` | How often to poll the leaderboard (min 5, default 30) |
| `/setleaderboard <True/False>` | Enable or disable automatic leaderboard posting (default on) |
| `/setrankchanges <True/False>` | Enable or disable rank change alerts for tracked teams (default on) |

**Example:**
```
/setcompetition titanic
/setchannel
/setleaderboardinterval 15
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
| `/cleartracked` | Remove all tracked teams for this server — only you can see the confirmation |

> The team name must match exactly as shown on the Kaggle leaderboard.

---

### Server jobs

> Requires `SERVER_HOST`, `SERVER_USER`, and `SERVER_ACCOUNT` to be set in `.env`.
> Job completion alerts are sent to every Discord server that has a channel configured via `/setchannel`.

| Command | Description |
|---------|-------------|
| `/server_jobs` | Show all running/pending jobs for the configured account |
| `/server_jobinfo <job_id>` | Show details of a specific job (state, user, partition, runtime, exit code, failure reason) |
| `/server_balance` | Show compute/GPU/memory allocation balance for the account |
| `/server_usage` | Show per-user SHr usage breakdown for the team account |

---

## How auto-updates work

1. The bot polls the leaderboard every N minutes per server (configured with `/setleaderboardinterval`)
2. If **Auto Leaderboard** is on — posts a refreshed top-10 embed to the configured channel
3. If **Rank Change Alerts** is on — sends a separate alert for any tracked team whose rank changed
4. **Job completion** — bot polls server jobs every 5 minutes and alerts when a job finishes or fails

---

## Logs

Logs are written to `logs/bot.log` and rotated daily at midnight. The last 30 days are kept.

```
logs/
  bot.log              — today's log
  bot.log.2026-05-18   — yesterday's log
  ...
```

---

## First-time setup checklist (per Discord server)

```
1. Run: python bot.py
2. In your team's Discord channel, run:
   /setcompetition <slug>
   /setchannel
   /setleaderboardinterval 15
   /track <your team name>
3. Run /leaderboard to confirm Kaggle data is being fetched correctly
4. Run /server_jobs to confirm server connection is working (if SERVER_* is configured)
```

---

## Project structure

```
bot.py               — entry point + logging setup
cogs/
  leaderboard_cog.py — /leaderboard, /track, /untrack, /tracklist, /cleartracked + background poller
  config_cog.py      — /setcompetition, /clearcompetition, /setchannel,
                        /setleaderboardinterval, /setleaderboard, /setrankchanges, /status
  server_cog.py      — /server_jobs, /server_jobinfo, /server_balance, /server_usage + job completion poller
                        (loaded only if SERVER_* env vars are set)
kaggle_client.py     — Kaggle API wrapper
server_client.py     — SSH client for compute server commands
state.py             — read/write config.json (per-guild)
logs/                — daily rotating log files (not committed)
.env                 — credentials (not committed)
config.json          — bot settings per Discord server (not committed)
```
