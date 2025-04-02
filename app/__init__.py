from flask import Flask 
# from app.routes.route import main_bp
# from app.routes.initialize import initialize_bp
# from app.routes.websites import websites_bp

# database
from app.db import init_db

import os
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

# Import your blueprint
# from app.routes.route import main_bp
# from app.routes.websites import websites_bp

# Import the functions/variables that need to be scheduled
# from app.services.url_status import update_html, check_email, url_check_time, email_check_time
#TODO issue with having these from before we run the initialize db. 

def create_app():
    """
    Application factory function. 
    Creates, configures, and returns a Flask app instance.
    """
    app = Flask(__name__)
    #TODO get rid of test variable change server name  
    app.config['SERVER_NAME'] = ''
    app.config['APPLICATION_ROOT'] = '\\'

    print("Initialize Database")
    init_db(db_path="my_database.db", script_path="create_tables.sql")

    #TODO insert database 

    from app.services.url_status import update_html, check_email, url_check_time, email_check_time
    from app.routes.route import main_bp
    from app.routes.initialize import initialize_bp
    from app.routes.websites import websites_bp
    # Register your blueprint(s)
    app.register_blueprint(main_bp)
    app.register_blueprint(websites_bp, url_prefix="/websites")

    # Initialize and start the background scheduler
    scheduler = BackgroundScheduler()
    scheduler.start()

    # Schedule the jobs:
    #   - update_html() runs every 'url_check_time' minutes
    #   - check_email() runs every 'email_check_time' minutes
    
    
    #Issue with updating html app_context
    def scheduled_task():
        with app.app_context():
            update_html()


    scheduler.add_job(scheduled_task, 'interval', minutes=url_check_time)
    scheduler.add_job(check_email, 'interval', minutes=email_check_time)

    return app
