'''
Created on 13 Jun 2020

@author: aretallack
'''

import os

from sqlalchemy import func, and_

from geojson import Polygon, Point, Feature

from flask import (
    Blueprint, g, redirect, render_template, request, session, url_for, current_app, flash
)
from werkzeug.utils import secure_filename

from datetime import datetime, timedelta

from . import helpers, flightplans
from .auth import requires_login
from .db import FlightPlan, Notam, Briefing, UserSetting, NavPoint
from .data_handling import sqa_session    #sqa_session is the Session object for the site
from .notams import get_new_deleted_notams

bp = Blueprint('viewmap', __name__)


@bp.route('/detailnotams', methods=('GET', 'POST'))
@requires_login
def detailnotams():
    
    sqa_sess = sqa_session()
    briefings = sqa_sess.query(Briefing.BriefingID, Briefing.Briefing_Ref, Briefing.Briefing_Date).order_by(Briefing.BriefingID.desc()).all()
    notam_list = None
    flight_date = None
    briefing_id = None

    default_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    if request.method == "POST":
        briefing_id = request.form['briefing']
        flight_date = request.form['flight_date']
        default_date = flight_date
        
    else:
        briefing_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]

    if flight_date:
        notam_list = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == briefing_id, Notam.From_Date <= flight_date, Notam.To_Date > flight_date))
    else:
        notam_list = sqa_sess.query(Notam).filter(Notam.BriefingID == briefing_id)
        
    
    return render_template('maps/detailnotams.html', briefings = briefings, notams = notam_list, 
                           briefing_id = briefing_id, default_date = default_date, flight_date = flight_date)
    
@bp.route('/changednotams', methods=('GET', 'POST'))
@requires_login
def changednotamdetail():

    sqa_sess = sqa_session()
    since_date = datetime.utcnow().date() - timedelta(days=60)
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefings = sqa_sess.query(Briefing.BriefingID, Briefing.Briefing_Ref, Briefing.Briefing_Date).filter(and_(Briefing.Briefing_Date > since_date, Briefing.BriefingID < latest_brief_id)).order_by(Briefing.BriefingID.desc()).all()
    
    if request.method == "POST":
        briefing_id = request.form['briefing']
        prev_briefing, new_notams, del_notams = get_new_deleted_notams(briefing_id=briefing_id, return_count_only=False)
    
    else:
        since_date = datetime.utcnow().date() - timedelta(days=7)
        prev_briefing, new_notams, del_notams = get_new_deleted_notams(since_date, return_count_only=False)
        briefing_id = prev_briefing.BriefingID

    
    return render_template('maps/changednotams.html', briefings = briefings, since_date = prev_briefing.Briefing_Date, prev_briefing_id=str(briefing_id), 
                           new_notams = new_notams, deleted_notams = del_notams)


@bp.route('/listnotams', methods=('GET', 'POST'))
@requires_login
def listnotams():
    
    sqa_sess = sqa_session()
    briefings = sqa_sess.query(Briefing.BriefingID, Briefing.Briefing_Ref, Briefing.Briefing_Date).all()
    notam_list = None
    default_date = datetime.utcnow().strftime("%Y-%m-%d")
    briefing_id = None

    if request.method == "POST":
        briefing_id = request.form['briefing']
        flight_date = request.form['flight_date']
        default_date = flight_date
        
        notam_list = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == briefing_id, Notam.From_Date <= flight_date, Notam.To_Date > flight_date))

    
    return render_template('maps/listnotams.html', briefings = briefings, notams = notam_list, default_date = default_date, briefing_id = briefing_id)


def generate_notam_geojson(notam_list):

    used_groups = []  #contains applicable groupings for use on the web page (i.e. it excludes groupings that do not appear) - used to filter layers on the map
    used_layers = []  #contains layer groupings in form: used_group+_+geometry (poly/circle) - used to separate layers on the map

    #Now we create the GEOJSON Collection     
     
    notam_features = []
    for ntm in notam_list:
        #Generate the formatted html text for this NOTAM

        ntm_from = datetime.strftime(ntm.From_Date,"%Y-%m-%d %H:%M") 
        if ntm.To_Date_Permanent == True:
            ntm_to = 'Perm'
        else:
            ntm_to = datetime.strftime(ntm.To_Date,"%Y-%m-%d %H:%M")
            ntm_to += " Est" if ntm.To_Date_Estimate == True else ""
        
        if ntm.Bounded_Area:
            coords = helpers.convert_bounded_dms_to_dd(ntm.Bounded_Area, reverse_coords=True)
            geojson_geom=Polygon([coords])
            type_suffix = '_polygon'
        elif ntm.is_circle():
            coords = helpers.convert_bounded_dms_to_dd(ntm.circle_bounded_area(), reverse_coords=True)
            geojson_geom=Polygon([coords])
            type_suffix = '_polygon'
        else:
            coords = (helpers.convert_dms_to_dd(ntm.Coord_Lon), helpers.convert_dms_to_dd(ntm.Coord_Lat))
            geojson_geom=Point(coords)
            type_suffix = '_circle'
        
        if ntm.Duration:
            ntm_duration = ntm.Duration
        else:
            ntm_duration = ''
        col_r = int(ntm.QCode_2_3_Lookup.Group_Colour[1:3],16)
        col_g = int(ntm.QCode_2_3_Lookup.Group_Colour[3:5],16)
        col_b = int(ntm.QCode_2_3_Lookup.Group_Colour[5:7],16)
        
        fill_col=f'rgba({col_r},{col_g},{col_b},0.4)'
        line_col=f'rgba({col_r},{col_g},{col_b},1)'
        notam_features.append(Feature(geometry=geojson_geom, properties={'fill':fill_col, 'line':line_col, 
                                                                 'group': ntm.QCode_2_3_Lookup.Grouping,
                                                                 'layer_group': ntm.QCode_2_3_Lookup.Grouping + type_suffix, 
                                                                 'notam_number': ntm.Notam_Number,
                                                                 'notam_location': ntm.A_Location,
                                                                 'from_date': ntm_from,
                                                                 'to_date' : ntm_to,
                                                                 'duration' : ntm_duration,
                                                                 'radius': ntm.Radius,
                                                                 'notam_text': ntm.Notam_Text}))
        #Add this group+geometry combination to the list, so the map knows to split out a layer for it.
        if (ntm.QCode_2_3_Lookup.Grouping + type_suffix) not in used_layers:
            used_layers.append(ntm.QCode_2_3_Lookup.Grouping + type_suffix)

        #Add the Notam Grouping to the collection of used groups
        if ntm.QCode_2_3_Lookup.Grouping not in used_groups:
            used_groups.append(ntm.QCode_2_3_Lookup.Grouping)
        
        used_groups.sort()
        used_layers.sort()
        
    return notam_features, used_groups, used_layers

    
@bp.route('/viewmap', methods=('GET', 'POST'))
@requires_login
def viewmap():
    
    flight_date = None
    
    if request.method == "POST":
        flight_date = request.form['flight-date']

        
    sqa_sess = sqa_session()
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)

    if flight_date:
        notam_list = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == latest_brief_id, Notam.From_Date <= flight_date, Notam.To_Date >= flight_date)).order_by(Notam.A_Location).all()
    else:
        notam_list = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == latest_brief_id)).order_by(Notam.A_Location).all()
    
    notam_features, used_groups, used_layers = generate_notam_geojson(notam_list)

    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers,
                           default_flight_date = flight_date)



@bp.route('/flightmap/<int:flight_id>', methods=('GET', 'POST'))
@requires_login
def flightmap(flight_id):
#    if request.method == "GET":
#        flight_id = request.args.get('flightid')

    flight_date = None
    
    if request.method == "POST":
        flight_date = request.form['flight-date']
    
    sqa_sess = sqa_session()
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)

    flight = sqa_sess.query(FlightPlan).get(flight_id)

    buffer_nm = UserSetting.get_setting(session['userid'], 'route_buffer').SettingValue
    if flight_date:
        notam_list = flightplans.filter_route_notams(flight_id, buffer_nm, date_of_flight=flight_date)
    else:
        notam_list = flightplans.filter_route_notams(flight_id, buffer_nm)
    
    notam_features, used_groups, used_layers = generate_notam_geojson(notam_list)

    flight_geojson = flightplans.generate_geojson(flight_id) #Convert the flight plans to GeoJSON
    flight_bounds = helpers.get_flight_bounds(flight)
    flight_centre = [(flight_bounds[0][0] + flight_bounds[1][0])/2, (flight_bounds[0][1] + flight_bounds[1][1])/2]

    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers,
                           flight=flight, default_flight_date = flight_date,
                           flight_geojson=flight_geojson, flight_bounds=flight_bounds, flight_centre=flight_centre)



@bp.route('/newnotams', methods=('GET', 'POST'))
@requires_login
def newnotams():
    sqa_sess = sqa_session()

    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    prev_briefing, new_notams, del_notams = get_new_deleted_notams(since_date=datetime.utcnow().date() - timedelta(days=7), return_count_only=False)
    
    
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)
    
    notam_features, used_groups, used_layers = generate_notam_geojson(new_notams)


    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers, prev_briefing=prev_briefing)


@bp.route('/homenotams', methods=('GET', 'POST'))
@requires_login
def homenotams():
    flight_date = None
    
    if request.method == "POST":
        flight_date = request.form['flight-date']
    
    sqa_sess = sqa_session()
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)

    home_aerodrome = UserSetting.get_setting(session['userid'], "home_aerodrome").SettingValue
    home_radius = UserSetting.get_setting(session['userid'], "home_radius").SettingValue
    home_navpt = sqa_sess.query(NavPoint).filter(NavPoint.ICAO_Code == home_aerodrome).first()
    
    radius = helpers.generate_circle_shapely(home_navpt.Latitude, home_navpt.Longitude, int(home_radius), format_is_dms=False)
    
    flight_bounds = helpers.get_shape_bounds(radius)
    
    if flight_date:
        notam_list = flightplans.filter_point_notams(home_navpt.Longitude, home_navpt.Latitude, home_radius, date_of_flight=flight_date)
    else:
        notam_list = flightplans.filter_point_notams(home_navpt.Longitude, home_navpt.Latitude, home_radius)
    
    notam_features, used_groups, used_layers = generate_notam_geojson(notam_list)

    flight_centre = [home_navpt.Longitude, home_navpt.Latitude]

    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers,
                           default_flight_date = flight_date, home_aerodrome=home_aerodrome,
                           flight_bounds=flight_bounds, flight_centre=flight_centre)


@bp.route('/uploadroute', methods=('GET', 'POST'))
@requires_login
def uploadroute():
    
    if request.method == "POST":
        
        if 'filename' not in request.files:
            flash('No file was selected')
            return redirect(request.url)
        
        up_file = request.files['filename']
        if up_file.filename == '':
            flash('No file was selected')
            return redirect(request.url)
        
        file_ext = up_file.filename.rsplit('.', 1)[1].lower()
        if not file_ext in ['gpx','ep1']:
            flash('We currentl only support files with EP1 and GPX extensions.')
            return redirect(request.url)
            
        filename = f"{session['userid']}__{datetime.strftime(datetime.utcnow(), '%Y%m%d%H%M%S%f')}__{secure_filename(up_file.filename)}"
        
        #Check the upload folder exists - if not, create it
        if not os.path.exists(current_app.config['UPLOAD_ARCHIVE_FOLDER']):
            os.makedirs(current_app.config['UPLOAD_ARCHIVE_FOLDER'])

        
        full_path = os.path.join(current_app.config['UPLOAD_ARCHIVE_FOLDER'], filename)
        
        up_file.save(full_path)
        
        if request.form['routedesc']:
            desc = request.form['routedesc']
        else:
            desc = "Imported Route"
            
        #File is saved, now generate GEOJSON so we can show a small version of it.
        if file_ext == 'gpx':
            fplans = flightplans.read_gpx_file(full_path, session['userid'], desc) #Read the GPX file
        elif file_ext == 'ep1':
            fplans = flightplans.read_easyplan_file(full_path, session['userid'], desc) #Read the EP1 file
        sqa_sess = sqa_session()
        sqa_sess.add(fplans[0])
        sqa_sess.commit()
        new_id = fplans[0].FlightplanID

        flight_geojson = flightplans.generate_geojson(new_id) #Convert the flight plans to GeoJSON

        flight_bounds = helpers.get_flight_bounds(fplans[0])
        flight_centre = [(flight_bounds[0][0] + flight_bounds[1][0])/2, (flight_bounds[0][1] + flight_bounds[1][1])/2]
        
        return render_template('maps/uploadsuccess.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], filename=filename,
                               flight_geojson=flight_geojson, flight_bounds=flight_bounds, flight_centre=flight_centre,
                               fplan=fplans[0])
    
    return render_template('maps/uploadroute.html')
