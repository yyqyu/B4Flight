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

from flightbriefing import helpers, flightplans
from flightbriefing.auth import requires_login
from flightbriefing.notams import Notam, Briefing
from flightbriefing.db import FlightPlan
from flightbriefing.data_handling import sqa_session    #sqa_session is the Session object for the site

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
        
##    session.remove()
    
    return render_template('maps/detailnotams.html', briefings = briefings, notams = notam_list, default_date = default_date, flight_date = flight_date)
    


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

##    session.remove()
    
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
        
        notam_features.append(Feature(geometry=geojson_geom, properties={'fill':ntm.QCode_2_3_Lookup.Group_Colour, 'fill-opacity':0.4, 
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
    
    sqa_sess = sqa_session()
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)

    notam_list = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == latest_brief_id)).order_by(Notam.A_Location).all()
    
    notam_features, used_groups, used_layers = generate_notam_geojson(notam_list)

    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers)



@bp.route('/flightmap', methods=('GET', 'POST'))
@requires_login
def flightmap():
    if request.method == "GET":
        flight_id = request.args.get('flightid')
    
    sqa_sess = sqa_session()
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)

    flight = sqa_sess.query(FlightPlan).get(flight_id)

    notam_list = flightplans.filter_route_notams(flight_id, 5)
    
    notam_features, used_groups, used_layers = generate_notam_geojson(notam_list)

    flight_geojson = flightplans.generate_geojson(flight_id) #Convert the flight plans to GeoJSON
    flight_bounds = helpers.get_flight_bounds(flight)
    flight_centre = [(flight_bounds[0][0] + flight_bounds[1][0])/2, (flight_bounds[0][1] + flight_bounds[1][1])/2]

    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers,
                           flight=flight,
                           flight_geojson=flight_geojson, flight_bounds=flight_bounds, flight_centre=flight_centre)


@bp.route('/newnotams', methods=('GET', 'POST'))
@requires_login
def newnotams():
    sqa_sess = sqa_session()

    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]

    #Find the new NOTAMS
    lw_briefing_id = sqa_sess.query(func.max(Briefing.BriefingID)).filter(Briefing.Briefing_Date < (datetime.utcnow().date() - timedelta(days=7))).first()[0]
    lw_briefing_date = sqa_sess.query(Briefing).get(lw_briefing_id).Briefing_Date
    tw_notams = sqa_sess.query(Notam.Notam_Number).filter(Notam.BriefingID == latest_brief_id)
    lw_notams = sqa_sess.query(Notam.Notam_Number).filter(Notam.BriefingID == lw_briefing_id)
    new_notams = tw_notams.except_(lw_notams)
    
    notam_list = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == latest_brief_id, Notam.Notam_Number.in_(new_notams))).order_by(Notam.A_Location).all()
    
    
    briefing = sqa_sess.query(Briefing).get(latest_brief_id)
    
    notam_features, used_groups, used_layers = generate_notam_geojson(notam_list)


    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_groups, used_layers=used_layers, last_wk_briefing_date=lw_briefing_date)

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
