import discord
from discord.ext import commands
from discord import app_commands
from utils.helpers import get_log_channel
from utils.logging import LogCollector
from datetime import datetime

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="clanstats", description="Zeige Statistiken des Clans an")
    async def clanstats(self, interaction: discord.Interaction):
        guild = interaction.guild
        log_collector = LogCollector(guild, "Clan-Statistiken", interaction.user, interaction.channel)
        log_collector.add_event("Statistiken angefordert")

        await interaction.response.defer(ephemeral=True)
        stats = {
            "Mitglieder": len(guild.members),
            "Siegquote": "75%",
            "Aktive Kriege": 2
        }
        stats_embed = discord.Embed(
            title="📊 Clan-Statistiken",
            description=(
                f"**Mitglieder:** {stats['Mitglieder']}\n"
                f"**Siegquote:** {stats['Siegquote']}\n"
                f"**Aktive Kriege:** {stats['Aktive Kriege']}"
            ),
            color=discord.Color.purple()
        )
        stats_embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1128712101349038160/1226579502036989992/oluja_logo.png")
        stats_embed.set_footer(text="Operation-Oluja | Statistik-Info", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=stats_embed)
        log_collector.add_event("Statistiken gesendet")
        await log_collector.post_log()

    @app_commands.command(name="memberstats", description="Zeige Statistiken eines Mitglieds an")
    async def memberstats(self, interaction: discord.Interaction, member: discord.Member):
        guild = interaction.guild
        log_collector = LogCollector(guild, "Mitglieds-Statistiken", interaction.user, interaction.channel)
        log_collector.add_event("Statistiken angefordert")

        await interaction.response.defer(ephemeral=True)
        stats = {
            "Beitrittsdatum": member.joined_at.strftime("%d.%m.%Y"),
            "Nachrichten": "150",
            "Kriegs-Teilnahme": "90%"
        }
        stats_embed = discord.Embed(
            title=f"📊 Statistiken von {member.name}",
            description=(
                f"**Beitrittsdatum:** {stats['Beitrittsdatum']}\n"
                f"**Nachrichten:** {stats['Nachrichten']}\n"
                f"**Kriegs-Teilnahme:** {stats['Kriegs-Teilnahme']}"
            ),
            color=discord.Color.purple()
        )
        stats_embed.set_thumbnail(url=member.display_avatar.url)
        stats_embed.set_footer(text="Operation-Oluja | Mitglieds-Info", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=stats_embed)
        log_collector.add_event("Statistiken gesendet")
        await log_collector.post_log()

async def setup(bot):
    await bot.add_cog(StatsCog(bot))