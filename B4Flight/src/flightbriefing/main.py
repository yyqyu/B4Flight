'''
Created on 07 Jun 2020

@author: aretallack
'''
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from flightbriefing import helpers
from flightbriefing import notams

db_connect = helpers.read_db_connect()
eng = create_engine(db_connect)

def initialise_notam_db():
    notams.init_db(eng)
    notams.create_new_db()

            
    

def import_notams():
    notams.init_db(eng)
    file_name = '..\\working_files\\Summary.txt'
    
    brf,ntm = notams.parseNotamTextFile(file_name, 'ZA')
    
    Session = sessionmaker(bind=eng)
    session = Session()
    session.add(brf)
    session.commit()
    
    print(f'Completed - written {len(ntm)} NOTAMS')
    
    pass

#initialise_notam_db()
import_notams()