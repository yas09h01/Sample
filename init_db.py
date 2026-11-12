import sqlite3


# Connect to the SQLite database file (SQLite creates it if it does not exist).
connection = sqlite3.connect("placements.db")

try:
    # Create a cursor so we can run an SQL command.
    cursor = connection.cursor()

    # Create the applications table if it has not been created yet.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            job_role TEXT NOT NULL,
            application_date TEXT,
            interview_date TEXT,
            status TEXT
        )
        """
    )

    # Keep older databases working by adding a missing interview_date column.
    cursor.execute("PRAGMA table_info(applications)")
    columns = {column[1] for column in cursor.fetchall()}
    if "interview_date" not in columns:
        cursor.execute("ALTER TABLE applications ADD COLUMN interview_date TEXT")

    connection.commit()

    print("Database and applications table created successfully.")
finally:
    # Always close the connection when we are finished.
    connection.close()
