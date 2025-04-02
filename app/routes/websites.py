import sqlite3
from flask import Blueprint, render_template, request, jsonify
from app.services.url_status import CheckStatus  # for building table_html, etc.

websites_bp = Blueprint("websites_bp", __name__)

def fetch_config_from_db():
    """Fetch the global config from the database. Returns a dictionary."""
    conn = sqlite3.connect("my_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT work_hours_start, work_hours_end, mute_all FROM config LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "work_hours_start": row[0],
            "work_hours_end": row[1],
            "mute_all": row[2],
        }
    else:
        # If no row exists, return defaults
        return {
            "work_hours_start": 7,
            "work_hours_end": 17,
            "mute_all": 0
        }

@websites_bp.route("/status", methods=["GET"])
def show_status():
    """
    Display the main status page with the current config and URL table.
    """
    # 1) Retrieve global config from the database
    config_row = fetch_config_from_db()

    # 2) Build the status table from CheckStatus
    CheckStatus.test_urls()
    table_html = CheckStatus.html

    # 3) Calculate refresh intervals
    #TODO refresh needs to be from the environment variables 
    refresh_seconds = (60 * 2) + 40
    refresh_ms = (2 * 60000) + 60000

    # 4) Render status.html, passing in table_html and config values
    return render_template(
        "status.html",
        table_html=table_html,
        refresh_seconds=refresh_seconds,
        refresh_ms=refresh_ms,
        work_hours_start=config_row["work_hours_start"],
        work_hours_end=config_row["work_hours_end"],
        mute_all=config_row["mute_all"]
        # check_interval=config_row["check_interval"]
    )


@websites_bp.route("/config", methods=["POST"])
def save_config():
    """
    Receives JSON data via AJAX to update global config values in the DB.
    Example JSON structure:
    {
      "workStart": "7",
      "workEnd": "17",
      "muteAll": "0",
      "checkInterval": "5"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No JSON data received"}), 400

    try:
        work_start = int(data.get("workStart", 7))
        work_end = int(data.get("workEnd", 17))
        mute_all = int(data.get("muteAll", 0))
        # check_interval = int(data.get("checkInterval", 5))
    except Exception as ex:
        return jsonify({"success": False, "message": f"Invalid data: {ex}"}), 400

    try:
        conn = sqlite3.connect("my_database.db")
        cursor = conn.cursor()
        # Check if a config row already exists (assume single row with id=1)
        cursor.execute("SELECT id FROM config LIMIT 1")
        row = cursor.fetchone()
        if row:
            config_id = row[0]
            cursor.execute("""
                UPDATE config
                SET work_hours_start = ?, work_hours_end = ?, mute_all = ?
                WHERE id = ?
            """, (work_start, work_end, mute_all, config_id))
        else:
            cursor.execute("""
                INSERT INTO config (work_hours_start, work_hours_end, mute_all)
                VALUES (?, ?, ?)
            """, (work_start, work_end, mute_all))
        conn.commit()
        conn.close()
    except Exception as ex:
        return jsonify({"success": False, "message": f"Error updating config: {ex}"}), 500

    return jsonify({"success": True, "message": "Config updated successfully"})


@websites_bp.route("/add", methods=["POST"])
def add_website():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No JSON data provided"}), 400

    url = data.get("url", "").strip()
    name = data.get("name", "").strip()
    emails = data.get("emails", [])  # <--- Now we expect a list here

    if not url or not name:
        return jsonify({"success": False, "message": "URL and Name cannot be empty."}), 400

    # Make sure `emails` is a list so we don't break code
    if not isinstance(emails, list):
        return jsonify({"success": False, "message": "Emails must be an array."}), 400

    try:
        with sqlite3.connect("my_database.db") as conn:
            cursor = conn.cursor()

            # Check if URL already exists
            cursor.execute("SELECT website_id FROM websites WHERE url = ?", (url,))
            existing = cursor.fetchone()
            if existing:
                return jsonify({"success": False, "message": "URL already exists in the database."}), 400

            # Insert the website record
            cursor.execute("""
                INSERT INTO websites (url, name, active)
                VALUES (?, ?, 1)
            """, (url, name))
            website_id = cursor.lastrowid

            # Insert each email (already a list)
            for e in emails:
                e_stripped = e.strip()
                if e_stripped:
                    cursor.execute("""
                        INSERT INTO website_emails (website_id, email)
                        VALUES (?, ?)
                    """, (website_id, e_stripped))

            return jsonify({"success": True, "message": "Website added successfully!"})
    except Exception as ex:
        return jsonify({"success": False, "message": f"Error inserting website: {ex}"}), 500


@websites_bp.route("/<int:website_id>/info", methods=["GET"])
def get_website_info(website_id):
    """
    Returns JSON with the website's info.
    """
    conn = sqlite3.connect("my_database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT url, name, active
        FROM websites
        WHERE website_id = ?
    """, (website_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"success": False, "message": "Website not found"}), 404

    url, name, active = row

    cursor.execute("""
        SELECT email
        FROM website_emails
        WHERE website_id = ?
    """, (website_id,))
    email_rows = cursor.fetchall()
    emails = [r[0] for r in email_rows]

    conn.close()

    return jsonify({
        "success": True,
        "website_id": website_id,
        "url": url,
        "name": name,
        "emails": emails,
        "active": active
    })


@websites_bp.route("/<int:website_id>/update", methods=["POST"])
def update_website(website_id):
    """
    Receives JSON to update a website's details.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    url = data.get("url", "").strip()
    name = data.get("name", "").strip()
    emails = data.get("emails", [])  # Expect an array
    active = int(data.get("active", 1))

    if not url or not name:
        return jsonify({"success": False, "message": "URL and Name cannot be empty"}), 400

    try:
        with sqlite3.connect("my_database.db") as conn:
            cursor = conn.cursor()

            # Update the main website record
            cursor.execute("""
                UPDATE websites
                SET url = ?, name = ?, active = ?
                WHERE website_id = ?
            """, (url, name, active, website_id))
            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "Website not found."}), 404

            # Clear out old emails
            cursor.execute("DELETE FROM website_emails WHERE website_id = ?", (website_id,))

            # Insert the new emails
            # (Because `emails` is a list of strings, no need for split(","))
            for em in emails:
                em_str = em.strip()
                if em_str:
                    cursor.execute("""
                        INSERT INTO website_emails (website_id, email)
                        VALUES (?, ?)
                    """, (website_id, em_str))

        return jsonify({"success": True, "message": "Website updated successfully!"})

    except Exception as ex:
        return jsonify({
            "success": False,
            "message": f"Error updating website: {ex}"
        }), 500



@websites_bp.route("/<int:website_id>/email/delete", methods=["POST"])
def delete_single_email(website_id):
    """
    Deletes a single email from the specified website.
    Expects JSON: { "email": "someEmail@example.com" }
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    email_to_delete = data.get("email", "").strip()
    if not email_to_delete:
        return jsonify({"success": False, "message": "No email provided"}), 400

    try:
        with sqlite3.connect("my_database.db") as conn:
            cursor = conn.cursor()

            # Check if the website exists
            cursor.execute("SELECT website_id FROM websites WHERE website_id = ?", (website_id,))
            existing = cursor.fetchone()
            if not existing:
                return jsonify({"success": False, "message": "Website not found."}), 404

            # Delete that one email
            cursor.execute(
                "DELETE FROM website_emails WHERE website_id = ? AND email = ?",
                (website_id, email_to_delete)
            )
            if cursor.rowcount == 0:
                return jsonify({
                    "success": False,
                    "message": f"Email '{email_to_delete}' not found or already deleted."
                }), 400

        return jsonify({"success": True, "message": "Email deleted successfully!"})

    except Exception as ex:
        return jsonify({
            "success": False,
            "message": f"Error deleting email: {ex}"
        }), 500


@websites_bp.route("/<int:website_id>/delete", methods=["POST"])
def delete_website(website_id):
    """
    Permanently deletes the given website and all its associated data.
    """

    print("\n\nDeleting website\n")

    try:
        with sqlite3.connect("my_database.db") as conn:
            cursor = conn.cursor()

            # Make sure the website exists
            cursor.execute("SELECT website_id FROM websites WHERE website_id = ?", (website_id,))
            existing = cursor.fetchone()
            if not existing:
                return jsonify({"success": False, "message": "Website not found."}), 404

            # Delete from "website_emails" first
            cursor.execute("DELETE FROM website_emails WHERE website_id = ?", (website_id,))

            # Delete the main record
            cursor.execute("DELETE FROM websites WHERE website_id = ?", (website_id,))
            # Alternatively, you could set 'active = 0' if you didn't truly want to remove it.

        return jsonify({"success": True, "message": "Website and all emails deleted successfully!"})

    except Exception as ex:
        return jsonify({
            "success": False,
            "message": f"Error deleting website: {ex}"
        }), 500
