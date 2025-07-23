import discord
from discord.ext import commands
import config
import asyncio

class FeedbackCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if "wie lange dauert" in message.content.lower():
            await message.channel.send("⏳ Die Bearbeitung dauert in der Regel 1-3 Tage. Danke für deine Geduld!")

async def setup(bot):
    await bot.add_cog(FeedbackCog(bot))