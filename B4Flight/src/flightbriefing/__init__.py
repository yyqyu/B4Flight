
import os

from flask import Flask


def create_app(test_config=None):
    # create and configure the app
    import configparser

    app = Flask(__name__, instance_relative_config=True)

    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(app.root_path,'flightbriefing.ini'))
    db_connect = cfg.get('database','connect_string')
    secret_key = cfg.get('application','secret_key')
    mapbox_token = cfg.get('maps','mapbox_token')

    app.config.from_mapping(
        SECRET_KEY='dev', #secret_key 
        DATABASE=db_connect, #os.path.join(app.instance_path, 'flaskr.sqlite'),
        MAPBOX_TOKEN=mapbox_token,
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

    from . import maptest
    app.register_blueprint(maptest.bp)


    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return f'Hello, World! {db_connect}'

    return app

