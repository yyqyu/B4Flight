'''
Created on 13 Jun 2020

@author: aretallack
'''
from sqlalchemy import func, and_

from geojson import Polygon, Point, Feature

from flask import (
    Blueprint, g, redirect, render_template, request, session, url_for, current_app
)

from datetime import datetime

from flightbriefing import helpers
from flightbriefing.notams import Notam, Briefing
from flightbriefing.data_handling import sqa_session    #sqa_session is the Session object for the site


bp = Blueprint('viewmap', __name__)

@bp.route('/detailnotams', methods=('GET', 'POST'))
def detailnotams():
    
    session = sqa_session()
    briefings = session.query(Briefing.BriefingID, Briefing.Briefing_Ref, Briefing.Briefing_Date).all()
    notam_list = None
    flight_date = None
    briefing_id = None

    default_date = datetime.now().strftime("%Y-%m-%d")
    
    if request.method == "POST":
        briefing_id = request.form['briefing']
        flight_date = request.form['flight_date']
        default_date = flight_date
        
        
        notam_list = session.query(Notam).filter(and_(Notam.BriefingID == briefing_id, Notam.From_Date <= flight_date, Notam.To_Date > flight_date))
        
##    session.remove()
    
    return render_template('maps/detailnotams.html', briefings = briefings, notams = notam_list, default_date = default_date, flight_date = flight_date)
    


@bp.route('/listnotams', methods=('GET', 'POST'))
def listnotams():
    
    session = sqa_session()
    briefings = session.query(Briefing.BriefingID, Briefing.Briefing_Ref, Briefing.Briefing_Date).all()
    notam_list = None
    default_date = datetime.now().strftime("%Y-%m-%d")
    briefing_id = None

    if request.method == "POST":
        briefing_id = request.form['briefing']
        flight_date = request.form['flight_date']
        default_date = flight_date
        
        notam_list = session.query(Notam).filter(and_(Notam.BriefingID == briefing_id, Notam.From_Date <= flight_date, Notam.To_Date > flight_date))

##    session.remove()
    
    return render_template('maps/listnotams.html', briefings = briefings, notams = notam_list, default_date = default_date, briefing_id = briefing_id)
    
@bp.route('/viewmap', methods=('GET', 'POST'))
def viewmap():
    
    session = sqa_session()
    latest_brief_id = session.query(func.max(Briefing.BriefingID)).first()[0]
    briefing = session.query(Briefing).filter(Briefing.BriefingID == latest_brief_id).first()

    notam_list = session.query(Notam).filter(and_(Notam.BriefingID == latest_brief_id)).order_by(Notam.A_Location).all()

#    notam_loc_group = {}
    used_goups = []  #contains applicable groupings for use on the web page (i.e. it excludes groupings that do not appear) - used to filter layers on the map
    used_layers = []  #contains layer groupings in form: used_group+_+geometry (poly/circle) - used to separate layers on the map
    
    
#First we combine NOTAMS:
#  Any NOTAM with the same Coords+Radius is combined, and Grouping is changed to "Multiple"
#  Any NOTAM that has a bounded area is separate
#     for x in notam_list:
#         #Generate the formatted html text for this NOTAM
#         txthtm = '<div class="row bg-secondary text-white">' + x.A_Location + '</div>' + \
#             '&nbsp; - &nbsp;' + x.Notam_Number + '</div><div class="row small">' + \
#             '<b>' + datetime.strftime(x.From_Date,"%Y-%m-%d %H:%M") + '</b> &nbsp; TO &nbsp; <b>'
#         if x.To_Date_Permanent == True:
#             txthtm += 'Perm'
#         else:
#             txthtm += datetime.strftime(x.To_Date,"%Y-%m-%d %H:%M")
#             txthtm += " Est" if x.To_Date_Estimate == True else ""
# 
#         txthtm += '</b><br><p>'+ x.Notam_Text + '</p></div>'
# 
#         #If this is a bounded area, separate it
#         if x.Bounded_Area:
#             notam_loc_group[x.Notam_Number] = {'Bounded_Area': x.Bounded_Area, 'Coord_Lon': x.Coord_Lon, 'Coord_Lat': x.Coord_Lat, 
#                                                'Radius': x.Radius, 'Location': x.A_Location, 'notam_identifier': x.Notam_Number,
#                                                'Notam_Grouping': x.QCode_2_3_Lookup.Grouping, 'Group_Colour': x.QCode_2_3_Lookup.Group_Colour,
#                                                'text_htm': txthtm}
# 
#         ## ****Need to include items with radius > 1 here****
#         
#         #If this is not a bounded area, and does not already exist, add to the dictionary
#         elif x.Unique_Geo_ID not in notam_loc_group:
#             if x.is_circle() == True and x.Radius > 500:
#                 notam_loc_group[x.Notam_Number] = {'Bounded_Area': x.circle_bounded_area(), 'Coord_Lon': x.Coord_Lon, 'Coord_Lat': x.Coord_Lat,
#                                                    'Radius': x.Radius, 'Location': x.A_Location, 'notam_identifier': x.Notam_Number,
#                                                    'Notam_Grouping': x.QCode_2_3_Lookup.Grouping, 'Group_Colour': x.QCode_2_3_Lookup.Group_Colour,
#                                                    'text_htm': txthtm}
#                 
#             elif x.is_circle() == True:
#                 notam_loc_group[x.Unique_Geo_ID] = {'Bounded_Area': x.circle_bounded_area(), 'Coord_Lon': x.Coord_Lon, 'Coord_Lat': x.Coord_Lat,
#                                                    'Radius': x.Radius, 'Location': x.A_Location, 'notam_identifier': x.Unique_Geo_ID,
#                                                    'Notam_Grouping': x.QCode_2_3_Lookup.Grouping, 'Group_Colour': x.QCode_2_3_Lookup.Group_Colour,
#                                                    'text_htm': txthtm}
#                 
#             else:
#                 notam_loc_group[x.Unique_Geo_ID] = {'Coord_Lon': x.Coord_Lon, 'Coord_Lat': x.Coord_Lat,
#                                                    'Radius': x.Radius, 'Location': x.A_Location, 'notam_identifier': x.Unique_Geo_ID,
#                                                    'Notam_Grouping': x.QCode_2_3_Lookup.Grouping, 'Group_Colour': x.QCode_2_3_Lookup.Group_Colour,
#                                                    'text_htm': txthtm}
# 
#         #Otherwhise this already exists to append the notam text and update the Notam_Grouping to "Multiple"
#         else:
#             notam_loc_group[x.Unique_Geo_ID]['Notam_Grouping'] = 'Aerodromes'
#             notam_loc_group[x.Unique_Geo_ID]['Group_Colour'] =  '#1a66ff'
#             notam_loc_group[x.Unique_Geo_ID]['text_htm'] += txthtm
# 
# 
# #Now we create the GEOJSON Collection     
#     
#     notam_features = []
#     for ntm in notam_loc_group.values():
# 
#         #Add the Notam Grouping to the collection of used groups
#         if ntm['Notam_Grouping'] not in used_goups:
#             used_goups.append(ntm['Notam_Grouping'])
# 
# 
#         if ntm.get('Bounded_Area'):
#             coords = helpers.convert_bounded_dms_to_dd(ntm['Bounded_Area'], reverse_coords=True)
#             poly=Polygon([coords])
#             notam_features.append(Feature(geometry=poly, properties={'fill':ntm['Group_Colour'], 'fill-opacity':0.4, 
#                                                                      'group': ntm['Notam_Grouping'],
#                                                                      'layer_group': ntm['Notam_Grouping'] + '_polygon', 
#                                                                      'notam_identifier': ntm['notam_identifier'],
#                                                                      'text_htm': '<div class="container">' + ntm['text_htm'] + '</div>'}))
#             #Add this group+geometry combination to the list, so the map knows to split out a layer for it.
#             if (ntm['Notam_Grouping'] + '_polygon') not in used_layers:
#                 used_layers.append(ntm['Notam_Grouping'] + '_polygon')
#             
#         elif ntm['Radius'] == 1:
#             coords = (helpers.convert_dms_to_dd(ntm['Coord_Lon']), helpers.convert_dms_to_dd(ntm['Coord_Lat']))
#             pnt=Point(coords)
#             notam_features.append(Feature(geometry=pnt, properties={'fill':ntm['Group_Colour'], 'fill-opacity':0.4, 
#                                                                      'group': ntm['Notam_Grouping'],
#                                                                      'layer_group': ntm['Notam_Grouping'] + '_circle', 
#                                                                      'notam_identifier': ntm['notam_identifier'],
#                                                                      'text_htm': '<div class="container">' + ntm['text_htm'] + '</div>'}))
#             #Add this group+geometry combination to the list, so the map knows to split out a layer for it.
#             if (ntm['Notam_Grouping'] + '_circle') not in used_layers:
#                 used_layers.append(ntm['Notam_Grouping'] + '_circle')


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
            
        notam_features.append(Feature(geometry=geojson_geom, properties={'fill':ntm.QCode_2_3_Lookup.Group_Colour, 'fill-opacity':0.4, 
                                                                 'group': ntm.QCode_2_3_Lookup.Grouping,
                                                                 'layer_group': ntm.QCode_2_3_Lookup.Grouping + type_suffix, 
                                                                 'notam_number': ntm.Notam_Number,
                                                                 'notam_location': ntm.A_Location,
                                                                 'from_date': ntm_from,
                                                                 'to_date' : ntm_to,
                                                                 'radius': ntm.Radius,
                                                                 'notam_text': ntm.Notam_Text}))
            #Add this group+geometry combination to the list, so the map knows to split out a layer for it.
        if (ntm.QCode_2_3_Lookup.Grouping + type_suffix) not in used_layers:
            used_layers.append(ntm.QCode_2_3_Lookup.Grouping + type_suffix)

        #Add the Notam Grouping to the collection of used groups
        if ntm.QCode_2_3_Lookup.Grouping not in used_goups:
            used_goups.append(ntm.QCode_2_3_Lookup.Grouping)
        
        used_goups.sort()
        used_layers.sort()

    return render_template('maps/showmap.html', mapbox_token=current_app.config['MAPBOX_TOKEN'], briefing=briefing, 
                           notam_geojson=notam_features, used_groups=used_goups, used_layers=used_layers)
