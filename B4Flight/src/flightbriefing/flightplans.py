"""Handles FlightPlan-related Functionality

This module contains functions to import flightplans, 
generate GEOJSON representations of flightplans,
and filter NOTAMS relevant to a specific flightplan

"""

from datetime import datetime

from sqlalchemy import func, and_

import xml.etree.ElementTree as ET
from shapely import geometry 

import re

from flask import session, current_app
from geojson import LineString, Feature

from .db import FlightPlan, FlightPlanPoint, Notam, Briefing, UserSetting
from .data_handling import sqa_session    #sqa_session is the Session object for the site
from . import helpers



def read_gpx_file(filename, user_id, flight_description):
    """Reads a GPX file and extracts the first route in the file, 
    creating instances of FlightPlan and FLightPlanPoint objects.
    If more than one route exists, only the first will be read.
    
    Parameters
    ----------
    gpxFilename : str
        path and filename to read
    user_id : str
        user_id of the user this flight "belongs" to
    flight_description : str
        user-entered description for the flightplan
    
    Returns
    -------
    FlightPlan 
        FlightPlan object containing route details
    str
        Error message
    """
    
    error_msg = None
    
    # Open GPX file - it is in XML format
    try:
        tree = ET.parse(filename)
        root = tree.getroot()

    # If we can't parse the XML file, throw an error
    except:
        # Log the error - the error handler should send an email
        current_app.logger.error(f'Uploaded GPX file not in XML Format - User is {user_id} - File is {filename}')

        # Return an error message
        error_msg = 'The GPX file does not appear to be in the correct format - no XML structure found.'
        return None, error_msg
        

    # See if there is a namespace - there should be.
    if root.tag[0] == '{':
        ns = root.tag[:root.tag.find('}')+1]

    # Find the first "rte" (route) element - it should contain a series of "rtept" (route points)
    route = root.find(ns+'rte')
    
    # Check that a route was found - if not, log an error
    if route is None:
        # Log the error - the error handler should send an email
        current_app.logger.error(f'Uploaded GPX file - route (RTE) not found - User is {user_id} - File is {filename}')

        # Return an error message
        error_msg = 'The GPX file does not appear to be in the correct format - no RTE (Route) was found.'
        return None, error_msg
        
        
        
    # Create FlightPlan object
    this_route = FlightPlan()

    # If there is no route name, then default to Imported Flight
    try:
        rtname = route.find(ns+'name').text
    except:
        rtname = 'Imported Flight'
    
    # Add Flightplan Details
    this_route.Flight_Name = rtname
    this_route.Flight_Desc = flight_description
    this_route.UserID = user_id
    this_route.Import_Date = datetime.utcnow()
    this_route.File_Name = filename

    routePts = []
    # Loop through route points in the XML file
    for routePt in route.findall(ns+'rtept'):
        this_pt = FlightPlanPoint()

        # If co-ordinates are not in correct format, log an error
        try:
            this_pt.Latitude = float(routePt.attrib['lat'])
            this_pt.Longitude = float(routePt.attrib['lon'])
        except:
            # Log the error - the error handler should send an email
            current_app.logger.error(f'Uploaded GPX file has invalid co-ordinates after rtepoint #{len(routePts)} - User is {user_id} - File is {filename}')
            # Return an error message
            error_msg = f'The GPX file does not appear to be in the correct format - invalid co-ordinates after waypoint #{len(routePts)}.'
            return None, error_msg
            
        # Elevation not always included - if missing default to zero.
        try:
            elev = routePt.find(ns+'ele').text
        except:
            elev = 0
            
        if elev == "":
            elev = 0
        this_pt.Elevation = elev
        
        # Get the point name
        try:
            name = routePt.find(ns+'name').text
        # If there is no point name, add numerical point name
        except:
            name = f'Point{len(routePts)+1}'

        this_pt.Name = name
        routePts.append(this_pt)

    # If there are less than 2 Route Points, route is invalid
    if len(routePts) < 2:
        # Log the error - the error handler should send an email
        current_app.logger.error(f'Uploaded GPX file has {len(routePts)} Route Points (RTEPT) - User is {user_id} - File is {filename}')
        # Return an error message
        error_msg = f'The GPX file does not appear to be in the correct format - {len(routePts)} route points were found.'
        return None, error_msg
        
        
    this_route.FlightPlanPoints = routePts

    return this_route, error_msg


def read_easyplan_file(filename, user_id, flight_description):
    """Reads an EasyPlan EP1 file and extracts the route, 
    creating instances of FlightPlan and FLightPlanPoint objects.
    
    Parameters
    ----------
    ep1Filename : str
        path and filename to read
    user_id : str
        user_id of the user this flight "belongs" to
    flight_description : str
        user-entered description for the flightplan
    
    Returns
    -------
    FlightPlan 
        FlightPlan object containing route details
    str
        Error message
    """
    
    error_msg = None
    route = None
    rtname = None

    #regPts = re.compile(r"^Name='(?P<point_name>[\w\s\.,;:\(\)/\\!@#$%^&\*\+\=\-'\"_]+)' Desig\s.*Elevation='(?P<elev>[0-9]+)'\s.*Lat=(?P<lat>[0-9\.]+)\s.*Long=(?P<lon>[0-9\.]+)\s.*")
    #regPts = re.compile(r"Desig=.*Elevation='(?P<elev>[0-9]+)'\s.*Lat=(?P<lat>[0-9\.]+)\s.*Long=(?P<lon>[0-9\.]+)\s.*")

    # Create the regular expression to extract flightplan components.  Example:
    # Name='Johannesburg Rand' Desig='FAGM' In_FP='yes' In_EET='no' Frequency='118.70' Nav_Freq='' Elevation='5483' Lat=26.2425333 Long=28.1511639 MVAR=18.5893044 TAS=90.0000000 WDIR=0.0000000 WSPD=0.0000000 CDEV=0.0000000 FUEL_CONS=8.0000000 FUEL_USED=3.0000000 FUEL_REM=35.0000000 TTRUE=0.0000000 TMAG=0.0000000 QTE=0.0000000 QUJ=237.4183847 QDR=0.0000000 QDM=0.0000000 HTRUE=0.0000000 HMAG=0.0000000 HCOMP=0.0000000 HEIGHT=7000.0000000 GSPD=0.0000000 DIST=15.0000000 ACC_DIST=0.0000000 DIST_REM=143.0084685 TLEG=0.0000000 ACC_TIME=0.0000000 ETA=0.0000000 RETA=0.0000000 ATA=0.0000000 NOTES='' EN_ROUTE='' FUEL_DEST=12.7118639 MSA=0.0000000 GRID_MORA=0.0000000
    regPts = re.compile(r"^Name='(?P<point_name>[\w\s\.,;:\(\)/\\!@#$%^&\*\+\=\-'\"_]+)'\sDesig=.*Elevation='(?P<elev>[0-9]+)'\s.*Lat=(?P<lat>[0-9\.]+)\s.*Long=(?P<lon>[0-9\.]+)\s.*")
    routePts = []

    with open(filename, "r") as ep_file:
        for in_line in ep_file:
            if in_line[:6] == "Route=":
                rtname = in_line.strip()[7:-1]
                rtname = rtname.replace("'", "")

            elif in_line[:5] == "Name=":

                # Use the Regular Expression to extract the components of the point
                try:
                    regPt = regPts.match(in_line.strip())

                    this_pt = FlightPlanPoint()
                    this_pt.Latitude = float(regPt['lat']) * -1 #EasyPlan doesn't sign the southern hemisphere
                    this_pt.Longitude = float(regPt['lon'])
                    this_pt.Elevation = int(regPt['elev'])
                    this_pt.Name = regPt['point_name']
                    routePts.append(this_pt)

                # If there's an error, log it and exit
                except:
                    # Log the error - the error handler should send an email
                    current_app.logger.error(f'Uploaded EP1 file failed matching RE on point #{len(routePts)} - User is {user_id} - File is {filename}')
                    # Return an error message
                    error_msg = 'The EP1 file does not appear to be in the correct format - error processing route points.'
                    return route, error_msg

    
    # If there are no Route Points, Log an error
    if len(routePts) < 2:
        # Log the error - the error handler should send an email
        current_app.logger.error(f'Uploaded EP1 file has {len(routePts)} Route Points (RTEPT) - User is {user_id} - File is {filename}')
        error_msg = f'The EP1 file does not appear to be in the correct format - {len(routePts)} route points were found.'
        
    # Otherwise create a flightplan
    else:
        if rtname is None: 
            rtname = 'Imported Route'
            current_app.logger.error(f'Uploaded EP1 file had no route name, but upload was successful - User is {user_id} - File is {filename}')
        
        route = FlightPlan()
        route.Flight_Name = rtname
        route.Flight_Desc = flight_description
        route.UserID = user_id
        route.Import_Date = datetime.utcnow()
        route.File_Name = filename
        route.FlightPlanPoints = routePts

    return route, error_msg


def generate_flight_geojson(flightplan_id):
    """Create a GEOJSON feature object from a FlightPlan, to be used
    by MapBox
    
    Parameters
    ----------
    flightplan_id : int
        The FlightPlan's ID
    
    Returns
    -------
    list
        GEOJSON Features (even though only 1 flightplan, a list needs to be returned with 1 element for it to be mapped correctly)
    """
    
    sqa_sess = sqa_session()
    
    # Retrieve the fligtplan for the specified ID
    flightplan = sqa_sess.query(FlightPlan).filter(FlightPlan.FlightplanID == flightplan_id).first()
    
    route_feature = []
    point_list = []
    # Loop through each route point, adding tuples of coordinates
    for rte_point in flightplan.FlightPlanPoints:
        point_list.append((rte_point.Longitude, rte_point.Latitude))

    # Create a GEOJSON Linestring from the tuples
    geojson_geom = LineString(point_list)
    
    #Set the line colour using the User's setting - if no setting, don't create one (use the app default)
    line_colour = UserSetting.get_setting(session['userid'], 'flight_route_colour', create_if_missing=False).SettingValue
    
    # Create the GEOJson feature
    this_route = Feature(geometry=geojson_geom, properties={'line-color': line_colour, 
                                                             'group': 'Flight',
                                                             'layer_group': 'flight', 
                                                             'flight_name': flightplan.Flight_Name})
    route_feature.append(this_route)
    
    return route_feature


def filter_route_notams(flightplan_id, buffer_width_nm, include_matches=True, date_of_flight=None):
    """Filters NOTAMS that are relevant to a flightplan.  
    Creates a Shapely geometry for the flightplan then calls "filter_relevant_notams" function

    Relevent NOTAMS are those within 'buffer_width_nm' nm either side of the route.
    Buffer is approximate, using the principle of 1 minute of lat = 1 nm
    
    Parameters
    ----------
    flightplan_id : int
        The FlightPlan's ID

    buffer_width_nm : int
        width of buffer along flightplan in approx nautical miles

    include_matches : bool, default = True
        show the NOTAMS that do intersect the buffer. Set to False to see those NOTAMS not on the route

    date_of_flight : date
        filter NOTAMS for a flight on a specific date - i.e. exclude NOTAMS not relevant on that date
        
    Returns
    -------
    list
        List of Notam object that meet criteria
    """

    sqa_sess = sqa_session()
    
    # Retrieve the flightplan for the specified ID
    flightplan = sqa_sess.query(FlightPlan).filter(FlightPlan.FlightplanID == flightplan_id).first()
    
    # Loop through the Route Points, adding them to a series of co-ordinate tuples
    lstring = []
    for rtePoint in flightplan.FlightPlanPoints: 
        lstring.append((float(rtePoint.Longitude),float(rtePoint.Latitude)))

    # Create a Shapely linestring for the route using the tuples of co-ordinates
    route = geometry.LineString(lstring)
    
    # Filter those NOTAMS on the route, and return the results
    return filter_relevant_notams(route, buffer_width_nm, include_matches=include_matches, date_of_flight=date_of_flight)
    

def filter_point_notams(longitude, latitude, buffer_radius_nm, include_matches=True, date_of_flight=None):
    """Filters NOTAMS that are relevant to a specific point - eg. an airfield.  
    Creates a Shapely geometry for the point then calls "filter_relevant_notams" function

    Relevent NOTAMS are those within a radius of 'buffer_radius_nm' nm arounf the point.
    Buffer is approximate, using the principle of 1 minute of lat = 1 nm
    
    Parameters
    ----------
    longitude : float
        Longitude of the point in decimal degrees

    latitude : float
        Latitude of the point in decimal degrees

    buffer_radius_nm : int
        radius of buffer around the point in approx nautical miles

    include_matches : bool, default = True
        show the NOTAMS that do intersect the buffer. Set to False to see those NOTAMS not on the route

    date_of_flight : date
        filter NOTAMS for a flight on a specific date - i.e. exclude NOTAMS not relevant on that date
        
    Returns
    -------
    list
        List of Notam object that meet criteria
    """

    # Create the co-ordinates into a Shapely Point
    point = geometry.Point(longitude, latitude)

    # Filter those NOTAMS around the point, and return the results
    return filter_relevant_notams(point, buffer_radius_nm, include_matches=include_matches, date_of_flight=date_of_flight)



def filter_relevant_notams(shapely_geom, buffer_width_nm, include_matches=True, date_of_flight=None):
    """Filters NOTAMS that are relevant to a specific geographic geometric feature (point, linestring).
    Relevent NOTAMS are those within a 'buffer_width_nm' nm around the feature.
    Buffer is approximate, using the principle of 1 minute of lat = 1 nm
    
    Parameters
    ----------
    shapely_geom : geometry
        Shapely Geometry around which to buffer (Shapely.geometry.Point, Shapely.geometry.LineString)

    buffer_width_nm : int
        width of buffer around the feature in approx nautical miles

    include_matches : bool, default = True
        show the NOTAMS that do intersect the buffer. Set to False to see those NOTAMS not on the route

    date_of_flight : date
        filter NOTAMS for a flight on a specific date - i.e. exclude NOTAMS not relevant on that date
        
    Returns
    -------
    list
        List of Notam object that meet criteria
    """

    sqa_sess = sqa_session()
    
    # Retrieve the latest NOTAM Briefing
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    
    # Retrieve the notams for the latest Briefing, filtering by Date of Flight if necessary
    if date_of_flight is None:
        notam_list = sqa_sess.query(Notam).filter(Notam.BriefingID == latest_brief_id).order_by(Notam.A_Location).all()
    else:
        notam_list = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == latest_brief_id, Notam.From_Date <= date_of_flight, Notam.To_Date >= date_of_flight)).all()
        

    # Calculate the buffer in degrees
    buffer_width_deg = float(buffer_width_nm) / 60.0  #approximate the NM buffer on the basis that 1 minute = 1 nm

    # Circular (closed) geometries, when buffered, create a filled polygon for the buffer.  
    # We don't want that - we want a "hole" in the middle of the buffer
    # To prevent that, we split the route into two and create two route buffers that overlap.
    
    # We only split the geometry if there are more than 2 co-ordinates in the geometry - i.e. it is a route
    if len(shapely_geom.coords)>2:
        
        # Split the route in two.
        rte_len = int(len(shapely_geom.coords)/2.0)
        # If there are 3 points, the above divides the route so that there is only 1 pt.  Make it 2
        if rte_len==1: rte_len=2
        # Separate out the points for route 1
        route1 = geometry.LineString(shapely_geom.coords[:rte_len])
        # Separate out the points for route 2, ensuring the first point overlaps with the last point of the prev route
        route2 = geometry.LineString(shapely_geom.coords[rte_len-1:])
        # Create the 2 buffers
        fplShapelyBuffers = [route1.buffer(buffer_width_deg)]
        fplShapelyBuffers.append(route2.buffer(buffer_width_deg))

    # If there is only one co-ordinate in the geometry - i.e. it is a point 
    else:
        # Buffer the point
        fplShapelyBuffers = [shapely_geom.buffer(buffer_width_deg)]

    # Now process each NOTAM, and check if it intersects with the route buffer.
    filtered_notams = []
    for this_notam in notam_list:
     
        # If the NOTAM has a bounded area - i.e. it is a polygon, create a Shapely Polygon 
        if this_notam.Bounded_Area:
            coords = helpers.convert_bounded_dms_to_dd(this_notam.Bounded_Area, reverse_coords=True)
            notam_shape = geometry.Polygon(coords)
            
        # Otherwise create either a "Shapely" point (radius is 1) or a "Shapely" circle (radius > 1) for this NOTAM 
        elif this_notam.Radius == 1:
            #long then lat
            notam_shape = geometry.Point(helpers.convert_dms_to_dd(this_notam.Coord_Lon), helpers.convert_dms_to_dd(this_notam.Coord_Lat)) #Shapely Point
        else:
            notam_shape = helpers.generate_circle_shapely(this_notam.Coord_Lat, this_notam.Coord_Lon, this_notam.Radius)
        
        doesIntersect = False # Assume this Notam does not intersect the Route Buffer

        # Test whether each of the buffers intersect with this NOTAM's geometry
        for routeBuf in fplShapelyBuffers:
            if routeBuf.intersects(notam_shape): doesIntersect = True
        
        # Check if this is of interest:
        # If we want to show notams that intersect (include_matches == True), add this NOTAM if it intersects
        # If we don't want to show notams that intersect (include_matches == False), add this NOTAM if it does not intersect
        if doesIntersect == include_matches:
            # Add NOTAM to list of notams
            filtered_notams.append(this_notam)


    # Return the new Filtered list of Notam objects
    return filtered_notams

