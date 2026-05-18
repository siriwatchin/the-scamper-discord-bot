import asyncio
import logging
import os
from logging.handlers import TimedRotatingFileHandler
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["DISCORD_TOKEN"]


def _setup_logging() -> None:
    os.makedirs("logs", exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = TimedRotatingFileHandler(
        filename="logs/bot.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("asyncssh").setLevel(logging.WARNING)


_setup_logging()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "cogs.config_cog",
    "cogs.leaderboard_cog",
]

SERVER_VARS = ["SERVER_HOST", "SERVER_USER", "SERVER_ACCOUNT"]


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! Latency: {round(bot.latency * 1000)}ms")


async def main():
    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
        if all(os.environ.get(v) for v in SERVER_VARS):
            await bot.load_extension("cogs.server_cog")
            print("Server cog loaded.")
        else:
            missing = [v for v in SERVER_VARS if not os.environ.get(v)]
            print(f"Server cog skipped (missing: {missing}).")
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
