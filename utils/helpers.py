import discord
import config
import io
import csv
import json
from datetime import datetime
from typing import Optional, List, Dict
import logging

APPLICATIONS_FILE = "applications.json"

def load_applications() -> List[Dict]:
    """
    Load applications from a JSON file.
    Returns an empty list if the file does not exist.
    """
    try:
        import os
        if os.path.exists(APPLICATIONS_FILE):
            with open(APPLICATIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except Exception as e:
        logging.error(f"Error loading applications from {APPLICATIONS_FILE}: {e}")
        return []

def save_applications(applications: List[Dict]):
    """
    Save applications to a JSON file.
    """
    try:
        with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(applications, f, indent=4, default=str)
        logging.info(f"Applications saved to {APPLICATIONS_FILE}")
    except Exception as e:
        logging.error(f"Error saving applications to {APPLICATIONS_FILE}: {e}")
        raise

def get_admin_role(guild: discord.Guild) -> Optional[discord.Role]:
    """
    Retrieve the admin role from the guild based on config.
    """
    try:
        role = discord.utils.get(guild.roles, name=config.ADMIN_ROLE_NAME)
        if not role:
            logging.warning(f"Admin role '{config.ADMIN_ROLE_NAME}' not found in guild {guild.name}")
        return role
    except Exception as e:
        logging.error(f"Error retrieving admin role for guild {guild.name}: {e}")
        return None

def get_log_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    """
    Retrieve the log channel from the guild based on config.
    """
    try:
        channel = discord.utils.get(guild.text_channels, name=config.LOG_CHANNEL_NAME)
        if not channel:
            logging.warning(f"Log channel '{config.LOG_CHANNEL_NAME}' not found in guild {guild.name}")
        return channel
    except Exception as e:
        logging.error(f"Error retrieving log channel for guild {guild.name}: {e}")
        return None

def get_archive_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    """
    Retrieve the archive channel from the guild based on config.
    """
    try:
        channel = discord.utils.get(guild.text_channels, name=config.ARCHIVE_CHANNEL_NAME)
        if not channel:
            logging.warning(f"Archive channel '{config.ARCHIVE_CHANNEL_NAME}' not found in guild {guild.name}")
        return channel
    except Exception as e:
        logging.error(f"Error retrieving archive channel for guild {guild.name}: {e}")
        return None

def add_application_entry(**kwargs):
    """
    Add an application entry to the in-memory list and save to file.
    """
    try:
        applications = load_applications()
        kwargs["date"] = kwargs.get("date", datetime.utcnow())
        applications.append(kwargs)
        save_applications(applications)
        logging.info(f"Application added for {kwargs.get('applicant_name', 'Unknown')}")
    except Exception as e:
        logging.error(f"Error adding application: {e}")
        raise

def export_applications_csv(status_filter: Optional[str] = None) -> discord.File:
    """
    Export applications to a CSV file, optionally filtered by status.
    Returns a discord.File object for sending via Discord.
    """
    try:
        applications = load_applications()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Bewerber", "Typ", "Spieler-Tag", "Strategien", "TH-Level", "Status", "Grund", "Bearbeiter", "Datum"])

        for app in applications:
            if status_filter and app.get("status") != status_filter:
                continue
            writer.writerow([
                app.get("applicant_name", "Unbekannt"),
                app.get("apply_type", "Unbekannt"),
                app.get("spieler_tag", ""),
                app.get("strategien", ""),
                app.get("th_level", ""),
                app.get("status", ""),
                app.get("reason", ""),
                app.get("handled_by", ""),
                app.get("date", "").strftime("%d.%m.%Y %H:%M") if isinstance(app.get("date"), datetime) else app.get("date", "")
            ])

        output.seek(0)
        logging.info(f"Applications exported to CSV with status filter: {status_filter or 'None'}")
        return discord.File(
            fp=io.BytesIO(output.getvalue().encode('utf-8')),
            filename="bewerber_export.csv"
        )
    except Exception as e:
        logging.error(f"Error exporting applications to CSV: {e}")
        raise