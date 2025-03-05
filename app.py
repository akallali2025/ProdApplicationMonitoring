import requests
import urllib3.exceptions
#from atlassian import Confluence
from datetime import datetime
import pytz
import smtplib
from email.mime.text import MIMEText
import subprocess
import pandas as pd
import os


from flask import (Flask, render_template_string, render_template)
from apscheduler.schedulers.background import BackgroundScheduler


app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()
est_timezone = pytz.timezone('America/Toronto')

# Environment Variables
url_check_time = int(os.environ.get('URL_CHECK_TIME', 2))
email_check_time = int(os.environ.get('EMAIL_CHECK_TIME', 3))
refresh_url = os.environ.get('REFRESH_URL', "https://app-monitorprod.azurewebsites.net/")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class URLStatus:

    def __init__(self, url_file_path):
        self.url_file_path = url_file_path
        self.down_urls = {} # Key: url, Value: time
        self.email_dict = {} # Key: url, Value: email
        self.emails_sent = {} # Key: url, Value: number of emails sent
        self.url_dict = self.excel_to_dict()
        self.smtp_server = "email-smtp.ca-central-1.amazonaws.com"
        self.smtp_port = 587
        self.smtp_username = "AKIA4DJHEGSUFLYWCP6B"
        self.smtp_password = "BOas76+n7Cke7TErhAEX6zEyozoW0RvQtovn+kWGffoz"
        self.email_from = "ssc.rsaarcher.donotreply-nepasrepondre.rsaarcher.ssc@ssc-spc.gc.ca"
        self.email_to = "abdelmonaam.kallali@ssc-spc.gc.ca"
        self.current_time = ""
        self.html = """
    <table id="server-status-table" style="border-collapse: collapse;">
        <tr>
            <th style="border: 1px solid black; padding: 5px; cursor: pointer;">URL</th>
            <th style="border: 1px solid black; padding: 5px;text-align:center;">Status</th>
            <th style="border: 1px solid black; padding: 5px;text-align:center;">Status Code</th>
            <th style="border: 1px solid black; padding: 5px;text-align:center;">Last Tested</th>
        </tr>
"""


    def excel_to_dict(self):
        df = pd.read_excel(self.url_file_path, header=1, names=["URL", "Website", "Email"]) #Load the Excel file into a pandas DataFrame
        #df = df.iloc[1:]# Remove the first row (Header)
        df = df.dropna()# skip if blank space
        #print(df)
        my_dict = dict(zip(df["URL"], df["Website"]))#combine the two column with the zip function to create a dict
        self.email_dict = dict(zip(df["URL"], df["Email"]))#combine the two column with the zip function to create a dict
        return my_dict
    

    def test_urls(self):
        self.html = """
    <table id="server-status-table" style="border-collapse: collapse;">
        <tr>
            <th style="border: 1px solid black; padding: 5px; cursor: pointer;">URL</th>
            <th style="border: 1px solid black; padding: 5px;text-align:center;">Status</th>
            <th style="border: 1px solid black; padding: 5px;text-align:center;">Status Code</th>
            <th style="border: 1px solid black; padding: 5px;text-align:center;">Last Tested</th>
        </tr>
"""

        for url in self.url_dict: # For all url in the dictionary
            try:
                response = requests.get(url, verify=False, timeout=5)
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0",
                    "Accept-Encoding": "*",
                    "Connection": "keep-alive"
                }
                status_code = response.status_code
                status = """<img src="images/green_light.jpg" alt="Green Light" width="20px"/>"""
                status_color = "white"
                
                if (status_code == 200):
                    # Clean up
                    self.down_urls.pop(url, None)
                    self.emails_sent.pop(url, None)
                else:
                    status = """<img src="images/red_light.jpg" alt="Red Light" width="20px"/>"""
                    if url not in self.down_urls:
                        self.down_urls[url] = datetime.now(est_timezone)
                
            except requests.exceptions.ConnectionError as e:
                status = """<img src="images/red_light.jpg" alt="Red Light" width="20px"/>"""
                status_color = "white"
                status_code = "N/A"

                if url not in self.down_urls:
                    self.down_urls[url] = datetime.now(est_timezone)
            except requests.exceptions.Timeout as e:
                status = """<img src="images/red_light.jpg" alt="Red Light" width="20px"/>"""
                status_color = "white"
                status_code = e.response.status_code if e.response else "Timeout"
                
                if url not in self.down_urls:
                    self.down_urls[url] = datetime.now(est_timezone)
            except requests.exceptions.HTTPError as e:
                status = """<img src="images/red_light.jpg" alt="Red Light" width="20px"/>"""
                status_color = "white"
                status_code = e.response.status_code if e.response else "Timeout"
                
                if url not in self.down_urls:
                    self.down_urls[url] = datetime.now(est_timezone)

            custom_url = self.url_dict.get(url, url)
            self.current_time = datetime.now(est_timezone).strftime("%Y-%m-%d %H:%M:%S")
            self.html += f"""
        <tr>
            <td style='border: 1px solid black; padding: 5px; width: 60%;'><a href='{url}'>{custom_url}</a></td>
            <td style='border: 1px solid black; padding: 5px; background-color:{status_color}; color:black;text-align:center;'>{status}</td>
            <td style='border: 1px solid black; padding: 5px; text-align:center;'>{status_code}</td><td style='border: 1px solid black; padding: 5px;'>{self.current_time}</td>
        </tr>\n""" #Format the html to add the status, picture, date and the urls as link
        self.html += "  </table>" # end the html formatting


    def send_email_down(self, url):
        message_body = f"""The following site is down:<br><a href="{url}">{self.url_dict[url]}</a><br>
        <p> Link to the Status of all other websites: <a href="https://app-monitorprod.azurewebsites.net/"> Server Status</a></p>
        <p> Time of initial detection: {self.down_urls[url].strftime("%Y-%m-%d %H:%M:%S")}"""
        message = MIMEText(message_body, "html")
        message["Subject"] = "Site Down Notification"
        message["From"] = self.email_from
        message["To"] = self.email_dict[url]
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.sendmail(self.email_from, self.email_dict[url].split(","), message.as_string())
            server.quit()

        # If emails were sent before, increment counter
        # Else, add it to the dictionary
        if (url in self.emails_sent):
            self.emails_sent[url] += 1
        else:
            self.emails_sent[url] = 1


CheckStatus = URLStatus("Url_List.xlsx")


# Set up initial html
def init_html():
    refresh_time = (60 * url_check_time) + 40
    global initial_html
    initial_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <title>App Monitor</title>
    <meta http-equiv="refresh" content="{refresh_time}" />
</head>
<body>
    <h1>Testing CIO Cloud Apps</h1>
    """


# Test URLs & Update HTML
def update_html():
    print("HTML update called")
    global initial_html
    CheckStatus.test_urls()
    init_html()
    initial_html += CheckStatus.html
    # WRITE TO PAGE TO SEE HOW SCRIPT IS APPENDED
    # TEST WITH EMULATOR
    # DOUBLE CHECK SYNTAX "location." or "window.location"
    refresh_time = (60000 * url_check_time) + 60000
    initial_html += """
    <button id="testButton">Test Now</button>

    <script>
        document.getElementById("testButton").addEventListener("click", function() {
            document.getElementById("testButton").disabled = true;

            var xhr = new XMLHttpRequest();
            xhr.open("GET", "/update", true);
            xhr.onreadystatechange = function() {
                if (xhr.readyState == 4 && xhr.status == 200) {
                    document.documentElement.innerHTML = xhr.responseText;

                    setTimeout(function() {
                        document.getElementById("testButton").disabled = false;
                    }, 60000);
                }
            };
            xhr.send();
        });

        setInterval(function() {
            location.reload();
        },"""
    initial_html += f""" {refresh_time});"""
    initial_html += """
    </script>
</body>
</html>
    """
    current_dir = os.getcwd()
    with open('index.html', 'w') as file:
        file.write(initial_html)
   # print(initial_html)
    return initial_html


# Initial HTML on deployment or restart
initial_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>App Monitor</title>
</head>
<body>
    <h1>Testing CIO Cloud Apps</h1>
    <h2>Still Initializing - The statuses will be updated shortly</h2>
</body>
</html>
"""


@app.route('/')
def index():
   print('Request for index page received')
   
   global initial_html
   return render_template_string(initial_html)


@app.route('/update')
def test_now():
    print("Test Now Button Clicked")
    new_html = update_html()
    return new_html


# Check urls that have been marked as down
# Check how many emails have been sent and compare it to how many hours have passed
# Aim to send repeat emails after every hour
# Send email if more hours than emails sent
def check_email():
    print("Check_email invoked")
    down_dict = CheckStatus.down_urls
    sent_emails = CheckStatus.emails_sent
 
    for durl in down_dict:
        print(durl)
        if durl in sent_emails:
            time_diff = datetime.now(est_timezone) - down_dict[durl]
            hours = time_diff.total_seconds() // 3600

            if (hours > (sent_emails[durl] - 1)):
                CheckStatus.send_email_down(durl)
        else:
            CheckStatus.send_email_down(durl)


# Schedule status checks and email updates
scheduler.add_job(update_html, 'interval', minutes=url_check_time)
scheduler.add_job(check_email, 'interval', minutes=email_check_time)


if __name__ == '__main__':
   app.run(debug=True)

# function_app redeploy