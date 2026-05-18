import os
import discord
from discord import app_commands
from discord.ext import commands

from state import load_config, save_config

_raw = os.environ.get("OWNER_ID")
OWNER_ID: int | None = int(_raw) if _raw else None


def is_owner_or_manager():
    def predicate(interaction: discord.Interaction) -> bool:
        if OWNER_ID and interaction.user.id == OWNER_ID:
            return True
        perms = interaction.user.guild_permissions
        return perms is not None and perms.manage_guild
    return app_commands.check(predicate)


class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setcompetition", description="Set the Kaggle competition to track")
    @app_commands.describe(slug="The Kaggle competition slug, e.g. titanic")
    @is_owner_or_manager()
    async def set_competition(self, interaction: discord.Interaction, slug: str):
        cfg = load_config()
        cfg["competition"] = slug
        save_config(cfg)
        await interaction.response.send_message(f"Competition set to **{slug}**.")

    @app_commands.command(name="setchannel", description="Set the channel for leaderboard auto-updates")
    @is_owner_or_manager()
    async def set_channel(self, interaction: discord.Interaction):
        cfg = load_config()
        cfg["update_channel_id"] = interaction.channel_id
        save_config(cfg)
        await interaction.response.send_message(f"Auto-update channel set to <#{interaction.channel_id}>.")

    @app_commands.command(name="setinterval", description="Set how often (in minutes) the leaderboard is checked")
    @app_commands.describe(minutes="Polling interval in minutes (minimum 5)")
    @is_owner_or_manager()
    async def set_interval(self, interaction: discord.Interaction, minutes: int):
        if minutes < 5:
            await interaction.response.send_message("Minimum interval is 5 minutes.", ephemeral=True)
            return
        cfg = load_config()
        cfg["interval_minutes"] = minutes
        save_config(cfg)
        await interaction.response.send_message(f"Polling interval set to **{minutes} minutes**.")

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
