# Scamper Discord Bot

A Discord bot for Kaggle hackathon teams — tracks the competition leaderboard and alerts you when rankings change.

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
```

- **Discord Token** — [Discord Developer Portal](https://discord.com/developers/applications) → Bot → Reset Token
- **Kaggle API key** — kaggle.com → Account → API → Create New Token (downloads `kaggle.json` — copy the username and key)

### 3. Run the bot

```bash
python bot.py
```

---

## Commands

### General

| Command | Description |
|---------|-------------|
| `/ping` | Check if the bot is online and show latency |

---

### Configuration (one-time setup)

| Command | Description |
|---------|-------------|
| `/setcompetition <slug>` | Set the Kaggle competition to track |
| `/setchannel` | Set the current channel to receive auto-updates |
| `/setinterval <minutes>` | How often to poll the leaderboard (min 5, default 30) |

**Example:**
```
/setcompetition titanic
/setchannel
/setinterval 15
```

> The slug is the last part of the competition URL:
> `https://www.kaggle.com/competitions/titanic` → slug is `titanic`

---

### Leaderboard

| Command | Description |
|---------|-------------|
| `/leaderboard` | Show the current top 10 with a link to Kaggle |

---

### Team tracking

| Command | Description |
|---------|-------------|
| `/track <team name>` | Watch a team and get alerted when their rank changes |
| `/untrack <team name>` | Stop watching a team |

**Example:**
```
/track MyAwesomeTeam
```

> The team name must match exactly as shown on the Kaggle leaderboard.

---

## How auto-updates work

1. The bot polls the leaderboard every N minutes (configured with `/setinterval`)
2. On each poll, it posts a refreshed top-10 embed to the configured channel
3. If any tracked team's rank changed, it sends a separate rank-change alert

---

## First-time setup checklist

```
1. Run: python bot.py
2. In your team's Discord channel, run:
   /setcompetition <slug>
   /setchannel
   /setinterval 15
   /track <your team name>
3. Run /leaderboard to confirm data is being fetched correctly
```

---

## Project structure

```
bot.py               — entry point
cogs/
  leaderboard_cog.py — /leaderboard, /track, /untrack + background poller
  config_cog.py      — /setcompetition, /setchannel, /setinterval
kaggle_client.py     — Kaggle API wrapper
state.py             — read/write config.json
.env                 — credentials (not committed)
config.json          — bot settings (not committed)
```
