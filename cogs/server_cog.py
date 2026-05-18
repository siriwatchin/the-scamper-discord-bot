import logging
import discord
from discord import app_commands
from discord.ext import commands

from server_client import get_jobs, get_job_info, get_balance, ACCOUNT

log = logging.getLogger(__name__)

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

        embed = discord.Embed(title=f"Account Balance — {ACCOUNT}", color=discord.Color.gold())
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (str, int, float)):
                    embed.add_field(name=key, value=str(value), inline=True)
                elif isinstance(value, list) and value:
                    embed.add_field(name=key, value="\n".join(str(v) for v in value[:5]), inline=False)
        else:
            embed.description = f"```{str(data)[:1000]}```"
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerCog(bot))
