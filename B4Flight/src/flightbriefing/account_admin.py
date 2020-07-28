'''
Created on 25 Jul 2020

@author: aretallack
'''

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
    
    sqa_sess = sqa_session()
    user = sqa_sess.query(User).get(session['userid'])

    home_aerodrome = UserSetting.get_setting(session['userid'], 'home_aerodrome') #sqa_sess.query(UserSetting).filter(and_(UserSetting.UserID ==  session['userid'], UserSetting.SettingName == "home_aerodrome")).first()
    home_radius = UserSetting.get_setting(session['userid'], 'home_radius') #sqa_sess.query(UserSetting).filter(and_(UserSetting.UserID ==  session['userid'], UserSetting.SettingName == "home_radius")).first()
    route_buffer = UserSetting.get_setting(session['userid'], 'route_buffer') #sqa_sess.query(UserSetting).filter(and_(UserSetting.UserID ==  session['userid'], UserSetting.SettingName == "route_buffer")).first()

    if request.method == "POST":

        errors = False
        
        if not request.form['firstname']: 
            flash('Please enter your First Name.', 'error')
            errors = True
        if not request.form['lastname']: 
            flash('Please enter your Last Name.', 'error')
            errors = True
        if not request.form['home_aerodrome']:
            flash('Please enter your Home Airfield.', 'error')
            errors = True
        elif sqa_sess.query(NavPoint).filter(NavPoint.ICAO_Code == request.form['home_aerodrome']).count() == 0:
            flash("We weren't able to find your homefield - please contact us.", 'error')
            errors = True
        
        if errors == True:
            return render_template('account/settings.html', user=user, 
                           home_aerodrome=request.form['home_aerodrome'], home_radius=request.form['home_radius'],
                           route_buffer=request.form['route_buffer'])
            
        user.Firstname = request.form['firstname']
        user.Lastname = request.form['lastname']
        home_aerodrome.SettingValue = request.form['home_aerodrome']

        if not request.form['home_radius'].isnumeric():
            flash("Your home aerodrome Radius didn't seem to be numeric - we defaulted it to 20nm.", 'error')
            home_radius.SettingValue = 20
        else:
            home_radius.SettingValue = request.form['home_radius']

        if not request.form['route_buffer'].isnumeric():
            flash("Your Route Buffer didn't seem to be numeric - we defaulted it to 5nm.", 'error')
            route_buffer.SettingValue = 5
        else:
            route_buffer.SettingValue = request.form['route_buffer']

        sqa_sess.commit()
        flash('Your details were successfully updated.','success')
    
    home_aerodrome = sqa_sess.query(UserSetting).filter(and_(UserSetting.UserID ==  session['userid'], UserSetting.SettingName == "home_aerodrome")).first()
    home_radius = sqa_sess.query(UserSetting).filter(and_(UserSetting.UserID ==  session['userid'], UserSetting.SettingName == "home_radius")).first()
    route_buffer = sqa_sess.query(UserSetting).filter(and_(UserSetting.UserID ==  session['userid'], UserSetting.SettingName == "route_buffer")).first()
    
    return render_template('account/settings.html', user=user, 
                           home_aerodrome=home_aerodrome.SettingValue, home_radius=home_radius.SettingValue, route_buffer=route_buffer.SettingValue)
