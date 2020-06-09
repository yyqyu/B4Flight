'''
Created on 07 Jun 2020

@author: aretallack
'''

def read_db_connect():
    import configparser
    
    print("Configuring the application")
    cfg = configparser.ConfigParser()
    cfg.read('flightbriefing.ini')
    db_connect = cfg.get('database','connect_string')
    print(db_connect)

    return db_connect