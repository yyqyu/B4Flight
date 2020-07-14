'''
Created on 07 Jun 2020

@author: aretallack
'''

from polycircles import polycircles
from shapely.geometry import Polygon
#from .db import FlightPlan, FlightPlanPoint
from flask import current_app
from email.message import EmailMessage
from threading import Thread

import smtplib, ssl


def read_db_connect():
    import configparser
    
    print("Configuring the application")
    cfg = configparser.ConfigParser()
    cfg.read('flightbriefing.ini')
    db_connect = cfg.get('database','connect_string')
    print(db_connect)

    return db_connect

'''---------------------------------------
 convert_dms_to_dd(coord_DMS):

 PURPOSE: converts a co-ordinate from Degrees-Minutes-Seconds to Decimal Degrees
          Accepts formats: ddmmS ddmmN dddmmE dddmmW ddmmssS ddmmssN dddmmssE dddmmssW

 INPUT: coord_DMS

 RETURNS: Decimal Degrees (Float)
---------------------------------------'''

def convert_dms_to_dd(coord_DMS):
    
    coord_DD = 0.0 #start with 0
    
    workingCoord = coord_DMS[:-1] #Strip the N/S/E/W off the end
    
    #Get the Degrees first - 2 digits for Lat and 3 for Lon
    if len(workingCoord) == 4 or len(workingCoord) == 6:
        coord_DD = float(workingCoord[0:2])
        workingCoord = workingCoord[2:]
    else:
        coord_DD = float(workingCoord[0:3])
        workingCoord = workingCoord[3:]
        
    #Now the minutes
    coord_DD += float(workingCoord[:2])/60.0
    
    #If there are seconds
    if len(workingCoord) == 4:
        coord_DD += float(workingCoord[2:])/60.0/60.0
    
    #South and West are negative
    if coord_DMS[-1] == 'S' or coord_DMS[-1] == 'W':
        coord_DD *= -1

    return coord_DD

'''---------------------------------------
 convert_dd_to_dms(lat_coord_DD, lon_coord_DD):

 PURPOSE: converts a co-ordinate pair from Decimal Degrees to Degrees-Minutes-Seconds

 INPUT: coord_DMS

 RETURNS: lat and lon in Degrees Minutes Seconds in format dddmmssX (X=N/S/W/E)
---------------------------------------'''

def convert_dd_to_dms(lat_coord_DD, lon_coord_DD):
    
    working_lat_dd = abs(lat_coord_DD)
    working_lon_dd = abs(lon_coord_DD)
    
    lat_coord_dms = f'{int(working_lat_dd)}'.zfill(2)
    lon_coord_dms = f'{int(working_lon_dd)}'.zfill(3)
    
    working_lat_dd = (working_lat_dd - int(working_lat_dd)) * 60
    working_lon_dd = (working_lon_dd - int(working_lon_dd)) * 60
    
    lat_coord_dms += f'{int(working_lat_dd)}'.zfill(2)
    lon_coord_dms += f'{int(working_lon_dd)}'.zfill(2)
    
    working_lat_dd = (working_lat_dd - int(working_lat_dd)) * 60
    working_lon_dd = (working_lon_dd - int(working_lon_dd)) * 60
    
    lat_coord_dms += f'{int(round(working_lat_dd,0))}'.zfill(2)
    lon_coord_dms += f'{int(round(working_lon_dd,0))}'.zfill(2)
    
    lat_coord_dms += 'N' if lat_coord_DD >= 0 else 'S'
    lon_coord_dms += 'E' if lon_coord_DD >= 0 else 'W'

    return lat_coord_dms, lon_coord_dms


def convert_bounded_dms_to_dd(bounded_coords, lat_lon_separator=",", coord_group_separator=" ", return_as_tuples=True, reverse_coords=False):
    if return_as_tuples == True:
        converted_coords = []
    else:
        converted_coords = ""
    
    if reverse_coords == True:
        ordr = [1,0]
    else:
        ordr = [0,1]
        
    for coord_grp in bounded_coords.split(coord_group_separator):
        coord_split = coord_grp.split(lat_lon_separator)

        if return_as_tuples == True:
            converted_coords.append((convert_dms_to_dd(coord_split[ordr[0]]),convert_dms_to_dd(coord_split[ordr[1]])))
        else:
            if len(converted_coords) > 0: converted_coords += coord_group_separator
            converted_coords += f'{convert_dms_to_dd(coord_split[ordr[0]])}{lat_lon_separator}{convert_dms_to_dd(coord_split[ordr[1]])}'
        
    return converted_coords


'''---------------------------------------
 switch_lat_lon(coords)

 PURPOSE: switched co-ordinate pairs - eg. lat, lon pairs need to be
          respresented as x, y on a graph - therefore switch around

 INPUT: coords = pairs of co-ordinates (lat, lon or x, y)
        convert_DMS_DD = set to True to convert co-ordinates from Degrees Minutes Seconds to Decimal Degrees
 RETURNS: pairs of co-ordinates

---------------------------------------'''

def switch_lat_lon(coords, convert_DMS_DD = False):
    switched = []
    for c in coords:
        if convert_DMS_DD == True:
            switched.append((convert_dms_to_dd(c[1]), convert_dms_to_dd(c[0])))
        else:
            switched.append((c[1], c[0]))
    return switched


def get_flight_bounds(flight_plan, offset_dd=0.25):
    min_x = 360
    min_y = 360
    max_x = -360
    max_y = -360
    
    for fp_point in flight_plan.FlightPlanPoints:
        min_x = min(min_x, fp_point.Longitude)
        min_y = min(min_y, fp_point.Latitude)
        max_x = max(max_x, fp_point.Longitude)
        max_y = max(max_y, fp_point.Latitude)
    
    return [[min_x - offset_dd, min_y - offset_dd], [max_x + offset_dd, max_y + offset_dd]]

def convert_rgb_to_hex(r,g,b):
    hex_colour='#'
    hex_colour += hex(r)[2:]
    hex_colour += hex(g)[2:]
    hex_colour += hex(b)[2:]
    
    return hex_colour
    

'''---------------------------------------
 generate_circle_shapely(centerLat, centerLon, radius_nm):

 PURPOSE: Creates a "Shapely" library circle

 INPUT: latitude and longitude of centre of circle - in Degrees Minutes Seconds
        radius of circle in nautical miles

 RETURNS: shapely Polygon
---------------------------------------'''

def generate_circle_shapely(centerLat, centerLon, radius_nm):
    
    radius_m = radius_nm * 1853 #convert radius from nautical miles to metres
    
    #create the circle
    polycircle = polycircles.Polycircle(latitude=convert_dms_to_dd(centerLat), longitude=convert_dms_to_dd(centerLon), radius=radius_m, number_of_vertices=20)
    circ_coord = polycircle.to_lat_lon()
    spolygon = Polygon(switch_lat_lon(circ_coord)) #Shapely Polygon
    return spolygon


def send_mail(sender, recipients_to, subject, body_text, body_html):
    
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender #Address(display_name = EMAIL_ADMIN_NAME, addr_spec = EMAIL_ADMIN_ADDRESS)
    msg['To'] = recipients_to #Address(display_name = 'Andrew', addr_spec = 'artech@live.co.za')
    
    msg.set_content(body_text)
    msg.add_alternative(body_html, subtype='html')

    context = ssl.create_default_context()
    if current_app.config['EMAIL_USE_TLS'] == True:

        with smtplib.SMTP(current_app.config['EMAIL_HOST'], current_app.config['EMAIL_PORT']) as server:
            server.starttls(context=context)
            server.login(current_app.config['EMAIL_HOST_USER'], current_app.config['EMAIL_HOST_PASSWORD'])
            server.send_message(msg)

    elif current_app.config['EMAIL_USE_SSL'] == True:
        with smtplib.SMTP_SSL(current_app.config['EMAIL_HOST'], current_app.config['EMAIL_PORT'], context=context) as server:
            server.login(current_app.config['EMAIL_HOST_USER'], current_app.config['EMAIL_HOST_PASSWORD'])
            server.send_message(msg)

