'''
Created on 26 Jun 2020

@author: aretallack
'''
from datetime import datetime

from sqlalchemy import func, and_

import xml.etree.ElementTree as ET
from polycircles import polycircles
from shapely import geometry 

from geojson import LineString, Feature

from flightbriefing.db import User, FlightPlan, FlightPlanPoint
from flightbriefing.notams import Notam, Briefing
from flightbriefing.data_handling import sqa_session    #sqa_session is the Session object for the site
from . import helpers





'''---------------------------------------
 read_gpx_file(filename)

 PURPOSE: Reads a GPX file and extracts the routes in the file

 INPUT: gpxFilename = path and filename to read
 RETURNS: List of FlightPlan Objects

---------------------------------------'''

def read_gpx_file(filename, user_id):
    #open GPX file - it is in XML format
    tree = ET.parse(filename)
    root = tree.getroot()

    #see if there is a namespace - there should be.
    if root.tag[0] == '{':
        ns = root.tag[:root.tag.find('}')+1]

    routes=[]

    #find all the "rte" (route) elements - each contains a series of "rtept" (route points)
    for route in root.findall(ns+'rte'):
        this_route = FlightPlan()

        rtname = route.find(ns+'name').text
        if rtname is None:
            rtname = 'Imported Flight'
        if rtname == '':
            rtname = 'Imported Flight'
            
        this_route.Flight_Name = rtname
        this_route.UserID = user_id
        this_route.Import_Date = datetime.today()
        this_route.File_Name = filename

        routePts = []
        #get route points
        for routePt in route.findall(ns+'rtept'):
            this_pt = FlightPlanPoint()
            this_pt.Latitude = float(routePt.attrib['lat'])
            this_pt.Longitude = float(routePt.attrib['lon'])
            elev = routePt.find(ns+'ele').text
            if elev == "":
                elev = 0
            this_pt.Elevation = elev
            routePts.append(this_pt)
        
        this_route.FlightPlanPoints = routePts
        routes.append(this_route)

    return routes

def generate_geojson(flightplan_id):
    
    #Collection of all the flightplans/routes (usually only 1)
    route_features = []

    sqa_sess = sqa_session()
    
    #retrieve the fligtplan for the specified ID
    flightplan = sqa_sess.query(FlightPlan).filter(FlightPlan.FlightplanID == flightplan_id).first()
    
    #create a GEOJSON Linestring
    point_list = []
    for rte_point in flightplan.FlightPlanPoints:
        point_list.append((rte_point.Longitude, rte_point.Latitude))

    geojson_geom = LineString(point_list)
        
    route_features.append(Feature(geometry=geojson_geom, properties={'line-color': '#6666ff', 
                                                             'group': 'Flight',
                                                             'layer_group': 'flight', 
                                                             'flight_name': flightplan.Flight_Name}))
    
    return route_features



def filter_route_notams(flightplan_id, buffer_width_nm, includeMatches=True, date_of_flight=None):

    sqa_sess = sqa_session()
    
    #retrieve the fligtplan for the specified ID
    flightplan = sqa_sess.query(FlightPlan).filter(FlightPlan.FlightplanID == flightplan_id).first()
    
    #retrieve the latest Briefing
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    #retrieve the notams for the latest Briefing
    if date_of_flight is None:
        notam_list = sqa_sess.query(Notam).filter(Notam.BriefingID == latest_brief_id).order_by(Notam.A_Location).all()
    else:
        notam_list = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == latest_brief_id, Notam.From_Date <= date_of_flight, Notam.To_Date >= date_of_flight)).all()
        
    #loop through the Route Points, adding them to a LineString
    lstring = []
    for rtePoint in flightplan.FlightPlanPoints: #First element is name, second is co-ordinates
        lstring.append((float(rtePoint.Longitude),float(rtePoint.Latitude)))

    #Create a Shapely linestring for the route
    route = geometry.LineString(lstring)

    #create a buffer
    buffer_width_deg = buffer_width_nm / 60.0  #approximate the NM buffer on the basis that 1 minute = 1 nm

    
    #-----To plot the RouteBuffer, split the route to prevent the polygon closing and filling.
    rl = int(len(route.coords)/2.0)
    route1 = geometry.LineString(route.coords[:rl])
    route2 = geometry.LineString(route.coords[rl-1:])
    #Create the buffer
    fplShapelyBuffers = [route1.buffer(buffer_width_deg)]
    fplShapelyBuffers.append(route2.buffer(buffer_width_deg))

    
    #Now process each NOTAM, and check for intersection with the route buffer.
    filtered_notams = []
    for this_notam in notam_list:
     
        #Generate either a "Shapely" circle or a "Shapely" point for this NOTAM 
        if this_notam.Bounded_Area:
            coords = helpers.convert_bounded_dms_to_dd(this_notam.Bounded_Area, reverse_coords=True)
            notam_shape = geometry.Polygon(coords)
            
        elif this_notam.Radius == 1:
            #long then lat
            notam_shape = geometry.Point(helpers.convert_dms_to_dd(this_notam.Coord_Lon), helpers.convert_dms_to_dd(this_notam.Coord_Lat)) #Shapely Point
        else:
            notam_shape = helpers.generate_circle_shapely(this_notam.Coord_Lat, this_notam.Coord_Lon, this_notam.Radius)
        
        doesIntersect = False #Does this Notam intersect the Route Buffer?
        for routeBuf in fplShapelyBuffers:
            if routeBuf.intersects(notam_shape): doesIntersect = True
        
        #This NOTAM does intersect the route, therefore is of interest:
        if doesIntersect == includeMatches:
            #Add NOTAM to list of notams
            filtered_notams.append(this_notam)


    #Return the new Filtered list of notams
    return filtered_notams

