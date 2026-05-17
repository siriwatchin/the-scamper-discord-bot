import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks

from kaggle_client import fetch_leaderboard
from state import load_config, save_config


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
        self._last_snapshot: dict[str, dict] = {}  # teamName -> row
        self.poller.start()

    def cog_unload(self):
        self.poller.cancel()

    # ── Slash commands ──────────────────────────────────────────────────────

    @app_commands.command(name="leaderboard", description="Show the current Kaggle leaderboard (top 10)")
    async def leaderboard(self, interaction: discord.Interaction):
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
            await interaction.followup.send(f"Failed to fetch leaderboard: `{e}`")
            return
        embed = _build_embed(competition, rows)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="track", description="Watch a team and get alerted when their rank changes")
    @app_commands.describe(team="Exact team name as shown on the leaderboard")
    async def track(self, interaction: discord.Interaction, team: str):
        cfg = load_config()
        tracked: list[str] = cfg.get("tracked_teams", [])
        if team in tracked:
            await interaction.response.send_message(f"Already tracking **{team}**.", ephemeral=True)
            return
        tracked.append(team)
        cfg["tracked_teams"] = tracked
        save_config(cfg)
        await interaction.response.send_message(f"Now tracking **{team}**. You'll be alerted on rank changes.")

    @app_commands.command(name="untrack", description="Stop tracking a team")
    @app_commands.describe(team="Team name to stop tracking")
    async def untrack(self, interaction: discord.Interaction, team: str):
        cfg = load_config()
        tracked: list[str] = cfg.get("tracked_teams", [])
        if team not in tracked:
            await interaction.response.send_message(f"**{team}** is not being tracked.", ephemeral=True)
            return
        tracked.remove(team)
        cfg["tracked_teams"] = tracked
        save_config(cfg)
        await interaction.response.send_message(f"Stopped tracking **{team}**.")

    # ── Background poller ───────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def poller(self):
        cfg = load_config()
        competition = cfg.get("competition")
        channel_id = cfg.get("update_channel_id")
        interval = cfg.get("interval_minutes", 30)
        tracked: list[str] = cfg.get("tracked_teams", [])

        if not competition or not channel_id:
            return

        # Only fire every `interval` minutes using a counter stored in config
        tick = cfg.get("_poll_tick", 0) + 1
        if tick < interval:
            cfg["_poll_tick"] = tick
            save_config(cfg)
            return
        cfg["_poll_tick"] = 0
        save_config(cfg)

        try:
            rows = await asyncio.to_thread(fetch_leaderboard, competition)
        except Exception:
            return

        new_snapshot = {r["teamName"]: r for r in rows}

        if not self._last_snapshot:
            self._last_snapshot = new_snapshot
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        # Post full leaderboard update
        embed = _build_embed(competition, rows, title_prefix="🔄 ")
        await channel.send(embed=embed)

        # Alert on tracked team rank changes
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
