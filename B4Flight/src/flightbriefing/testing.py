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


#taf_list = read_taf_ZA('https://aviation.weathersa.co.za/pib/pages/actuals/tafs.php')
#for x in taf_list: print(x['aerodrome'], x['body'])

#print(generate_taf_geojson(taf_list))
#x=flightplans.filter_route_sigairmets(23, 5,'https://aviation.weathersa.co.za/pib/pages/actuals/sigmet.php')

#for y in x: print(y['type'])

def mailchimp_ping():
    
    from mailchimp_marketing import Client
    mailchimp = Client()

    mailchimp_api_key = '5c2b37b42fd75fb3b4eee6113a155772-us7'
    mailchimp_server_prefix = 'us7'
    
    mailchimp.set_config({
        "api_key": mailchimp_api_key,
        "server": mailchimp_server_prefix})
    mc_response = mailchimp.ping.get()
    print(mc_response)
    
    print(mc_response["health_status"] == "Everything's Chimpy!")
    
def mailchimp_list_subscribers():
    import mailchimp_marketing as MailchimpMarketing
    from mailchimp_marketing.api_client import ApiClientError

    mailchimp_api_key = '5c2b37b42fd75fb3b4eee6113a155772-us7'
    mailchimp_server_prefix = 'us7'
    mailchimp_list_id = "1753d98442"

    try:
        client = MailchimpMarketing.Client()
        client.set_config({
            "api_key": mailchimp_api_key,
            "server": mailchimp_server_prefix
      })
    
        mc_response = client.lists.get_list_members_info(mailchimp_list_id, count=100)
        #print(mc_response)
        for m in mc_response['members']:
            print(m['id'], m['merge_fields']['FNAME'], m['merge_fields']['LNAME'],m['merge_fields']['MMERGE6'],m['merge_fields']['MMERGE7'], m['merge_fields']['MMERGE8'], m['email_address'], m['status'])
    except ApiClientError as error:
        print("Error: {}".format(error.text))


def mailchimp_add_subscriber():
    import mailchimp_marketing as MailchimpMarketing
    from mailchimp_marketing.api_client import ApiClientError

    mailchimp_api_key = '5c2b37b42fd75fb3b4eee6113a155772-us7'
    mailchimp_server_prefix = 'us7'
    mailchimp_list_id = "1753d98442"
    mailchimp_userid_field = 'MMERGE6'
    mailchimp_username_field = 'MMERGE7'
    mailchimp_active_field = 'MMERGE8'

    try:
        client = MailchimpMarketing.Client()
        client.set_config({
            "api_key": mailchimp_api_key,
            "server": mailchimp_server_prefix
      })
    
        mc_response = client.lists.add_list_member(mailchimp_list_id, {
            'email_address':'test1@live.co.za', 
            'status':'cleaned',
            'merge_fields':{'FNAME':'Test First','LNAME':'Test Last', mailchimp_userid_field:'1234', mailchimp_username_field:'username', mailchimp_active_field:'Y'}, 
            'tags':['Beta_Tester']})
        print(mc_response)
    except ApiClientError as error:
        print("Error: {}".format(error.text))


def mailchimp_update_subscriber():
    import hashlib
    import mailchimp_marketing as MailchimpMarketing
    from mailchimp_marketing.api_client import ApiClientError

    mailchimp_api_key = '5c2b37b42fd75fb3b4eee6113a155772-us7'
    mailchimp_server_prefix = 'us7'
    mailchimp_list_id = "1753d98442"
    mailchimp_userid_field = 'MMERGE6'
    mailchimp_username_field = 'MMERGE7'
    mailchimp_active_field = 'MMERGE8'
    
    user_email = 'aretallack@live.co.za'
    # Conver e-mail to lower-case, and then encode as binary (i.e. a b'...' string) 
    bin_user_email = user_email.lower().encode()
    # Now has to MD5 in order to pass to Mailchimp API
    user_email_hash = hashlib.md5(bin_user_email).hexdigest()
    print(user_email_hash)

    try:
        client = MailchimpMarketing.Client()
        client.set_config({
            "api_key": mailchimp_api_key,
            "server": mailchimp_server_prefix
      })
        
        
        client.lists.update_list
        mc_response = client.lists.update_list_member(list_id=mailchimp_list_id, subscriber_hash=user_email_hash, body={
            'merge_fields':{mailchimp_active_field:'Y'}
            })
        print(mc_response)
    except ApiClientError as error:
        print("Error: {}".format(error.text))

#mailchimp_ping()
#mailchimp_add_subscriber()
#mailchimp_update_subscriber()

#mailchimp_list_subscribers()

def pdftest(file_path, file_out_path):
    from io import StringIO
    
    from pdfminer.converter import TextConverter
    from pdfminer.layout import LAParams
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfparser import PDFParser

    output_string = StringIO()
    with open(file_path, 'rb') as in_file:
        parser = PDFParser(in_file)
        doc = PDFDocument(parser)
        rsrcmgr = PDFResourceManager()
        device = TextConverter(rsrcmgr, output_string, laparams=LAParams())
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for page in PDFPage.create_pages(doc):
            interpreter.process_page(page)
    
    x=open(file_out_path,'w')
    x.write(output_string.getvalue())
    return(output_string.getvalue())

#pdftest('C:/Users/aretallack/git/B4Flight/B4Flight/src/instance/notam_archives/ZA_notam_2020-06-16.pdf', 'C:/Users/aretallack/Desktop/ZA_notam_2020-06-16.txt')



def get_latest_CAA_briefing_date_ZA(caa_webpage_url=None):
    """Checks the CAA website for the latest briefing date, and returns that date.
    Used to avoid downloading and parsing the PDF file to check if latest B4Flight briefing is current
    
    Parameters
    ----------
    caa_webpage_url : str
        full url to the CAA webpage containing the briefing download docs
        If NONE will get the page from the setting file
    
    Returns
    -------
    date
        date of the latest briefing
    OR
    None
        if the action failed, returns None
    """
    
    # If we don't have a URL then retrieve one from the flightbriefing.ini settings file
    if caa_webpage_url is None:
        cfg = configparser.ConfigParser()
        cfg.read(os.path.join(current_app.root_path, 'flightbriefing.ini'))
        update_url = cfg.get('notam_import_ZA', 'caa_updated_url')
    else:
        update_url = caa_webpage_url
    
    # Start with the result being None
    updated_date = None
    
    # Check the URL, streaming it to limit impact
    resp = requests.get(update_url, stream=True)
    
    # Did we succeed in retrieving the page?  200=success
    if resp.status_code == 200:
        
        # How is page encoded?
        enc = resp.encoding
        
        # Process page one line at a time to conserve resources
        for line in resp.iter_lines():
            # Does the line contain the text 'Last update'?
            if 'LAST UPDATE' in line.decode(enc).upper():
                start = line.decode(enc).upper().find('LAST UPDATE')
                end = line.decode(enc).upper().find('</SPAN>', start)
                found = line.decode(enc)[start:end]
                found = found.replace('&#58;', ':').replace('&#160;', ' ')
                
                # Typical contents of variable "found":
                # Last update&#58;&#160;&#160;25 <span lang="EN-US" style="font-family&#58;calibri, sans-serif;font-size&#58;11pt;">September 2020
                # Extract the day of month - in this case the "25": &#160;25 <span
                dom = found[:found.upper().rfind('<SPAN')]
                dom = dom[dom.upper().rfind(';')+1:].strip()
                # Extract the Month + Year:
                month_year = found[found.rfind('>')+1:]
                # If the above search fails, then need to look for re-formatted version:
                # Last update&#58;&#160;11 March 2021</strong>
                if month_year == '':
                    full_date = found[found.upper().rfind(';')+1:]
                    #Remove the Strong closing tag
                    full_date = full_date[:full_date.upper().rfind('</STRONG')].strip()
                    #Remove the Last Update: prefix
                    full_date = full_date[full_date.find(':')+1:].strip()
                    
                    # This should give us just the date in formay dd mmm yyyy
                    dom, month, year = full_date.split(' ')
                else:
                    month, year = month_year.split(' ')
                
                updated_date = datetime.strptime(f'{dom} {month} {year}', '%d %B %Y')
                updated_date_str = datetime.strftime(updated_date, '%Y-%m-%d')
                resp.close()
                break

    return updated_date

#get_latest_CAA_briefing_date_ZA('http://www.caa.co.za/Pages/Aeronautical%20Information/Notam-summaries-PIB.aspx')

def testMetar():
    metars = weather.read_metar_ZA('https://aviation.weathersa.co.za/pib/pages/actuals/metars.php')
    print(len(metars))
    for m in metars:
        if m['has_no_data'] == False:
            print(f"{m['aerodrome']} Temp={m['temperature']} QNH={m['qnh']} Wind = {m['wind']} Correction={m['is_correction']}")

testMetar()            