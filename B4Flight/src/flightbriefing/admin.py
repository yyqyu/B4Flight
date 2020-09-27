"""Handles Administration Functionality

This module contains views to allow an administrator to administer the app

Functionality is implemented using FLASK

"""

from datetime import datetime

from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for, current_app, make_response, abort
)

from sqlalchemy import func, and_

import requests
import configparser
import os

from . import helpers
from .auth import requires_login
from .db import User, UserSetting, NavPoint, Briefing
from .data_handling import sqa_session    #sqa_session is the Session object for the site


bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/import_notams_ZA', methods=('GET', 'POST'))
@requires_login
def import_notams_ZA():
    """Implements html page that allows administrator to import NOTAMS
    
    """
    if session['user_admin'] == False:
        abort(403)
    
    # Check what the latest NOTAM date is per the CAA website 
    
    # What URL do we need to check this on?
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(current_app.root_path, 'flightbriefing.ini'))
    update_url = cfg.get('notam_import_ZA', 'caa_updated_url')
    
    # Check the URL, streaming it to limit impact
    resp = requests.get(update_url, stream=True)
    
    updated_date_str= None
    
    # Did we succeed in retrieving the page?  200=success
    if resp.status_code == 200:
        check = True
        
        # How is page encoded?
        enc = resp.encoding
        
        # Process page one line at a time
        for line in resp.iter_lines():
            # Does the line contain the text 'Last update'?
            if 'LAST UPDATE' in line.decode(enc).upper():
                start = line.decode(enc).upper().find('LAST UPDATE')
                end = line.decode(enc).upper().find('</SPAN>', start)
                found = line.decode(enc)[start:end]
                
                # Typical contents of variable "found":
                # Last update&#58;&#160;&#160;25 <span lang="EN-US" style="font-family&#58;calibri, sans-serif;font-size&#58;11pt;">September 2020
                # Extract the day of month - in this case the "25": &#160;25 <span
                dom = found[:found.upper().rfind('<SPAN')]
                dom = dom[dom.upper().rfind(';')+1:].strip()
                # Extract the Month + Year:
                month_year = found[found.rfind('>')+1:]
                month, year = month_year.split(' ')
                updated_date = datetime.strptime(f'{dom} {month} {year}', '%d %B %Y')
                updated_date_str = datetime.strftime(updated_date, '%Y-%m-%d')
                resp.close()
                break
        
    else:
        check = False


    # Intialise the SQLAlchemy session we'll use
    sqa_sess = sqa_session()
    
    # Get the latest briefing
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)

    if updated_date:
        is_briefing_current = updated_date.date() <= briefing.Briefing_Date
    else:
        is_briefing_current = False

    return render_template('admin/import_notams.html', briefing=briefing, notam_count=len(briefing.Notams), last_update=updated_date_str,
                           is_briefing_current=is_briefing_current)


@bp.route('/user_list', methods=('GET', 'POST'))
@requires_login
def user_list():
    """Implements html page that allows administrator to view all users and administer them
    
    """
    if session['user_admin'] == False:
        abort(403)

    # Retrieve all Users
    sqa_sess = sqa_session()
    users = sqa_sess.query(User).all()

    return render_template('admin/user_list.html', users=users)