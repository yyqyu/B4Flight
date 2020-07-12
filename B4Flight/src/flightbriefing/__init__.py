
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
    working_folder = cfg.get('application','working_folder')
    upload_archive_folder = cfg.get('application','upload_archive_folder')
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
        MAPBOX_TOKEN=mapbox_token,
        WORKING_FOLDER=working_folder,
        UPLOAD_ARCHIVE_FOLDER=upload_archive_folder,
        MAX_CONTENT_LENGTH=3*1024*1024,
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
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from flightbriefing import viewmap
    app.register_blueprint(viewmap.bp)
    
    from flightbriefing import auth
    app.register_blueprint(auth.bp)

    from flightbriefing import home
    app.register_blueprint(home.bp)

    from flightbriefing.data_handling import sqa_session
    


    @app.teardown_appcontext
    def shutdown_session(exception=None):
        sqa_session.remove()

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return f'Hello, World! '

    return app

#-----Remove this for the Production Version
#if __name__ == "__main__":
#    x = create_app()
#    x.run(debug=True)
