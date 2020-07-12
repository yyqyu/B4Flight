'''
Created on 13 Jun 2020

@author: aretallack
'''
import os

import click
from flask import current_app, g
from flask.cli import with_appcontext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

from flightbriefing import notams, db

import configparser
    
cfg = configparser.ConfigParser()
app_path = os.path.dirname(os.path.abspath( __file__ ))
cfg.read(os.path.join(app_path,'flightbriefing.ini'))
db_connect = cfg.get('database','connect_string')
pool_recycle = cfg.get('database','pool_recycle')

sqa_engine = create_engine(db_connect, pool_recycle=pool_recycle)
sqa_session = scoped_session(sessionmaker(bind=sqa_engine))

Base = declarative_base(bind=sqa_engine)


def create_db():
    cfg = configparser.ConfigParser()
    sql_script_folder = os.path.join(current_app.root_path, cfg.get('database','sql_script_folder'))

    notams.init_db(sqa_engine)
    notams.create_new_db(sql_script_folder)
    
    db.create_new_db()
    db.create_admin_user("artech@live.co.za")
