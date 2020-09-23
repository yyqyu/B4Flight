"""Handles User Registration and Authentication Functionality

This module contains views to allow users to register, login and logout
It also provides helper functions to check if a user is logged in,
and the 'requires_login' decorator

Functionality is implemented using FLASK

"""

from datetime import datetime

from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for, current_app, make_response
)

from email.headerregistry import Address

import functools

from werkzeug.security import check_password_hash
import jwt

from . import helpers
from .db import User, UserSetting, NavPoint
from .data_handling import sqa_session    #sqa_session is the Session object for the site


bp = Blueprint('auth', __name__, url_prefix='/auth')

def requires_login(view):
    """ Decorator to use for all views in this app that require a user to be logged in
    
    If user is not logged in, redirects the user the login page
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):

        if is_logged_in():
            return view(**kwargs)
        else:
            return redirect(url_for("auth.login"))
        
    return wrapped_view


def is_logged_in():
    """Function to check if a user is logged in
    
    First check if a username exists in the session, otherwise check if a username cookie was set
    Then validate that the user exists and is active, and set session details 
     
    Returns
    -------
    boolean
        indicates if user is logged in
    """
    uname = None
    
    # Does a username exist in the Session?
    if session.get("username") is not None:
        uname=session.get("username")
    
    # If not, check if one exists in the "Remember Me" Cookie
    else:
        # Cookie is encoded
        baked = request.cookies.get("_flightbriefing")
        if baked:
            try:
                uname = jwt.decode(baked, current_app.config['SECRET_KEY'], 'HS256')['username']
                
            except:
                current_app.logger.error(f'Invalid _flightbriefing COOKIE was processed: {baked}')
                uname = None
            
    # Try to validate the user is a username was found.  If successful, return TRUE
    if uname:
        if log_user_in(uname) is None: #This function returns login errors - if none exist login was OK
            return True
    
    # Not able to log user in, so clear session and return FALSE
    session.clear()
    return False


def log_user_in(username, password=None, login_from_session=True):
    """Function to log a user in
    
    Validates the username exists, validates password if supplied, 
    ensures user status is active and status is not pending (Pending means awiting registration confirmation)
    If login successful, set the Session variables  
     
    Parameters
    ----------
    username : str
        Username to validate
    password : str, optional
        If a password is supplied, user is logging in from Login form.  
        If no password, user is being logged in from a session variable or stored cookie
    login_from_session : bool, optional
        Is the user being logged in from a session variable?  Governs whether session is cleared or not
    
    Returns
    -------
    str
        LOGIN SUCCESS: None
        LOGIN FAILURE: Error message explaining why user was not logged in
    """
    error_msg = None
    
    sess = sqa_session()

    # Attempt to retrieve user object from database 
    usr = sess.query(User).filter(User.Username == username).first()
    
    # No user was found with that name
    if usr is None:
        error_msg = 'Username or password is incorrect'
    
    # If password supplied to function, check it against hashed password in DB
    elif password is not None:
        if check_password_hash(usr.Password, password) == False:
            error_msg = 'Username or password is incorrect'
    

        # If user is pending, they have not yet clicked the activation link mailed to them
        elif usr.Status_Pending == True:
            error_msg = "Your account hasn't been activated yet.  Please check your email for the activation link."
        # If user is not active, let them know.  This can be used to manage paid user subscriptions or abuse/spam 
        elif usr.Status_Active == False:
            error_msg = "Your account is no longer active.  Please contact us for help."
    
    # If no errors, user has logged in successfully.  Set the Session variables
    if error_msg is None:
        #If this is a login from a session variable, don't clear the session - just check user and store date 
        if login_from_session == False:
            session.clear()
        
        session['userid'] = usr.UserID
        session['username'] = usr.Username
        session['user_fname'] = usr.Firstname
        session['user_admin'] = usr.Access_Admin
        session['user_email'] = usr.Email

        # Update with last login date
        usr.Last_Login_Date = datetime.utcnow()
        sess.commit()
    
    return error_msg


def create_cookie_token(username):
    """Create the token for the remember-me cookie that saves the logged-in user
    Add some variability by adding the login date
    
    Parameters
    ----------
    username : str
        username to store in cookie
        
    Returns
    -------
    str
        encoded cookie token in UTF-8 format
    """ 
    
    # Encode the cookie using the JWT (JSON Web Token) library 
    logindate = datetime.strftime(datetime.utcnow(), '%Y-%m-%d %H-%M')
    tkn = jwt.encode({'username' : username, 'login_date' : logindate}, current_app.config['SECRET_KEY'], 'HS256').decode('utf-8')
    
    return tkn


@bp.route('/register', methods=('GET', 'POST'))
def register():
    """Implements html page that allows users to Register.
    
    - Displays the registration form 
    - Validates the information supplied.  HTML page contains 
    client-side validations
    - Adds user to database, and sends email with validation link
    
    """
    # Start with variables as None - this allows a blank register form to be displayed
    # if no user details have been entered yet 
    username = None
    email = None
    firstname = None
    lastname = None
    home_aerodrome = None
    
    # User has submitted details - process them
    if request.method == 'POST':
        
        username = request.form['username']
        email = request.form['email']
        passwd = request.form['password']
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        home_aerodrome = request.form['home_aerodrome']

        sess = sqa_session() #SQLAlchemy Session
        
        error_msg = None
        
        # Client-side validation checks all these. These validations are a backup
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
        elif not request.form['home_aerodrome']:
            error_msg = 'Please provide a home aerodrome.'
        
        # Check username doesn't already exist
        elif sess.query(User).filter(User.Username == username).count() > 0:
            error_msg = 'This username already exists - please choose another.'
        
        # Check e-mail address doesn't already exist
        elif sess.query(User).filter(User.Email == email).count() > 0:
            error_msg = 'This e-mail address is already associated with another user.'

        # Ensure that the Home Aerodrome is a recognised CAA aerodrome
        elif sess.query(NavPoint).filter(NavPoint.ICAO_Code == home_aerodrome).count() == 0:
            error_msg = "We weren't able to find your home aerodrome - please contact us so we can add it."

        # No errors, so process the user
        if error_msg is None:
            # Create User object
            new_user = User()
            new_user.Username = username
            new_user.Email = email
            new_user.set_password(passwd)
            new_user.Firstname = firstname
            new_user.Lastname = lastname
            
            # Create the settings - use Home Aerodrome as supplied, others use default values 
            setts = []
            setts.append(UserSetting(SettingName = "home_aerodrome", SettingValue = home_aerodrome))
            setts.append(UserSetting(SettingName = "home_radius", SettingValue = current_app.config['DEFAULT_HOME_RADIUS']))
            setts.append(UserSetting(SettingName = "route_buffer", SettingValue = current_app.config['DEFAULT_ROUTE_BUFFER']))
            new_user.Settings = setts
            
            # Add user and commit
            sess.add(new_user)
            sess.flush() # This gets the ID of the new user
            
            # Don't commit yet, until e-mail has been successfully sent
            
            # Create an activation token for the user
            activation_token = new_user.create_activation_token()
            # Create an HTML and a text e-mail body including the authentication token
            msg_html = render_template('emails/activate_email.html', token=activation_token, user_fname=new_user.Firstname)
            msg_txt = render_template('emails/activate_email.txt', token=activation_token, user_fname=new_user.Firstname)
            # Create the email addresses in python's Address format
            user_fullname = new_user.Firstname + ' ' + new_user.Lastname
            mail_to = Address(display_name = user_fullname.rstrip(), addr_spec = new_user.Email)
            mail_from = Address(display_name = current_app.config['EMAIL_ADMIN_NAME'], addr_spec = current_app.config['EMAIL_ADMIN_ADDRESS'])
            # Send the activation e-mail - BCC in the administrator
            was_mail_sent = helpers.send_mail(mail_from, mail_to,'Confirm your registration with B4Flight', msg_txt, msg_html, recipients_bcc=mail_from)
            
            # Only save the user if the registration e-mail is successfully sent
            if was_mail_sent == True:
                # Commit - user is created
                sess.commit()
    
                # Redirect to the Registration Success page
                return redirect(url_for("auth.regsuccess", firstname=new_user.Firstname))
        
            # Mail not sent - rollback and warn user
            else:
                sess.rollback()
                error_msg = "We encountered a problem sending you a confirmation e-mail - please contact us.  Your user has not been created."

        # If there were errors flash them 
        flash(error_msg, 'error')
        
        # show the template, using any info already filled in 
    return render_template('auth/register.html', username = username, 
            email = email, firstname = firstname,
            lastname = lastname, home_aerodrome = home_aerodrome)


@bp.route('/regsuccess', methods=('GET', 'POST'))
def regsuccess():
    """Shows the html page that confirmed User has successfully registered."""
    
    if request.method == 'GET':
        user_fname = request.args.get('firstname')
             
    if user_fname is None:
        user_fname = "Visitor"
    
    return render_template('auth/regsuccess.html', firstname = user_fname)


@bp.route('/activate/<token>', methods=('GET', 'POST'))
def activate(token):
    """Validate the link the user clicked and activate the user,
    returning any errors or show a success page"""
    
    # Validate the token, and activate the user if correctly validated
    usr_activated = User.activate_user(token)
    
    # if function returns None, it means link is not valid
    if usr_activated is None:
        
        # Flash a message and redirect to the register page 
        flash('The confirmation link you clicked on was not valid. Please check you copied it correctly.', 'error')
        return redirect(url_for('auth.register'))
    
    # if function returns "-1" the user is already activated 
    elif usr_activated == -1:
        
        #Flash a message and redirect to login screen
        flash('You have already confirmed your account - please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/activated.html', firstname = usr_activated.Firstname)
        

@bp.route('/login', methods=('GET', 'POST'))
def login():
    """Implements html page that allows users to Login.
    
    - Displays the login page
    - Validates the login details and return any errors 
    - Store user details to a cookie if Remember Me is ticked
    - Redirects to home page once logged in
    
    """
    
    # Process the form returned
    if request.method == 'POST':
        
        username = request.form['username']
        passwd = request.form['password']
        remember = request.form.get('remember')

        error_msg = None
        # Validate username and password supplied
        if not username:
            error_msg = 'Please enter a username.'
        elif not passwd:
            error_msg = 'Please enter a password.'

        # Username and password supplied - try to log in
        else:
            # The log_user_in function validates username and password 
            error_msg = log_user_in(username, passwd)
            
            # If the function returns "None", the details validated successfully 
            if error_msg is None:
                # First create the response, so that we can add the cookie to the headers
                next_page = make_response(redirect(url_for("home.index")))

                # If the "Remember Me" box is ticked, save user details in an encoded cookie
                if remember is not None:
                    tkn = create_cookie_token(username)
                    # Set the cookie on the 
                    next_page.set_cookie('_flightbriefing', tkn, max_age = 60*60*24*365, samesite = "strict", httponly=True)
                
                # If remember me not ticked, remove cookie by setting max_age to 0
                else:
                    next_page.set_cookie('_flightbriefing', "", max_age = 0, samesite = "strict", httponly=True)
                
                # Redirect user to the next page
                return next_page
        
        # We were not able to log user in - so flash message and return to login page
        flash(error_msg)
        
    return render_template('auth/login.html')


@bp.route('/forgotpass', methods=('GET', 'POST'))
def forgotpass():
    """Show html page allowing user to request a password reset.
    Once the request is submitted, validate username and send e-mail to user with reset link
    
    """
    # Process the form returned
    if request.method == 'POST':
        
        username = request.form['username']

        # Validate username supplied.  Client-side validation is performed - this is a backup to that
        if not username:
            flash('Please enter a username.')

        # Username supplied
        else:

            sess = sqa_session() #SQLAlchemy Session

            # Retrieve a user if one exists
            forgot_user = sess.query(User).filter(User.Username == username).first()
            
            # If a user exists, then send them an e-mail with a pwd recovery link
            if not forgot_user is None:

                # Create a password recovery token for the user
                recovery_token = forgot_user.create_recovery_token()
                
                # Create an HTML and a text e-mail body including the authentication token
                msg_html = render_template('emails/recover_pass.html', token=recovery_token, user_fname=forgot_user.Firstname)
                msg_txt = render_template('emails/recover_pass.txt', token=recovery_token, user_fname=forgot_user.Firstname)
                
                # Create the email addresses in python's Address format
                user_fullname = forgot_user.Firstname + ' ' + forgot_user.Lastname
                mail_to = Address(display_name = user_fullname.rstrip(), addr_spec = forgot_user.Email)
                mail_from = Address(display_name = current_app.config['EMAIL_ADMIN_NAME'], addr_spec = current_app.config['EMAIL_ADMIN_ADDRESS'])
                
                # Send the e-mail - BCC in the administrator
                was_mail_sent = helpers.send_mail(mail_from, mail_to,'Recover your B4Flight password', msg_txt, msg_html, recipients_bcc=mail_from)
                
                # If the mail wasn't sent, warn the user
                if was_mail_sent == False:
                    flash('We tried to send you a password reset mail but encountered a problem.  Please try again or contact us.', 'error')
                
                # Otherwise show a message and redirect to login page
                else:
                    flash("PASSWORD RESET: We've sent you an e-mail with password recovery instructions (assuming the username you entered exists).", "success")
                    return redirect(url_for('auth.login'))
            
            # Even though the user doesn't exist, we display the same message and redirect to login page
            else:
                flash("PASSWORD RESET: We've sent you an e-mail with password recovery instructions (assuming the username you entered exists).", "success")
                return redirect(url_for('auth.login'))

    # Show the html page to reset the password
    return render_template('auth/forgotpass.html')


@bp.route('/passreset/<token>', methods=('GET', 'POST'))
def passreset(token):
    """This function is run when the user clicks the password reset link in the e-mail
    Validate the link the user clicked and display the password reset screen.
    If link is not valid, show an error and redirect to login screen
    """

    # A POST request means the user has submitted the form with a new password
    if request.method == 'POST':
        
        username = request.form['username']
        passwd = request.form['password']
        passwdchk = request.form['passwordcheck']
        
        error_msg = None
        
        # Client-side validation checks all these. These validations are a backup
        if not username:
            error_msg = 'Please enter a username.'
        elif not passwd:
            error_msg = 'Please enter a password.'
        elif not passwdchk:
            error_msg = 'Please enter both passwords.'

        elif len(passwd) < 8:
            error_msg = 'Please enter a password of at least 8 characters.'

        elif passwd != passwdchk:
            error_msg = 'You did not re-enter your password correctly.'
        
        if error_msg:
            flash(error_msg, 'error')
            return render_template('auth/resetpass.html',username=username)
        
        
        # Form was validated - now reset the password
        
        sess = sqa_session() #SQLAlchemy Session

        # Retrieve the user
        forgot_user = sess.query(User).filter(User.Username == username).first()
        # Update password
        forgot_user.set_password(passwd)
        # Save to DB
        sess.commit()
        
        flash('Your password has been reset.  Please login', 'success')
        return redirect(url_for('auth.login'))
    
    # If not a POST then must be a GET - therefore this is the first click on the link
    else:
        # If there is no token, show an error msg and redirect to login form
        if token is None:
            flash('The poassword recovery link you clicked on was not valid.', 'error')
            return redirect(url_for('auth.login'))

        # Validate the token, and display password reset screen
        usr = User.validate_recovery_token(token)
    
        # if function returns None, it means link is not valid
        if usr is None:
            # Flash error message and redirect to the login page 
            flash('The poassword recovery link you clicked on was not valid. Please check you copied it correctly.', 'error')
            return redirect(url_for('auth.login'))
        
        # If function returns "-1" the link has expired
        elif usr == -1:
            # Flash error message and redirect to the login page
            flash('The poassword recovery link you clicked on has expired. Links are only valid for 24 hrs', 'error')
            return redirect(url_for('auth.login'))
        
        # Token is valid - show the password reset form 
        else:
            return render_template('auth/resetpass.html',username=usr.Username)



@bp.route('/logout')
def logout():
    """Implements function that logs users out of system
    """
    
    # Clear the session - so the user's details are "forgotten" 
    session.clear()
    
    # Clear the cookie by setting max_age to 0 - so user's details are also forgotten
    # First setup the redirect to the Login page, then add to the redirect 
    next_page = make_response(redirect(url_for("auth.login")))
    next_page.set_cookie('_flightbriefing', "", max_age = 0, samesite = "strict", httponly=True)
    
    return next_page
