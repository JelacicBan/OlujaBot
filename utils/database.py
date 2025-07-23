import mysql.connector
from datetime import datetime
from mysql.connector import Error
import logging
from typing import Optional

class Database:
    """
    A singleton class to manage MySQL database connections and operations for the Operation-Oluja bot.
    Handles tables for applications, moderation logs, member events, and CWL polls.
    """
    
    _instance = None

    def __new__(cls):
        """Ensures only one instance of the Database class is created (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize database connection and create necessary tables."""
        if hasattr(self, '_initialized') and self._initialized:
            return
        try:
            self.conn = mysql.connector.connect(
                host="localhost",  # Use environment variable or config in production
                port=3306,
                user="your_username",  # Replace with environment variable in production
                password="your_password",  # Replace with environment variable in production
                database="oluja_data"
            )
            self.cursor = self.conn.cursor()
            self._create_tables()
            self._initialized = True
            logging.info("Database connection established and tables initialized.")
        except Error as e:
            logging.error(f"Failed to connect to database: {e}")
            raise

    def _create_tables(self):
        """Create database tables if they do not exist."""
        try:
            # Applications table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS applications (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    applicant_name VARCHAR(255) NOT NULL,
                    applicant_id BIGINT NOT NULL,
                    apply_type VARCHAR(50) NOT NULL,
                    spieler_tag VARCHAR(15),
                    strategien TEXT,
                    th_level VARCHAR(10),
                    status VARCHAR(50) NOT NULL,
                    reason TEXT,
                    handled_by VARCHAR(255),
                    date DATETIME NOT NULL
                )
            ''')

            # Moderation logs table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS moderation_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    user_name VARCHAR(255) NOT NULL,
                    action_type VARCHAR(50) NOT NULL,
                    reason TEXT,
                    duration INT,
                    handled_by VARCHAR(255),
                    date DATETIME NOT NULL
                )
            ''')

            # Member events table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS member_events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    user_name VARCHAR(255) NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    date DATETIME NOT NULL
                )
            ''')

            # CWL polls table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS cwl_polls (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    poll_id BIGINT UNIQUE NOT NULL,
                    channel_id BIGINT NOT NULL,
                    channel_name VARCHAR(255) NOT NULL,
                    duration INT NOT NULL,
                    yes_count INT DEFAULT 0,
                    no_count INT DEFAULT 0,
                    date DATETIME NOT NULL
                )
            ''')

            self.conn.commit()
            logging.info("Database tables created successfully or already exist.")
        except Error as e:
            logging.error(f"Error creating tables: {e}")
            self.conn.rollback()
            raise

    def add_application(
        self,
        applicant_name: str,
        applicant_id: int,
        apply_type: str,
        spieler_tag: Optional[str],
        strategien: Optional[str],
        th_level: Optional[str],
        status: str,
        reason: Optional[str],
        handled_by: Optional[str]
    ):
        """Add a new application to the database."""
        try:
            date = datetime.utcnow()
            sql = '''
                INSERT INTO applications 
                (applicant_name, applicant_id, apply_type, spieler_tag, strategien, th_level, status, reason, handled_by, date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            self.cursor.execute(sql, (
                applicant_name, applicant_id, apply_type, spieler_tag, strategien, 
                th_level, status, reason, handled_by, date
            ))
            self.conn.commit()
            logging.info(f"Application added for {applicant_name} (ID: {applicant_id})")
        except Error as e:
            logging.error(f"Error adding application for {applicant_name}: {e}")
            self.conn.rollback()
            raise

    def add_moderation_log(
        self,
        user_id: int,
        user_name: str,
        action_type: str,
        reason: Optional[str],
        duration: Optional[int],
        handled_by: Optional[str]
    ):
        """Add a moderation log entry to the database."""
        try:
            date = datetime.utcnow()
            sql = '''
                INSERT INTO moderation_logs 
                (user_id, user_name, action_type, reason, duration, handled_by, date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            '''
            self.cursor.execute(sql, (user_id, user_name, action_type, reason, duration, handled_by, date))
            self.conn.commit()
            logging.info(f"Moderation log added for {user_name} (Action: {action_type})")
        except Error as e:
            logging.error(f"Error adding moderation log for {user_name}: {e}")
            self.conn.rollback()
            raise

    def add_member_event(self, user_id: int, user_name: str, event_type: str):
        """Add a member event to the database."""
        try:
            date = datetime.utcnow()
            sql = '''
                INSERT INTO member_events (user_id, user_name, event_type, date)
                VALUES (%s, %s, %s, %s)
            '''
            self.cursor.execute(sql, (user_id, user_name, event_type, date))
            self.conn.commit()
            logging.info(f"Member event '{event_type}' added for {user_name}")
        except Error as e:
            logging.error(f"Error adding member event for {user_name}: {e}")
            self.conn.rollback()
            raise

    def add_cwl_poll(self, poll_id: int, channel_id: int, channel_name: str, duration: int, yes_count: int, no_count: int):
        """Add or update a CWL poll in the database."""
        try:
            date = datetime.utcnow()
            self.cursor.execute("SELECT id FROM cwl_polls WHERE poll_id = %s", (poll_id,))
            if self.cursor.fetchone():
                sql = '''
                    UPDATE cwl_polls 
                    SET channel_id = %s, channel_name = %s, duration = %s, yes_count = %s, no_count = %s, date = %s
                    WHERE poll_id = %s
                '''
                self.cursor.execute(sql, (channel_id, channel_name, duration, yes_count, no_count, date, poll_id))
                logging.info(f"CWL poll {poll_id} updated: Yes={yes_count}, No={no_count}")
            else:
                sql = '''
                    INSERT INTO cwl_polls (poll_id, channel_id, channel_name, duration, yes_count, no_count, date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                '''
                self.cursor.execute(sql, (poll_id, channel_id, channel_name, duration, yes_count, no_count, date))
                logging.info(f"CWL poll {poll_id} created: Yes={yes_count}, No={no_count}")
            self.conn.commit()
        except Error as e:
            logging.error(f"Error saving CWL poll {poll_id}: {e}")
            self.conn.rollback()
            raise

    def get_applications(self, status: Optional[str] = None) -> list:
        """Retrieve applications from the database, optionally filtered by status."""
        try:
            if status:
                self.cursor.execute("SELECT * FROM applications WHERE status = %s", (status,))
            else:
                self.cursor.execute("SELECT * FROM applications")
            columns = [col[0] for col in self.cursor.description]
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except Error as e:
            logging.error(f"Error retrieving applications: {e}")
            raise

    def close(self):
        """Close the database cursor and connection."""
        try:
            self.cursor.close()
            self.conn.close()
            logging.info("Database connection closed.")
        except Error as e:
            logging.error(f"Error closing database connection: {e}")
            raise

# Singleton instance (initialize only when needed)
db = None

def get_db() -> Database:
    """Get the singleton Database instance, initializing it if necessary."""
    global db
    if db is None:
        db = Database()
    return db