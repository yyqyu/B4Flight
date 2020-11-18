'''
Created on 07 Jun 2020

@author: aretallack
'''
import os
from sqlalchemy import create_engine, func, and_
from sqlalchemy.orm import sessionmaker 

from geojson import Polygon, Feature, FeatureCollection, Point
import re

import requests
from bs4 import BeautifulSoup

from flightbriefing import helpers
from flightbriefing import notams
from flightbriefing import flightplans
from flightbriefing import weather

from flightbriefing import db
from flightbriefing.db import User, FlightPlan, FlightPlanPoint, Notam, Briefing, UserHiddenNotam, NavPoint
from flightbriefing.data_handling import sqa_session

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

#test_import_notams()

def test_join():
    Session = sessionmaker(bind=eng)
    session = Session()
    latest_brief_id = 32
    flight_date = datetime.utcnow().date()
    notam_list = session.query(Notam, UserHiddenNotam.Notam_Number.label('HiddenNotam')).filter(
        and_(Notam.BriefingID == latest_brief_id, Notam.From_Date <= flight_date, Notam.To_Date >= flight_date)
        ).join(UserHiddenNotam, Notam.Notam_Number == UserHiddenNotam.Notam_Number).order_by(Notam.A_Location).all()

    for x in notam_list:
        print(f'NOTAM {x.HiddenNotam}')

    lst = [x.HiddenNotam for x in notam_list ]
    print(lst)
    
    print('D0358/20' in lst)
    
#test_join()


def calc_metar_taf_date(day, hr, mn=0):
    """ Function that calculates teh FULL date for a METAR/TAF, based on the day, hour and minute 
        As METARS can be expired, and TAFs can be in the future, we need to work out the Year and Month 
        
    
    Parameters
    ----------
    day: int
        Day of month
    hr: int
        Hour
    mn: int
        Minute
    
    Returns
    -------
        datetime
            The full date and time
        OR
        None
            If no date or time could be calculated
    """

    yr=0
    mth=0
    # Now get the month and year: METARS/TAFs can be from the day before (eg around midnight) or older; TAF's can be valid for a tomorrow...
    # so we need to compare to today's date
    
    if day == datetime.utcnow().day:
        # METAR/TAF is from today
        yr = datetime.utcnow().year
        mth = datetime.utcnow().month
    
    #METAR/TAF is not from today, so start from today +1 (TAF validity may be in the future) and go back in time up to 25 days
    else:
        for d in range(-1,26):
            # Go back in time
            full_date = datetime.utcnow() - timedelta(days=d)
            # Check if the days match
            if day == (full_date.day):
                # They do, so we have the year and month for the METAR
                yr = full_date.year
                mth = full_date.month
                break
    
    # If we couldn't find a date (unlikely) then set date to None
    if yr == 0:
        full_date = None
    #Otherwise set the datetime
    else:
        full_date = datetime(yr, mth, day, hr, mn, 0)
    
    return full_date



def read_taf_ZA(taf_url):
    """ Function that webscrapes TAF data from specified URL, 
        returning a list of TAF dictionary items for further processing
        
    
    Parameters
    ----------
    taf_url: string
        URL from which to scrape the TAF data
    
    Returns
    -------
        taf_list : list of dictionary elements
            aerodrome: ICAO code
            is_amended_corrected: boolean
            time: date and time of the TAF
            valid_From: date TAF is valid from
            valid_to: date teh TAF is valid to
            body: full body of the TAF
            coords: co-ord pair for the aerodrome - LONG, LAT in decimal degrees
        
    """

    
    taf_list = [] # The list of disctionaries that will be returned, containing SIGMAT/AIRMET data
    
    
    # Retrieve the webpage containing TAF data
    r = requests.get(taf_url, verify=False)
    
    # If error retrieving page, return None
    if r.status_code != 200: 
#####        current_app.logger.error(f"Error retrieving TAF: URL = {taf_url}: {r.status_code} - {r.reason}")
        print(f"Error retrieving TAF: URL = {taf_url}: {r.status_code} - {r.reason}")
        return None
    
    # Setup Beautiful Soup, and extract all the "PRE" tags - these are where the TAF data is stored
    soup = BeautifulSoup(r.text, 'html.parser')
    tafs = soup.find_all('pre')
    
    #Connect to DB
    sess = sqa_session()
    
    # Loop through the individual TAF
    for this_taf in tafs:
        
        # Get just the text.  Sould be: similar to: ''View DecodedTAF FAOR 171000Z 1712/1818 30012KT CAVOK\xa0\xa0\xa0TX31 ...'
        taf_string = str(this_taf.text).replace(u'\xa0',' ') #replace \xa0 (a unicode non-breaking space) with a normal space.
        
        # Determine if this is an amended TAF, normal TAF, or a line to be ignored
        s = taf_string.find('TAF AMD') + taf_string.find('TAF COR') + 1# Is it an amended/corrected TAF?
        
        # This is an amended TAF
        if s >= 0:
            s+=7 # the length of text "TAF AMD"
            is_amended_corrected = True
        
        # If text not found, is this a normal TAF?
        else:
            s = taf_string.find('TAF') # Is it a normal TAF?
            # This is a normal TAF
            if s >= 0:
                s+=3 # the length of text "TAF"
                is_amended_corrected = False

            
            # This is neither - ignore it
            else:
                continue

        # Remove TAF text - we should now have the raw TAF only (eg. 'FAWK 170900Z 1710/1718 31010KT CAVOK TX31/1712Z TN23/1718Z=')
        taf_string = taf_string[s:].strip()
        
        # Extract aerodrome name
        aerodrome = taf_string[:4]
        # Get aerodrome NavPoint - contains coordinates
        aero_point = sess.query(NavPoint).filter(NavPoint.ICAO_Code == aerodrome).first()
        
        # If aerdrome not found, this is a non-aerodrome station - ignore it (May implement later)
        if not aero_point:
            continue
        
        # Get the date and time the TAF was issued
        day = int(taf_string[5:7])
        hr = int(taf_string[7:9])
        mn = int(taf_string[9:11])
        
        taf_date = calc_metar_taf_date(day,hr,mn)
        
        # Now get the validity of the TAF
        from_day = int(taf_string[13:15])
        from_hr = int(taf_string[15:17])
        valid_from = calc_metar_taf_date(from_day, from_hr)

        to_day = int(taf_string[18:20])
        to_hr = int(taf_string[20:22])
        valid_to = calc_metar_taf_date(to_day, to_hr)


        
        taf_dict = {'aerodrome': aerodrome , 'coords': (aero_point.Longitude, aero_point.Latitude) , 
                    'is_amended_corrected': is_amended_corrected, 'time': taf_date, 'valid_from': valid_from, 'valid_to':valid_to, 
                    'body': taf_string}
        
        taf_list.append(taf_dict)
        

    return taf_list



def generate_taf_geojson(taf_list):
    """ Function that accepts METAR data, and creates a list of GEOJSON features
    
    Parameters
    ----------
    taf_list : list of dictionary elements containing TAF data
            aerodrome: ICAO code
            is_amended_corrected: boolean
            time: date and time of the TAF
            valid_From: date TAF is valid from
            valid_to: date teh TAF is valid to
            body: full body of the TAF
            coords: co-ord pair for the aerodrome - LONG, LAT in decimal degrees
        
    Returns
    -------
    list
        taf_features: list of GEOJSON Feature strings - each element in the list includes details for TAF
    """

    # Initialise Variables
    taf_features = []
    
    #Get the colours
    colr='#09f7e7'
    opacity=0.4
#####    colr = current_app.config['WEATHER_TAF_COLOUR']
#####    opacity = current_app.config['WEATHER_TAF_OPACITY']
    col_r = int(colr[1:3],16)
    col_g = int(colr[3:5],16)
    col_b = int(colr[5:7],16)
    
    # Create the Fill Colour attribute - opacity as set above
    fill_col=f'rgba({col_r},{col_g},{col_b},{opacity})'
    # Create the Line Colour attribute - opacity of 1
    line_col=f'rgba({col_r},{col_g},{col_b},1)'

    
    # Create a GEOJSON Feature for each Notam - Feature contains specific Notam attributes
    for this_taf in taf_list:
        
        # Create the Point geometry
        geojson_geom = Point(this_taf['coords'])
        #Calculate the age of the TAF
        taf_age = datetime.utcnow() - this_taf['time']
        if taf_age.days > 0:
            taf_age = f'{taf_age.days} day(s) old'
        elif (taf_age.seconds/3600) > 2:
            taf_age = f'{int(taf_age.seconds/3600)} hours old'
        else:
            taf_age = f'{int(taf_age.seconds/60)} minutes old'
        

        # Append this Feature to the collection, setting the various attributes as properties
        taf_features.append(Feature(geometry=geojson_geom, properties={'fill':fill_col, 'line':line_col, 
                                                                 'group': 'TAF',
                                                                 'layer_group': 'TAF_symbol', 
                                                                 'aerodrome': this_taf['aerodrome'],
                                                                 'date_time': datetime.strftime(this_taf['time'], '%H:%M %d-%b'),
                                                                 'valid_from': datetime.strftime(this_taf['valid_from'], '%d-%b %H:%M'),
                                                                 'valid_to': datetime.strftime(this_taf['valid_to'], '%d-%b %H:%M'),
                                                                 'taf_age' : taf_age,
                                                                 'text': this_taf['body']}))

    return taf_features


taf_list = read_taf_ZA('https://aviation.weathersa.co.za/pib/pages/actuals/tafs.php')
#for x in taf_list: print(x['aerodrome'], x['body'])

print(generate_taf_geojson(taf_list))
#x=flightplans.filter_route_sigairmets(23, 5,'https://aviation.weathersa.co.za/pib/pages/actuals/sigmet.php')

#for y in x: print(y['type'])
