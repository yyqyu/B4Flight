'''
Created on 22 Jun 2020

@author: aretallack
'''
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)

from datetime import datetime
from email.headerregistry import Address

import functools

from werkzeug.security import check_password_hash, generate_password_hash

from . import helpers
from .db import User
from .data_handling import sqa_session    #sqa_session is the Session object for the site


bp = Blueprint('auth', __name__, url_prefix='/auth')

def requires_login(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if session.get("userid") is None:
            return redirect(url_for("auth.login"))
        
        return view(**kwargs)
    return wrapped_view

def is_logged_in():
    if session.get("userid") is None:
        return False
    else:
        return True
    

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

        sess = sqa_session()
        
        error_msg = None
        
        if not username:
            error_msg = 'Please enter a username.'
        elif not passwd:
            error_msg = 'Please enter a password.'

        else:
            usr = sess.query(User).filter(User.Username == username).first()
            if usr is None:
                error_msg = 'Username does not exist'
            elif check_password_hash(usr.Password, passwd) == False:
                error_msg = 'Incorrect password'
            elif usr.Status_Pending == True:
                error_msg = "Your account hasn't been activated yet"
            elif usr.Status_Active == False:
                error_msg = "Your account is no longer active"
            
            else:
                session.clear()
                session['userid'] = usr.UserID
                session['username'] = usr.Username
                session['user_fname'] = usr.Firstname

                return redirect(url_for("home.index"))
        
        flash(error_msg)
        
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    session.clear()
    
    return redirect(url_for("auth.login"))
