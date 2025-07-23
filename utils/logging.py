import logging
from datetime import datetime
import discord
from typing import Optional
from utils.helpers import get_log_channel

def setup_logging() -> logging.Logger:
    """
    Configure and return a logger for the Operation-Oluja bot.
    Logs to a file with a standardized format.
    """
    logger = logging.getLogger("OperationOlujaBot")
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler("bot.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(file_handler)

    return logger

logger = setup_logging()

class LogCollector:
    """
    A class to collect and log events for a specific process, sending a summary to a Discord log channel.
    """
    def __init__(self, guild: discord.Guild, process_name: str, user: Optional[discord.User] = None, channel: Optional[discord.TextChannel] = None):
        self.guild = guild
        self.process_name = process_name
        self.user = user
        self.channel = channel
        self.events: list[dict[str, str]] = []
        self.start_time = datetime.utcnow()

    def add_event(self, event: str, level: str = "INFO"):
        """
        Add an event to the log collector with a specified log level.
        """
        self.events.append({"event": event, "level": level})
        logger.log(getattr(logging, level), f"{self.process_name} - {event}")

    @property
    def has_errors(self) -> bool:
        """
        Check if any events have an ERROR or WARNING level.
        """
        return any(event["level"] in ("ERROR", "WARNING") for event in self.events)

    async def post_log(self, status: str = "Completed", color: discord.Color = discord.Color.green()):
        """
        Post a summary of collected events to the guild's log channel as a Discord embed.
        """
        log_channel = get_log_channel(self.guild)
        if not log_channel or not self.events:
            logger.warning(f"No log channel or events to log for {self.process_name}")
            return

        try:
            embed = discord.Embed(
                title=f"📋 {self.process_name} - {status}",
                description="**Prozesszusammenfassung:**\n\n" + "\n".join(
                    f"[{e['level']}] {e['event']}" for e in self.events
                ),
                color=color,
                timestamp=datetime.utcnow()
            )
            if self.user:
                embed.set_author(name=f"{self.user.name} (ID: {self.user.id})", icon_url=self.user.display_avatar.url)
            if self.channel:
                embed.add_field(name="Kanal", value=f"{self.channel.mention} (ID: {self.channel.id})", inline=True)
            embed.add_field(name="Dauer", value=f"{(datetime.utcnow() - self.start_time).seconds} Sekunden", inline=True)
            embed.set_footer(text=f"Operation-Oluja | {datetime.utcnow().strftime('%d.%m.%Y %H:%M UTC')}")
            
            await log_channel.send(embed=embed)
            logger.info(f"Log posted to {log_channel.name} for {self.process_name}")
        except Exception as e:
            logger.error(f"Error posting log to {log_channel.name}: {e}")
            raise