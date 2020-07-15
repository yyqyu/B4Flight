'''
Created on 13 Jun 2020

@author: aretallack
'''
import os

from flask import current_app, g
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

import configparser
    
cfg = configparser.ConfigParser()
app_path = os.path.dirname(os.path.abspath( __file__ ))
cfg.read(os.path.join(app_path,'flightbriefing.ini'))
db_connect = cfg.get('database','connect_string')
pool_recycle = int(cfg.get('database','pool_recycle'))
#db_connect = current_app.config(['DATABASE_CONNECT_STRING'])
#pool_recycle = current_app.config(['DATABASE_POOL_RECYCLE'])

sqa_engine = create_engine(db_connect, pool_recycle=pool_recycle)
sqa_session = scoped_session(sessionmaker(bind=sqa_engine))

Base = declarative_base(bind=sqa_engine)
