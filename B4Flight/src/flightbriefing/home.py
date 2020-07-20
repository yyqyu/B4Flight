'''
Created on 03 Jul 2020

@author: aretallack
'''
from flask import (
    Blueprint, g, redirect, render_template, request, session, url_for, current_app, flash
)
from sqlalchemy import func, and_

from datetime import datetime, timedelta

from .db import Briefing, Notam, FlightPlan, FlightPlanPoint, User
from .notams import get_new_deleted_notams
from .auth import is_logged_in
from .data_handling import sqa_session    #sqa_session is the Session object for the site

bp = Blueprint('home', __name__)

@bp.route('/', methods=('GET', 'POST'))
def index():

    #redirect users not logged in to generic index/welcome page
    if is_logged_in() == False:
        return render_template("index.html")

    #Intialise the SQLAlchemy session we'll use
    sqa_sess = sqa_session()
    
    #Get the latest briefing
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)
    
    #Load the flights for this user- newest to oldest
    flights = sqa_sess.query(FlightPlan).filter(FlightPlan.UserID == session.get("userid")).order_by(FlightPlan.FlightplanID.desc()).limit(5).all()
    
    #Show what's changed over the last week
    prev_briefing, new_notams, deleted_notams = get_new_deleted_notams(datetime.utcnow().date() - timedelta(days=7))
    lw_briefing_date = prev_briefing.Briefing_Date
    
    return render_template("home.html", briefing=briefing, notam_count=len(briefing.Notams), flights=flights, 
                           last_wk_brief_date=lw_briefing_date, new_notams=new_notams, deleted_notams=deleted_notams)