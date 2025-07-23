import discord
from discord.ext import commands, tasks
from discord import app_commands
import config
from utils.helpers import get_admin_role, get_log_channel
from utils.logging import logger, LogCollector
from utils.database import db
from datetime import datetime, timedelta
import asyncio
import random
import csv
import io

TEAM_NOTIFY_COOLDOWNS = {}  # channel_id: datetime

FUNFACTS = [
    "Immer alle Angriffe nutzen!!!",
    "Ajmo brat",
    "'Oluja' ist 'Sturm' auf Kroatisch."
]

def animated_progress_bar(percent):
    blocks = int(percent // 10)
    return "█" * blocks + "░" * (10 - blocks)

def validate_player_tag(tag: str) -> bool:
    return tag.startswith("#") and 8 <= len(tag[1:]) <= 10 and tag[1:].isalnum()

class ApplicationDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Mitglieder-Bewerbung", description="Bewirb dich als Mitglied", emoji="👥"),
            discord.SelectOption(label="Staff-Bewerbung", description="Bewirb dich für unser Team", emoji="🛡️"),
        ]
        super().__init__(
            placeholder="🎯 Wähle deine Bewerbungsart...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="bewerbung_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user
        log_collector = LogCollector(guild, "Bewerbungsprozess", user, interaction.channel)
        log_collector.add_event("Bewerbung gestartet")

        existing_channel = next((ch for ch in guild.text_channels if ch.name.startswith((f"bewerbung-{user.name[:20]}", f"angenommen-{user.name[:20]}"))), None)
        if existing_channel:
            await interaction.followup.send(embed=discord.Embed(
                title="⚠️ Offene Bewerbung",
                description="Du hast bereits eine offene Bewerbung. Bitte warte, bis sie bearbeitet wurde.",
                color=discord.Color.red()
            ), ephemeral=True)
            log_collector.add_event("Abbruch: Offene Bewerbung erkannt", "WARNING")
            await log_collector.post_log(status="Abgebrochen", color=discord.Color.red())
            return

        admin_role = get_admin_role(guild)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True),
            admin_role: discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True) if admin_role else None
        }
        overwrites = {k: v for k, v in overwrites.items() if v is not None}

        channel_name = f"bewerbung-{user.name[:20]}"
        ticket_channel = await guild.create_text_channel(
            channel_name,
            overwrites=overwrites,
            topic=f"Bewerbung von {user.name} | ID: {user.id}"
        )
        log_collector.channel = ticket_channel
        log_collector.add_event("Bewerbungskanal erstellt")

        welcome_embed = discord.Embed(
            title=f"🎉 Willkommen, {user.name}!",
            description=(
                f"**{user.mention}, danke für deine Bewerbung bei Operation-Oluja!**\n\n"
                "Bitte beantworte die folgenden Fragen, um deine Bewerbung abzuschließen.\n"
                "📝 Du hast 5 Minuten pro Frage, bevor der Kanal geschlossen wird."
            ),
            color=discord.Color.gold()
        )
        welcome_embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1128712101349038160/1226579502036989992/oluja_logo.png")
        welcome_embed.set_footer(text=f"Clan: {config.CLAN_TAG} | Operation-Oluja", icon_url=user.display_avatar.url)

        await ticket_channel.send(content=admin_role.mention if admin_role else "", embed=welcome_embed, view=FAQView())
        log_collector.add_event("Willkommensnachricht gesendet")

        questions = config.APPLICATION_QUESTIONS[self.values[0]]
        answers = []
        def check(m): return m.author == user and m.channel == ticket_channel

        try:
            for idx, question in enumerate(questions):
                percent = int((idx+1)/len(questions)*100)
                q_embed = discord.Embed(
                    title=f"Frage {idx+1}/{len(questions)}",
                    description=(
                        f"{question}\n\n"
                        f"**Fortschritt:** [{animated_progress_bar(percent)}] {percent}%\n"
                        f"⏰ Du hast 5 Minuten, um zu antworten."
                    ),
                    color=discord.Color.blue()
                )
                q_embed.set_footer(text="Antworte direkt hier im Kanal.")
                q_msg = await ticket_channel.send(embed=q_embed)

                if idx == 0 and "Spieler-Tag" in question:
                    max_attempts = 2
                    for attempt in range(max_attempts):
                        msg = await interaction.client.wait_for('message', check=check, timeout=300)
                        if validate_player_tag(msg.content):
                            answers.append(msg.content)
                            await q_msg.delete()
                            await msg.delete()
                            log_collector.add_event(f"Spieler-Tag akzeptiert: {msg.content}")
                            break
                        else:
                            if attempt == max_attempts - 1:
                                await self._handle_invalid_tag(ticket_channel, user, log_collector, max_attempts)
                                return
                            await self._handle_invalid_tag_attempt(ticket_channel, user, log_collector, attempt, max_attempts)
                            await msg.delete()
                            continue
                else:
                    msg = await interaction.client.wait_for('message', check=check, timeout=300)
                    answers.append(msg.content)
                    await q_msg.delete()
                    await msg.delete()
                    log_collector.add_event(f"Antwort auf Frage {idx+1}: {msg.content}")
        except asyncio.TimeoutError:
            await self._handle_timeout(ticket_channel, user, log_collector)
            return
        except Exception as e:
            await self._handle_error(ticket_channel, user, log_collector, str(e))
            return

        summary_embed = discord.Embed(
            title="📄 Deine Bewerbungszusammenfassung",
            description=(
                f"**{user.mention}, hier ist deine Bewerbung:**\n\n"
                f"**Bewerbungsart:** {self.values[0]}\n"
                "Das Team wird deine Bewerbung bald prüfen. Danke für deine Geduld! 🙏"
            ),
            color=discord.Color.green()
        )
        summary_embed.set_thumbnail(url=user.display_avatar.url)
        for i, q in enumerate(questions):
            summary_embed.add_field(name=f"Frage {i+1}", value=f"**Antwort:** {answers[i]}", inline=False)
        summary_embed.set_footer(text="Operation-Oluja | Danke für deine Bewerbung!", icon_url="https://cdn.discordapp.com/attachments/1128712101349038160/1226579502036989992/oluja_logo.png")

        view = AcceptDenyView(ticket_channel, user, summary_embed, self.values[0], answers)
        await ticket_channel.send(embed=summary_embed, view=view)
        log_collector.add_event("Bewerbungszusammenfassung gesendet")

        await interaction.followup.send(embed=discord.Embed(
            title="✅ Bewerbung erstellt",
            description=f"Deine Bewerbung wurde in {ticket_channel.mention} erstellt.",
            color=discord.Color.green()
        ), ephemeral=True)
        log_collector.add_event("Bewerbung erfolgreich erstellt")
        await log_collector.post_log(status="Erstellt")

    async def _handle_invalid_tag(self, channel, user, log_collector, max_attempts):
        error_embed = discord.Embed(
            title="⚠️ Ungültiger Spieler-Tag",
            description=(
                "Du hast keine weiteren Versuche.\n"
                "Ein korrekter Spieler-Tag beginnt mit #, gefolgt von 8-10 alphanumerischen Zeichen (z.B. #LJC8V0GCJ).\n"
                "Der Kanal wird geschlossen."
            ),
            color=discord.Color.red()
        )
        await channel.send(embed=error_embed)
        log_collector.add_event(f"Ungültiger Spieler-Tag nach {max_attempts} Versuchen", "WARNING")
        await self._send_dm_and_close(user, channel, log_collector, "Ungültiger Spieler-Tag")

    async def _handle_invalid_tag_attempt(self, channel, user, log_collector, attempt, max_attempts):
        error_embed = discord.Embed(
            title="⚠️ Ungültiger Spieler-Tag",
            description=(
                f"Bitte gib einen korrekten Tag im Format `#LJC8V0GCJ` ein.\n"
                f"**Versuch {attempt + 2}/{max_attempts}**\n"
                "Ein korrekter Spieler-Tag beginnt mit #, gefolgt von 8-10 alphanumerischen Zeichen."
            ),
            color=discord.Color.orange()
        )
        await channel.send(embed=error_embed)
        log_collector.add_event(f"Ungültiger Spieler-Tag, Versuch {attempt + 2}/{max_attempts}", "WARNING")

    async def _handle_timeout(self, channel, user, log_collector):
        timeout_embed = discord.Embed(
            title="⏰ Zeit abgelaufen",
            description="Du hast zu lange gebraucht, um die Fragen zu beantworten. Bitte starte die Bewerbung erneut.",
            color=discord.Color.red()
        )
        await channel.send(embed=timeout_embed)
        log_collector.add_event("Timeout bei der Antwort", "WARNING")
        await self._send_dm_and_close(user, channel, log_collector, "Timeout")

    async def _handle_error(self, channel, user, log_collector, error):
        error_embed = discord.Embed(
            title="❌ Ein Fehler ist aufgetreten",
            description=f"Fehler: {error}\nBitte wende dich an das Team.",
            color=discord.Color.red()
        )
        await channel.send(embed=error_embed)
        log_collector.add_event(f"Fehler: {error}", "ERROR")
        await self._send_dm_and_close(user, channel, log_collector, "Fehler")

    async def _send_dm_and_close(self, user, channel, log_collector, reason):
        dm_embed = discord.Embed(
            title="❌ Dein Ticket wurde geschlossen",
            description=(
                f"Deine Bewerbung wurde abgebrochen, weil {reason.lower()} aufgetreten ist.\n"
                "Bitte starte die Bewerbung erneut oder kontaktiere das Team für Unterstützung."
            ),
            color=discord.Color.red()
        )
        dm_embed.set_footer(text="Operation-Oluja")
        try:
            await user.send(embed=dm_embed)
            log_collector.add_event(f"DM gesendet: {reason}")
        except discord.Forbidden:
            log_collector.add_event("DM konnte nicht gesendet werden", "WARNING")
        await channel.delete()
        await log_collector.post_log(status="Abgebrochen", color=discord.Color.red())

class ApplicationDropdownView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ApplicationDropdown())

class FAQView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="❓ FAQ anzeigen", style=discord.ButtonStyle.secondary, custom_id="faq_button")
    async def show_faq(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❓ Häufige Fragen (FAQ)",
            description=config.FAQ_TEXT,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Operation-Oluja")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log_collector = LogCollector(interaction.guild, "FAQ-Anzeige", interaction.user, interaction.channel)
        log_collector.add_event("FAQ angezeigt")
        await log_collector.post_log()

class AcceptDenyView(discord.ui.View):
    def __init__(self, channel, applicant, embed, apply_type, answers):
        super().__init__(timeout=1800)
        self.channel = channel
        self.applicant = applicant
        self.embed = embed
        self.apply_type = apply_type
        self.answers = answers
        self.add_item(NotifyTeamButton())

    def _is_admin(self, user: discord.Member):
        admin_role = get_admin_role(user.guild)
        return admin_role and admin_role in user.roles

    @discord.ui.button(label="✅ Annehmen", style=discord.ButtonStyle.green, custom_id="accept_button")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        log_collector = LogCollector(interaction.guild, "Bewerbungsbearbeitung", interaction.user, self.channel)
        log_collector.add_event("Bewerbungsbearbeitung gestartet")

        if not self._is_admin(interaction.user):
            await interaction.response.send_message(embed=discord.Embed(
                title="❌ Keine Berechtigung",
                description="Nur Teammitglieder dürfen das!",
                color=discord.Color.red()
            ), ephemeral=True)
            log_collector.add_event("Unbefugter Zugriff", "WARNING")
            await log_collector.post_log(status="Abgebrochen", color=discord.Color.red())
            return

        member_role = interaction.guild.get_role(config.MEMBER_ROLE_ID)
        if not member_role:
            await interaction.response.send_message(embed=discord.Embed(
                title="⚠️ Fehler",
                description="Member-Rolle nicht gefunden.",
                color=discord.Color.orange()
            ), ephemeral=True)
            log_collector.add_event("Fehler: Member-Rolle nicht gefunden", "ERROR")
            await log_collector.post_log(status="Abgebrochen", color=discord.Color.red())
            return

        await self.applicant.add_roles(member_role, reason="Bewerbung angenommen")
        log_collector.add_event("Mitgliederrolle zugewiesen")

        clan_link = f"https://link.clashofclans.com/de?action=OpenClanProfile&tag={config.CLAN_TAG.replace('#','')}"
        clan_logo = "https://cdn.discordapp.com/attachments/1128712101349038160/1226579502036989992/oluja_logo.png"
        funfact = random.choice(FUNFACTS)
        countdown = 5

        clan_embed = discord.Embed(
            title="☢️ Willkommen bei Operation-Oluja! ☢️",
            description=(
                f"**{self.applicant.mention}, du bist offiziell angenommen!**\n\n"
                f"{'⏳ **Clanbeitritt in {i}...**\n' * countdown}\n"
                f"\n**Fun Fact:** {funfact}\n\n"
                "Klicke auf den Button, um direkt unserem Clan beizutreten! 🎉"
            ),
            color=discord.Color.gold()
        )
        clan_embed.set_thumbnail(url=clan_logo)
        clan_embed.set_image(url="https://media.giphy.com/media/3o6Zt481isNVuQI1l6/giphy.gif")
        clan_embed.add_field(name="Clan-Link", value=f"[🏰 Direkt beitreten]({clan_link})", inline=False)
        clan_embed.set_footer(text="Wir freuen uns auf dich! 🎈🎉", icon_url=clan_logo)

        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="Clan beitreten", url=clan_link, style=discord.ButtonStyle.link, emoji="🏰"))

        try:
            await self.applicant.send(embed=clan_embed, view=view)
            log_collector.add_event("Clan-Link-DM gesendet")
        except discord.Forbidden:
            log_collector.add_event("Clan-Link-DM konnte nicht gesendet werden", "WARNING")

        await self.channel.send(embed=clan_embed, view=view)

        success_embed = discord.Embed(
            title="🎉 Bewerbung angenommen!",
            description=f"Willkommen im Clan, {self.applicant.mention}!",
            color=discord.Color.green()
        )
        success_embed.set_thumbnail(url=self.applicant.display_avatar.url)
        await self.channel.send(embed=success_embed, view=CloseTicketView())
        await self.channel.send(view=FeedbackButtonView())

        db.add_application(
            applicant_name=self.applicant.name,
            applicant_id=self.applicant.id,
            apply_type=self.apply_type,
            spieler_tag=self.answers[0],
            strategien=self.answers[1] if len(self.answers) > 1 else "",
            th_level=self.answers[2] if len(self.answers) > 2 else "",
            status="Angenommen",
            reason="",
            handled_by=interaction.user.name
        )

        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Erfolg",
            description="Bewerbung angenommen. Der Bewerber hat einen Clan-Link erhalten.",
            color=discord.Color.green()
        ), ephemeral=True)
        await self.channel.edit(name=f"angenommen-{self.applicant.name[:20]}")

        end_time = datetime.utcnow()
        duration = (end_time - log_collector.start_time).seconds
        embed = discord.Embed(
            title="🎉 Bewerbungsprozess abgeschlossen",
            description=(
                f"**Bewerber:** {self.applicant.mention} ({self.applicant.name})\n"
                f"**Moderatoren:** {interaction.user.mention} ({interaction.user.name})\n"
                f"**Status:** Angenommen :white_check_mark:"
            ),
            color=discord.Color.green(),
            timestamp=end_time
        )
        embed.add_field(name="Dauer", value=f"{duration} Sekunden", inline=False)
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1128712101349038160/1226579502036989992/oluja_logo.png")
        embed.set_footer(text="Operation-Oluja | Abschluss", icon_url=self.applicant.display_avatar.url)
        await self.channel.send(embed=embed)

        log_collector.add_event(f"Bewerbung an Accepted von {interaction.user.name}")
        await log_collector.post_log(status="Angenommen")

    @discord.ui.button(label="❌ Ablehnen", style=discord.ButtonStyle.red, custom_id="deny_button")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_admin(interaction.user):
            await interaction.response.send_message(embed=discord.Embed(
                title="❌ Keine Berechtigung",
                description="Nur Teammitglieder dürfen das!",
                color=discord.Color.red()
            ), ephemeral=True)
            log_collector = LogCollector(interaction.guild, "Bewerbungsbearbeitung", interaction.user, self.channel)
            log_collector.add_event("Unbefugter Zugriff", "WARNING")
            await log_collector.post_log(status="Abgebrochen", color=discord.Color.red())
            return
        await interaction.response.send_modal(DenyReasonModal(self))

    async def process_deny(self, interaction: discord.Interaction, reason: str):
        log_collector = LogCollector(interaction.guild, "Bewerbungsbearbeitung", interaction.user, self.channel)
        log_collector.add_event("Bewerbungsbearbeitung gestartet")

        reason = reason.strip() or "Kein Grund angegeben."
        deny_embed = discord.Embed(
            title="❌ Bewerbung abgelehnt",
            description=f"{self.applicant.mention}, leider konnten wir dich nicht aufnehmen.\n**Grund:** {reason}",
            color=discord.Color.red()
        )
        deny_embed.set_thumbnail(url=self.applicant.display_avatar.url)
        await self.channel.send(embed=deny_embed)
        await asyncio.sleep(2)

        dm_embed = discord.Embed(
            title="❌ Deine Bewerbung wurde abgelehnt",
            description="Leider wurde deine Bewerbung abgelehnt. Du kannst dich in 2 Wochen erneut bewerben.",
            color=discord.Color.red()
        )
        dm_embed.add_field(name="Grund", value=reason, inline=False)
        summary = "\n".join([f"**{field.name}:** {field.value}" for field in self.embed.fields])
        dm_embed.add_field(name="Bewerbungszusammenfassung", value=summary, inline=False)
        dm_embed.set_footer(text="Operation-Oluja")
        try:
            await self.applicant.send(embed=dm_embed)
            log_collector.add_event("Ablehnungs-DM gesendet")
        except discord.Forbidden:
            log_collector.add_event("Ablehnungs-DM konnte nicht gesendet werden", "WARNING")

        db.add_application(
            applicant_name=self.applicant.name,
            applicant_id=self.applicant.id,
            apply_type=self.apply_type,
            spieler_tag=self.answers[0],
            strategien=self.answers[1] if len(self.answers) > 1 else "",
            th_level=self.answers[2] if len(self.answers) > 2 else "",
            status="Abgelehnt",
            reason=reason,
            handled_by=interaction.user.name
        )

        await interaction.followup.send(embed=discord.Embed(
            title="✅ Erfolg",
            description="Bewerbung abgelehnt und DM gesendet." if not log_collector.has_errors else "Bewerbung abgelehnt, aber DM konnte nicht zugestellt werden.",
            color=discord.Color.green() if not log_collector.has_errors else discord.Color.orange()
        ), ephemeral=True)

        end_time = datetime.utcnow()
        duration = (end_time - log_collector.start_time).seconds
        embed = discord.Embed(
            title="❌ Bewerbungsprozess abgeschlossen",
            description=(
                f"**Bewerber:** {self.applicant.mention} ({self.applicant.name})\n"
                f"**Moderatoren:** {interaction.user.mention} ({interaction.user.name})\n"
                f"**Status:** Abgelehnt :x:"
            ),
            color=discord.Color.red(),
            timestamp=end_time
        )
        embed.add_field(name="Dauer", value=f"{duration} Sekunden", inline=False)
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1128712101349038160/1226579502036989992/oluja_logo.png")
        embed.set_footer(text="Operation-Oluja | Abschluss", icon_url=self.applicant.display_avatar.url)
        await self.channel.send(embed=embed)

        await self.channel.delete()
        log_collector.add_event(f"Bewerbung abgelehnt von {interaction.user.name}. Grund: {reason}")
        await log_collector.post_log(status="Abgelehnt", color=discord.Color.red())

class DenyReasonModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="Bewerbung ablehnen")
        self.parent_view = parent_view
        self.reason = discord.ui.TextInput(
            label="Grund für die Ablehnung (optional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=300,
            custom_id="deny_reason"
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.parent_view.process_deny(interaction, self.reason.value)

class NotifyTeamButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Team benachrichtigen", style=discord.ButtonStyle.primary, custom_id="notify_team", emoji="📢")

    async def callback(self, interaction: discord.Interaction):
        log_collector = LogCollector(interaction.guild, "Team-Benachrichtigung", interaction.user, interaction.channel)
        log_collector.add_event("Benachrichtigung gestartet")

        now = datetime.utcnow()
        channel_id = interaction.channel.id
        cooldown = TEAM_NOTIFY_COOLDOWNS.get(channel_id)
        if cooldown and now < cooldown:
            minutes = int((cooldown - now).total_seconds() // 60) + 1
            await interaction.response.send_message(embed=discord.Embed(
                title="🚫 Cooldown",
                description=f"Das Team kann erst in {minutes} Minute(n) erneut benachrichtigt werden.",
                color=discord.Color.red()
            ), ephemeral=True)
            log_collector.add_event(f"Cooldown: {minutes} Minuten verbleibend", "WARNING")
            await log_collector.post_log(status="Abgebrochen", color=discord.Color.red())
            return

        admin_role = get_admin_role(interaction.guild)
        if not admin_role:
            await interaction.response.send_message(embed=discord.Embed(
                title="⚠️ Fehler",
                description="Admin-Rolle nicht gefunden.",
                color=discord.Color.orange()
            ), ephemeral=True)
            log_collector.add_event("Fehler: Admin-Rolle nicht gefunden", "ERROR")
            await log_collector.post_log(status="Abgebrochen", color=discord.Color.red())
            return

        TEAM_NOTIFY_COOLDOWNS[channel_id] = now + timedelta(minutes=15)
        await interaction.response.send_message(embed=discord.Embed(
            title="📢 Team benachrichtigt",
            description=f"{admin_role.mention} - Bitte beachtet diese Bewerbung!",
            color=discord.Color.blue()
        ))
        log_collector.add_event("Team benachrichtigt")
        await log_collector.post_log()

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Ticket schließen", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        log_collector = LogCollector(interaction.guild, "Ticket-Schließung", interaction.user, interaction.channel)
        log_collector.add_event("Ticket-Schließung gestartet")

        admin_role = get_admin_role(interaction.guild)
        if not admin_role or admin_role not in interaction.user.roles:
            await interaction.response.send_message(embed=discord.Embed(
                title="❌ Keine Berechtigung",
                description="Du hast keine Berechtigung.",
                color=discord.Color.red()
            ), ephemeral=True)
            log_collector.add_event("Unbefugter Zugriff", "WARNING")
            await log_collector.post_log(status="Abgebrochen", color=discord.Color.red())
            return

        await interaction.response.send_message(embed=discord.Embed(
            title="🔒 Ticket wird geschlossen",
            description="Der Kanal wird in Kürze gelöscht...",
            color=discord.Color.blue()
        ), ephemeral=True)
        log_collector.add_event(f"Ticket für {interaction.channel.topic.split('|')[0].strip()} geschlossen")
        await asyncio.sleep(2)
        await interaction.channel.delete()
        await log_collector.post_log()

class FeedbackButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Feedback geben", style=discord.ButtonStyle.primary, custom_id="feedback_button")
    async def feedback_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FeedbackModal())

class FeedbackModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Feedback zur Bewerbung")
        self.feedback = discord.ui.TextInput(
            label="Dein Feedback (optional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500,
            custom_id="feedback_text"
        )
        self.add_item(self.feedback)

    async def on_submit(self, interaction: discord.Interaction):
        log_collector = LogCollector(interaction.guild, "Feedback", interaction.user, interaction.channel)
        log_collector.add_event("Feedback eingereicht")

        log_channel = get_log_channel(interaction.guild)
        if log_channel:
            embed = discord.Embed(
                title="📣 Bewerber-Feedback",
                description=f"Feedback von {interaction.user.mention}:\n{self.feedback.value or '*Kein Feedback gegeben*'}",
                color=discord.Color.green()
            )
            embed.set_footer(text="Operation-Oluja")
            await log_channel.send(embed=embed)

        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Danke!",
            description="Vielen Dank für dein Feedback! 🙏",
            color=discord.Color.green()
        ), ephemeral=True)
        log_collector.add_event(f"Feedback: {self.feedback.value or 'Kein Text'}")
        await log_collector.post_log()

class ApplicationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_open_applications.start()

    def cog_unload(self):
        self.check_open_applications.cancel()

    @app_commands.command(name="bewerberexport", description="Exportiere angenommene Bewerber als CSV")
    @app_commands.checks.has_permissions(administrator=True)
    async def bewerberexport(self, interaction: discord.Interaction):
        log_collector = LogCollector(interaction.guild, "Bewerber-Export", interaction.user, interaction.channel)
        log_collector.add_event("Export angefordert")

        applications = db.get_applications(status="Angenommen")
        if not applications:
            await interaction.response.send_message(embed=discord.Embed(
                title="⚠️ Keine Daten",
                description="Keine angenommenen Bewerbungen gefunden.",
                color=discord.Color.orange()
            ), ephemeral=True)
            log_collector.add_event("Keine angenommenen Bewerbungen gefunden")
            await log_collector.post_log(status="Abgebrochen", color=discord.Color.orange())
            return

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Applicant Name", "Applicant ID", "Apply Type", "Spieler Tag", "Strategien", "TH Level", "Status", "Handled By"])
        for app in applications:
            writer.writerow([
                app.applicant_name,
                app.applicant_id,
                app.apply_type,
                app.spieler_tag,
                app.strategien,
                app.th_level,
                app.status,
                app.handled_by
            ])

        await interaction.response.send_message(
            embed=discord.Embed(
                title="✅ Export erfolgreich",
                description="Angenommene Bewerbungen wurden als CSV exportiert.",
                color=discord.Color.green()
            ),
            file=discord.File(fp=io.StringIO(output.getvalue()), filename="bewerbungen.csv"),
            ephemeral=True
        )
        log_collector.add_event("Export erfolgreich")
        await log_collector.post_log(status="Erfolgreich")

    @tasks.loop(hours=6)
    async def check_open_applications(self):
        for guild in self.bot.guilds:
            log_collector = LogCollector(guild, "Bewerbungserinnerung")
            log_collector.add_event("Erinnerung gestartet")

            admin_role = get_admin_role(guild)
            log_channel = get_log_channel(guild)
            if not admin_role or not log_channel:
                log_collector.add_event("Fehler: Admin-Rolle oder Log-Kanal nicht gefunden", "ERROR")
                await log_collector.post_log(status="Fehler", color=discord.Color.red())
                continue

            for channel in guild.text_channels:
                if channel.name.startswith("bewerbung-"):
                    created_at = channel.created_at.replace(tzinfo=None)
                    if (datetime.utcnow() - created_at).total_seconds() > config.REMINDER_HOURS * 3600:
                        await log_channel.send(embed=discord.Embed(
                            title="⏰ Offene Bewerbung",
                            description=f"{admin_role.mention} ⚠️ Die Bewerbung in {channel.mention} ist seit über {config.REMINDER_HOURS} Stunden offen!",
                            color=discord.Color.orange()
                        ))
                        log_collector.add_event(f"Erinnerung für {channel.name} gesendet")
            await log_collector.post_log()

    @check_open_applications.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    bot.add_view(ApplicationDropdownView())
    bot.add_view(FAQView())
    await bot.add_cog(ApplicationCog(bot))