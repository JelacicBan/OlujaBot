import discord
from discord.ext import commands, tasks
from discord import app_commands
from utils.logging import LogCollector
from utils.database import db  # MySQL database integration
from datetime import datetime
import asyncio
import logging
import mysql.connector

class CWLCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_polls = {}  # Speichert aktive Umfragen: {message_id: {'channel': channel, 'duration': duration, 'responses': {}, 'start_time': datetime, 'poll_id': message_id}}
        self.had_active_polls = False  # Zustandsvariable zur Verfolgung vorheriger Aktivität
        logging.info("CWLCog initialisiert")
        self.save_poll_progress.start()  # Starte die Zwischenspeicherung

    def cog_unload(self):
        """Beende die Zwischenspeicherung, wenn der Cog entladen wird."""
        logging.info("CWLCog wird entladen")
        self.save_poll_progress.cancel()

    @tasks.loop(minutes=2)  # 2-Minuten-Intervall
    async def save_poll_progress(self):
        """Speichere den Fortschritt aller aktiven Umfragen alle 2 Minuten."""
        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        logging.info(f"save_poll_progress gestartet um {current_time}")
        has_active_polls = bool(self.active_polls)
        
        if not has_active_polls and self.had_active_polls:
            logging.warning("Keine aktiven Umfragen zum Speichern (Zustandsänderung)")
        elif has_active_polls and not self.had_active_polls:
            logging.info("Aktive Umfragen erkannt")

        if has_active_polls:
            logging.info(f"Aktive Umfragen: {list(self.active_polls.keys())}")
            for message_id, poll_data in list(self.active_polls.items()):
                responses = poll_data.get('responses', {})
                yes_count = sum(1 for r in responses.values() if r == "✅")
                no_count = sum(1 for r in responses.values() if r == "❌")
                logging.info(f"Verarbeitung Umfrage {message_id}: Ja={yes_count}, Nein={no_count}")
                try:
                    db.add_cwl_poll(
                        poll_id=poll_data['poll_id'],
                        channel_id=poll_data['channel'].id,
                        channel_name=poll_data['channel'].name,
                        duration=poll_data['duration'],
                        yes_count=yes_count,
                        no_count=no_count
                    )
                    logging.info(f"Zwischenspeicherung für Umfrage {message_id} erfolgreich: Ja={yes_count}, Nein={no_count}")
                except Exception as e:
                    logging.error(f"Fehler beim Zwischenspeichern der Umfrage {message_id}: {e}")
                    # Versuche, die Verbindung neu zu starten, falls sie fehlschlägt
                    try:
                        self._reconnect_database()
                        db.add_cwl_poll(
                            poll_id=poll_data['poll_id'],
                            channel_id=poll_data['channel'].id,
                            channel_name=poll_data['channel'].name,
                            duration=poll_data['duration'],
                            yes_count=yes_count,
                            no_count=no_count
                        )
                        logging.info(f"Erneute Zwischenspeicherung für Umfrage {message_id} erfolgreich nach Reconnect")
                    except Exception as e2:
                        logging.error(f"Reconnect und erneutes Speichern fehlgeschlagen für Umfrage {message_id}: {e2}")
        self.had_active_polls = has_active_polls

    def _reconnect_database(self):
        """Versuche, die Datenbankverbindung neu herzustellen."""
        try:
            db.conn.close()
            db.conn = mysql.connector.connect(
                host="db2.sillydevelopment.co.uk",
                port=3306,
                user="u52481_uuC019WM8H",
                password="YOUR_PASSWORD_HERE",  # Ersetze mit deinem Passwort
                database="s52481_Oluja_DATA"
            )
            db.cursor = db.conn.cursor()
            logging.info("Datenbankverbindung erfolgreich neu hergestellt")
        except Exception as e:
            logging.error(f"Fehler beim erneuten Verbinden zur Datenbank: {e}")

    @save_poll_progress.before_loop
    async def before_save_poll_progress(self):
        """Warte, bis der Bot bereit ist, bevor die Zwischenspeicherung startet."""
        await self.bot.wait_until_ready()
        logging.info("Bot ist bereit, save_poll_progress wird gestartet")

    @app_commands.command(name="cwl-req", description="Starte eine Umfrage für CWL-Teilnahme")
    async def cwl_req(self, interaction: discord.Interaction, duration: int, channel: discord.TextChannel = None):
        log_collector = LogCollector(interaction.guild, "CWL-Umfrage", interaction.user, channel or interaction.channel)
        log_collector.add_event("Umfrage gestartet")

        await interaction.response.defer(ephemeral=True)
        if duration <= 0:
            await interaction.followup.send(embed=discord.Embed(
                title="⚠️ Fehler",
                description="Die Dauer muss positiv sein!",
                color=discord.Color.red()
            ), ephemeral=True)
            log_collector.add_event("Ungültige Dauer", "WARNING")
            await log_collector.post_log(status="Abgebrochen", color=discord.Color.red())
            return

        target_channel = channel or interaction.channel
        poll_embed = discord.Embed(
            title="📣 CWL-Teilnahme Umfrage",
            description=(
                "Möchtest du an der kommenden Clan War League teilnehmen?\n"
                "Bitte reagiere mit ✅ für Ja oder ❌ für Nein."
            ),
            color=discord.Color.blue()
        )
        poll_embed.set_footer(text=f"Umfrage endet in {duration} Minuten | Operation-Oluja", icon_url=interaction.user.display_avatar.url)
        poll_message = await target_channel.send(embed=poll_embed)
        await poll_message.add_reaction("✅")
        await poll_message.add_reaction("❌")

        self.active_polls[poll_message.id] = {
            'channel': target_channel,
            'duration': duration,
            'responses': {},
            'start_time': datetime.utcnow(),
            'poll_id': poll_message.id  # poll_id ist die message_id
        }
        logging.info(f"Neue Umfrage gestartet: {poll_message.id} in {target_channel.name}")

        await interaction.followup.send(embed=discord.Embed(
            title="✅ Umfrage gestartet",
            description=f"Die Umfrage läuft für {duration} Minuten in {target_channel.mention}.",
            color=discord.Color.green()
        ), ephemeral=True)
        log_collector.add_event(f"Umfrage gestartet in {target_channel.name} für {duration} Minuten")
        await log_collector.post_log()

        await asyncio.sleep(duration * 60)
        await self._end_poll(poll_message.id)

    async def _end_poll(self, message_id):
        if message_id not in self.active_polls:
            logging.warning(f"Umfrage {message_id} nicht mehr in active_polls gefunden")
            return

        poll_data = self.active_polls.pop(message_id)
        channel = poll_data['channel']
        duration = poll_data['duration']
        responses = poll_data['responses']
        poll_id = poll_data['poll_id']

        yes_count = sum(1 for r in responses.values() if r == "✅")
        no_count = sum(1 for r in responses.values() if r == "❌")
        total = yes_count + no_count

        result_embed = discord.Embed(
            title="📊 CWL-Umfrage Ergebnisse",
            description=(
                f"**Dauer:** {duration} Minuten\n"
                f"**Ja (✅):** {yes_count} ({(yes_count / total * 100 if total > 0 else 0):.1f}%)\n"
                f"**Nein (❌):** {no_count} ({(no_count / total * 100 if total > 0 else 0):.1f}%)"
            ),
            color=discord.Color.purple()
        )
        result_embed.set_footer(text="Operation-Oluja | Ergebnisse", icon_url="https://cdn.discordapp.com/attachments/1128712101349038160/1226579502036989992/oluja_logo.png")
        await channel.send(embed=result_embed)

        admin_user = self.bot.get_user(963467218606247946)
        if admin_user:
            dm_embed = discord.Embed(
                title="📩 CWL-Umfrage Ergebnisse",
                description=(
                    f"**Umfrage in {channel.name}:**\n"
                    f"**Dauer:** {duration} Minuten\n"
                    f"**Ja (✅):** {yes_count} ({(yes_count / total * 100 if total > 0 else 0):.1f}%)\n"
                    f"**Nein (❌):** {no_count} ({(no_count / total * 100 if total > 0 else 0):.1f}%)"
                ),
                color=discord.Color.purple()
            )
            dm_embed.set_footer(text="Operation-Oluja | DM an Admin", icon_url="https://cdn.discordapp.com/attachments/1128712101349038160/1226579502036989992/oluja_logo.png")
            try:
                await admin_user.send(embed=dm_embed)
                log_collector = LogCollector(channel.guild, "CWL-Umfrage", admin_user)
                log_collector.add_event("Ergebnisse an Admin gesendet")
                await log_collector.post_log()
            except discord.Forbidden:
                log_collector = LogCollector(channel.guild, "CWL-Umfrage", admin_user)
                log_collector.add_event("DM an Admin konnte nicht gesendet werden", "WARNING")
                await log_collector.post_log()

        try:
            db.add_cwl_poll(
                poll_id=poll_id,
                channel_id=channel.id,
                channel_name=channel.name,
                duration=duration,
                yes_count=yes_count,
                no_count=no_count
            )
            logging.info(f"Endgültige Ergebnisse für Umfrage {message_id} gespeichert: Ja={yes_count}, Nein={no_count}")
        except Exception as e:
            logging.error(f"Fehler beim Speichern der endgültigen Ergebnisse für Umfrage {message_id}: {e}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot or reaction.message.id not in self.active_polls:
            return

        poll_data = self.active_polls[reaction.message.id]
        if str(reaction.emoji) in ["✅", "❌"]:
            poll_data['responses'][user.id] = str(reaction.emoji)
            logging.info(f"Reaktion hinzugefügt für Umfrage {reaction.message.id}: {user.name} -> {reaction.emoji}")

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.bot or reaction.message.id not in self.active_polls:
            return

        poll_data = self.active_polls[reaction.message.id]
        if user.id in poll_data['responses']:
            del poll_data['responses'][user.id]
            logging.info(f"Reaktion entfernt für Umfrage {reaction.message.id}: {user.name}")

async def setup(bot):
    await bot.add_cog(CWLCog(bot))