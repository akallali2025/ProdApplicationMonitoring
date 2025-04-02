import os
import sqlite3
import requests
import pytz
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from flask import render_template, current_app

# ----------------------------
# Environment Variables & Time
# ----------------------------
est_timezone = pytz.timezone('America/Toronto')
url_check_time = int(os.environ.get('URL_CHECK_TIME', 2))
email_check_time = int(os.environ.get('EMAIL_CHECK_TIME', 3))

# A refresh URL 

refresh_url = os.environ.get('REFRESH_URL', "https://monitoring-prod-apps.azurewebsites.net/")




class URLStatus:
    """
    Manages:
      - Loading config (mute_all, work_hours_start/end) from DB,
      - Loading websites (active/inactive) + their emails,
      - Checking site statuses (unless muted) and building HTML,
      - Sending 'Site Down' emails within work hours.
    """

    def __init__(self, db_path="my_database.db"):
        self.db_path = db_path

        # Track which URLs are down { url: datetime_when_it_went_down }
        self.down_urls = {}
        # Track how many emails have been sent per URL { url: count }
        self.emails_sent = {}

        # url_dict[url] = { "name": <str>, "active": <int>, "website_id": <int> }
        self.url_dict = {}
        # email_dict[url] = [email1, email2, ...]
        self.email_dict = {}

        # Email settings 
        self.smtp_server = "email-smtp.ca-central-1.amazonaws.com"
        self.smtp_port = 587
        self.smtp_username = "AKIA4DJHEGSUFLYWCP6B"
        self.smtp_password = "BOas76+n7Cke7TErhAEX6zEyozoW0RvQtovn+kWGffoz"
        self.email_from = "ssc.rsaarcher.donotreply-nepasrepondre.rsaarcher.ssc@ssc-spc.gc.ca"
        self.email_to = "abdelmonaam.kallali@ssc-spc.gc.ca"


        self.html = ""         # Holds the generated HTML table
        self.current_time = "" # For last tested

        # Global config
        self.config = {}  # e.g. {"work_hours_start":7, "work_hours_end":17, "mute_all":0}

        # Initial load
        self.load_config()
        self.load_data_from_db()

    def load_config(self):
        """
        Pulls the config row (work_hours_start, work_hours_end, mute_all) from DB.
        If not found, uses default {7,17,0}.
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT work_hours_start, work_hours_end, mute_all
            FROM config
            LIMIT 1
        """)
        row = cur.fetchone()
        conn.close()

        if row:
            self.config = {
                "work_hours_start": row[0],
                "work_hours_end":   row[1],
                "mute_all":         row[2]
            }
        else:
            # If no config row, just default
            self.config = {
                "work_hours_start": 7,
                "work_hours_end":   17,
                "mute_all":         0
            }

    def load_data_from_db(self):
        """
        Loads all rows from 'websites' (including inactive),
        plus all emails from 'website_emails'.
        """
        self.url_dict.clear()
        self.email_dict.clear()

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # websites (active/inactive)
        self._website_id_map = {}
        self._url_id_map = {}

        cur.execute("""
            SELECT website_id, url, name, active
            FROM websites
        """)
        for (wid, url, name, active) in cur.fetchall():
            self.url_dict[url] = {
                "name": name,
                "active": active,
                "website_id": wid
            }
            self._website_id_map[wid] = url
            self._url_id_map[url] = wid

        # website_emails
        cur.execute("""
            SELECT website_id, email
            FROM website_emails
        """)
        for (wid, email) in cur.fetchall():
            if wid in self._website_id_map:
                the_url = self._website_id_map[wid]
                self.email_dict.setdefault(the_url, []).append(email)

        conn.close()

    def update_last_tested(self, url):
        """
        Save the current time to 'last_tested' for the given URL .
        Update 
        """
        if url not in self._url_id_map:
            return  # unknown or not loaded

        wid = self._url_id_map[url]
        now_str = datetime.now(est_timezone).strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            UPDATE websites
            SET last_tested = ?
            WHERE website_id = ?
        """, (now_str, wid))
        conn.commit()
        conn.close()

    #Test URL gets called every 2 min from the scheduled job 
    def test_urls(self):
        """
        1) Reload config + websites from DB,
        2) If mute_all=1 => all sites paused,
        3) If site is inactive => site paused,
        4) Otherwise do requests.get,
        5) Build HTML table with status/pause icons.
        """
        self.load_config()
        self.load_data_from_db()

        self.html = """
        <table id="server-status-table" style="border-collapse: collapse;">
            <tr>
                <th style="border:1px solid black; padding:5px; cursor: pointer;">URL</th>
                <th style="border:1px solid black; padding:5px; text-align:center;">Status</th>
                <th style="border:1px solid black; padding:5px; text-align:center;">Status Code</th>
                <th style="border:1px solid black; padding:5px; text-align:center;">Last Tested</th>
                <th style="border:1px solid black; padding:5px; text-align:center;">Settings</th>
            </tr>
        """

        mute_all = self.config.get("mute_all")

        for url, info in self.url_dict.items():
            site_name = info["name"] or url
            site_active = info["active"]
            wid = info["website_id"]

            # If MUTE_ALL or site is inactive => pause
            if mute_all == 1 or site_active == 0:
                status_icon = "&#10073;&#10073;"  # pause
                status_code = "--"
                self.current_time = datetime.now(est_timezone).strftime("%Y-%m-%d %H:%M:%S")

                self.html += f"""
                <tr>
                    <td style='border:1px solid black; padding:5px; width:60%;'>
                        <a href='{url}'>{site_name}</a>
                    </td>
                    <td style='border:1px solid black; padding:5px; text-align:center;'>
                        {status_icon}
                    </td>
                    <td style='border:1px solid black; padding:5px; text-align:center;'>
                        {status_code}
                    </td>
                    <td style='border:1px solid black; padding:5px;'>
                        {self.current_time}
                    </td>
                    <td style='border:1px solid black; padding:5px; text-align:center;'>
                        <!-- Replaced 'Settings' with a gear icon + extra class -->
                        <button class="site-settings-btn settings-button" 
                                data-website-id="{wid}" 
                                title="Edit Website">
                            &#9881;
                        </button>
                    </td>
                </tr>
                """
                continue

            # Site is active + not globally muted => do the HTTP check
            #TODO call send_email down from here. check database first. 
            try:
                resp = requests.get(url, verify=False, timeout=5)
                status_code = resp.status_code
                status_icon = """<img src="../static/green_light.jpg" alt="Green" width="20px"/>"""
                if status_code != 200:
                    status_icon = """<img src="../static/red_light.jpg" alt="Red" width="20px"/>"""
                    if url not in self.down_urls:
                        self.down_urls[url] = datetime.now(est_timezone)
                else:
                    # If previously down, remove it
                    self.down_urls.pop(url, None)
                    self.emails_sent.pop(url, None)

            except requests.exceptions.RequestException:
                status_code = "N/A"
                status_icon = """<img src="../static/red_light.jpg" alt="Red" width="20px"/>"""
                if url not in self.down_urls:
                    self.down_urls[url] = datetime.now(est_timezone)
            
            #update_last tested should be updateding database. 
            self.update_last_tested(url)

            self.current_time = datetime.now(est_timezone).strftime("%Y-%m-%d %H:%M:%S")
            self.html += f"""
            <tr>
                <td style='border:1px solid black; padding:5px; width:60%;'>
                    <a href='{url}'>{site_name}</a>
                </td>
                <td style='border:1px solid black; padding:5px; text-align:center;'>
                    {status_icon}
                </td>
                <td style='border:1px solid black; padding:5px; text-align:center;'>
                    {status_code}
                </td>
                <td style='border:1px solid black; padding:5px;'>
                    {self.current_time}
                </td>
                <td style='border:1px solid black; padding:5px; text-align:center;'>
                    <button class="site-settings-btn settings-button" 
                            data-website-id="{wid}" 
                            title="Edit Website">
                        &#9881;
                    </button>
                </td>
            </tr>
            """

        self.html += "</table>"

    def send_email_down(self, url):
        """
        Send a 'Site Down' email for the URL, but only if the current local hour is
        within [work_hours_start, work_hours_end).
        #TODO This is not getting grom db
        #TODO if email is sent increase int on db for 'total_emails_sent' and ensure only 1 email sends per day
        #TODO reset int every 24h
        """
        # conn = sqlite3.connect(self.db_path)
        # cur = conn.cursor()
        # cur.execute("""
        #     SELECT work_hours_start, work_hours_end, mute_all
        #     FROM config
        #     LIMIT 1
        # """)
        # row = cur.fetchone()
        # conn.close()

        now_local = datetime.now(est_timezone)
        current_h = now_local.hour
        start_h = self.config.get("work_hours_start")
        end_h   = self.config.get("work_hours_end")

        # If outside [start_h, end_h), skip
        if not (start_h <= current_h < end_h):
            print(f"Skipping email for {url}, it's outside work hours.")
            return

        if (self.config.get("mute_all") == 1):
            return
        
        all_emails = self.email_dict.get(url, [])
        if not all_emails:
            # No emails => do nothing
            return

        # Build body
        down_since = self.down_urls[url].strftime("%Y-%m-%d %H:%M:%S")
        site_name = self.url_dict.get(url, {}).get("name", url)

        msg_body = f"""
        The following site is down:<br>
        <a href="{url}">{site_name}</a><br>
        <p>Time of initial detection: {down_since}</p>
        <p>Please check as soon as possible.</p>
        """

        msg = MIMEText(msg_body, "html")
        msg["Subject"] = "Site Down Notification"
        msg["From"] = self.email_from
        msg["To"] = all_emails[0]  # or use ", ".join(all_emails)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)

                server.sendmail(self.email_from, all_emails, msg.as_string())
                server.quit()
            print(f"Email sent: {url} is down.")
        except Exception as e:
            print(f"Email failed for {url}: {e}")

        # Track how many we've sent
        #TODO track how many we have sent through db
        self.emails_sent[url] = self.emails_sent.get(url, 0) + 1


# Create a global instance
CheckStatus = URLStatus(db_path="my_database.db")

# Basic HTML placeholder
initial_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>App Monitor</title>
    <link rel="icon" href="../static/monitoring_title.jpeg" type="image/x-icon">
</head>
<body>
    <h1>Testing x Cloud Apps</h1>
    <h2><img src="../static/Logo.png" alt="Logo" width="200px" height="100"/>
        Still Initializing - The statuses will be updated shortly
    </h2>
</body>
</html>
"""

def init_html():
    refresh_secs = (60 * url_check_time) + 40
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <title>App Monitor</title>
    <link rel="icon" href="./static/monitoring_title.jpeg" type="image/x-icon">
    <meta http-equiv="refresh" content="{refresh_secs}" />
</head>
<body>
    <h1><img src="./static/Logo.png" alt="Logo" width="200px" height="100"/>Testing</h1>
    """

#runs every two min
'''

'''
def update_html():
    """
    Render the 'status.html' template with the table HTML from test_urls().
    """
    print("update_html called\n\n")
    CheckStatus.test_urls()
    print("update_html called -> CheckStatus.test_urls called\n\n")

    table_html = CheckStatus.html
    refresh_secs = (60 * url_check_time) + 40
    refresh_ms = (url_check_time * 60000) + 60000

    print(current_app.config['test_varaible'])
    print("Testing variable!")


    return render_template(
        "status.html",
        table_html=table_html,
        refresh_seconds=refresh_secs,
        refresh_ms=refresh_ms
    )

#Runs every 3 min 
def check_email():
    """
    Check any down URLs. If they've been down longer than X hours => send another email,
    provided it's during work hours.
    """
    print("check_email invoked")
    now_local = datetime.now(est_timezone)

    for durl in CheckStatus.down_urls:
        down_start = CheckStatus.down_urls[durl]
        hours_down = (now_local - down_start).total_seconds() / 3600.0
        emails_sent = CheckStatus.emails_sent.get(durl, 0)

        if hours_down > emails_sent:
            CheckStatus.send_email_down(durl)

