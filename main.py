import discord
from discord.ext import commands
import config
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, application_id=config.APPLICATION_ID)

async def load_cogs():
    print("Starting to load cogs...")
    for cog in ["cogs.application", "cogs.admin", "cogs.feedback", "cogs.events", "cogs.war", "cogs.moderation", "cogs.stats", "cogs.cwl"]:
        try:
            print(f"Loading {cog}...")
            await bot.load_extension(cog)
            print(f"Successfully loaded {cog}")
        except Exception as e:
            print(f"Failed to load {cog}: {str(e)}")

@bot.event
async def on_ready():
    print(f"Eingeloggt als {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Clan Bewerbungen"))

@bot.event
async def setup_hook():
    await load_cogs()
    await bot.tree.sync()

if __name__ == "__main__":
    asyncio.run(bot.start(config.BOT_TOKEN))