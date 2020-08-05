"""Handles User Account Admin Functionality

This module contains views to manage user account administrative 
functionality, for example updating settings, changing passwords, etc.

Functionality is implemented using FLASK

"""

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app, make_response
)

from sqlalchemy import and_

from .db import User, UserSetting, NavPoint
from .auth import requires_login
from .data_handling import sqa_session    #sqa_session is the Session object for the site

bp = Blueprint('account_admin', __name__, url_prefix='/account')


@bp.route('/settings', methods=('GET', 'POST'))
@requires_login
def settings():
    """Implements html page that allows users to view and amend their settings.
    
    - Displays the settings stored in the database, returning defaults 
    if none exist
    - Validates and saves changes made by the user.  HTML page contains 
    client-side validations
    
    Does not allow for changing username, email address, password 
    
    """
    
    # Retrieve current user object
    sqa_sess = sqa_session()
    user = sqa_sess.query(User).get(session['userid'])
    
    # Retrieve UserSetting objects for available settings 
    home_aerodrome = UserSetting.get_setting(session['userid'], 'home_aerodrome') # Home Aerodrome 
    home_radius = UserSetting.get_setting(session['userid'], 'home_radius') # Radius around Home AD to show notams for, in nm
    route_buffer = UserSetting.get_setting(session['userid'], 'route_buffer') # Buffer along route to show notams for, in nm

    # If user is saving changes
    if request.method == "POST":

        errors = False #Used to flag any validation errors
        
        # Validate the required details were submitted on the form, 
        # adding error msgs to be shown to user
        if not request.form['firstname']: 
            flash('Please enter your First Name.', 'error')
            errors = True
        if not request.form['lastname']: 
            flash('Please enter your Last Name.', 'error')
            errors = True
        if not request.form['home_aerodrome']:
            flash('Please enter your Home Airfield.', 'error')
            errors = True
        
        # Ensure that the Home Aerodrome is a recognised CAA aerodrome
        elif sqa_sess.query(NavPoint).filter(NavPoint.ICAO_Code == request.form['home_aerodrome']).count() == 0:
            flash("We weren't able to find your home aerodrome - please contact us so we can add it.", 'error')
            errors = True
        
        # If there are errors, pass the captured details 
        # back to the form and show the html page with errors 
        if errors == True:
            return render_template('account/settings.html', user=user, 
                           home_aerodrome=request.form['home_aerodrome'], home_radius=request.form['home_radius'],
                           route_buffer=request.form['route_buffer'])
        
        # Otherwise no errors, so update the user's details
        user.Firstname = request.form['firstname']
        user.Lastname = request.form['lastname']
        home_aerodrome.SettingValue = request.form['home_aerodrome']

        # Numeric type is specified on the HTML form - this is a backup check,
        # and to avoid frustration to user, we simply apply the default setting if not numeric 
        if not request.form['home_radius'].isnumeric():
            flash(f"Your home aerodrome Radius didn't seem to be numeric - we defaulted it to {current_app.config['DEFAULT_HOME_RADIUS']}nm.", 'error')
            home_radius.SettingValue = current_app.config['DEFAULT_HOME_RADIUS']
        # otherwise value is numeric so update setting
        else:
            home_radius.SettingValue = request.form['home_radius']

        # Numeric type is specified on the HTML form - this is a backup check,
        # and to avoid frustration to user, we simply apply the default setting if not numeric
        if not request.form['route_buffer'].isnumeric():
            flash(f"Your Route Buffer didn't seem to be numeric - we defaulted it to {current_app.config['DEFAULT_ROUTE_BUFFER']}nm.", 'error')
            route_buffer.SettingValue = current_app.config['DEFAULT_ROUTE_BUFFER']
        # otherwise value is numeric so update setting
        else:
            route_buffer.SettingValue = request.form['route_buffer']

        # Commit changes and add a flask FLASH message to show success
        sqa_sess.commit()
        flash('Your details were successfully updated.','success')
    
    
    return render_template('account/settings.html', user=user, 
                           home_aerodrome=home_aerodrome.SettingValue, home_radius=home_radius.SettingValue, route_buffer=route_buffer.SettingValue)