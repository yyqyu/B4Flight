"""Handles Map and Notam Presentation on HTML Pages

This module contains views to 
Display Notams on a Map (all notams / new notams / notams on flight path / notams for home aerodrome )
Display list of Notam details (all notams / new & deleted notams )
Upload a Flight Plan/Route

Functionality is implemented using FLASK

"""

import os

from sqlalchemy import func, and_

from flask import (
    Blueprint, redirect, render_template, request, session, url_for, current_app, flash, abort
)
from werkzeug.utils import secure_filename

from datetime import datetime, timedelta

from . import helpers, flightplans
from .auth import requires_login
from .db import FlightPlan, Notam, Briefing, UserSetting, NavPoint
from .data_handling import sqa_session    #sqa_session is the Session object for the site
from .notams import get_new_deleted_notams, generate_notam_geojson

bp = Blueprint('viewmap', __name__)


@bp.route('/detailnotams', methods=('GET', 'POST'))
@requires_login
def detailnotams():
    """Displays html template showing Notam Details
    User has ability to select specific briefing
    User has ability to filter for specific flight date
    """    

    # Retrieve all Briefings
    sqa_sess = sqa_session()
    briefings = sqa_sess.query(Briefing.BriefingID, Briefing.Briefing_Ref, Briefing.Briefing_Date).order_by(Briefing.BriefingID.desc()).all()

    # Initialise variables
    notam_list = None
    flight_date = None
    briefing_id = None

    # Start with Notams a flight today
    default_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    # User posts a form filtering specific Notams
    if request.method == "POST":
        briefing_id = request.form['briefing']
        flight_date = request.form['flight_date']
        default_date = flight_date
        
    # Otherwise start with the latest notam
    else:
        briefing_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]

    # Filter for a flight on a specific date if requested
    if flight_date:
        notam_list = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == briefing_id, Notam.From_Date <= flight_date, Notam.To_Date > flight_date))
    # Otherwise fetch all
    else:
        notam_list = sqa_sess.query(Notam).filter(Notam.BriefingID == briefing_id)
        
    
    return render_template('maps/detailnotams.html', briefings = briefings, notams = notam_list, 
                           briefing_id = briefing_id, default_date = default_date, flight_date = flight_date)

    
@bp.route('/changednotams', methods=('GET', 'POST'))
@requires_login
def changednotamdetail():
    """Displays html list showing all New and Expired (deleted) Notams
    User has ability to select which briefing to compare the current briefing to.
    """    
    sqa_sess = sqa_session()
    # Only show Briefings from last 60 days
    since_date = datetime.utcnow().date() - timedelta(days=60)
    # Get the latest briefing
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    # Get all historic briefings except for the latest
    briefings = sqa_sess.query(Briefing.BriefingID, Briefing.Briefing_Ref, Briefing.Briefing_Date).filter(and_(Briefing.Briefing_Date > since_date, Briefing.BriefingID < latest_brief_id)).order_by(Briefing.BriefingID.desc()).all()
    
    # If user has requested a specific briefing, retrieve the New/Expired brifings compared to that briefing
    if request.method == "POST":
        briefing_id = request.form['briefing']
        prev_briefing, new_notams, del_notams = get_new_deleted_notams(briefing_id=briefing_id, return_count_only=False)
    
    # Otherwise, get New/Expired briefings compared to a week ago
    else:
        since_date = datetime.utcnow().date() - timedelta(days=7)
        prev_briefing, new_notams, del_notams = get_new_deleted_notams(since_date, return_count_only=False)
        briefing_id = prev_briefing.BriefingID

    
    return render_template('maps/changednotams.html', briefings = briefings, since_date = prev_briefing.Briefing_Date, prev_briefing_id=str(briefing_id), 
                           new_notams = new_notams, deleted_notams = del_notams)


@bp.route('/listnotams', methods=('GET', 'POST'))
@requires_login
def listnotams():
    """Displays html page showing a list of Notams
    User has ability to select which briefing to show, as well as to filter NOTAMS by flight date
    """    

    # Only want to see last 60 days briefings
    since_date = datetime.utcnow().date() - timedelta(days=60)

    # SQLAlchemy session
    sqa_sess = sqa_session()
    
    # Retrieve Briefing details - these will be displayed in a drop-down on webpage
    briefings = sqa_sess.query(Briefing.BriefingID, Briefing.Briefing_Ref, Briefing.Briefing_Date).filter(Briefing.Briefing_Date > since_date).order_by(Briefing.BriefingID.desc()).all()

    # Initialise Variables
    notam_list = None
    default_date = datetime.utcnow().strftime("%Y-%m-%d")
    briefing_id = None

    # If the user selected specific briefing and flight date use those
    if request.method == "POST":
        briefing_id = request.form['briefing']
        flight_date = request.form['flight_date']
        default_date = flight_date
        
        # If a Flight Date was chosen, filter
        if flight_date:
            notam_list = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == briefing_id, Notam.From_Date <= flight_date, Notam.To_Date > flight_date)).all()
        #Otherwise show all
        else:
            notam_list = sqa_sess.query(Notam).filter(Notam.BriefingID == briefing_id).all()

    
    return render_template('maps/listnotams.html', briefings = briefings, notams = notam_list, default_date = default_date, briefing_id = briefing_id)


    
@bp.route('/viewmap', methods=('GET', 'POST'))
@requires_login
def viewmap():
    """Displays html page showing Notams on a Map
    User has ability to filter NOTAMS by flight date
    """    
    
    # Start with no filter on Flight Date
    flight_date = None
    
    # User has asked to filter by flight date
    if request.method == "POST":
        flight_date = request.form['flight-date']

    # Retrieve the most recent briefing
    sqa_sess = sqa_session()
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)

    # Filter applicable NOtams for the Briefing - filtering by flight date if required
    if flight_date:
        notam_list = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == latest_brief_id, Notam.From_Date <= flight_date, Notam.To_Date >= flight_date)).order_by(Notam.A_Location).all()
    else:
        notam_list = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == latest_brief_id)).order_by(Notam.A_Location).all()
    
    # Create the GEOJSON Features, Groups and Layers needed for the map
    notam_features, used_groups, used_layers = generate_notam_geojson(notam_list)

    # Display the map
    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers,
                           default_flight_date = flight_date)



@bp.route('/flightmap/<int:flight_id>', methods=('GET', 'POST'))
@requires_login
def flightmap(flight_id):
    """Displays html page showing Flight Route and applicable Notams on a Map
    User has ability to filter NOTAMS by flight date
    
    Parameters
    ----------
    flight_id : int
        ID of the flight to show
        
    """    

    # Start without filtering by flight date
    flight_date = None
    
    # User has filtered by Flight Date
    if request.method == "POST":
        flight_date = request.form['flight-date']
    
    #Establish session to connect to DB 
    sqa_sess = sqa_session()

    # Retrieve the Flight
    flight = sqa_sess.query(FlightPlan).get(flight_id)
    
    #Check the flight exists
    if flight is None:
        abort(404)
        
    # Check that the Flight belongs to the currently logged-in user, and user is not an admin
    if flight.UserID != int(session['userid']) and session['user_admin'] == False:
        abort(403)

    # Get latest briefing
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)

    # What buffer does this user want to use?
    buffer_nm = UserSetting.get_setting(session['userid'], 'route_buffer').SettingValue

    # Filter by flight date if one is given
    if flight_date:
        notam_list = flightplans.filter_route_notams(flight_id, buffer_nm, date_of_flight=flight_date)
    else:
        notam_list = flightplans.filter_route_notams(flight_id, buffer_nm)
    
    # Generate the GEOJSON features for the Notams
    notam_features, used_groups, used_layers = generate_notam_geojson(notam_list)

    # Generate the GEOJSON for the flight plan
    flight_geojson = flightplans.generate_flight_geojson(flight_id) 
    
    # Get flight bounds and centre-point, so map can be centered on the flight
    flight_bounds = helpers.get_flight_bounds(flight)
    flight_centre = [(flight_bounds[0][0] + flight_bounds[1][0])/2, (flight_bounds[0][1] + flight_bounds[1][1])/2]

    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers,
                           flight=flight, default_flight_date = flight_date,
                           flight_geojson=flight_geojson, flight_bounds=flight_bounds, flight_centre=flight_centre)


@bp.route('/newnotams', methods=('GET', 'POST'))
@requires_login
def newnotams():
    """Displays html page showing New Notams on a Map
    """
    
    sqa_sess = sqa_session()

    # Get the latest briefing
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)

    # Compare Latest briefing to one from 7 days ago
    prev_briefing, new_notams, del_notams = get_new_deleted_notams(since_date=datetime.utcnow().date() - timedelta(days=7), return_count_only=False)
    
    # Create the GEOJSON Features
    notam_features, used_groups, used_layers = generate_notam_geojson(new_notams)


    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers, prev_briefing=prev_briefing)


@bp.route('/homenotams', methods=('GET', 'POST'))
@requires_login
def homenotams():
    """Displays html page showing Notams within a radius of the user's Home Aerodrome
    User has the ability to filter by date of flight
    """

    # No Flight Date supplied yet
    flight_date = None
    
    # User provides flight date
    if request.method == "POST":
        flight_date = request.form['flight-date']
    
    sqa_sess = sqa_session()
    # Get the latest briefing
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)

    # Get user's home aerodrome and radius to use to filter notams
    home_aerodrome = UserSetting.get_setting(session['userid'], "home_aerodrome").SettingValue
    home_radius = UserSetting.get_setting(session['userid'], "home_radius").SettingValue

    # Get the Nav Point for the home aerodrome
    home_navpt = sqa_sess.query(NavPoint).filter(NavPoint.ICAO_Code == home_aerodrome).first()
    
    # Generate a circle for the radius around the home aerodrome
    radius = helpers.generate_circle_shapely(home_navpt.Latitude, home_navpt.Longitude, int(home_radius), format_is_dms=False)
    
    # Filter applicable Notams within the radius- using the date of flight if supplied
    if flight_date:
        notam_list = flightplans.filter_point_notams(home_navpt.Longitude, home_navpt.Latitude, home_radius, date_of_flight=flight_date)
    else:
        notam_list = flightplans.filter_point_notams(home_navpt.Longitude, home_navpt.Latitude, home_radius)
    
    # Generate the GEOJSON for the notams
    notam_features, used_groups, used_layers = generate_notam_geojson(notam_list)

    # Get bounds and center point for the maps
    flight_bounds = helpers.get_shape_bounds(radius)
    flight_centre = [home_navpt.Longitude, home_navpt.Latitude]

    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers,
                           default_flight_date = flight_date, home_aerodrome=home_aerodrome,
                           flight_bounds=flight_bounds, flight_centre=flight_centre)


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
