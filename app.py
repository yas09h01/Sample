"""A simple Streamlit app for tracking job applications."""

from contextlib import closing
from pathlib import Path
import sqlite3
from datetime import date

import pandas as pd
import streamlit as st


# Keep the database next to this Python file so the app finds it from any folder.
DATABASE_PATH = Path(__file__).with_name("placements.db")

# These are the application statuses people can choose in the form.
STATUS_OPTIONS = [
    "Applied",
    "Shortlisted",
    "Interview Scheduled",
    "Selected",
    "Rejected",
]


def get_applications():
    """Read application records and summary information from SQLite."""
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        applications = connection.execute(
            """
            SELECT application_id, company_name, job_role, application_date, status
            FROM applications
            ORDER BY application_date DESC, application_id DESC
            """
        ).fetchall()

        role_counts = connection.execute(
            """
            SELECT job_role, COUNT(*) AS application_count
            FROM applications
            GROUP BY job_role
            ORDER BY application_count DESC, job_role COLLATE NOCASE ASC
            """
        ).fetchall()

        status_rows = connection.execute(
            """
            SELECT status, COUNT(*) AS application_count
            FROM applications
            GROUP BY status
            """
        ).fetchall()

    return applications, role_counts, status_rows


def add_application(company_name, job_role, application_date, status):
    """Save one application using placeholders to safely pass user input."""
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO applications (company_name, job_role, application_date, status)
                VALUES (?, ?, ?, ?)
                """,
                (company_name, job_role, application_date, status),
            )


def main():
    """Build and display the Placement Application Tracker."""
    st.set_page_config(
        page_title="Placement Application Tracker",
        page_icon="📋",
        layout="wide",
    )
    st.title("📋 Placement Application Tracker")
    st.write("Keep your job applications organized and see your progress at a glance.")

    try:
        applications, role_counts, status_rows = get_applications()
    except sqlite3.Error as error:
        st.error(f"Could not read the applications database: {error}")
        st.info("Check that placements.db is next to app.py and that it contains an applications table.")
        return

    st.header("Add an application")
    with st.form("add_application_form", clear_on_submit=True):
        company_name = st.text_input("Company Name")
        job_role = st.text_input("Job Role")
        application_date = st.date_input("Application Date", value=date.today())
        status = st.selectbox("Status", STATUS_OPTIONS)
        submitted = st.form_submit_button("Add Application", type="primary")

    if submitted:
        company_name = company_name.strip()
        job_role = job_role.strip()
        if not company_name or not job_role:
            st.error("Please enter both a Company Name and a Job Role.")
        else:
            try:
                # Store dates in the requested YYYY-MM-DD format.
                add_application(
                    company_name,
                    job_role,
                    application_date.isoformat(),
                    status,
                )
                st.success("Application added successfully.")
                st.rerun()
            except sqlite3.Error as error:
                st.error(f"Could not save the application: {error}")

    st.header("Your application summary")
    total_count = len(applications)
    first_role_count = role_counts[0]["application_count"] if role_counts else 0
    most_applied_roles = [
        row["job_role"]
        for row in role_counts
        if row["application_count"] == first_role_count
    ]

    metric_columns = st.columns(2)
    metric_columns[0].metric("Total Applications", total_count)
    if most_applied_roles:
        # If roles are tied, show all of them in alphabetical order.
        tied_roles = sorted(most_applied_roles, key=str.casefold)
        metric_columns[1].metric(
            "Most Applied Role",
            tied_roles[0] if len(tied_roles) == 1 else f"{len(tied_roles)} roles tied",
        )
        if len(tied_roles) > 1:
            metric_columns[1].caption(", ".join(tied_roles))
    else:
        metric_columns[1].metric("Most Applied Role", "No applications yet")

    st.subheader("Status-wise Summary")
    status_counts = {status_name: 0 for status_name in STATUS_OPTIONS}
    for row in status_rows:
        status_name = row["status"] or "Unspecified"
        status_counts[status_name] = row["application_count"]

    summary_columns = st.columns(min(len(status_counts), 5))
    for column, (status_name, count) in zip(summary_columns, status_counts.items()):
        column.metric(status_name, count)

    chart_data = pd.DataFrame(
        {
            "Status": list(status_counts.keys()),
            "Applications": list(status_counts.values()),
        }
    )
    st.bar_chart(chart_data, x="Status", y="Applications", color="#6C63FF")

    st.header("All applications")
    if applications:
        # Convert SQLite rows to dictionaries for a readable Streamlit table.
        table_data = [dict(application) for application in applications]
        st.dataframe(
            table_data,
            width="stretch",
            hide_index=True,
            column_config={
                "application_id": st.column_config.NumberColumn("Application ID"),
                "company_name": st.column_config.TextColumn("Company Name"),
                "job_role": st.column_config.TextColumn("Job Role"),
                "application_date": st.column_config.TextColumn("Application Date"),
                "status": st.column_config.TextColumn("Status"),
            },
        )
    else:
        st.info("No applications yet. Add one using the form above.")


if __name__ == "__main__":
    main()
