"""A simple Streamlit app for tracking job applications."""

from contextlib import closing
from io import StringIO
from pathlib import Path
import sqlite3
from datetime import date, timedelta

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


def ensure_schema():
    """Add any missing table columns needed for the tracker features."""
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        columns = connection.execute("PRAGMA table_info(applications)").fetchall()
        existing_columns = {column[1] for column in columns}
        if "interview_date" not in existing_columns:
            connection.execute(
                "ALTER TABLE applications ADD COLUMN interview_date TEXT"
            )
        connection.commit()


def get_applications(search_query="", status_filter="All"):
    """Read application records and summary information from SQLite."""
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        search_value = search_query.strip()
        like_value = f"%{search_value}%"

        applications = connection.execute(
            """
            SELECT application_id, company_name, job_role, application_date, interview_date, status
            FROM applications
            WHERE (? = '' OR company_name COLLATE NOCASE LIKE ?)
              AND (? = 'All' OR status = ?)
            ORDER BY application_date DESC, application_id DESC
            """,
            (search_value, like_value, status_filter, status_filter),
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


def add_application(company_name, job_role, application_date, status, interview_date=None):
    """Save one application using placeholders to safely pass user input."""
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO applications (company_name, job_role, application_date, interview_date, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (company_name, job_role, application_date, interview_date, status),
            )


def update_application_status(application_id, status, interview_date=None):
    """Update an application's status and, optionally, its interview date."""
    normalized_interview_date = interview_date.strip() if interview_date else None
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        with connection:
            connection.execute(
                """
                UPDATE applications
                SET status = ?, interview_date = ?
                WHERE application_id = ?
                """,
                (status, normalized_interview_date, application_id),
            )


def delete_application(application_id):
    """Delete a single application after confirmation."""
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        with connection:
            connection.execute(
                "DELETE FROM applications WHERE application_id = ?",
                (application_id,),
            )


def export_applications_csv(search_query="", status_filter="All"):
    """Return a CSV string for the current filtered applications list."""
    applications, _, _ = get_applications(search_query, status_filter)
    application_rows = [dict(row) for row in applications]
    dataframe = pd.DataFrame(application_rows)
    if dataframe.empty:
        dataframe = pd.DataFrame(
            columns=[
                "application_id",
                "company_name",
                "job_role",
                "application_date",
                "interview_date",
                "status",
            ]
        )
    csv_buffer = StringIO()
    dataframe.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    return csv_buffer


def get_upcoming_interviews(days=14):
    """Find interview dates within the next N days."""
    end_date = (date.today() + timedelta(days=days)).isoformat()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        upcoming = connection.execute(
            """
            SELECT application_id, company_name, job_role, interview_date, status
            FROM applications
            WHERE interview_date IS NOT NULL
              AND interview_date BETWEEN date('now') AND ?
            ORDER BY interview_date ASC, company_name COLLATE NOCASE ASC
            """,
            (end_date,),
        ).fetchall()
    return upcoming


def main():
    """Build and display the Placement Application Tracker."""
    ensure_schema()

    st.set_page_config(
        page_title="Placement Application Tracker",
        page_icon="📋",
        layout="wide",
    )
    st.title("📋 Placement Application Tracker")
    st.write("Keep your job applications organized and see your progress at a glance.")

    try:
        all_applications, role_counts, status_rows = get_applications()
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
    total_count = len(all_applications)
    first_role_count = role_counts[0]["application_count"] if role_counts else 0
    most_applied_roles = [
        row["job_role"]
        for row in role_counts
        if row["application_count"] == first_role_count
    ]

    metric_columns = st.columns(2)
    metric_columns[0].metric("Total Applications", total_count)
    if most_applied_roles:
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

    st.header("Manage applications")
    search_query = st.text_input("Search company name", placeholder="Type a company name")
    status_filter = st.selectbox("Filter by status", ["All", *STATUS_OPTIONS])

    filtered_applications, _, _ = get_applications(search_query, status_filter)

    if filtered_applications:
        filtered_table = []
        for item in filtered_applications:
            filtered_table.append(dict(item))
        st.dataframe(
            filtered_table,
            width="stretch",
            hide_index=True,
            column_config={
                "application_id": st.column_config.NumberColumn("Application ID"),
                "company_name": st.column_config.TextColumn("Company Name"),
                "job_role": st.column_config.TextColumn("Job Role"),
                "application_date": st.column_config.TextColumn("Application Date"),
                "interview_date": st.column_config.TextColumn("Interview Date"),
                "status": st.column_config.TextColumn("Status"),
            },
        )
    else:
        st.info("No applications match the current search or status filter.")

    if filtered_applications:
        selected_id = st.selectbox(
            "Select an application to update or delete",
            options=[row["application_id"] for row in filtered_applications],
            format_func=lambda app_id: next(
                row["company_name"] for row in filtered_applications if row["application_id"] == app_id
            ),
        )
        selected_row = next(
            row for row in filtered_applications if row["application_id"] == selected_id
        )

        with st.form("update_application_form"):
            current_status = selected_row["status"]
            selected_status = st.selectbox(
                "Status",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0,
            )

            current_interview_date = selected_row["interview_date"]
            if current_interview_date:
                default_interview_date = date.fromisoformat(current_interview_date)
            else:
                default_interview_date = date.today()

            interview_date = st.date_input(
                "Interview Date",
                value=default_interview_date,
            )
            clear_interview_date = st.checkbox("Clear interview date")
            update_submitted = st.form_submit_button("Update Status", type="primary")

        if update_submitted:
            try:
                interview_value = None if clear_interview_date else interview_date.isoformat()
                update_application_status(selected_id, selected_status, interview_value)
                st.success("Application status updated successfully.")
                st.rerun()
            except sqlite3.Error as error:
                st.error(f"Could not update the application: {error}")

        with st.form("delete_application_form"):
            confirm_delete = st.checkbox("I confirm I want to delete this record")
            delete_submitted = st.form_submit_button("Delete Application", type="secondary")

        if delete_submitted and confirm_delete:
            try:
                delete_application(selected_id)
                st.success("Application deleted successfully.")
                st.rerun()
            except sqlite3.Error as error:
                st.error(f"Could not delete the application: {error}")
        elif delete_submitted and not confirm_delete:
            st.warning("Please confirm the deletion before removing the record.")

    st.header("Upcoming interviews")
    upcoming_rows = get_upcoming_interviews(14)
    if upcoming_rows:
        upcoming_data = [dict(row) for row in upcoming_rows]
        st.dataframe(
            upcoming_data,
            width="stretch",
            hide_index=True,
            column_config={
                "application_id": st.column_config.NumberColumn("Application ID"),
                "company_name": st.column_config.TextColumn("Company Name"),
                "job_role": st.column_config.TextColumn("Job Role"),
                "interview_date": st.column_config.TextColumn("Interview Date"),
                "status": st.column_config.TextColumn("Status"),
            },
        )
    else:
        st.info("No interviews scheduled in the next 14 days.")

    st.header("Export application records")
    csv_data = export_applications_csv(search_query, status_filter)
    st.download_button(
        label="Download CSV",
        data=csv_data.getvalue(),
        file_name="applications.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
