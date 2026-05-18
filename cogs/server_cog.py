import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks

from server_client import get_jobs, get_job_info, get_balance, ACCOUNT
from state import load_config, config_lock, load_guild_config

log = logging.getLogger(__name__)


def _bar(pct: float, width: int = 12) -> str:
    filled = round(min(pct, 1.0) * width)
    return "█" * filled + "░" * (width - filled)


STATE_COLOR = {
    "RUNNING": discord.Color.green(),
    "PENDING": discord.Color.yellow(),
    "COMPLETED": discord.Color.blue(),
    "FAILED": discord.Color.red(),
    "CANCELLED": discord.Color.og_blurple(),
}

STATE_ICON = {
    "COMPLETED": "✅",
    "FAILED": "❌",
    "CANCELLED": "🚫",
    "TIMEOUT": "⏱️",
}


class ServerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._job_snapshot: dict[int, dict] = {}  # job_id -> row
        self.job_poller.start()

    def cog_unload(self):
        self.job_poller.cancel()

    # ── Slash commands ──────────────────────────────────────────────────────

    @app_commands.command(name="server_jobs", description="Show running/pending jobs for the team")
    async def jobs(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            rows = await get_jobs()
        except Exception as e:
            log.error("get_jobs failed: %s", e)
            await interaction.followup.send("Failed to fetch jobs. Check bot logs for details.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Jobs — {ACCOUNT}", color=discord.Color.blue())
        if not rows:
            embed.description = "No running or pending jobs."
        else:
            lines = []
            for j in rows:
                icon = {"RUNNING": "🟢", "PENDING": "🟡"}.get(j["state"], "⚪")
                lines.append(
                    f"{icon} `{j['job_id']}` **{j['name']}** — {j['user']}\n"
                    f"  State: {j['state']} | Nodes: {j['nodes']} | Time: {j['elapsed']}/{j['limit']}"
                )
            embed.description = "\n\n".join(lines)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="server_jobinfo", description="Show details of a specific job")
    @app_commands.describe(job_id="The numeric job ID")
    async def jobinfo(self, interaction: discord.Interaction, job_id: int):
        await interaction.response.defer()
        try:
            info = await get_job_info(job_id)
        except Exception as e:
            log.error("get_job_info(%s) failed: %s", job_id, e)
            await interaction.followup.send("Failed to fetch job info. Check bot logs for details.", ephemeral=True)
            return

        if info is None:
            await interaction.followup.send(f"Job `{job_id}` not found.", ephemeral=True)
            return

        color = STATE_COLOR.get(info["state"], discord.Color.greyple())
        embed = discord.Embed(title=f"Job {info['job_id']}: {info['name']}", color=color)
        embed.add_field(name="State", value=info["state"], inline=True)
        embed.add_field(name="User", value=info["user"], inline=True)
        embed.add_field(name="Partition", value=info["partition"], inline=True)
        embed.add_field(name="Nodes", value=info["nodes"], inline=True)
        embed.add_field(name="Elapsed", value=info["elapsed"], inline=True)
        embed.add_field(name="Time Limit", value=info["limit"], inline=True)
        embed.add_field(name="Exit Code", value=str(info["exit_code"]), inline=True)
        if info.get("reason") and info["reason"] not in ("None", ""):
            embed.add_field(name="Reason", value=info["reason"], inline=True)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="server_balance", description="Show compute/GPU/memory allocation balance for the team")
    async def balance(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            data = await get_balance()
        except Exception as e:
            log.error("get_balance failed: %s", e)
            await interaction.followup.send("Failed to fetch balance. Check bot logs for details.", ephemeral=True)
            return

        if data is None:
            await interaction.followup.send(f"No balance data found for account `{ACCOUNT}`.", ephemeral=True)
            return

        pct_remaining = data.get("percent_remaining", 1.0)
        sh_used = data.get("sh_used", 0.0)
        sh_alloc = data.get("sh_alloc", 0.0)
        sh_remaining = data.get("sh_remaining", 0.0)

        embed = discord.Embed(
            title=f"Account Balance — {ACCOUNT}",
            description=(
                f"{_bar(pct_remaining)} **{pct_remaining * 100:.2f}% remaining**\n"
                f"Used: `{sh_used:.2f}` SHr | Alloc: `{sh_alloc:.2f}` SHr | Remaining: `{sh_remaining:.2f}` SHr"
            ),
            color=discord.Color.gold(),
        )

        for label, used_key, alloc_key, remaining_key in [
            ("Compute (SHr)", "su_used_compute", "su_alloc_compute", "su_remaining_compute"),
            ("GPU (SHr)",     "su_used_gpu",     "su_alloc_gpu",     "su_remaining_gpu"),
            ("Memory (SHr)",  "su_used_memory",  "su_alloc_memory",  "su_remaining_memory"),
        ]:
            used = data.get(used_key, 0.0)
            alloc = data.get(alloc_key, 0.0)
            remaining = data.get(remaining_key, 0.0)
            if alloc == 0:
                continue
            pct_rem = remaining / alloc
            embed.add_field(
                name=label,
                value=(
                    f"{_bar(pct_rem)} {pct_rem * 100:.1f}% remaining\n"
                    f"Used: `{used:.2f}` | Alloc: `{alloc:.2f}` | Remaining: `{remaining:.2f}`"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    # ── Background job poller ───────────────────────────────────────────────

    @tasks.loop(minutes=5)
    async def job_poller(self):
        async with config_lock:
            cfg = load_config()
        channel_ids = [
            g.get("update_channel_id")
            for g in cfg.get("guilds", {}).values()
            if g.get("update_channel_id")
        ]
        if not channel_ids:
            return

        try:
            rows = await get_jobs()
        except Exception as e:
            log.error("Job poller failed: %s", e)
            return

        new_snapshot = {j["job_id"]: j for j in rows}

        if not self._job_snapshot:
            self._job_snapshot = new_snapshot
            return

        finished_ids = set(self._job_snapshot) - set(new_snapshot)
        if not finished_ids:
            self._job_snapshot = new_snapshot
            return

        channels = [self.bot.get_channel(cid) for cid in channel_ids if self.bot.get_channel(cid)]
        if not channels:
            self._job_snapshot = new_snapshot
            return

        for job_id in finished_ids:
            prev = self._job_snapshot[job_id]
            try:
                info = await get_job_info(job_id)
            except Exception as e:
                log.error("sacct for job %s failed: %s", job_id, e)
                continue

            state = info["state"] if info else "UNKNOWN"
            icon = STATE_ICON.get(state, "⚪")
            elapsed = info["elapsed"] if info else prev["elapsed"]
            name = info["name"] if info else prev["name"]

            user = info["user"] if info else prev.get("user", "—")
            partition = info["partition"] if info else "—"
            exit_code = str(info["exit_code"]) if info else "—"
            reason = info.get("reason", "") if info else ""

            detail_parts = [f"User: `{user}`", f"Partition: `{partition}`", f"Time: {elapsed}", f"Exit: `{exit_code}`"]
            if reason and reason not in ("None", ""):
                detail_parts.append(f"Reason: `{reason}`")

            for channel in channels:
                await channel.send(
                    f"{icon} Job `{job_id}` **{name}** — **{state}**\n"
                    + " | ".join(detail_parts)
                )

        self._job_snapshot = new_snapshot

    @job_poller.before_loop
    async def before_job_poller(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerCog(bot))
