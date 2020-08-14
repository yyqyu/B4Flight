"""Handles Flight Administration on HTML Pages

This module contains views to 
Upload a Flight Plan/Route
View list of flights, and edit them
Create new flight point-to-point


Functionality is implemented using FLASK

"""

import os

from sqlalchemy import func, and_

from flask import (
    Blueprint, redirect, render_template, request, session, url_for, current_app, flash, abort
)
from werkzeug.utils import secure_filename

from datetime import datetime

from . import helpers, flightplans
from .auth import requires_login
from .db import FlightPlan
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
    """Displays HTML page that allows a user to view existing flights and edit them
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


    if request.method == "POST":
        if request.form['flight_deleted'] == "1":
            flight.Is_Deleted = True
            sqa_sess.commit()
            flash("Your flight was successfully deleted.", "success")
            return redirect(url_for('flightadmin.listflights'))
        
        else:
            flight.Flight_Desc = request.form['flightdesc']
            flight.Flight_Name = request.form['flightname']
            
            if request.form['flightdesc'] == '':
                flash('Please enter a flight description', 'error')
            elif request.form['flightname'] == '':
                flash('Please enter a flight name', 'error')
            else:
                sqa_sess.commit()
                flash("Your flight was successfully updated.", "success")
                return redirect(url_for('flightadmin.listflights'))
                

    flight_geojson = flightplans.generate_flight_geojson(flight_id) 
    
    # Get flight bounds and centre point to focus the map.
    flight_bounds = helpers.get_flight_bounds(flight)
    flight_centre = [(flight_bounds[0][0] + flight_bounds[1][0])/2, (flight_bounds[0][1] + flight_bounds[1][1])/2]

    return render_template('maps/editflight.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], flight_geojson=flight_geojson, 
                           flight_bounds=flight_bounds, flight_centre=flight_centre, flight=flight)
