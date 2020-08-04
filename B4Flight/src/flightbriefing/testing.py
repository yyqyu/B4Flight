'''
Created on 07 Jun 2020

@author: aretallack
'''
import os
from sqlalchemy import create_engine, func, and_
from sqlalchemy.orm import sessionmaker 

from geojson import Polygon, Feature, FeatureCollection
import re

from flightbriefing import helpers
from flightbriefing import notams
from flightbriefing import flightplans

from flightbriefing import db
from flightbriefing.db import User, FlightPlan, FlightPlanPoint, Notam, Briefing

from polycircles import polycircles
from datetime import datetime, timedelta

from xml.etree.ElementTree import ElementTree as ET
import csv

db_connect = helpers.read_db_connect()
eng = create_engine(db_connect, pool_recycle=280)

#def initialise_notam_db():
#    notams.init_db(eng)
#    notams.create_new_db(eng)

            
    

def test_import_notams():
#    notams.init_db(eng)
    file_name = 'C:/Users/aretallack/git/B4Flight/B4Flight/src/instance/notam_archives/ZA_notam_2020-07-24.txt'
    
    brf = notams.parse_notam_text_file(file_name, 'ZA')
    
#    Session = sessionmaker(bind=eng)
#    session = Session()
#    session.add(brf)
#    session.commit()
#    
#    print(f'Completed - written {len(ntm)} NOTAMS')
#    
#    pass


def test_top_notams():
    Session = sessionmaker(bind=eng)
    session = Session()

    max_id = session.query(func.max(notams.Briefing.BriefingID)).first()
    print(max_id[0])

    ntm = session.query(notams.Notam).filter(and_(notams.Notam.BriefingID == max_id[0], notams.Notam.Q_Code_2_3 == 'WU')).limit(5).all()
    print(len(ntm))
    feat = []
    
    for x in ntm:
        if x.Bounded_Area:
            coords = helpers.convert_bounded_dms_to_dd(x.Bounded_Area, reverse_coords=True)
#            print(coords)
        
            poly=Polygon([coords])
            print(poly)
            feat.append(Feature(geometry=poly, properties={'fill':'#00ff80', 'fill-opacity':0.4, 'Notam-Ref':x.Notam_Number}))
    
    y=FeatureCollection(feat)
    print(y)
#    for y in ntm[0].Bounded_Area.split(" "):
#        x = y.split(",")
#        print(f'{x[0]} = {helpers.convertDmsToDd(x[0])}')
        #x=helpers.convertDmsToDd(y[0])



def test_circles():
    Session = sessionmaker(bind=eng)
    session = Session()

    max_id = session.query(func.max(notams.Briefing.BriefingID)).first()
    print(max_id[0])

    ntm = session.query(notams.Notam).filter(notams.Notam.NotamID.in_([1,4])).all()
    for row in ntm:
        print(row.Notam_Number, row.Radius, row.Bounded_Area, row.is_circle(), row.circle_bounded_area())



def initialise_user_db():
    db.init_db(eng)
    db.create_new_db()
    db.create_admin_user('artech@live.co.za')


#initialise_notam_db()
#import_notams()

#test_top_notams()
#test_circles()
#polycircle = polycircles.Polycircle(latitude=-26, longitude=30, radius=1000, number_of_vertices=20)
#print(helpers.convert_dd_to_dms(-10.1010, -10.1010))

#initialise_user_db()

def test_GPX():
    fname="C:\\Users\\aretallack\\git\\B4Flight\\B4Flight\\src\\upload_archives\\2__20200626102054920032__Flight_Test_FAGM-FAHG-FASC-FAMB-FAGC-FAGM.gpx"
    print(os.path.exists(fname))
    fpls = flightplans.read_gpx_file(fname)
    for fpl in fpls:
        print(fpl.Flight_Name)
        for pt in fpl.FlightPlanPoints:
            print(pt.Longitude, pt.Latitude, pt.Elevation)

    geo=flightplans.generate_flight_geojson(fpls)
    print(geo)
    
#test_GPX()
#flightplans.filter_route_notams(9, 5)

#initialise_user_db()

def test_except():
    Session = sessionmaker(bind=eng)
    session = Session()
    
    print(session.query(func.max(db.Briefing.BriefingID)).filter(db.Briefing.Briefing_Date < (datetime.utcnow().date() - timedelta(days=7))).first()[0])
    print('---------')
    #q1 = session.query(notams.Notam.Notam_Number).filter(notams.Notam.BriefingID == 3)
    #q2 = session.query(notams.Notam.Notam_Number).filter(notams.Notam.BriefingID == 4)
    #q3 = q1.except_(q2).all() #Deleted
    #q3 = q2.except_(q1).all() #Deleted
    q1 = session.query(db.Notam.Notam_Number).filter(db.Notam.BriefingID == 13)
    q2 = session.query(db.Notam.Notam_Number).filter(db.Notam.BriefingID == 14)
    #q2 = session.query(db.Notam.Notam_Number).filter(and_(db.Notam.BriefingID == 14, ~db.Notam.Notam_Number.in_(q1)))
    q3 = q1.filter(~db.Notam.Notam_Number.in_(q2))
    #print(len(q2))
    
    for x in q3:
        print(x.Notam_Number)
    
#test_except()

def test_mail():
    import smtplib, ssl
    from email.message import EmailMessage
    from email.headerregistry import Address
    
    MAIL_HOST = "smtp.gmail.com"
    EMAIL_HOST_USER = "andytallack@gmail.com"
    EMAIL_HOST_PASSWORD = 'etmkomczzehoqwwy'
    EMAIL_ADMIN_NAME = 'B4Flight - Andrew'
    EMAIL_ADMIN_ADDRESS = 'andytallack@gmail.com'
    EMAIL_PORT = 587
    
    msg = EmailMessage()
    msg.set_content('This is a test mail from Python\n Enjoy\n')

    msg['Subject'] = "Welcome to B4Flight"
    msg['From'] = Address(display_name = EMAIL_ADMIN_NAME, addr_spec = EMAIL_ADMIN_ADDRESS)
    msg['To'] = Address(display_name = 'Andrew', addr_spec = 'artech@live.co.za')
    
    msg.set_content('Hello! \n \n Welcome to B4Flight.  Click on the link below to verify your e-mail address\n')
    msg.add_alternative('<html><head></head><body><h1>Hello!</h1><p>Welcome to B4Flight.  Click on the link below to verify your e-mail address</p><a href="www.google.com">CLick</a></body></html>', subtype='html')

    context = ssl.create_default_context()
    with smtplib.SMTP(MAIL_HOST, EMAIL_PORT) as server:
        server.starttls(context=context)
        server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        server.send_message(msg)

    print("done")
    
#test_mail()

def extract_ATNS_data(filename, csv_filename):
    
    aip_data = []
    
    tree = ET()
    tree.parse(filename)
    
    root = tree.getroot()
    
    if root.tag.find('{') > -1:
        ns_name=root.tag[root.tag.find('{')+1:root.tag.find('}')]
    else:
        ns_name=''
    
    ns={'ns':ns_name}
    
    base = root.find('ns:Document', ns)
    base = base.find('ns:Folder', ns)
    folders = base.findall('ns:Folder', ns)
    
    for category in folders:
        category_name = category[0].text
        
        if category_name not in ['Aerodromes', 'Helistops', 'VOR', 'NDB', 'Waypoints']:
            break
        
        extract_ATNS_items(ns, category, category_name, aip_data)
        
        csv_columns = ['Category','ID', 'Description', 'Longitude', 'Latitude']
        
        with open(csv_filename, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for data in aip_data:
                writer.writerow(data)
        print(f'Written to filename {csv_filename}')

def extract_ATNS_items(ns, branch, category_name, data_list):
    
    sub_items = branch.findall('ns:Placemark', ns)
    for this_item in sub_items:
        x={}
        x['Category'] = category_name
        x['ID'] = this_item.find('ns:name', ns).text
        try:
            x['Description'] = this_item.find('ns:description', ns).text
        except:
            x['Description'] = x['ID']
            print(f'No Description for {category_name} -- {x["ID"]}')
            
        point = this_item.find('ns:Point', ns)
        coords = point.find('ns:coordinates', ns).text.split(',')
        x['Longitude'] = coords[0]
        x['Latitude'] = coords[1]
        data_list.append(x)
    
    sub_folders = branch.findall('ns:Folder', ns)
    for fldr in sub_folders:
        extract_ATNS_items(ns, fldr, category_name, data_list)

#extract_ATNS_data('C:/Users/aretallack/git/B4Flight/RSA DATA - 16JUL2020.kml', 'C:/Users/aretallack/git/B4Flight/RSA DATA - 16JUL2020.csv')

test_import_notams()
