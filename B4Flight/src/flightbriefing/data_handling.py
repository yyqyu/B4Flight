"""Module to create the connection to SQLAlchemy database,
setting up a SCOPED session - i.e. allows recycling of sessions across the app
and particularly across multiple threads
https://docs.sqlalchemy.org/en/13/orm/contextual.html

"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

import configparser

# Get the database configuration from the flightbriefing.ini file.
# We can't use the flask app settings as the app context won't have been created
# at the point when this module is imported     
cfg = configparser.ConfigParser()
app_path = os.path.dirname(os.path.abspath( __file__ ))
cfg.read(os.path.join(app_path,'flightbriefing.ini'))
db_connect = cfg.get('database','connect_string')
pool_recycle = int(cfg.get('database','pool_recycle'))

# Create the SQLAlchemy Engine
sqa_engine = create_engine(db_connect, pool_recycle=pool_recycle)
# Create the scoped session - this is used to create session objects across the app
sqa_session = scoped_session(sessionmaker(bind=sqa_engine))

Base = declarative_base(bind=sqa_engine)
