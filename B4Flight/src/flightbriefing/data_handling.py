'''
Created on 13 Jun 2020

@author: aretallack
'''
import os

import click
from flask import current_app, g
from flask.cli import with_appcontext
from sqlalchemy import create_engine


from flightbriefing import notams



def get_sqa_engine():
    if 'sqa_engine' not in g:
        g.sqa_engine = create_engine(current_app.config['DATABASE'])

    return g.sqa_engine


def create_db():
    import configparser
    
    sqa_engine = get_sqa_engine()

    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(current_app.root_path,'flightbriefing.ini'))
    sql_script_folder = os.path.join(current_app.root_path, cfg.get('database','sql_script_folder'))

    notams.init_db(sqa_engine)
    notams.create_new_db(sql_script_folder)


def close_db(e=None):
    db = g.pop('db_engine', None)

    if db is not None:
        db.close()
