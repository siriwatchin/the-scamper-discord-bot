import discord
from discord import app_commands
from discord.ext import commands

from state import load_config, save_config


class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setcompetition", description="Set the Kaggle competition to track")
    @app_commands.describe(slug="The Kaggle competition slug, e.g. titanic")
    @app_commands.default_permissions(manage_guild=True)
    async def set_competition(self, interaction: discord.Interaction, slug: str):
        cfg = load_config()
        cfg["competition"] = slug
        save_config(cfg)
        await interaction.response.send_message(f"Competition set to **{slug}**.")

    @app_commands.command(name="setchannel", description="Set the channel for leaderboard auto-updates")
    @app_commands.default_permissions(manage_guild=True)
    async def set_channel(self, interaction: discord.Interaction):
        cfg = load_config()
        cfg["update_channel_id"] = interaction.channel_id
        save_config(cfg)
        await interaction.response.send_message(f"Auto-update channel set to <#{interaction.channel_id}>.")

    @app_commands.command(name="setinterval", description="Set how often (in minutes) the leaderboard is checked")
    @app_commands.describe(minutes="Polling interval in minutes (minimum 5)")
    @app_commands.default_permissions(manage_guild=True)
    async def set_interval(self, interaction: discord.Interaction, minutes: int):
        if minutes < 5:
            await interaction.response.send_message("Minimum interval is 5 minutes.", ephemeral=True)
            return
        cfg = load_config()
        cfg["interval_minutes"] = minutes
        save_config(cfg)
        await interaction.response.send_message(f"Polling interval set to **{minutes} minutes**.")


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
