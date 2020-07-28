import os

from flask import Flask

#PythonAnywhere SQL Pass:
#pyth0n_Any

#SET FLASK_APP=flightbriefing
#SET FLASK_ENV=development

def create_app(test_config=None):
    # create and configure the app
    import configparser

    app = Flask(__name__, instance_relative_config=True)

    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(app.root_path,'flightbriefing.ini'))
    secret_key = cfg.get('application','secret_key')
    mapbox_token = cfg.get('maps','mapbox_token')
    working_folder = os.path.join(app.instance_path, cfg.get('application','working_folder'))
    upload_archive_folder = os.path.join(app.instance_path, cfg.get('application','upload_archive_folder'))
    notam_archive_folder = os.path.join(app.instance_path, cfg.get('notam_import_ZA','archive_folder'))
    database_connect_string = cfg.get('database','connect_string')
    database_pool_recycle = int(cfg.get('database','pool_recycle'))
    default_home_aerodrome = cfg.get('defaults','home_aerodrome')
    default_home_radius = int(cfg.get('defaults','home_radius'))
    default_route_buffer = int(cfg.get('defaults','route_buffer'))
    email_host = cfg.get('email','email_host')
    email_host_user = cfg.get('email','email_host_user')
    email_host_password = cfg.get('email','email_host_password')
    email_admin_name = cfg.get('email','email_admin_name')
    email_admin_address = cfg.get('email','email_admin_address')
    email_port = cfg.get('email','email_port')
    email_use_ssl = cfg.get('email','email_use_ssl') == '1'
    email_use_tls = cfg.get('email','email_use_tls') == '1'
    

    app.config.from_mapping(
        SECRET_KEY=secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='strict', 
        MAPBOX_TOKEN=mapbox_token,
        WORKING_FOLDER=working_folder,
        UPLOAD_ARCHIVE_FOLDER=upload_archive_folder,
        NOTAM_ARCHIVE_FOLDER=notam_archive_folder,
        DATABASE_CONNECT_STRING=database_connect_string,
        DATABASE_POOL_RECYCLE=database_pool_recycle,
        MAX_CONTENT_LENGTH=3*1024*1024,
        DEFAULT_HOME_AERODROME=default_home_aerodrome,
        DEFAULT_HOME_RADIUS=default_home_radius,
        DEFAULT_ROUTE_BUFFER=default_route_buffer,
        EMAIL_HOST = email_host,
        EMAIL_HOST_USER = email_host_user,
        EMAIL_HOST_PASSWORD = email_host_password,
        EMAIL_ADMIN_NAME = email_admin_name,
        EMAIL_ADMIN_ADDRESS = email_admin_address,
        EMAIL_PORT = email_port,
        EMAIL_USE_SSL = email_use_ssl,
        EMAIL_USE_TLS = email_use_tls,
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    if not os.path.exists(app.instance_path):
        os.makedirs(app.instance_path)

    #Check that the working folder and the archive folder exist - if not, create them
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

    from .data_handling import sqa_session


    @app.teardown_appcontext
    def shutdown_session(exception=None):
        sqa_session.remove()


    return app

#-----Remove this for the Production Version
#if __name__ == "__main__":
#    x = create_app()
#    x.run(debug=True)
