"""Handles Map and Notam Presentation on HTML Pages

This module contains views to 
Display Notams on a Map (all notams / new notams / notams on flight path / notams for home aerodrome )
Display list of Notam details (all notams / new & deleted notams )

Functionality is implemented using FLASK

"""

from sqlalchemy import func, and_

from flask import (
    Blueprint, redirect, render_template, request, session, url_for, current_app, flash, abort
)

from datetime import datetime, timedelta

from . import helpers, flightplans
from .auth import requires_login
from .db import FlightPlan, Notam, Briefing, UserSetting, NavPoint, UserHiddenNotam
from .data_handling import sqa_session    #sqa_session is the Session object for the site
from .notams import get_new_deleted_notams, generate_notam_geojson, get_hidden_notams
from .weather import read_sigmet_airmet_ZA, read_metar_ZA, read_taf_ZA, generate_sigmet_geojson, generate_metar_geojson, generate_taf_geojson

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
    notam_features, used_groups, used_layers = generate_notam_geojson(notam_list, hide_user_notams = True)
    
    # Retrieve the SIGMET/AIRMET list and create the GEOJSON collection
    sigair_list = read_sigmet_airmet_ZA(current_app.config['WEATHER_SIGMET_AIRMET_URL_ZA'])
    sigair_geojson, used_wx_groups, used_wx_layers = generate_sigmet_geojson(sigair_list)
    
    # Retrieve the METAR list and create the GEOJSON collection
    metar_list = read_metar_ZA(current_app.config['WEATHER_METAR_URL_ZA'])
    metar_geojson = generate_metar_geojson(metar_list)
    used_wx_groups.append('METAR')
    used_wx_layers.append('METAR_symbol')

    taf_list = read_taf_ZA(current_app.config['WEATHER_TAF_URL_ZA'])
    taf_geojson = generate_taf_geojson(taf_list)
    used_wx_groups.append('TAF')
    used_wx_layers.append('TAF_symbol')
    

    radius_default = UserSetting.get_setting(session['userid'], 'map_radius_filter').SettingValue
    
    # Display the map
    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], radius_default=radius_default, 
                           map_bounds=helpers.get_max_map_bounds(), briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers,
                           sigair_geojson=sigair_geojson, metar_geojson=metar_geojson, taf_geojson=taf_geojson, 
                           used_wx_groups=used_wx_groups, used_wx_layers=used_wx_layers,
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
    
    #What is the purpose of this page?  Is it to print a briefing (True) or to show the map (false)
    purpose_print_brief = False;
    
    # User has clicked on teh "Print" FLight Briefing button
    if request.method == "POST":
        
        # The purpose of this is to print a Flight Briefing
        purpose_print_brief = True;
        #flight_date = request.form['flight-date']
        hidden_notams = request.form['hidden-notams']
        flight_date = request.form['briefing-flight-date']
        print(flight_date)

        # Ensure Flight_Date is correctly set as a DATE 
        if flight_date is not None:
            if flight_date == "": 
                flight_date = None
            else:
                flight_date = datetime.strptime(flight_date,'%Y-%m-%d').date()
        
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

    
    # If this is a text Flight Briefing, then prepare the briefing
    if purpose_print_brief == True:
        
        # Create an array of NOTAMS that were hidden on the map - the user will be able to choose to include these in the briefing
        if hidden_notams:
            hidden_notams = hidden_notams.strip().split(" ")
        else:
            hidden_notams = []
            
        # Get permanently hidden notams
        perm_hidden_notams = get_hidden_notams(latest_brief_id)
        

        # For audit purposes the date the briefing was run
        generate_date = datetime.strftime(datetime.utcnow(), "%Y-%m-%d %H:%M")
        
        # Get the departure point and destination point for the flight plan
        depart = flight.FlightPlanPoints[0]
        dest = flight.FlightPlanPoints[-1]
        
        # Get NOTAMS within 5nm of dep and dest.
        # If the departure and destination are the same, only get for departure point
        if depart.Latitude == dest.Latitude and depart.Longitude == dest.Longitude:
            depart_notams = flightplans.filter_point_notams(depart.Longitude, depart.Latitude, 5, True, flight_date)
            dest_notams = []
        # Otherwise get for departure and destination
        else:
            depart_notams = flightplans.filter_point_notams(depart.Longitude, depart.Latitude, 5, True, flight_date)
            dest_notams = flightplans.filter_point_notams(dest.Longitude, dest.Latitude, 5, True, flight_date)
        
        # Filter by flight date if one is given
        if flight_date:
            enroute_notams = flightplans.filter_route_notams(flight_id, buffer_nm, date_of_flight=flight_date)
        else:
            enroute_notams = flightplans.filter_route_notams(flight_id, buffer_nm)

        # Remove Notams applicable to the departure point from the dest list
        for ntm in depart_notams:
            if ntm in dest_notams: dest_notams.remove(ntm)
        
            # Remove Notams applicable to the departure point from the en-route list
            if ntm in enroute_notams: enroute_notams.remove(ntm)

        # Remove Notams applicable to the dest point from the en-route list
        for ntm in dest_notams:
            if ntm in enroute_notams: enroute_notams.remove(ntm)
        
        # Create a list of relevant permanently hidden Notam Numbers
        relevant_perm_hidden_notams = [n.Notam_Number for n in depart_notams if n.Notam_Number in perm_hidden_notams]
        relevant_perm_hidden_notams += [n.Notam_Number for n in dest_notams if n.Notam_Number in perm_hidden_notams]
        relevant_perm_hidden_notams += [n.Notam_Number for n in enroute_notams if n.Notam_Number in perm_hidden_notams]

        print(f'notam_no_list: {relevant_perm_hidden_notams}')
        print(f'notam_no_list: {perm_hidden_notams}')
        
        
        # We now have Departure, Destination and En-Route notams

        # Get the weather...
        # If flight date is today or tomorrow, retrieve WEATHER and filter it by date
        if flight_date is None or flight_date <= (datetime.utcnow().date() + timedelta(days=1)):
            sigairmet_list = flightplans.filter_route_sigairmets_ZA(flight_id, buffer_nm, current_app.config['WEATHER_SIGMET_AIRMET_URL_ZA'], flight_date)
            
            metar_list, taf_list = flightplans.filter_route_metar_taf_ZA(flight_id, buffer_nm, current_app.config['WEATHER_METAR_URL_ZA'], current_app.config['WEATHER_TAF_URL_ZA'])
            
            # Get METAR and TAF for departure and destination aerodromes 
            if depart.Latitude == dest.Latitude and depart.Longitude == dest.Longitude:
                depart_metar, depart_taf = flightplans.filter_point_metar_taf_ZA(depart.Longitude, depart.Latitude, 5, current_app.config['WEATHER_METAR_URL_ZA'], current_app.config['WEATHER_TAF_URL_ZA'])
                dest_metar = []
                dest_taf = []
            # Otherwise get for departure and destination
            else:
                depart_metar, depart_taf = flightplans.filter_point_metar_taf_ZA(depart.Longitude, depart.Latitude, 5, current_app.config['WEATHER_METAR_URL_ZA'], current_app.config['WEATHER_TAF_URL_ZA'])
                dest_metar, dest_taf = flightplans.filter_point_metar_taf_ZA(dest.Longitude, dest.Latitude, 5, current_app.config['WEATHER_METAR_URL_ZA'], current_app.config['WEATHER_TAF_URL_ZA'])
            
            # Now remove depart and dest metars from the list of metars
            for dep_met in depart_metar:
                if dep_met in metar_list: metar_list.remove(dep_met)
                if dep_met in dest_metar: dest_metar.remove(dep_met)
                if dep_met['has_no_data']: depart_metar.remove(dep_met)
            for dest_met in dest_metar:
                if dest_met in metar_list: metar_list.remove(dest_met)
                if dest_met['has_no_data']: dest_metar.remove(dest_met)
            
            # Now remove depart and dest tafs from the list of tafs
            for dep_taf in depart_taf:
                if dep_taf in taf_list: taf_list.remove(dep_taf)
                if dep_taf in dest_taf: dest_taf.remove(dep_taf)
            for dest_tf in dest_taf:
                if dest_tf in taf_list: taf_list.remove(dest_tf)
            
        else:
            sigairmet_list = []
            metar_list = []
            taf_list = []
            depart_metar = []
            dest_metar = []
            depart_taf = []
            dest_taf = []

        return render_template("maps/flightbriefing.html", hidden_notams=hidden_notams, perm_hidden_notams=relevant_perm_hidden_notams,
                               no_header=True, flight_date = flight_date, flight=flight,
                               generate_date =  f"{generate_date} UTC", briefing=briefing, 
                               depart_notams=depart_notams, dest_notams=dest_notams, enroute_notams=enroute_notams,
                               depart_metar=depart_metar, dest_metar=dest_metar, enroute_metar=metar_list,
                               depart_taf=depart_taf, dest_taf=dest_taf, enroute_taf=taf_list,
                               enroute_sigairmet=sigairmet_list)
    

    # We are generating the MAP briefing
    else:
        # Filter by flight date if one is given
        if flight_date:
            notam_list = flightplans.filter_route_notams(flight_id, buffer_nm, date_of_flight=flight_date)
            
        else:
            notam_list = flightplans.filter_route_notams(flight_id, buffer_nm)
            
        #If flight date is today or tomorrow, retrieve WEATHER and filter it by date
        used_wx_groups = []
        used_wx_layers = []
        if flight_date is None or flight_date <= (datetime.utcnow().date() + timedelta(days=1)):
            sigairmet_list = flightplans.filter_route_sigairmets_ZA(flight_id, buffer_nm, current_app.config['WEATHER_SIGMET_AIRMET_URL_ZA'], flight_date)
            sigairmet_geojson, used_wx_groups, used_wx_layers = generate_sigmet_geojson(sigairmet_list)
            
            metar_list, taf_list = flightplans.filter_route_metar_taf_ZA(flight_id, buffer_nm, current_app.config['WEATHER_METAR_URL_ZA'], current_app.config['WEATHER_TAF_URL_ZA'])
            if len(metar_list) > 0:
                metar_geojson = generate_metar_geojson(metar_list)
                used_wx_groups.append('METAR')
                used_wx_layers.append('METAR_symbol')
            else:
                metar_geojson = None
            
            if len(taf_list) > 0:
                taf_geojson = generate_taf_geojson(taf_list)
                used_wx_groups.append('TAF')
                used_wx_layers.append('TAF_symbol')
            else:
                taf_geojson = None
            
        else:
            sigairmet_geojson = None
            metar_geojson = None
            taf_geojson = None
            


        # Generate the GEOJSON features for the Notams
        notam_features, used_groups, used_layers = generate_notam_geojson(notam_list, hide_user_notams = True)
    
        # Generate the GEOJSON for the flight plan
        flight_geojson = flightplans.generate_flight_geojson(flight_id) 
        
        # Get flight bounds and centre-point, so map can be centered on the flight
        flight_bounds = helpers.get_flight_bounds(flight)
        flight_centre = [(flight_bounds[0][0] + flight_bounds[1][0])/2, (flight_bounds[0][1] + flight_bounds[1][1])/2]

        radius_default = UserSetting.get_setting(session['userid'], 'map_radius_filter').SettingValue

        return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], radius_default=radius_default,
                               map_bounds=helpers.get_max_map_bounds(), briefing=briefing, 
                               notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers,
                               flight=flight, default_flight_date = flight_date,
                               flight_geojson=flight_geojson, 
                               sigair_geojson=sigairmet_geojson, used_wx_groups=used_wx_groups, used_wx_layers=used_wx_layers,
                               metar_geojson=metar_geojson, taf_geojson=taf_geojson, 
                               flight_bounds=flight_bounds, flight_centre=flight_centre)


@bp.route('/weathermap', methods=('GET', 'POST'))
@requires_login
def weathermap():
    """Displays html page showing weather on a map
    """    
    
    # Retrieve the SIGMET/AIRMET list and create the GEOJSON collection
    sigair_list = read_sigmet_airmet_ZA(current_app.config['WEATHER_SIGMET_AIRMET_URL_ZA'])
    sigair_geojson, used_groups, used_layers = generate_sigmet_geojson(sigair_list)
    
    # Retrieve the METAR list and create the GEOJSON collection
    metar_list = read_metar_ZA(current_app.config['WEATHER_METAR_URL_ZA'])
    metar_geojson = generate_metar_geojson(metar_list)
    used_groups.append('METAR')
    used_layers.append('METAR_symbol')
    
    # Retrieve the TAF list and create the GEOJSON collection
    taf_list = read_taf_ZA(current_app.config['WEATHER_TAF_URL_ZA'])
    taf_geojson = generate_taf_geojson(taf_list)
    used_groups.append('TAF')
    used_layers.append('TAF_symbol')

    # Display the map
    return render_template('maps/weathermap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'],  
                           map_bounds=helpers.get_max_map_bounds(), 
                           sigair_geojson=sigair_geojson, metar_geojson=metar_geojson, taf_geojson=taf_geojson,
                           used_groups=used_groups, used_layers=used_layers)




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
    
    if len(new_notams) == 0:
        flash("No new NOTAMS were released in the past week.")
        return redirect(url_for("home.index"))
    
    # Create the GEOJSON Features
    notam_features, used_groups, used_layers = generate_notam_geojson(new_notams, hide_user_notams = True)

    radius_default = UserSetting.get_setting(session['userid'], 'map_radius_filter').SettingValue

    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], radius_default=radius_default, 
                           map_bounds=helpers.get_max_map_bounds(), briefing=briefing, 
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
    notam_features, used_groups, used_layers = generate_notam_geojson(notam_list, hide_user_notams = True)

    # Get bounds and center point for the maps
    flight_bounds = helpers.get_shape_bounds(radius)
    flight_centre = [home_navpt.Longitude, home_navpt.Latitude]

    radius_default = UserSetting.get_setting(session['userid'], 'map_radius_filter').SettingValue

    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], radius_default=radius_default, 
                           map_bounds=helpers.get_max_map_bounds(), briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers,
                           default_flight_date = flight_date, home_aerodrome=home_aerodrome,
                           flight_bounds=flight_bounds, flight_centre=flight_centre)


