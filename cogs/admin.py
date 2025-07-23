import discord
from discord.ext import commands
from discord import app_commands
import config
from utils.helpers import get_admin_role, get_log_channel, get_archive_channel, export_applications_csv

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Setup für den Bewerbungs-Bot")
    @app_commands.describe(channel="Channel für das Bewerbungsmenü")
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Nur Admins können diesen Befehl nutzen!", ephemeral=True)
            return

        admin_role = get_admin_role(interaction.guild)
        if not admin_role:
            admin_role = await interaction.guild.create_role(name=config.ADMIN_ROLE_NAME)

        log_channel = get_log_channel(interaction.guild)
        if not log_channel:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                admin_role: discord.PermissionOverwrite(read_messages=True),
            }
            await interaction.guild.create_text_channel(
                config.LOG_CHANNEL_NAME, overwrites=overwrites, reason="Log-Channel für Bewerbungen"
            )

        archive_channel = get_archive_channel(interaction.guild)
        if not archive_channel:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                admin_role: discord.PermissionOverwrite(read_messages=True),
            }
            await interaction.guild.create_text_channel(
                config.ARCHIVE_CHANNEL_NAME, overwrites=overwrites, reason="Archiv-Channel für Bewerbungen"
            )

        menu_embed = discord.Embed(
            title="📝 Clan Bewerbungssystem",
            description="**Wähle unten deine Bewerbungsart aus:**\n\n👥 Mitglieder-Bewerbung\n🛡️ Staff-Bewerbung",
            color=0x5865F2
        )
        menu_embed.set_footer(text=f"Clan: {config.CLAN_TAG}")
        from cogs.application import ApplicationDropdownView
        await channel.send(embed=menu_embed, view=ApplicationDropdownView())
        await interaction.response.send_message(
            f"✅ Bewerbungssystem erfolgreich in {channel.mention} eingerichtet!", ephemeral=True
        )

    @app_commands.command(name="bewerbungsexport", description="Exportiert alle Bewerbungen als CSV (Admins only)")
    async def bewerbungsexport(self, interaction: discord.Interaction):
        admin_role = get_admin_role(interaction.guild)
        if not admin_role or admin_role not in interaction.user.roles:
            await interaction.response.send_message("❌ Nur Teammitglieder dürfen diesen Befehl nutzen.", ephemeral=True)
            return
        file = export_applications_csv()
        log_channel = get_log_channel(interaction.guild)
        if log_channel:
            await log_channel.send("📥 Bewerbungs-Export:", file=file)
            await interaction.response.send_message("✅ Bewerbungs-Export wurde im Log-Channel hochgeladen.", ephemeral=True)
        else:
            await interaction.response.send_message("Log-Channel nicht gefunden.", ephemeral=True)

    @app_commands.command(name="editquestions", description="Bearbeite die Bewerbungsfragen (Admins only)")
    @app_commands.describe(bewerbungsart="Bewerbungsart", question_index="Index der Frage (1-3)", new_question="Neue Frage")
    async def edit_questions(self, interaction: discord.Interaction, bewerbungsart: str, question_index: int, new_question: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Nur Admins können diesen Befehl nutzen!", ephemeral=True)
            return
        
        if bewerbungsart not in config.APPLICATION_QUESTIONS:
            await interaction.response.send_message("⚠️ Ungültige Bewerbungsart. Verfügbar: Mitglieder-Bewerbung, Staff-Bewerbung", ephemeral=True)
            return
        
        if not (1 <= question_index <= len(config.APPLICATION_QUESTIONS[bewerbungsart])):
            await interaction.response.send_message(f"⚠️ Ungültiger Fragen-Index. Muss zwischen 1 und {len(config.APPLICATION_QUESTIONS[bewerbungsart])} liegen.", ephemeral=True)
            return
        
        config.APPLICATION_QUESTIONS[bewerbungsart][question_index-1] = new_question
        await interaction.response.send_message(f"✅ Frage {question_index} für {bewerbungsart} wurde aktualisiert: {new_question}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))