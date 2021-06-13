"""Handles Weather-related Functionality

This module contains functions to 
- Retrieve SIGMET and AIRMET data and generate GEOJSON features
- Retrieve METAR data and generate GEOJSON features
- Retrieve TAF data and generate GEOJSON features
 
"""

from geojson import Polygon, Feature, Point
import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from flask import (
    current_app
)

from .data_handling import sqa_session
from . import helpers
from .db import NavPoint


def calc_metar_taf_date(day, hr, mn=0):
    """ Function that calculates the FULL date for a METAR/TAF, based on the day, hour and minute 
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
        if hr == 24: #Aviation weather uses hr 24, python only uses 0-23.  If hr is 24, make it ) on the next day
            full_date = datetime(yr, mth, day, 0, mn, 0) + timedelta(days=1)
        else:
            full_date = datetime(yr, mth, day, hr, mn, 0)
    
    return full_date



def read_sigmet_airmet_ZA(sigmet_url):
    """ Function that webscrapes SIGMET and AIRMET data from specified URL, 
        returning a list of SIGMET/AIRMET dictionary items for further processing
        
    
    Parameters
    ----------
    sigmet_url: string
        URL from which to scrape the SIGMET/AIRMET data
    
    Returns
    -------
        sigair_met_list : list of dictionary elements
        type: SIGMET / AIRMET
        valid_from: datetime
        valid_to: datetime
        body: body of the Sigmet/Airmet
        coords: list of co-ord pairs - LONG, LAT in decimal degrees
        flevels: vertical limits
        
    """

    
    sigair_met_list = [] # The list of disctionaries that will be returned, containing SIGMAT/AIRMET data
    
    # Regular expressions to extract the co-ordinats and the Flight Level
    coord_re = re.compile(r'([NS]\d{4,4} [EW]\d{5,5})')
    valid_re = re.compile(r'VALID (?P<valid_from>[0-9]{6,6})[/](?P<valid_to>[0-9]{6,6})')
    fl_sfc_re = re.compile(r'SFC[/](FL.+)|(TOP FL[0-9/]+)=') 
    fl_re = re.compile(r'(FL.+)|(TOP FL[0-9/]+)=')
    
    # Retrieve the webpage containing SIGMET/AIRMET data
    try:
        r = requests.get(sigmet_url, verify=False)
    except:
        current_app.logger.error(f"Error retrieving SIGMET - failed at REQUESTS call")
        return None
    
    # If error retrieving page, return None
    if r.status_code != 200: 
        current_app.logger.error(f"Error retrieving SIGMET: URL = {sigmet_url}: {r.status_code} - {r.reason}")
        return None
    
    # Setup Beautiful Soup, and extract all teh "PRE" tags - these are where the AIRMET data is stored
    soup = BeautifulSoup(r.text, 'html.parser')
    mets = soup.find_all('pre')

    # Loop through the individual SIGMETS/AIRMETS
    for met in mets:
        # Convert to a string and replace newline with space
        met_string = str(met.string).replace("\n", " ")

        # Extract the co-ords using regex
        coords = coord_re.findall(met_string)

        # If there are coords, then process this SIGMET
        if coords:
            # List to store the separated co-ords
            split_coords = []
            
            # For each co-ord pair
            for c in coords:

                # Split the co-ord pair
                c_split = c.split(" ")

                # Then convert from N9999 to 9999N, LONG first then LAT, and convert to Decimal Degrees
                c_split[0] = helpers.convert_dms_to_dd(c_split[0][1:] + c_split[0][0:1])
                c_split[1] = helpers.convert_dms_to_dd(c_split[1][1:] + c_split[1][0:1])
                
                # Add these coords to the list
                split_coords.append([c_split[1], c_split[0]])
            
            # We need to close the shape the coords outline, if it isn't already closed
            # If the first and last coords are equal, shape is closed - otherwise append the first coord to the end
            if split_coords[0] != split_coords[-1]: split_coords.append(split_coords[0])
            
            # Extract Validity period
            try:
                valid_from = valid_re.search(met_string).group('valid_from')
                valid_to = valid_re.search(met_string).group('valid_to')
                
                valid_from = calc_metar_taf_date(int(valid_from[0:2]), int(valid_from[2:4]), int(valid_from[4:6]))
                valid_to = calc_metar_taf_date(int(valid_to[0:2]), int(valid_to[2:4]), int(valid_to[4:6]))
                
            except:
                current_app.logger.error(f"Error parsing SIGMET/AIRMET validity: {met_string}")
                valid_from = None
                valid_to = None
            
                 
            # Extract the Flight Levels
            # First see if there is a "SFC/FLxxx" string
            flevels = fl_sfc_re.search(met_string)
            # If there isn't, try normal flight levels
            if not flevels:              
                flevels = fl_re.search(met_string)
            # If something found, extract it
            if flevels:
                flevels = flevels.group().strip().replace("=","")
            
            # Extract the body of the message.  Do this by selecting text to the left of the first coord
            # Get the first coord
            first_coord = coords[0].split(" ")[0]
            # Select the body text and strip any trailing spaces
            body = met_string[:met_string.find(first_coord)].strip()
            # If body ends "WI" - this specifies the coords - then remove it
            if body[-3:] == ' WI': body = body[:-3].strip()
            
            # Specify the type - SIGMET or AIRMET
            sa_type = 'SIGMET' if body.find("SIGMET")>=0 else 'AIRMET'

            # Create the dictionary object for this Sig/Air MET
            this_met = {'type':sa_type, 'valid_from': valid_from, 'valid_to': valid_to, 'body':body, 'coords': split_coords, 'flevels': flevels}

            # Add to the list
            sigair_met_list.append(this_met)

    return sigair_met_list

            
def generate_sigmet_geojson(sigair_met_list):
    """ Function that accepts SIGMET and AIRMET data, and creates a list of GEOJSON features grouped into SIGMET and AIRMET 
    Each Feature will form a layer on the map - this allows for easy filtering of layers.
    The function also returns a list of the Groups applicable (eg. there may be no AIRMETS so only SIGMETS will be returned)
    
    Parameters
    ----------
    sigair_met_list : list of dictionary elements containing SIGMET/AIRMET data
        type: SIGMET / AIRMET
        body: body of the Sigmet/Airmet
        coords: list of co-ord pairs - LONG, LAT in decimal degrees
        flevels: vertical limits
        
    Returns
    -------
    tuple
        sigair_met_features: list of GEOJSON Feature strings - each element in the list includes details for SIGMET or AIRMET
        used_groups: list of groups that were used - one of SIGMET or AIRMET
    """

    # Initialise Variables
    used_groups = []  #contains applicable groupings for use on the web page (i.e. it excludes groupings that do not appear) - used to filter layers on the map
    used_layers = []
    sigair_met_features = []

        # If there are no Sig/Airmets (incase None is passed)
    if sigair_met_list is None:
        return sigair_met_features, used_groups, used_layers
    
    # Create the Fill Colour attributes
    fill_col = {}
    line_col = {}
    
    # Set fill colours for SIGMET
    colr = current_app.config['WEATHER_SIGMET_COLOUR']
    opacity = current_app.config['WEATHER_SIGMET_OPACITY']
    col_r = int(colr[1:3],16)
    col_g = int(colr[3:5],16)
    col_b = int(colr[5:7],16)

    fill_col['SIGMET'] = f'rgba({col_r},{col_g},{col_b},{opacity})'
    line_col['SIGMET'] = f'rgba({int(col_r*0.75)},{int(col_g*0.75)},{int(col_b*0.75)},1)' #f'rgba({col_r},{col_g},{col_b},1)'

    # Set fill colours for AIRMET
    colr = current_app.config['WEATHER_AIRMET_COLOUR']
    opacity = current_app.config['WEATHER_AIRMET_OPACITY']
    col_r = int(colr[1:3],16)
    col_g = int(colr[3:5],16)
    col_b = int(colr[5:7],16)

    fill_col['AIRMET'] = f'rgba({col_r},{col_g},{col_b},{opacity})'
    line_col['AIRMET'] = f'rgba({int(col_r*0.75)},{int(col_g*0.75)},{int(col_b*0.75)},1)'


    # Create a GEOJSON Feature for each Notam - Feature contains specific Notam attributes
    for met in sigair_met_list:
        
        geojson_geom=Polygon([met['coords']])

        # Append this Feature to the collection, setting the various attributes as properties
        sigair_met_features.append(Feature(geometry=geojson_geom, properties={'fill':fill_col[met['type']], 'line':line_col[met['type']], 
                                                                 'group': met['type'],
                                                                 'valid_from': datetime.strftime(met['valid_from'], '%d-%b %H:%M'),
                                                                 'valid_to': datetime.strftime(met['valid_to'], '%d-%b %H:%M'),
                                                                 'layer_group': met['type']+'_polygon', 
                                                                 'text': met['body'],
                                                                 'flight_levels': met['flevels']}))

        # Add this group+geometry combination to the list, so the map knows to split out a layer for it.
        if (met['type'] + '_polygon') not in used_layers:
            used_layers.append(met['type'] + '_polygon')

        # Add the Notam Grouping to the collection of used groups
        if met['type'] not in used_groups:
            used_groups.append(met['type'])
        
    # Sort groups alphabetically for better display on the map
        
    return sigair_met_features, used_groups, used_layers



def read_metar_ZA(metar_url, date_as_ISO_text=False):
    """ Function that webscrapes METAR data from specified URL, 
        returning a list of METAR dictionary items for further processing
        
    
    Parameters
    ----------
    metar_url: string
        URL from which to scrape the METAR data
    date_as_ISO_text: boolean, optional
        Return the Metar Date/Time as an ISO text string (allows use in JSON)
    
    Returns
    -------
        metar_list : list of dictionary elements
            aerodrome: ICAO code
            has_no_data: boolean
            is_speci: boolean
            time: date and time of the METAR
            wind: dictionary containing (direction, strength, gusting, is_variable).  Direction of -1 means variable
            temperature: temp in degrees centigrade
            dew_point: dewpoint temp in degrees centigrade (integer, so M01 is shown as -01)
            QNH: QNH in hPa
            body: full body of the METAR
            coords: co-ord pair for the aerodrome - LONG, LAT in decimal degrees
        
    """

    
    metar_list = [] # The list of dictionaries that will be returned, containing METAR data
    
    # Regular expressions to extract the wind
    re_wind_no_gust = re.compile(r'(?P<direction>[0-9]{3,3})(?P<spd>[0-9]{2,2})KT') # 10005KT
    re_wind_gust = re.compile(r'(?P<direction>[0-9]{3,3})(?P<spd>[0-9]{2,2})G(?P<gust>[0-9]{2,2})KT') # 10005G15KT
    re_wind_variable = re.compile(r'(?P<direction>VRB)(?P<spd>[0-9]{2,2})KT') # VRB05KT
    re_no_data = re.compile(r'No Data For (?P<missing>[A-Z,a-z]{4,4})', re.IGNORECASE) # No data for FAGC
    re_temp = re.compile(r' (?P<temp>[M]?[0-9]{2,2})+/(?P<dewpt>[M]?[0-9]{2,2}) ') #temp in format 20/12 or 20/M02 or M03/M10 etc. 
    re_qnh = re.compile(r'Q(?P<qnh>[0-9]{3,4})')
    
    
    # Retrieve the webpage containing METAR data
    try:
        r = requests.get(metar_url, verify=False)
    except:
        current_app.logger.error(f"Error retrieving METAR - failed at REQUESTS call")
        return None
        
    
    # If error retrieving page, return None
    if r.status_code != 200: 
        current_app.logger.error(f"Error retrieving METAR: URL = {metar_url}: {r.status_code} - {r.reason}")
        return None
    
    # Setup Beautiful Soup, and extract all the "PRE" tags - these are where the METAR data is stored
    soup = BeautifulSoup(r.text, 'html.parser')
    mets = soup.find_all('pre')
    
    #Connect to DB
    sess = sqa_session()
    
    # Loop through the individual METAR
    for met in mets:
        
        # Get just the text.  Sould be: similar to: 'View DecodedMETAR FAOR 100530Z 19015KT CAVOK 15/M03 Q1020 NOSIG='
        met_string = str(met.text)
        
        is_speci = False # Is this a SPECI and not a METAR - default to False
        
        # Determine if this is a METAR, a SPECI, or a line to be ignored
        s = met_string.find('METAR') # Is it a METAR?
        
        # If text not found, this is not a METAR - is it a SPECI?
        if s < 0:
            s = met_string.find('SPECI') # Is it a SPECI

            if s >= 0: # It is a speci
                is_speci = True
            
            else: # It's not a SPECI either, so continue to the next element
                continue

        s += 5 # 5 is the length of the text METAR and SPECI - we want to remove this.
        # Remove METAR/SPECI text - we should now have the raw METAR/SPECI only (eg. 'FAOR 100530Z 19015KT CAVOK 15/M03 Q1020 NOSIG=')
        met_string = met_string[s:].strip()
        
        # Extract aerodrome name
        aerodrome = met_string[:4]
        # Get aerodrome NavPoint - contains coordinates
        aero_point = sess.query(NavPoint).filter(NavPoint.ICAO_Code == aerodrome).first()
        
        # If aerdrome not found, this is a non-aerodrome station - ignore it (May implement later)
        if not aero_point:
            continue
        
        # Get the date and time
        day = int(met_string[5:7])
        hr = int(met_string[7:9])
        mn = int(met_string[9:11])
        
        met_date = calc_metar_taf_date(day, hr, mn)
        
        #Get the winds
        wind_variable = False # Wind defaults to not light and variable
        wind_gust = 0 # Gust defaults to 0
        no_wind = False #Is there no wind data avail (i.e. /////KT)
        
        
        #Check whether there is now wind specified (i.e. /////KT)
        if met_string.find('///KT') > 0:
            no_wind = True
            wind_dir = 0
            wind_spd = 0
        else:
            
            # Use regular expression to try to extract non-gusting wind (eg. 10010KT)
            tmp = re_wind_no_gust.search(met_string)
            if tmp:
                try:
                    wind_dir = tmp.group('direction')
                    wind_spd = tmp.group('spd')
                except:
                    current_app.logger.error(f"Error passing METAR winds: {met_string}")
    
            # Use regular expression to try to extract gusting wind (eg. 10010G15KT)
            elif re_wind_gust.search(met_string):
                tmp = re_wind_gust.search(met_string)
                try:
                    wind_dir = tmp.group('direction')
                    wind_spd = tmp.group('spd')
                    wind_gust = tmp.group('gust')
                except:
                    current_app.logger.error(f"Error passing METAR wind GUSTING: {met_string}")
                    
            # Use regular expression to try to extract variable wind (eg. VRB02KT)
            elif re_wind_variable.search(met_string):
                tmp = re_wind_variable.search(met_string)
                try:
                    wind_dir = -1
                    wind_spd = tmp.group('spd')
                    wind_variable = True
                except:
                    current_app.logger.error(f"Error passing METAR wind VARIABLE: {met_string}")

        # Use regular expression to try to extract Temp and Dewpoint (eg. 25/M02)
        temperature = 0
        dew_point = 0

        tmp = re_temp.search(met_string)
        if tmp:
            try:
                temperature = int(tmp.group('temp').replace('M','-'))
                dew_point = int(tmp.group('dewpt').replace('M','-'))
            except:
                current_app.logger.error(f"Error passing METAR temperature: {met_string}")


        # Use regular expression to try to extract QNH (eg. Q1025)
        qnh = 1013
        
        tmp = re_qnh.search(met_string)
        if tmp:
            try:
                qnh = tmp.group('qnh')
            except:
                current_app.logger.error(f"Error passing METAR QNH: {met_string}")
        
        if date_as_ISO_text == True:
            met_date = datetime.isoformat(met_date)
        
        met_dict = {'aerodrome': aerodrome , 'coords': (aero_point.Longitude, aero_point.Latitude), 
                    'has_no_data': False , 'is_speci': is_speci, 'time': met_date, 
                    'wind': {'no_wind_data': no_wind, 'direction': wind_dir, 'speed': wind_spd, 'gusting': wind_gust, 'is_variable': wind_variable},  #(wind_dir, wind_spd, wind_gust, wind_variable) , 
                    'temperature': temperature, 'dew_point': dew_point,
                    'qnh': qnh,
                     'body': met_string}
        
        metar_list.append(met_dict)
        
    # Check for any stations with no data - search the whole page
    aero_no_datas = re_no_data.findall(soup.text)
    # If there are stations with no data, iterate through them
    if aero_no_datas:
        for aerodrome in aero_no_datas:
            # Get aerodrome NavPoint - contains coordinates
            aero_point = sess.query(NavPoint).filter(NavPoint.ICAO_Code == aerodrome).first()
    
            # If aerdrome not found, this is a non-aerodrome station - ignore it (May implement later)
            if not aero_point:
                continue
        
            # Add a disctionary item
            met_dict = {'aerodrome': aerodrome , 'coords': (aero_point.Longitude, aero_point.Latitude) , 
                        'has_no_data': True, 'body': f'No data for {aerodrome}'}
            
            metar_list.append(met_dict)

    return metar_list



def generate_metar_geojson(metar_list):
    """ Function that accepts METAR data, and creates a list of GEOJSON features
    
    Parameters
    ----------
    metar_list : list of dictionary elements containing METAR data
        aerodrome: ICAO code
        has_no_data: boolean
        is_speci: boolean
        time: date and time of the METAR
        metar_age: string: how old is the METAR
        wind: dictionary containing (direction, strength, gusting, is_variable).  Direction of -1 means variable
        body: full body of the METAR
        coords: co-ord pair for the aerodrome - LONG, LAT in decimal degrees
        
    Returns
    -------
    list
        metar_features: list of GEOJSON Feature strings - each element in the list includes details for METAR
    """

    # Initialise Variables
    metar_features = []
    
    # If there are no Metars (incase None is passed)
    if metar_list is None:
        return metar_features
    
    #Get the colours
    colr = current_app.config['WEATHER_METAR_COLOUR']
    opacity = current_app.config['WEATHER_METAR_OPACITY']
    col_r = int(colr[1:3],16)
    col_g = int(colr[3:5],16)
    col_b = int(colr[5:7],16)
    
    # Create the Fill Colour attribute - opacity as set above
    fill_col=f'rgba({col_r},{col_g},{col_b},{opacity})'
    # Create the Line Colour attribute - opacity of 1
    line_col=f'rgba({col_r},{col_g},{col_b},1)'

    
    # Create a GEOJSON Feature for each Notam - Feature contains specific Notam attributes
    for met in metar_list:
        
        # If there is no data, then ignore this notam
        if met['has_no_data'] : continue
        
        geojson_geom=Point(met['coords'])
        metar_age = datetime.utcnow() - met['time']
        if metar_age.days > 0:
            metar_age = f'{metar_age.days} day(s) old'
        elif (metar_age.seconds/3600) > 2:
            metar_age = f'{int(metar_age.seconds/3600)} hours old'
        else:
            metar_age = f'{int(metar_age.seconds/60)} minutes old'
        

        # Append this Feature to the collection, setting the various attributes as properties
        metar_features.append(Feature(geometry=geojson_geom, properties={'fill':fill_col, 'line':line_col, 
                                                                 'group': 'METAR',
                                                                 'layer_group': 'METAR_symbol', 
                                                                 'aerodrome': met['aerodrome'],
                                                                 'wind_direction': 'variable' if met['wind']['is_variable'] == True else met['wind']['direction'],
                                                                 'wind_speed_kts': met['wind']['speed'],
                                                                 'wind_gust_kts': met['wind']['gusting'],
                                                                 'date_time': datetime.strftime(met['time'], '%H:%M %d-%b'),
                                                                 'metar_age' : metar_age,
                                                                 'text': met['body']}))

    return metar_features



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
    try:
        r = requests.get(taf_url, verify=False)
    except:
        current_app.logger.error(f"Error retrieving TAF - failed at REQUESTS call")
        return None
        
    
    # If error retrieving page, return None
    if r.status_code != 200: 
        current_app.logger.error(f"Error retrieving TAF: URL = {taf_url}: {r.status_code} - {r.reason}")
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
    
    # If there are no TAFs (incase None is passed)
    if taf_list is None:
        return taf_features
    
    #Get the colours
    colr = current_app.config['WEATHER_TAF_COLOUR']
    opacity = current_app.config['WEATHER_TAF_OPACITY']
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
        if (datetime.utcnow() < this_taf['time']):
            taf_age = ''
        else:
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


