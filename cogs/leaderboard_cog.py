import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks

from kaggle_client import fetch_leaderboard
from state import load_config, save_config, config_lock, load_guild_config, set_guild_config

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
        self._last_snapshot: dict[str, dict[str, dict]] = {}  # guild_id -> teamName -> row
        self.poller.start()

    def cog_unload(self):
        self.poller.cancel()

    # ── Slash commands ──────────────────────────────────────────────────────

    @app_commands.command(name="leaderboard", description="Show the current Kaggle leaderboard (top 10)")
    @app_commands.checks.cooldown(rate=1, per=60, key=lambda i: i.guild_id)
    async def leaderboard(self, interaction: discord.Interaction):
        async with config_lock:
            cfg = load_config()
        guild_cfg = load_guild_config(cfg, interaction.guild_id)
        competition = guild_cfg.get("competition")
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
            guild_cfg = load_guild_config(cfg, interaction.guild_id)
            tracked: list[str] = guild_cfg.get("tracked_teams", [])
            if team in tracked:
                await interaction.response.send_message(f"Already tracking **{team}**.", ephemeral=True)
                return
            tracked.append(team)
            guild_cfg["tracked_teams"] = tracked
            set_guild_config(cfg, interaction.guild_id, guild_cfg)
            save_config(cfg)
        await interaction.response.send_message(f"Now tracking **{team}**. You'll be alerted on rank changes.", ephemeral=True)

    @app_commands.command(name="untrack", description="Stop tracking a team")
    @app_commands.describe(team="Team name to stop tracking")
    async def untrack(self, interaction: discord.Interaction, team: str):
        async with config_lock:
            cfg = load_config()
            guild_cfg = load_guild_config(cfg, interaction.guild_id)
            tracked: list[str] = guild_cfg.get("tracked_teams", [])
            if team not in tracked:
                await interaction.response.send_message(f"**{team}** is not being tracked.", ephemeral=True)
                return
            tracked.remove(team)
            guild_cfg["tracked_teams"] = tracked
            set_guild_config(cfg, interaction.guild_id, guild_cfg)
            save_config(cfg)
        await interaction.response.send_message(f"Stopped tracking **{team}**.", ephemeral=True)

    @app_commands.command(name="tracklist", description="Show all teams currently being tracked")
    async def tracklist(self, interaction: discord.Interaction):
        async with config_lock:
            cfg = load_config()
        guild_cfg = load_guild_config(cfg, interaction.guild_id)
        tracked: list[str] = guild_cfg.get("tracked_teams", [])
        if not tracked:
            await interaction.response.send_message("No teams are being tracked.", ephemeral=True)
            return
        lines = "\n".join(f"• {t}" for t in tracked)
        await interaction.response.send_message(f"**Tracked teams:**\n{lines}", ephemeral=True)

    # ── Background poller ───────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def poller(self):
        async with config_lock:
            cfg = load_config()
            guilds_cfg = cfg.get("guilds", {})

            guilds_to_poll = []
            for guild_id_str, guild_cfg in guilds_cfg.items():
                competition = guild_cfg.get("competition")
                channel_id = guild_cfg.get("update_channel_id")
                interval = guild_cfg.get("interval_minutes", 30)

                if not competition or not channel_id:
                    continue

                tick = guild_cfg.get("_poll_tick", 0) + 1
                if tick < interval:
                    guild_cfg["_poll_tick"] = tick
                    continue

                guild_cfg["_poll_tick"] = 0
                guilds_to_poll.append({
                    "guild_id": guild_id_str,
                    "competition": competition,
                    "channel_id": channel_id,
                    "tracked": list(guild_cfg.get("tracked_teams", [])),
                    "post_leaderboard": guild_cfg.get("post_leaderboard", True),
                    "post_rank_changes": guild_cfg.get("post_rank_changes", True),
                })

            save_config(cfg)

        for guild_info in guilds_to_poll:
            guild_id = guild_info["guild_id"]
            competition = guild_info["competition"]

            try:
                rows = await asyncio.to_thread(fetch_leaderboard, competition)
            except Exception as e:
                log.error("Leaderboard poll failed for guild %s: %s", guild_id, e)
                continue

            new_snapshot = {r["teamName"]: r for r in rows}
            last = self._last_snapshot.get(guild_id, {})

            if not last:
                self._last_snapshot[guild_id] = new_snapshot
                continue

            channel = self.bot.get_channel(guild_info["channel_id"])
            if channel is None:
                self._last_snapshot[guild_id] = new_snapshot
                continue

            if guild_info["post_leaderboard"]:
                embed = _build_embed(competition, rows, title_prefix="🔄 ")
                await channel.send(embed=embed)

            if guild_info["post_rank_changes"]:
                for team in guild_info["tracked"]:
                    old = last.get(team)
                    new = new_snapshot.get(team)
                    if old and new and old["rank"] != new["rank"]:
                        direction = "⬆️" if new["rank"] < old["rank"] else "⬇️"
                        await channel.send(
                            f"{direction} **{team}** moved from rank **{old['rank']}** → **{new['rank']}** "
                            f"(score: {new['score']})"
                        )

            self._last_snapshot[guild_id] = new_snapshot

    @poller.before_loop
    async def before_poller(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))
