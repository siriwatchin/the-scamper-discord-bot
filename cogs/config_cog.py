import os
import discord
from discord import app_commands
from discord.ext import commands

from state import load_config, save_config, config_lock

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
        async with config_lock:
            cfg = load_config()
            cfg["competition"] = slug
            save_config(cfg)
        await interaction.response.send_message(f"Competition set to **{slug}**.")

    @app_commands.command(name="setchannel", description="Set the channel for leaderboard auto-updates")
    @is_owner_or_manager()
    async def set_channel(self, interaction: discord.Interaction):
        async with config_lock:
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
        async with config_lock:
            cfg = load_config()
            cfg["interval_minutes"] = minutes
            save_config(cfg)
        await interaction.response.send_message(f"Polling interval set to **{minutes} minutes**.")

    @app_commands.command(name="setleaderboard", description="Turn automatic leaderboard posting on or off")
    @app_commands.describe(enabled="on or off")
    @is_owner_or_manager()
    async def set_leaderboard(self, interaction: discord.Interaction, enabled: bool):
        async with config_lock:
            cfg = load_config()
            cfg["post_leaderboard"] = enabled
            save_config(cfg)
        await interaction.response.send_message(
            f"Auto leaderboard post: **{'on' if enabled else 'off'}**.", ephemeral=True
        )

    @app_commands.command(name="setrankchanges", description="Turn rank change alerts on or off")
    @app_commands.describe(enabled="on or off")
    @is_owner_or_manager()
    async def set_rank_changes(self, interaction: discord.Interaction, enabled: bool):
        async with config_lock:
            cfg = load_config()
            cfg["post_rank_changes"] = enabled
            save_config(cfg)
        await interaction.response.send_message(
            f"Rank change alerts: **{'on' if enabled else 'off'}**.", ephemeral=True
        )

    @app_commands.command(name="status", description="Show current bot configuration")
    async def status(self, interaction: discord.Interaction):
        async with config_lock:
            cfg = load_config()
        embed = discord.Embed(title="Bot Status", color=discord.Color.blurple())
        embed.add_field(name="Competition", value=cfg.get("competition") or "—", inline=True)
        embed.add_field(name="Interval", value=f"{cfg.get('interval_minutes', 30)} min", inline=True)
        channel_id = cfg.get("update_channel_id")
        embed.add_field(name="Update Channel", value=f"<#{channel_id}>" if channel_id else "—", inline=True)
        tracked = cfg.get("tracked_teams", [])
        embed.add_field(name="Tracked Teams", value=str(len(tracked)), inline=True)
        server_account = os.environ.get("SERVER_ACCOUNT") or "—"
        embed.add_field(name="Server Account", value=server_account, inline=True)
        embed.add_field(name="Auto Leaderboard", value="on" if cfg.get("post_leaderboard", True) else "off", inline=True)
        embed.add_field(name="Rank Change Alerts", value="on" if cfg.get("post_rank_changes", True) else "off", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
