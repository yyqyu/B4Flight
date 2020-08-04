"""Contains various Helper functions used across the application

- read_db_connect : read the database connection string
- convert_dms_to_dd : convert from degrees-minutes-seconds to decimal degrees
- convert_dd_to_dms : convert from decimal degrees to degrees-minutes-seconds
- convert_bounded_dms_to_dd : convert a bounded shape's co-ordinates from degrees-minutes-seconds to decimal degrees
- switch_lat_lon : reverse latitude and longitude co-ordinates
- get_flight_bounds : get the two bounding co-ords for a flightplan
- get_shape_bounds  : get the two bounding co-ords for a Shapely geometry
- convert_rgb_to_hex : convert RGB colour to HEX
- generate_circle_shapely : generate a Shapely circle geometry for a radius around a point
- send_mail : send an e-mail

"""

from polycircles import polycircles
from shapely.geometry import Polygon
from flask import current_app
from email.message import EmailMessage

import smtplib, ssl


def read_db_connect():
    """Reads the application configuration file (flightbriefing.ini) 
    and return the database connection string
    
    Returns
    -------
    str 
        database connection string
    """
    import configparser
    
    print("Configuring the application")
    cfg = configparser.ConfigParser()
    cfg.read('flightbriefing.ini')
    db_connect = cfg.get('database','connect_string')
    print(db_connect)

    return db_connect


def convert_dms_to_dd(coord_DMS):
    """Converts a co-ordinate from Degrees-Minutes-Seconds to Decimal Degrees
    Accepts formats: ddmmS ddmmN dddmmE dddmmW ddmmssS ddmmssN dddmmssE dddmmssW
    
    Parameters
    ----------
    coord_DMS : str
        co-ordinate in DMS format (ddmmS ddmmN dddmmE dddmmW ddmmssS ddmmssN dddmmssE dddmmssW)
    
    Returns
    -------
    float
        co-ordinate in decimal degrees
    """

    # Start with 0
    coord_DD = 0.0 
    
    # Strip the N/S/E/W off the end
    workingCoord = coord_DMS[:-1] 
    
    # Get the Degrees first - 2 digits for Lat and 3 for Lon
    if len(workingCoord) == 4 or len(workingCoord) == 6:
        coord_DD = float(workingCoord[0:2])
        workingCoord = workingCoord[2:]
    else:
        coord_DD = float(workingCoord[0:3])
        workingCoord = workingCoord[3:]
        
    # Now the minutes
    coord_DD += float(workingCoord[:2])/60.0
    
    # If there are seconds
    if len(workingCoord) == 4:
        coord_DD += float(workingCoord[2:])/60.0/60.0
    
    # South and West are negative
    if coord_DMS[-1] == 'S' or coord_DMS[-1] == 'W':
        coord_DD *= -1
    
    # Return the decimal degrees
    return coord_DD

def convert_dd_to_dms(lat_coord_DD, lon_coord_DD):
    """converts a co-ordinate pair from Decimal Degrees to Degrees-Minutes-Seconds
    
    Parameters
    ----------
    lat_coord_DD : float
        latitude in decimal degrees
    lon_coord_DD : float
        longitude in decimal degrees
    
    Returns
    -------
    tuple (str)
        lat and lon in Degrees Minutes Seconds in format dddmmssX (X=N/S/W/E)
        
    """
    # Set working variables
    working_lat_dd = abs(lat_coord_DD)
    working_lon_dd = abs(lon_coord_DD)
    
    # Start with degrees, and pad with leading zeros 
    lat_coord_dms = f'{int(working_lat_dd)}'.zfill(2)
    lon_coord_dms = f'{int(working_lon_dd)}'.zfill(3)
    
    # Remove the degrees and calculate the minutes
    working_lat_dd = (working_lat_dd - int(working_lat_dd)) * 60
    working_lon_dd = (working_lon_dd - int(working_lon_dd)) * 60
    
    # Add the minutes, padding with leading zeros
    lat_coord_dms += f'{int(working_lat_dd)}'.zfill(2)
    lon_coord_dms += f'{int(working_lon_dd)}'.zfill(2)
    
    # Remove the minutes and calculate the seconds
    working_lat_dd = (working_lat_dd - int(working_lat_dd)) * 60
    working_lon_dd = (working_lon_dd - int(working_lon_dd)) * 60
    
    # Add the seconds, padding with leading zeros
    lat_coord_dms += f'{int(round(working_lat_dd,0))}'.zfill(2)
    lon_coord_dms += f'{int(round(working_lon_dd,0))}'.zfill(2)
    
    # Finally add the cardinal point - N and E are positive, S and W are negative
    lat_coord_dms += 'N' if lat_coord_DD >= 0 else 'S'
    lon_coord_dms += 'E' if lon_coord_DD >= 0 else 'W'

    # Return a tuple of the DMS co-ordinates
    return lat_coord_dms, lon_coord_dms


def convert_bounded_dms_to_dd(bounded_coords, lat_lon_separator=",", coord_group_separator=" ", return_as_tuples=True, reverse_coords=False):
    """Converts a series of co-ordinates forming a bounded area, from Degrees-Minutes-Seconds to Decimal Degrees
    Accepts formats: ddmmS ddmmN dddmmE dddmmW ddmmssS ddmmssN dddmmssE dddmmssW
    Example bounded_coords: "2632S,02833E 2633S,02920E 2730S,02830N"
    
    Parameters
    ----------
    bounded_coords : str
        a string of co-ordinate pairs, where pairs are separated by <coord_group_separator> and 
        individual lat/lon co-ordinates are separated by <lat_lon_separator>
        
    lat_lon_separator : str, default = ","
        separator between the latitude and longitude co-ordinates
    
    coord_group_separator : str, default = " "
        separator between co-ordinate pairs
    
    return_as_tuples : bool, default = True
        return the co-ordinates as tuples of (lat,lon)?  Otherwise return as a string using same separators
    
    reverse_coords : bool, default = False
        reverse latitude and longitude?  Some mapping software expects lon,lat which other apps expect lat,lon

    Returns
    -------
    list of tuples, str
        co-ordinate pairs in decimal degrees either as tuples or as a string
        
    """

    # If we need to return a list of tuples, create empty list; otherwise empty string
    if return_as_tuples == True:
        converted_coords = []
    else:
        converted_coords = ""
    
    # Store the order of the co-ordinates in a simple list - we either reverse them or don't
    if reverse_coords == True:
        ordr = [1,0]
    else:
        ordr = [0,1]
        
    # Separate the co-ordinate pairs using the separator, and loop through them
    for coord_grp in bounded_coords.split(coord_group_separator):
        
        # Separate out the individual lat/lon co-ordinates
        coord_split = coord_grp.split(lat_lon_separator)

        if return_as_tuples == True:
            # Convert the pair to a tuple of decimal degrees, storing them in the order we set above; append to list
            converted_coords.append((convert_dms_to_dd(coord_split[ordr[0]]),convert_dms_to_dd(coord_split[ordr[1]])))
        else:
            # Convert the pair to a separated decimal degrees, and separate the pair; append to string
            if len(converted_coords) > 0: converted_coords += coord_group_separator
            converted_coords += f'{convert_dms_to_dd(coord_split[ordr[0]])}{lat_lon_separator}{convert_dms_to_dd(coord_split[ordr[1]])}'

    # Return the resultant list or string
    return converted_coords


def switch_lat_lon(coords, convert_DMS_DD = False):
    """Switched the order of co-ordinate pairs - eg. lat, lon pairs need to be
    represented as lon, lat in some mapping interfaces
    
    Parameters
    ----------
    coords : list
        list of co-ordinate pairs (lat, lon or x, y)
    
    convert_DMS_DD : bool, default = False
        set to True to convert co-ordinates from Degrees Minutes Seconds to Decimal Degrees at the same time

    Returns
    -------
    list of tuples
        list of tuples containing co-ordinate pairs
        
    """
    # Start with empty list
    switched = []

    # For each co-ordinate pair
    for c in coords:
        # If they need to be converted from DMS to DD, convert them, switch the order of the result, and add the tuple to the list
        if convert_DMS_DD == True:
            switched.append((convert_dms_to_dd(c[1]), convert_dms_to_dd(c[0])))
        # Otherwise just switch the order and add the tuple to the list
        else:
            switched.append((c[1], c[0]))
    
    # Return the list of co-ord tuples
    return switched


def get_flight_bounds(flight_plan, offset_dd=0.25):
    """Get the upper-left and lower-right bounding box for a flight plan, and return the co-ordinates
    You have the ability to expand the bounding box by an offset
    
    Parameters
    ----------
    flight_plan : FlightPlan
        FlightPlan object
    
    offset : float, default=0.25
        how many degrees to expand the bounding box by

    Returns
    -------
    list of tuples
        list of two tuples containing upper left and lower-right co-ordinate tuple in decimal degrees
        
    """
    min_x = 360
    min_y = 360
    max_x = -360
    max_y = -360
    
    # Find the min and max points
    for fp_point in flight_plan.FlightPlanPoints:
        min_x = min(min_x, fp_point.Longitude)
        min_y = min(min_y, fp_point.Latitude)
        max_x = max(max_x, fp_point.Longitude)
        max_y = max(max_y, fp_point.Latitude)

    # Return them as co-ordinate pairs, taking the offset into account to enlarge the bounding box
    return [[min_x - offset_dd, min_y - offset_dd], [max_x + offset_dd, max_y + offset_dd]]


def get_shape_bounds(shapely_geom, offset_dd=0.25):
    """Get the upper-left and lower-right bounding box for a Shapely geometry, and return the co-ordinates
    You have the ability to expand the bounding box by an offset
    
    Parameters
    ----------
    shapely_geom : Shapely.geometry
        A Shapely geometry object (polygon, linestring, etc.)
    
    offset : float, default=0.25
        how many degrees to expand the bounding box by

    Returns
    -------
    list of tuples
        list of two tuples containing upper left and lower-right co-ordinate tuple in decimal degrees
        
    """

    # Find the min and max points using Shapely's bounds function
    min_x = shapely_geom.bounds[0]
    min_y = shapely_geom.bounds[1]
    max_x = shapely_geom.bounds[2]
    max_y = shapely_geom.bounds[3]
    
    # Return them as co-ordinate pairs, taking the offset into account to enlarge the bounding box
    return [[min_x - offset_dd, min_y - offset_dd], [max_x + offset_dd, max_y + offset_dd]]

def convert_rgb_to_hex(r,g,b):
    hex_colour='#'
    hex_colour += hex(r)[2:]
    hex_colour += hex(g)[2:]
    hex_colour += hex(b)[2:]
    
    return hex_colour
    


def generate_circle_shapely(centerLat, centerLon, radius_nm, format_is_dms=True, number_vertices=32):
    """Creates a "Shapely" geometry polygon object that approximates a circle with centre at centerLat and centerLon, 
    and a radius of radius_nm.  Center point co-ordinates either in decimal degrees
    or in degrees-minutes-seconds
    
    Parameters
    ----------
    centerLat
        Latitude of the centre point - either a float (if decimal degrees) or a string (if degrees-minutes-seconds)
    centerLon
        Longitude of the centre point - either a float (if decimal degrees) or a string (if degrees-minutes-seconds)
    radius_nm : int
        radius of the circle in nautical miles
    format_is_dms : bool, default=True
        Are the co-ordinates in Degrees-Minutes-Seconds (eg. 0283422S)?  If not, they are Decimal Degrees
    number_vertices : int, default=32
        The number of vertices the circles should have - more vertices mean a more accurate circle

    Returns
    -------
    Shapely.geometry.Polygon
        A Shepely Polygon object approximating a circle
        
    """

    # Convert radius from nautical miles to metres
    radius_m = radius_nm * 1853
    
    # Create the circle using the PolyCircle library
    # If Degrees-Minutes-Seconds, convert to decimal degrees and then create
    if format_is_dms == True:
        polycircle = polycircles.Polycircle(latitude=convert_dms_to_dd(centerLat), longitude=convert_dms_to_dd(centerLon), 
                                            radius=radius_m, number_of_vertices=number_vertices)
    else:
        polycircle = polycircles.Polycircle(latitude=centerLat, longitude=centerLon, 
                                            radius=radius_m, number_of_vertices=number_vertices)

    # Get the co-ordinates of the circle (in lat,lon pairs)
    circ_coord = polycircle.to_lat_lon()

    # Create the Shapely Polygon (which needs coods in lon,lat pairs - so switch them(
    spolygon = Polygon(switch_lat_lon(circ_coord)) 
    
    return spolygon


def send_mail(sender, recipients_to, subject, body_text, body_html):
    """Sends an e-mail based on the e-mail details passed in the parameters, 
    including both a text and an HTML version of the message.
    Any errors are logged as ERRORS - Errors in this app usually send e-mails to the administrator which may also fail 
    
    Parameters
    ----------
    sender : email.headerregistry.Address
        Sender's e-mail address as an email.headerregistry.Address object
    
    recipients_to : email.headerregistry.Address
        Recipient's e-mail address as an email.headerregistry.Address object
    
    subject : str
        email Subject Line
    
    body_text : str
        email message body in text

    body_html : str
        email message body in HTML
    Returns
    -------
    bool
        Was e-mail successfully sent?
        
    """
    
    # Create the message
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender 
    msg['To'] = recipients_to 
    
    # Set the text body, and then add the html as well
    msg.set_content(body_text)
    msg.add_alternative(body_html, subtype='html')

    # Create an SSL default context for use in TLS messages
    context = ssl.create_default_context()
    
    # Is App setup to use TLS?
    if current_app.config['EMAIL_USE_TLS'] == True:
        # Sent the email, catching and logging any exceptions
        try:
            with smtplib.SMTP(current_app.config['EMAIL_HOST'], current_app.config['EMAIL_PORT']) as server:
                server.starttls(context=context)
                server.login(current_app.config['EMAIL_HOST_USER'], current_app.config['EMAIL_HOST_PASSWORD'])
                server.send_message(msg)
        except Exception as exception:
            current_app.logger.error(f'Error occurred sending TLS e-mail: {exception}')
            current_app.logger.warning(f'Address was {recipients_to} ')
            return False
            
    # Is App setup to use SSL?
    elif current_app.config['EMAIL_USE_SSL'] == True:
        # Sent the email, catching and logging any exceptions
        try:
            with smtplib.SMTP_SSL(current_app.config['EMAIL_HOST'], current_app.config['EMAIL_PORT'], context=context) as server:
                server.login(current_app.config['EMAIL_HOST_USER'], current_app.config['EMAIL_HOST_PASSWORD'])
                server.send_message(msg)
        except Exception as exception:
            current_app.logging.error(f'Error occurred sending SSL e-mail: {exception}')
            current_app.logging.warning(f'Address was {recipients_to} ')
            return False

    # Email sent successfully
    return True