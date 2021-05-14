import os

from flask import Flask, render_template

import logging
from logging.config import fileConfig
from logging.handlers import SMTPHandler

import ssl

#SET FLASK_APP=flightbriefing
#SET FLASK_ENV=development


def internal_server_error(e):
    """Shows custom error pages"""
    return render_template('errors/500.html'), 500

def page_not_found_error(e):
    """Shows custom error pages"""
    return render_template('errors/404.html'), 404

def forbidden_error(e):
    """Shows custom error pages"""
    return render_template('errors/403.html'), 403



def create_app(test_config=None):
    # create and configure the app
    import configparser

    app = Flask(__name__, instance_relative_config=True)

    # Custom Error Pages
    app.register_error_handler(500, internal_server_error)
    app.register_error_handler(404, page_not_found_error)
    app.register_error_handler(403, forbidden_error)
    
    # Configure logging using the logging.cfg file
    fileConfig(os.path.join(app.root_path,'logging.cfg'))


    # Read settings from flightbriefing.ini - may change this to use CONFIG.PY at some stage
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(app.root_path,'flightbriefing.ini'))
    secret_key = cfg.get('application','secret_key')
    mapbox_token = cfg.get('maps','mapbox_token')
    map_use_category_colours = cfg.get('maps','use_category_colours')
    map_default_category_colour = cfg.get('maps','default_category_colour')
    map_notam_opacity = cfg.get('maps','notam_opacity')
    map_hidden_notam_colour = cfg.get('maps','hidden_notam_colour')
    map_hidden_notam_opacity = cfg.get('maps','hidden_notam_opacity')
    map_flight_route_opacity = cfg.get('maps','flight_route_opacity')
    map_bounds_min_coords = (int(cfg.get('maps','limit_min_lon')), int(cfg.get('maps','limit_max_lat')))
    map_bounds_max_coords = (int(cfg.get('maps','limit_max_lon')), int(cfg.get('maps','limit_min_lat')))
    working_folder = os.path.join(app.instance_path, cfg.get('application','working_folder'))
    upload_archive_folder = os.path.join(app.instance_path, cfg.get('application','upload_archive_folder'))
    notam_archive_folder = os.path.join(app.instance_path, cfg.get('notam_import_ZA','archive_folder'))
    database_connect_string = cfg.get('database','connect_string')
    database_pool_recycle = int(cfg.get('database','pool_recycle'))
    default_home_aerodrome = cfg.get('defaults','home_aerodrome')
    default_home_radius = int(cfg.get('defaults','home_radius'))
    default_route_buffer = int(cfg.get('defaults','route_buffer'))
    default_map_radius_filter = int(cfg.get('defaults','map_radius_filter'))
    default_flight_route_colour = cfg.get('defaults', 'flight_route_colour')
    email_host = cfg.get('email','email_host')
    email_host_user = cfg.get('email','email_host_user')
    email_host_password = cfg.get('email','email_host_password')
    email_admin_name = cfg.get('email','email_admin_name')
    email_admin_address = cfg.get('email','email_admin_address')
    email_contactus_address = cfg.get('email', 'email_contactus_address')
    email_port = cfg.get('email','email_port')
    email_use_ssl = cfg.get('email','email_use_ssl') == '1'
    email_use_tls = cfg.get('email','email_use_tls') == '1'
    weather_sigmet_airmet_url_ZA = cfg.get('weather','sigmet_airmet_url_ZA')
    weather_metar_url_ZA = cfg.get('weather','metar_url_ZA')
    weather_taf_url_ZA = cfg.get('weather','taf_url_ZA')
    weather_sigmet_colour = cfg.get('weather','sigmet_colour')
    weather_sigmet_opacity = cfg.get('weather','sigmet_opacity')
    weather_airmet_colour = cfg.get('weather','airmet_colour')
    weather_airmet_opacity = cfg.get('weather','airmet_opacity')
    weather_metar_colour = cfg.get('weather','metar_colour')
    weather_metar_opacity = cfg.get('weather','metar_opacity')
    weather_taf_colour = cfg.get('weather','taf_colour')
    weather_taf_opacity = cfg.get('weather','taf_opacity')
    

    app.config.from_mapping(
        SECRET_KEY=secret_key,  #used to encode session cookie
        SESSION_COOKIE_HTTPONLY=True,   #don't allow session cookie to be accessed from scripting lang
        SESSION_COOKIE_SAMESITE='strict',   #only allow session cookie to be accessed from this site
        MAPBOX_TOKEN=mapbox_token,  #mapbox API token - from https://account.mapbox.com/access-tokens/create
        MAP_USE_CATEGORY_COLOURS=map_use_category_colours, #do we use the colours specified in QCode for NOTAM display
        MAP_DEFAULT_CATEGORY_COLOUR=map_default_category_colour, #if we don't use QCode colours, what colour should we use?
        MAP_NOTAM_OPACITY=map_notam_opacity, #Opacity to use on map for regular notams
        MAP_HIDDEN_NOTAM_COLOUR=map_hidden_notam_colour, # The colour to use on map for hidden notams
        MAP_HIDDEN_NOTAM_OPACITY=map_hidden_notam_opacity, # Opacity to use on map for hidden notams
        MAP_FLIGHT_ROUTE_OPACITY=map_flight_route_opacity, # The opacity to be used for the flight route
        MAP_BOUNDS_MIN_COORDS=map_bounds_min_coords, # The min bounds to limit the map to - South-West point
        MAP_BOUNDS_MAX_COORDS=map_bounds_max_coords, # The max bounds to limit the map to - North-East point
        WORKING_FOLDER=working_folder, #temp folder
        UPLOAD_ARCHIVE_FOLDER=upload_archive_folder, #Saved copies of uploaded route files - for debugging
        NOTAM_ARCHIVE_FOLDER=notam_archive_folder, #saved copied of NOTAM files - for debugging / historical 
        DATABASE_CONNECT_STRING=database_connect_string, #connection string to database
        DATABASE_POOL_RECYCLE=database_pool_recycle, #limit timeouts - refer to https://help.pythonanywhere.com/pages/UsingMySQL
        MAX_CONTENT_LENGTH=3*1024*1024, 
        DEFAULT_HOME_AERODROME=default_home_aerodrome, #Default home aerodrome in ICAO format - for users without this setting
        DEFAULT_HOME_RADIUS=default_home_radius, #Default radius around home aerodrome in ICAO format - for users without this setting
        DEFAULT_ROUTE_BUFFER=default_route_buffer, #Default route buffer in nm - for users without this setting
        DEFAULT_MAP_RADIUS_FILTER=default_map_radius_filter, #Default initial radius filter on map
        DEFAULT_FLIGHT_ROUTE_COLOUR=default_flight_route_colour, #Default colour for the flight rourt on the map - for users without this setting
        EMAIL_HOST = email_host, #Email host name
        EMAIL_HOST_USER = email_host_user, #Email host username
        EMAIL_HOST_PASSWORD = email_host_password, #Email host password
        EMAIL_ADMIN_NAME = email_admin_name, #The "friendly name" for the administrator
        EMAIL_ADMIN_ADDRESS = email_admin_address, #Email address for the administrator - mails are sent from here
        EMAIL_CONTACTUS_ADDRESS = email_contactus_address, #Email address to use for Contact Us
        EMAIL_PORT = email_port, #Email server port to use - needs to match the USE_SSL or USE_TLS
        EMAIL_USE_SSL = email_use_ssl, #Email - Use Secure Sockets Layer for email sending 
        EMAIL_USE_TLS = email_use_tls, #Email - Use Transport Layer Security for email sending
        WEATHER_SIGMET_AIRMET_URL_ZA = weather_sigmet_airmet_url_ZA, #URL for ZA Sigmets and Airmets
        WEATHER_METAR_URL_ZA = weather_metar_url_ZA, #URL for ZA Metars
        WEATHER_TAF_URL_ZA = weather_taf_url_ZA, #URL for ZA TAFs
        WEATHER_AIRMET_COLOUR = weather_airmet_colour, #Colour for AIRMETs on the map
        WEATHER_AIRMET_OPACITY = weather_airmet_opacity, #opacity for AIRMETs on the map
        WEATHER_SIGMET_COLOUR = weather_sigmet_colour, #colour for SIGMETs on the map
        WEATHER_SIGMET_OPACITY = weather_sigmet_opacity, #opacity for SIGMETs on the map
        WEATHER_METAR_COLOUR = weather_metar_colour, #Colour for METARs on the map
        WEATHER_METAR_OPACITY = weather_metar_opacity, #opacity for METARs on the map
        WEATHER_TAF_COLOUR = weather_taf_colour, #colour for TAF on the map
        WEATHER_TAF_OPACITY = weather_taf_opacity, #opacity for TAF on the map
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # Add a Mail Handler for error logging
    mail_handler = SMTPHandler(
        mailhost = (app.config['EMAIL_HOST'], app.config['EMAIL_PORT']),
        fromaddr = app.config['EMAIL_ADMIN_ADDRESS'],
        toaddrs = [app.config['EMAIL_ADMIN_ADDRESS']],
        subject = 'B4Flight Error',
        credentials = (app.config['EMAIL_HOST_USER'], app.config['EMAIL_HOST_PASSWORD']),
        secure = ())
    # Set it to only trigger on ERROR messages
    mail_handler.setLevel(logging.ERROR)
    mail_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s'))
    # Add the mail handler to the logger, so it automatically triggers on an ERROR log event
    app.logger.addHandler(mail_handler)

    # ensure the instance folder exists
    if not os.path.exists(app.instance_path):
        os.makedirs(app.instance_path)

    #Check that the working and archive folders exist - if not, create them
    if not os.path.exists(app.config['WORKING_FOLDER']):
        os.makedirs(app.config['WORKING_FOLDER'])

    if not os.path.exists(app.config['UPLOAD_ARCHIVE_FOLDER']):
        os.makedirs(app.config['UPLOAD_ARCHIVE_FOLDER'])

    if not os.path.exists(app.config['NOTAM_ARCHIVE_FOLDER']):
        os.makedirs(app.config['NOTAM_ARCHIVE_FOLDER'])

    from . import db
    db.init_app(app)
    
    from . import notam_import
    notam_import.init_app(app)

    from . import viewmap
    app.register_blueprint(viewmap.bp)
    
    from . import auth
    app.register_blueprint(auth.bp)

    from . import home
    app.register_blueprint(home.bp)

    from . import account_admin
    app.register_blueprint(account_admin.bp)

    from . import flightadmin
    app.register_blueprint(flightadmin.bp)

    from . import admin
    app.register_blueprint(admin.bp)
    
    from . import weather
    app.register_blueprint(weather.bp)

    #This is the SQLAlchemy session used across the application - allows for scoped sessions
    from .data_handling import sqa_session


    @app.teardown_appcontext
    def shutdown_session(exception=None):
        sqa_session.remove()


    return app

#-----Remove this for the Production Version
#if __name__ == "__main__":
#    x = create_app()
#    x.run(debug=True)
