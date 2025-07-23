import discord
from discord.ext import commands, tasks
from discord import app_commands
import config
from utils.helpers import get_admin_role, get_log_channel
from utils.logging import LogCollector
from datetime import datetime, timedelta

class WarCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.war_reminder.start()

    def cog_unload(self):
        self.war_reminder.cancel()

    @tasks.loop(hours=12)
    async def war_reminder(self):
        for guild in self.bot.guilds:
            log_collector = LogCollector(guild, "Kriegs-Erinnerung")
            log_collector.add_event("Erinnerung gestartet")

            admin_role = get_admin_role(guild)
            log_channel = get_log_channel(guild)
            if not admin_role or not log_channel:
                log_collector.add_event("Fehler: Admin-Rolle oder Log-Kanal nicht gefunden", "ERROR")
                await log_collector.post_log(status="Fehler", color=discord.Color.red())
                continue

            reminder_embed = discord.Embed(
                title="⏰ Kriegs-Erinnerung",
                description=f"{admin_role.mention} ⚠️ Erinnere alle Mitglieder, ihre Angriffe im aktuellen Krieg auszuführen!\nBitte überprüfe die Teilnahme.",
                color=discord.Color.orange()
            )
            reminder_embed.set_footer(text=f"Operation-Oluja | {datetime.utcnow().strftime('%d.%m.%Y %H:%M UTC')}")
            await log_channel.send(embed=reminder_embed)
            log_collector.add_event("Erinnerung gesendet")
            await log_collector.post_log()

    @war_reminder.before_loop
    async def before_reminder(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="warstatus", description="Zeige den aktuellen Kriegsstatus an")
    async def warstatus(self, interaction: discord.Interaction):
        guild = interaction.guild
        log_collector = LogCollector(guild, "Kriegsstatus-Anfrage", interaction.user, interaction.channel)
        log_collector.add_event("Status angefordert")

        await interaction.response.defer(ephemeral=True)
        # Simuliert Kriegsstatus
        war_status = {
            "Status": "Aktiv",
            "Teilnahme": "80%",
            "Nächster Krieg": "Morgen, 18:00 Uhr"
        }
        status_embed = discord.Embed(
            title="🏹 Kriegsstatus",
            description=(
                f"**Status:** {war_status['Status']}\n"
                f"**Teilnahme:** {war_status['Teilnahme']}\n"
                f"**Nächster Krieg:** {war_status['Nächster Krieg']}"
            ),
            color=discord.Color.blue()
        )
        status_embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1128712101349038160/1226579502036989992/oluja_logo.png")
        status_embed.set_footer(text="Operation-Oluja | Kriegs-Info", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=status_embed)
        log_collector.add_event("Status gesendet")
        await log_collector.post_log()

async def setup(bot):
    await bot.add_cog(WarCog(bot))