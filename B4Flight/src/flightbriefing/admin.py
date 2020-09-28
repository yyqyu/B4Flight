"""Handles Administration Functionality

This module contains views to allow an administrator to administer the app

Functionality is implemented using FLASK

"""

from datetime import datetime

from flask import (
    Blueprint, flash, render_template, request, session, url_for, current_app, abort
)

from sqlalchemy import func, and_

from . import helpers
from .auth import requires_login
from .db import User, Briefing
from .notam_import import import_notam_ZA, get_latest_CAA_briefing_date_ZA
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
    updated_date = get_latest_CAA_briefing_date_ZA()
    

    # Intialise the SQLAlchemy session we'll use
    sqa_sess = sqa_session()
    
    # Get the latest briefing
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    first_brief_id = sqa_sess.query(func.min(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)

    # Get stats for display on page - earliest briefing and number of briefings
    first_briefing = sqa_sess.query(Briefing).get(first_brief_id)
    briefing_count = sqa_sess.query(Briefing).count()
    

    # If updated_date is not None, we retrieved the date from the website
    if updated_date:
        # Is the B4Fligh briefing current?
        is_briefing_current = updated_date.date() <= briefing.Briefing_Date
        # Format the CAA date nicely
        updated_date_str = datetime.strftime(updated_date, '%Y-%m-%d')

    # Otherwise we had a problem
    else:
        is_briefing_current = False
        updated_date_str = None

    # Has the user asked to update the NOTAM briefing?
    if request.method == 'POST':
        if request.form['update']:

            # If the briefing is current, don't update it.
            if is_briefing_current == True:
                flash('The NOTAMS for ZA are already current - we have not updated them.', 'error')

            # Otherwise update it
            else:
                # Import the NOTAMS
                brf = import_notam_ZA(overwrite_existing_file=True)
                # If the update failed:
                if brf is None:
                    flash('Failed to update B4Flight with the latest briefing - check the log file', 'error')

                # If the update succeeded
                else:
                    flash(f'Updated B4Flight with briefing {brf.Briefing_Ref} dated {brf.Briefing_Date}.', 'success')
                    briefing = brf
                    is_briefing_current = True
        

    return render_template('admin/import_notams.html', briefing=briefing, notam_count=len(briefing.Notams), last_update=updated_date_str,
                           is_briefing_current=is_briefing_current, first_briefing=first_briefing, briefing_count=briefing_count)


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