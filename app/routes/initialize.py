# Initialize the main page 

from flask import (Flask, render_template_string, render_template, send_from_directory, url_for, request,redirect, Blueprint)

initialize_bp = Blueprint("initialize_bp", __name__)
