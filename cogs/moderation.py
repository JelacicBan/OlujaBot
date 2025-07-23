import discord
from discord.ext import commands
from discord import app_commands
from utils.helpers import get_admin_role, get_log_channel
from utils.logging import LogCollector
from utils.database import db  # Import der Datenbank
from datetime import datetime
import asyncio

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _is_admin(self, user: discord.Member):
        admin_role = get_admin_role(user.guild)
        return admin_role and admin_role in user.roles

    @app_commands.command(name="mute", description="Stumm schalten eines Mitglieds")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "Kein Grund angegeben"):
        log_collector = LogCollector(interaction.guild, "Mute-Aktion", interaction.user, interaction.channel)
        log_collector.add_event("Mute gestartet")

        if not self._is_admin(interaction.user):
            await interaction.response.send_message(embed=discord.Embed(
                title="❌ Keine Berechtigung",
                description="Nur Teammitglieder dürfen das!",
                color=discord.Color.red()
            ), ephemeral=True)
            log_collector.add_event("Unbefugter Zugriff", "WARNING")
            await log_collector.post_log(status="Abgebrochen", color=discord.Color.red())
            return

        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
        if not mute_role:
            await interaction.guild.create_role(name="Muted", permissions=discord.Permissions(send_messages=False))
            mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
            for channel in interaction.guild.text_channels:
                await channel.set_permissions(mute_role, send_messages=False)
            log_collector.add_event("Mute-Rolle erstellt")

        await member.add_roles(mute_role, reason=f"Mute by {interaction.user.name}: {reason}")
        await interaction.response.send_message(embed=discord.Embed(
            title="🔇 Mitglied stumm geschaltet",
            description=f"{member.mention} wurde für {duration} Minuten stumm geschaltet. Grund: {reason}",
            color=discord.Color.orange()
        ), ephemeral=True)
        log_collector.add_event(f"{member.name} stumm geschaltet für {duration} Minuten. Grund: {reason}")

        db.add_moderation_log(
            user_id=member.id,
            user_name=member.name,
            action_type="Mute",
            reason=reason,
            duration=duration,
            handled_by=interaction.user.name
        )

        await asyncio.sleep(duration * 60)
        await member.remove_roles(mute_role, reason=f"Mute expired by {interaction.user.name}")
        log_collector.add_event("Mute aufgehoben")

        db.add_moderation_log(
            user_id=member.id,
            user_name=member.name,
            action_type="Unmute (Auto)",
            reason="Mute abgelaufen",
            duration=None,
            handled_by=interaction.user.name
        )

        await log_collector.post_log()

    @app_commands.command(name="unmute", description="Stummschaltung eines Mitglieds aufheben")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        log_collector = LogCollector(interaction.guild, "Unmute-Aktion", interaction.user, interaction.channel)
        log_collector.add_event("Unmute gestartet")

        if not self._is_admin(interaction.user):
            await interaction.response.send_message(embed=discord.Embed(
                title="❌ Keine Berechtigung",
                description="Nur Teammitglieder dürfen das!",
                color=discord.Color.red()
            ), ephemeral=True)
            log_collector.add_event("Unbefugter Zugriff", "WARNING")
            await log_collector.post_log(status="Abgebrochen", color=discord.Color.red())
            return

        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
        if mute_role and mute_role in member.roles:
            await member.remove_roles(mute_role, reason=f"Unmute by {interaction.user.name}")
            await interaction.response.send_message(embed=discord.Embed(
                title="🔊 Stummschaltung aufgehoben",
                description=f"{member.mention} wurde entstummt.",
                color=discord.Color.green()
            ), ephemeral=True)
            log_collector.add_event(f"{member.name} entstummt")

            db.add_moderation_log(
                user_id=member.id,
                user_name=member.name,
                action_type="Unmute",
                reason="Manuell entstummt",
                duration=None,
                handled_by=interaction.user.name
            )
        else:
            await interaction.response.send_message(embed=discord.Embed(
                title="⚠️ Fehler",
                description=f"{member.mention} ist nicht stumm geschaltet.",
                color=discord.Color.orange()
            ), ephemeral=True)
            log_collector.add_event("Fehler: Mitglied nicht stumm", "WARNING")
        await log_collector.post_log()

    @app_commands.command(name="warn", description="Warnen eines Mitglieds")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Kein Grund angegeben"):
        log_collector = LogCollector(interaction.guild, "Warn-Aktion", interaction.user, interaction.channel)
        log_collector.add_event("Warnung gestartet")

        if not self._is_admin(interaction.user):
            await interaction.response.send_message(embed=discord.Embed(
                title="❌ Keine Berechtigung",
                description="Nur Teammitglieder dürfen das!",
                color=discord.Color.red()
            ), ephemeral=True)
            log_collector.add_event("Unbefugter Zugriff", "WARNING")
            await log_collector.post_log(status="Abgebrochen", color=discord.Color.red())
            return

        warn_embed = discord.Embed(
            title="⚠️ Warnung",
            description=f"{member.mention}, du wurdest gewarnt!\n**Grund:** {reason}",
            color=discord.Color.orange()
        )
        warn_embed.set_footer(text="Operation-Oluja")
        await member.send(embed=warn_embed)
        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Warnung gesendet",
            description=f"{member.mention} wurde gewarnt. Grund: {reason}",
            color=discord.Color.green()
        ), ephemeral=True)
        log_collector.add_event(f"{member.name} gewarnt. Grund: {reason}")

        db.add_moderation_log(
            user_id=member.id,
            user_name=member.name,
            action_type="Warn",
            reason=reason,
            duration=None,
            handled_by=interaction.user.name
        )

        await log_collector.post_log()

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))