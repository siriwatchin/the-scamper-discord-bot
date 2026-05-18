import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks

from kaggle_client import fetch_leaderboard
from state import load_config, save_config, config_lock

log = logging.getLogger(__name__)


def _build_embed(competition: str, rows: list[dict], title_prefix: str = "") -> discord.Embed:
    embed = discord.Embed(
        title=f"{title_prefix}Leaderboard: {competition}",
        color=discord.Color.blue(),
        url=f"https://www.kaggle.com/competitions/{competition}/leaderboard",
    )
    lines = []
    for row in rows[:10]:
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(row["rank"], f"#{row['rank']}")
        lines.append(f"{medal} **{row['teamName']}** — {row['score']}")
    embed.description = "\n".join(lines) if lines else "No data."
    return embed


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_snapshot: dict[str, dict] = {}
        self.poller.start()

    def cog_unload(self):
        self.poller.cancel()

    # ── Slash commands ──────────────────────────────────────────────────────

    @app_commands.command(name="leaderboard", description="Show the current Kaggle leaderboard (top 10)")
    @app_commands.checks.cooldown(rate=1, per=60, key=lambda i: i.guild_id)
    async def leaderboard(self, interaction: discord.Interaction):
        async with config_lock:
            cfg = load_config()
        competition = cfg.get("competition")
        if not competition:
            await interaction.response.send_message(
                "No competition set. Use `/setcompetition <slug>` first.", ephemeral=True
            )
            return
        await interaction.response.defer()
        try:
            rows = await asyncio.to_thread(fetch_leaderboard, competition)
        except Exception as e:
            log.error("fetch_leaderboard failed: %s", e)
            await interaction.followup.send("Failed to fetch leaderboard. Check bot logs for details.", ephemeral=True)
            return
        embed = _build_embed(competition, rows)
        await interaction.followup.send(embed=embed)

    @leaderboard.error
    async def leaderboard_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"Slow down! Try again in **{error.retry_after:.0f}s**.", ephemeral=True
            )

    @app_commands.command(name="track", description="Watch a team and get alerted when their rank changes")
    @app_commands.describe(team="Exact team name as shown on the leaderboard")
    async def track(self, interaction: discord.Interaction, team: str):
        async with config_lock:
            cfg = load_config()
            tracked: list[str] = cfg.get("tracked_teams", [])
            if team in tracked:
                await interaction.response.send_message(f"Already tracking **{team}**.", ephemeral=True)
                return
            tracked.append(team)
            cfg["tracked_teams"] = tracked
            save_config(cfg)
        await interaction.response.send_message(f"Now tracking **{team}**. You'll be alerted on rank changes.", ephemeral=True)

    @app_commands.command(name="untrack", description="Stop tracking a team")
    @app_commands.describe(team="Team name to stop tracking")
    async def untrack(self, interaction: discord.Interaction, team: str):
        async with config_lock:
            cfg = load_config()
            tracked: list[str] = cfg.get("tracked_teams", [])
            if team not in tracked:
                await interaction.response.send_message(f"**{team}** is not being tracked.", ephemeral=True)
                return
            tracked.remove(team)
            cfg["tracked_teams"] = tracked
            save_config(cfg)
        await interaction.response.send_message(f"Stopped tracking **{team}**.", ephemeral=True)

    @app_commands.command(name="tracklist", description="Show all teams currently being tracked")
    async def tracklist(self, interaction: discord.Interaction):
        async with config_lock:
            cfg = load_config()
        tracked: list[str] = cfg.get("tracked_teams", [])
        if not tracked:
            await interaction.response.send_message("No teams are being tracked.", ephemeral=True)
            return
        lines = "\n".join(f"• {t}" for t in tracked)
        await interaction.response.send_message(f"**Tracked teams:**\n{lines}", ephemeral=True)

    # ── Background poller ───────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def poller(self):
        # Read config and update tick — lock released before network call
        async with config_lock:
            cfg = load_config()
            competition = cfg.get("competition")
            channel_id = cfg.get("update_channel_id")
            interval = cfg.get("interval_minutes", 30)
            tracked = list(cfg.get("tracked_teams", []))
            post_leaderboard = cfg.get("post_leaderboard", True)
            post_rank_changes = cfg.get("post_rank_changes", True)

            if not competition or not channel_id:
                return

            tick = cfg.get("_poll_tick", 0) + 1
            if tick < interval:
                cfg["_poll_tick"] = tick
                save_config(cfg)
                return
            cfg["_poll_tick"] = 0
            save_config(cfg)

        # Network call happens outside the lock
        try:
            rows = await asyncio.to_thread(fetch_leaderboard, competition)
        except Exception as e:
            log.error("Leaderboard poll failed: %s", e)
            return

        new_snapshot = {r["teamName"]: r for r in rows}

        if not self._last_snapshot:
            self._last_snapshot = new_snapshot
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        if post_leaderboard:
            embed = _build_embed(competition, rows, title_prefix="🔄 ")
            await channel.send(embed=embed)

        if post_rank_changes:
            for team in tracked:
                old = self._last_snapshot.get(team)
                new = new_snapshot.get(team)
                if old and new and old["rank"] != new["rank"]:
                    direction = "⬆️" if new["rank"] < old["rank"] else "⬇️"
                    await channel.send(
                        f"{direction} **{team}** moved from rank **{old['rank']}** → **{new['rank']}** "
                        f"(score: {new['score']})"
                    )

        self._last_snapshot = new_snapshot

    @poller.before_loop
    async def before_poller(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))
