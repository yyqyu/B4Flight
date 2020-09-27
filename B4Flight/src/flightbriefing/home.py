"""Handles User Home Page

This module contains views to manage the home page

Functionality is implemented using FLASK

"""

from flask import (
    Blueprint, render_template, redirect, request, session, url_for, current_app, flash
)
from sqlalchemy import func, and_

from datetime import datetime, timedelta

from .db import Briefing, Notam, FlightPlan, FlightPlanPoint, User, UserSetting, NavPoint, ContactMessage
from .notams import get_new_deleted_notams
from .auth import is_logged_in
from .data_handling import sqa_session    #sqa_session is the Session object for the site
from .flightplans import filter_point_notams

bp = Blueprint('home', __name__)

@bp.route('/', methods=('GET', 'POST'))
def index():
    """Implements html home page dashboard
    
    """

    # Redirect users not logged in to generic index/welcome page
    if is_logged_in() == False:
        return render_template("index.html")

    # Intialise the SQLAlchemy session we'll use
    sqa_sess = sqa_session()
    
    # Get the latest briefing
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)
    
    # Load the flights for this user- newest to oldest
    flights = sqa_sess.query(FlightPlan).filter(and_(FlightPlan.UserID == session.get("userid"), FlightPlan.Is_Deleted == False)).order_by(FlightPlan.FlightplanID.desc()).limit(5).all()
    
    # Show what's changed over the last week
    prev_briefing, new_notams, deleted_notams = get_new_deleted_notams(datetime.utcnow().date() - timedelta(days=7))
    lw_briefing_date = prev_briefing.Briefing_Date
    
    # NOTAMS within NM of home
    home_aerodrome = UserSetting.get_setting(session['userid'], "home_aerodrome").SettingValue
    home_radius = UserSetting.get_setting(session['userid'], "home_radius").SettingValue
    home_navpt = sqa_sess.query(NavPoint).filter(NavPoint.ICAO_Code == home_aerodrome).first()
    if home_navpt is not None:
        home_notams = len(filter_point_notams(home_navpt.Longitude, home_navpt.Latitude, home_radius))
    else:
        home_notams = None
    
    return render_template("home.html", briefing=briefing, notam_count=len(briefing.Notams), flights=flights, 
                           last_wk_brief_date=lw_briefing_date, new_notams=new_notams, deleted_notams=deleted_notams,
                           home_notams=home_notams, home_radius=home_radius, home_aerodrome=home_aerodrome)
    

@bp.route('/contact', methods=('GET', 'POST'))
def contact():
    """Implements Contact Us Page
    
    """
    # First get name and e-mail address if user is logged in - if not logged in they return None
    firstname=session.get("user_fname")
    email=session.get("user_email")

    # If we're processing a form
    if request.method == 'POST':
        
        # Get the message details
        firstname = request.form['firstname']
        email = request.form['email']
        message = request.form['message']
        
        # Validate input - this is a backup to client-side validations
        if not firstname:
            flash('Please enter your name - so we can call you by name', 'error')
        elif not email:
            flash('Please enter your email address', 'error')
        elif not message:
            flash('Please enter a message', 'error')
        # Validations Passed - Process the form
        else:
            userid = session.get('userid')
            # Create the message and send the mail.  We don't need the msg object
            result, msg = ContactMessage.send_message(firstname, email, message, user_id = userid)
            return redirect(url_for('home.contactsuccess', result=result, firstname=firstname, contact_email=current_app.config['EMAIL_CONTACTUS_ADDRESS']))
    
    return render_template("contact.html", firstname=firstname, email=email, contact_email=current_app.config['EMAIL_CONTACTUS_ADDRESS'])

@bp.route('/contactsuccess', methods=('GET', 'POST'))
def contactsuccess():
    """Shows the html page that confirmed User has successfully contacted us."""
    
    if request.method == 'GET':
        result = request.args.get('result')
        firstname = request.args.get('firstname')
        contact_email = request.args.get('contact_email')
             
    return render_template('contact_success.html', result=result, firstname=firstname, contact_email=contact_email)

@bp.route('/gettingstarted', methods=('GET', 'POST'))
def gettingstarted():
    """Shows the Getting Started page
    
    """

    return render_template("help/getting_started.html")
