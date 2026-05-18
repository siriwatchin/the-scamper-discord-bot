import logging
import discord
from discord import app_commands
from discord.ext import commands

from server_client import get_jobs, get_job_info, get_balance, ACCOUNT

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


class ServerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
        embed.add_field(name="User", value=info["user"], inline=True)
        embed.add_field(name="State", value=info["state"], inline=True)
        embed.add_field(name="Nodes", value=info["nodes"], inline=True)
        embed.add_field(name="Elapsed", value=info["elapsed"], inline=True)
        embed.add_field(name="Exit Code", value=str(info["exit_code"]), inline=True)
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

        embed = discord.Embed(title=f"Account Balance — {ACCOUNT}", color=discord.Color.gold())

        pct_used = data.get("percent_used", 0)
        su_used = data.get("su_used", 0)
        su_alloc = data.get("su_alloc", 0)
        su_remaining = data.get("su_remaining", 0)
        embed.add_field(
            name="Service Units",
            value=(
                f"{_bar(pct_used)}\n"
                f"Used: `{su_used:,}` | Alloc: `{su_alloc:,}` | Remaining: `{su_remaining:,}`\n"
                f"({pct_used * 100:.1f}% used)"
            ),
            inline=False,
        )

        for label, used_key, alloc_key, remaining_key in [
            ("Compute (hrs)", "su_used_compute", "su_alloc_compute", "su_remaining_compute"),
            ("GPU (hrs)",     "su_used_gpu",     "su_alloc_gpu",     "su_remaining_gpu"),
            ("Memory (hrs)",  "su_used_memory",  "su_alloc_memory",  "su_remaining_memory"),
        ]:
            used = data.get(used_key, 0)
            alloc = data.get(alloc_key, 0)
            remaining = data.get(remaining_key, 0)
            pct = (used / alloc) if alloc else 0
            embed.add_field(
                name=label,
                value=(
                    f"{_bar(pct)}\n"
                    f"Used: `{used:.1f}` | Alloc: `{alloc:.1f}` | Remaining: `{remaining:.1f}`"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerCog(bot))
