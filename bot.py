import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["DISCORD_TOKEN"]

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "cogs.config_cog",
    "cogs.leaderboard_cog",
]


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
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
