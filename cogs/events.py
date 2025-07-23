import discord
from discord.ext import commands
from utils.helpers import get_log_channel
from utils.logging import LogCollector
from utils.database import db  # Import der Datenbank
from datetime import datetime

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Eingeloggt als {self.bot.user} (ID: {self.bot.user.id})")
        log_collector = LogCollector(self.bot.guilds[0], "Bot-Start")
        log_collector.add_event("Bot gestartet")
        await log_collector.post_log()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        log_channel = get_log_channel(guild)
        log_collector = LogCollector(guild, "Mitglied Beitritt", member)
        log_collector.add_event("Neuer Beitritt")

        if log_channel:
            welcome_embed = discord.Embed(
                title="🎉 Willkommen!",
                description=f"**{member.mention}**, willkommen bei Operation-Oluja!\nBitte lies die Regeln und bewirb dich im Bewerbungskanal.",
                color=discord.Color.gold()
            )
            welcome_embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1128712101349038160/1226579502036989992/oluja_logo.png")
            welcome_embed.set_footer(text=f"Operation-Oluja | {datetime.utcnow().strftime('%d.%m.%Y %H:%M UTC')}", icon_url=member.display_avatar.url)
            await log_channel.send(embed=welcome_embed)
            log_collector.add_event("Willkommensnachricht gesendet")

        db.add_member_event(
            user_id=member.id,
            user_name=member.name,
            event_type="Join"
        )

        await log_collector.post_log()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        log_collector = LogCollector(guild, "Mitglied Austritt", member)
        log_collector.add_event("Mitglied verlassen")

        db.add_member_event(
            user_id=member.id,
            user_name=member.name,
            event_type="Leave"
        )

        await log_collector.post_log()

async def setup(bot):
    await bot.add_cog(EventsCog(bot))