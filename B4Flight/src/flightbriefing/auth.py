'''
Created on 22 Jun 2020

@author: aretallack
'''
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from flightbriefing import helpers
from flightbriefing.users import User
from flightbriefing.data_handling import sqa_session    #sqa_session is the Session object for the site


bp = Blueprint('auth', __name__, url_prefix='/auth')



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
            g.user_fname = new_user.Firstname
##
##        Need to send e-mail here
##            
            return redirect(url_for("auth.regsuccess", firstname=g.user_fname))
        
        flash(error_msg)
        
    return render_template('auth/register.html')

@bp.route('/regsuccess', methods=('GET', 'POST'))
def regsuccess():
    
    if request.method == 'GET':
        user_fname = request.args.get('firstname')
             
    if user_fname is None:
        user_fname = "Visitor"
    
    return render_template('auth/regsuccess.html', firstname = user_fname)


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

                return redirect(url_for("viewmap.viewmap"))
        
        flash(error_msg)
        
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    session.clear()
    
    return redirect(url_for("auth.login"))
