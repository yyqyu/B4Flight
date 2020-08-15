"""Handles Flight Administration on HTML Pages

This module contains views to 
Upload a Flight Plan/Route
View list of flights, and edit them
Create new flight point-to-point


Functionality is implemented using FLASK

"""

import os
import json

from sqlalchemy import func, and_

from flask import (
    Blueprint, redirect, render_template, request, session, url_for, current_app, flash, abort
)
from werkzeug.utils import secure_filename

from datetime import datetime

from . import helpers, flightplans
from .auth import requires_login
from .db import FlightPlan, FlightPlanPoint, NavPoint
from .data_handling import sqa_session    #sqa_session is the Session object for the site

bp = Blueprint('flightadmin', __name__)


@bp.route('/uploadroute', methods=('GET', 'POST'))
@requires_login
def uploadroute():
    """Displays HTML page that allows a user to upload a flightplan
    Various validations are performed on the files
    """
    
    # If user has submitted the form
    if request.method == "POST":
        
        # Client-side validations were performed - these are a backup
        # was a filename provided
        if 'filename' not in request.files:
            flash('No file was selected')
            return redirect(request.url)
        
        up_file = request.files['filename']
        if up_file.filename == '':
            flash('No file was selected')
            return redirect(request.url)
        
        # Check file is a GPX or EP1
        file_ext = up_file.filename.rsplit('.', 1)[1].lower()
        if not file_ext in ['gpx','ep1']:
            flash('We currentl only support files with EP1 and GPX extensions.')
            return redirect(request.url)
            
        # Generate a unique filename to store the flightplan with on the server
        filename = f"{session['userid']}__{datetime.strftime(datetime.utcnow(), '%Y%m%d%H%M%S%f')}__{secure_filename(up_file.filename)}"
        
        # Check the upload folder exists - if not, create it
        if not os.path.exists(current_app.config['UPLOAD_ARCHIVE_FOLDER']):
            os.makedirs(current_app.config['UPLOAD_ARCHIVE_FOLDER'])

        # Create file path and save the file
        full_path = os.path.join(current_app.config['UPLOAD_ARCHIVE_FOLDER'], filename)
        up_file.save(full_path)
        
        # Add a route description
        if request.form['routedesc']:
            desc = request.form['routedesc']
        else:
            desc = "Imported Route"
            
        # File is saved, now create FlightPlan object.  
        if file_ext == 'gpx':
            fplan, err_msg = flightplans.read_gpx_file(full_path, session['userid'], desc) #Read the GPX file
        elif file_ext == 'ep1':
            fplan, err_msg = flightplans.read_easyplan_file(full_path, session['userid'], desc) #Read the EP1 file
        
        # If an error message was returned - i.e. file wasn't validated successfully - flash it and return to the Upload page
        if err_msg:
            flash(err_msg)

        # Otherwise, create the flightplan and display a "success" page
        else:
            sqa_sess = sqa_session()
            sqa_sess.add(fplan)
            sqa_sess.commit()
            new_id = fplan.FlightplanID

            # Generate GEOJSON so we can show a small version of the flightplan to user
            flight_geojson = flightplans.generate_flight_geojson(new_id) 
            
            # Get flight bounds and centre point to focus the map.
            flight_bounds = helpers.get_flight_bounds(fplan)
            flight_centre = [(flight_bounds[0][0] + flight_bounds[1][0])/2, (flight_bounds[0][1] + flight_bounds[1][1])/2]
            
            # Return an upload-succes page
            return render_template('maps/uploadsuccess.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], filename=filename,
                                   flight_geojson=flight_geojson, flight_bounds=flight_bounds, flight_centre=flight_centre,
                                   fplan=fplan)
    
    return render_template('maps/uploadroute.html')




@bp.route('/listflights', methods=('GET', 'POST'))
@requires_login
def listflights():
    """Displays HTML page that allows a user to view existing flights and click to edit them
    """
    # Intialise the SQLAlchemy session we'll use
    sqa_sess = sqa_session()

    # Load the flights for this user- newest to oldest
    flights = sqa_sess.query(FlightPlan).filter(and_(FlightPlan.UserID == session.get("userid"), FlightPlan.Is_Deleted == False)).order_by(FlightPlan.FlightplanID.desc()).all()

    return render_template('maps/listflights.html', flights=flights)


@bp.route('/editflight/<int:flight_id>', methods=('GET', 'POST'))
@requires_login
def editflight(flight_id):
    """Displays HTML page that allows a user to view and edit an existing flight
    
    """
    
    # Intialise the SQLAlchemy session we'll use
    sqa_sess = sqa_session()

    # Retrieve the Flight
    flight = sqa_sess.query(FlightPlan).get(flight_id)
    
    #Check the flight exists
    if flight is None:
        abort(404)
        
    # Check that the Flight belongs to the currently logged-in user, and user is not an admin
    if flight.UserID != int(session['userid']) and session['user_admin'] == False:
        abort(403)

    # Process the POST request
    if request.method == "POST":
        # If the Flight was Deleted (i.e. hidden form field was set to 1)
        if request.form['flight_deleted'] == "1":
            # Mark it as deleted in the DB and commit
            flight.Is_Deleted = True
            sqa_sess.commit()
            # Display success message and return to the list of flights 
            flash("Your flight was successfully deleted.", "success")
            return redirect(url_for('flightadmin.listflights'))
        
        # If flight not deleted, then proceed to update it
        else:
            
            # Get fields off the FORM
            flight.Flight_Desc = request.form['flightdesc']
            flight.Flight_Name = request.form['flightname']
            
            # Do validation to ensure all fields are entered - backup to existing client-side validation
            if request.form['flightdesc'] == '':
                flash('Please enter a flight description', 'error')
            elif request.form['flightname'] == '':
                flash('Please enter a flight name', 'error')
            
            # Validation passed, so update database and display success message - return to list of flights
            else:
                sqa_sess.commit()
                flash("Your flight was successfully updated.", "success")
                return redirect(url_for('flightadmin.listflights'))
                
    # Either form not posted, or validations failed
    
    # Get the flightplan's GEOJson representation 
    flight_geojson = flightplans.generate_flight_geojson(flight_id) 
    
    # Get flight bounds and centre point to focus the map.
    flight_bounds = helpers.get_flight_bounds(flight)
    flight_centre = [(flight_bounds[0][0] + flight_bounds[1][0])/2, (flight_bounds[0][1] + flight_bounds[1][1])/2]

    # Display the form with flight details
    return render_template('maps/editflight.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], flight_geojson=flight_geojson, 
                           flight_bounds=flight_bounds, flight_centre=flight_centre, flight=flight)



@bp.route('/enterroute', methods=('POST','GET'))
def enterroute():
    """Displays HTML page that allows a user to capture a new Flightplan by entering waypoints
    """
    
    if request.method == 'POST':
        # Do validation to ensure all fields are entered - backup to existing client-side validation
        if request.form['flightdesc'] == '':
            flash('Please enter a flight description', 'error')
        elif request.form['flightname'] == '':
            flash('Please enter a flight name', 'error')
        elif request.form['route'] == '':
            flash('Please enter a flight route', 'error')
        
        # Validation passed, so update database and display success message - return to list of flights
        else:
            # Process the route, returning whether it is valid, route points, and an error message
            route_valid, route_list, error_msg = process_flightplan_points(request.form['route'])
            
            # If route is not valid, return an error message
            if route_valid == False:
                flash(error_msg, 'error')
            
            # Otherwise create the FlightPlan
            else:
                
                # Populate with details
                flight = FlightPlan()
                flight.Flight_Desc = request.form['flightdesc']
                flight.Flight_Name = request.form['flightname']
                flight.Import_Date = datetime.utcnow()
                flight.UserID = session['userid']
                flight.FlightPlanPoints = route_list
                
                # Create session and write to database
                sqa_sess = sqa_session()
                
                sqa_sess.add(flight)
                sqa_sess.commit()
                
                # Re-route to the flightbriefing map
                return redirect(url_for('viewmap.flightmap', flight_id=flight.FlightplanID))
            
    
    return render_template('maps/enterroute.html', mapbox_token=current_app.config['MAPBOX_TOKEN'])


@bp.route('/validateroute', methods=('POST',))
def validateroute():
    """Implements AJAX call to create a check a route made up of significant points (eg "FAGM GAV FAPY RD FAGM")
    Returns JSON structure containing status on whether route is valid:
    - if route is not valid, return list of Waypoints and whether they are valid or not 
    - if route is valid then return a GEOJSON structure
    
    Expects: json data to be POSTed containing route string { route: <STR> }
    
    Returns: json structure {   is-route-valid: false ,
                                route-points: [{point-name: <STR>, is-valid: <BOOL>, longitude: <FLOAT>, latitude: <FLOAT>},...] 
                            }
                            ---OR---
                            json structure {   is-route-valid: true ,
                                GEOJSON: <GEOJSON OBJECT> 
                            }
    
    """

    # Process hte request's data
    if request.method == 'POST':
        # Get data in JSON format
        req_data = request.get_json()

        # If there is request data then process it
        if req_data:
            # Get the route text
            route_text = req_data.get('route')
            
            # If no route text then log an error_msg and return false
            if not route_text:
                current_app.logger.warning(f'No route was posted. URL [{request.url}] ... JSON Data[{request.get_json()}]')
                return json.dumps({'is-route-valid' : False, 'route_points' : [], 'error' : 'No Waypoints in the route'})
                
            # Process the route, returning whether it is valid, route points, and an error_msg message
            route_valid, route_list, error_msg = process_flightplan_points(route_text)
            
            # If the route is not valid, return it
            if route_valid == False:
                return json.dumps({'is_route_valid' : False, 'route_points' : route_list, 'error' : error_msg})
            
            # Route is valid
            # Create a Flightplan object - used to create a GEOJSON object
            fplan = FlightPlan()
            
            # Add the FlightPlanPoints to the route (if route is valis, then route_list is a list of FlightPlanPoint objects
            fplan.FlightPlanPoints = route_list
            # Pass flightplan to generate a GEOJSON object, generating a JSON response showing route is valid 
            fpl_geojson = flightplans.generate_flight_geojson(flightplan_object=fplan)

            # Then return a JSON string, showing the status and the GEOJSON object
            fp_json = json.dumps({'is_route_valid' : route_valid, 'GEOJSON' : fpl_geojson})
                
            return fp_json 
            
    # No request data passed
    return json.dumps({'is_route_valid' : False, 'error' : 'No request data passed'})


def process_flightplan_points(route_text):
    """Processes the textual route made up of significant points (eg "FAGM GAV FAPY RD FAGM")
    Returns JSON structure containing status on whether route is valid:
    - if route is not valid, return list of Waypoints and whether they are valid or not 
    - if route is valid then return a list of FlightPlanPoints
    
    Parameters
    ----------
    route_text : str
        route string
    
    Returns
    -------
    bool
        Is the route valid?
    list
        If route is valid: list of route-points: [{point-name: <STR>, is-valid: <BOOL>}] 
        If route is not valid: list of FlightPlanPoints
    str
        String containing details of error message
    
    """
    # Clean the route up: Trim it, replace "dashes" with "spaces" and convert to UPPERCASE
    route = route_text.strip().replace('-', ' ').upper()
    # Replace Newline with space
    route = route.replace('\n', ' ')
    # Replace any double-spacing with single spacing
    while route.find('  ') > -1:
        route = route.replace('  ', ' ')
    
    # Split out waypoints - separated by spaces
    route_list = route.split(' ')
    
    # Check there are more than 2 waypoints
    if len(route_list) < 2:
        return False, [], 'Only 1 Waypoint in the route'
    
    # Start builing up the route - start with empty lists
    route_points = []
    fpl_points = []
    fplan = FlightPlan()
    
    # Connect to DB
    sqa_sess = sqa_session()

    # Route starts out as valid
    route_valid = True
    # Process each waypoint
    for point in route_list:
        # Does it exist in the nav database?
        pt = sqa_sess.query(NavPoint).filter(NavPoint.ICAO_Code == point).first()
        # Yes it exists
        if pt:
            # Add it to list of points as valid
            route_points.append({'point_name':point, 'is_valid': True})
            # Add it to the list of FlightPLanPoint objects
            fpl_points.append(FlightPlanPoint(Latitude=pt.Latitude, Longitude=pt.Longitude, Name=point))
        
        # No waypoint doesn't exist
        else:
            # Route no longer valid
            route_valid = False
            # Mark this point as invalid
            route_points.append({'point_name':point, 'is_valid': False})
    
    # If the entire route is valid
    if route_valid:
        # Return the valid route and list of FlightPlanPoints
        return True, fpl_points, ''
        
    # Route is not valid
    else:
        # Create return valud that shows route is not valid, containing list of points showing which specific points are not valid
        return False, route_points, 'Some waypoints are invalid'
    
