'''
Created on 22 Jun 2020

@author: aretallack
'''
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app, make_response
)

from email.headerregistry import Address

import functools

from werkzeug.security import check_password_hash

from . import helpers
from .db import User, UserSetting
from .data_handling import sqa_session    #sqa_session is the Session object for the site


bp = Blueprint('auth', __name__, url_prefix='/auth')

def requires_login(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):

        if is_logged_in():
            return view(**kwargs)
        else:
            return redirect(url_for("auth.login"))
        
    return wrapped_view

def is_logged_in():
    
    if session.get("username") is not None:
        uname=session.get("username")
    
    else:
        uname = request.cookies.get("remember_username")
        
    if uname:
        if log_user_in(uname) is None:
            return True
    
    session.clear()
    return False


def log_user_in(username, password=None):
    error_msg = None
    
    sess = sqa_session()

    usr = sess.query(User).filter(User.Username == username).first()
    if usr is None:
        error_msg = 'Username or password is incorrect'
    
    elif password is not None:
        if check_password_hash(usr.Password, password) == False:
            error_msg = 'Username or password is incorrect'
    
    if usr.Status_Pending == True:
        error_msg = "Your account hasn't been activated yet"
    
    if usr.Status_Active == False:
        error_msg = "Your account is no longer active"
    
    if error_msg is None:
        session.clear()
        session['userid'] = usr.UserID
        session['username'] = usr.Username
        session['user_fname'] = usr.Firstname
    
    return error_msg

@bp.route('/register', methods=('GET', 'POST'))
def register():

    if request.method == 'POST':
        
        username = request.form['username']
        email = request.form['email']
        passwd = request.form['password']

        sess = sqa_session()
        
        error_msg = None
        
        if not username:
            error_msg = 'Please enter a username.'
        elif not passwd:
            error_msg = 'Please enter a password.'
        elif len(passwd) < 8:
            error_msg = 'Please enter a password of at least 8 characters.'
        elif passwd != request.form['passwordcheck']:
            error_msg = 'You did not re-enter your password correctly.'
        elif not email:
            error_msg = 'Please enter your e-mail address.'
        
        elif sess.query(User).filter(User.Username == username).count() > 0:
            error_msg = 'This username already exists - please choose another.'
        
        elif sess.query(User).filter(User.Email == email).count() > 0:
            error_msg = 'This e-mail address is already associated with another user.'

        if error_msg is None:
            new_user = User()
            new_user.Username = request.form['username']
            new_user.Email = request.form['email']
            new_user.Password = request.form['password']
            new_user.Firstname = request.form['firstname']
            new_user.Lastname = request.form['lastname']
            
            setts = []
            setts.append(UserSetting(SettingName = "home_aerodrome", SettingValue = request.form['home_aerodrome']))
            setts.append(UserSetting(SettingName = "home_radius", SettingValue = 25))
            setts.append(UserSetting(SettingName = "route_buffer", SettingValue = 5))
            new_user.Settings = setts
            

            sess.add(new_user)
            sess.commit()
            
            activation_token = new_user.get_activation_token()
            msg_html = render_template('auth/activate_email.html', token=activation_token, user_fname=new_user.Firstname)
            msg_txt = render_template('auth/activate_email.html', token=activation_token, user_fname=new_user.Firstname)
            user_fullname = new_user.Firstname + ' ' + new_user.Lastname
            mail_to = Address(display_name = user_fullname.rstrip(), addr_spec = new_user.Email)
            mail_from = Address(display_name = current_app.config['EMAIL_ADMIN_NAME'], addr_spec = current_app.config['EMAIL_ADMIN_ADDRESS'])
            helpers.send_mail(mail_from, mail_to,'Confirm your registration wiht B4Flight', msg_txt, msg_html)
            
            return redirect(url_for("auth.regsuccess", firstname=new_user.Firstname))
        
        flash(error_msg)
        
    return render_template('auth/register.html')

@bp.route('/regsuccess', methods=('GET', 'POST'))
def regsuccess():
    
    if request.method == 'GET':
        user_fname = request.args.get('firstname')
             
    if user_fname is None:
        user_fname = "Visitor"
    
    return render_template('auth/regsuccess.html', firstname = user_fname)


@bp.route('/activate/<token>', methods=('GET', 'POST'))
def activate(token):
    usr_activated = User.activate_user(token)

    return render_template('auth/activated.html', firstname = usr_activated.Firstname)
        

@bp.route('/login', methods=('GET', 'POST'))
def login():
    
    if request.method == 'POST':
        
        username = request.form['username']
        passwd = request.form['password']
        remember = request.form.get('remember')

        error_msg = None
        
        if not username:
            error_msg = 'Please enter a username.'
        elif not passwd:
            error_msg = 'Please enter a password.'

        else:
            
            error_msg = log_user_in(username, passwd)
            if error_msg is None:
                ret = make_response(redirect(url_for("home.index")))

                if remember is not None:
                    ret.set_cookie('remember_username', username, max_age = 60*60*24*365, samesite = "strict", httponly=True)
                else:
                    ret.set_cookie('remember_username', "", max_age = 0, samesite = "strict", httponly=True)
                
                return ret#redirect(url_for("home.index"))
        
        flash(error_msg)
        
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    session.clear()
    #clear Cookie
    ret = make_response(redirect(url_for("auth.login")))
    ret.set_cookie('remember_username', "", max_age = 0, samesite = "strict")
    
    return ret
