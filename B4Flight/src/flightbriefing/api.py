"""Exposes APIs for use by external apps

APIs allow for Cross-Origin call

APIs exposed are: 
- get_metar_za: return Metars in a JSON format for ZA aerodromes 
 
"""



import json

from flask import (
    Blueprint, request, session, current_app
)

from flask_cors import CORS #CORS allows for cross-origin requests

from .weather import read_metar_ZA

bp = Blueprint('api', __name__, url_prefix='/api')
CORS(bp)

@bp.route('/get_metar_za', methods=('POST','GET'))
def get_metar_za():
    """API to return Metars in a JSON format for ZA aerodromes
    Returns JSON structure containing Metar data
    
    Expects: No data: returns all aerodromes
            {aerodrome: ICAO} - returns for specified aerodrome
    
    Returns: json array of objects:
            aerodrome: ICAO code
            has_no_data: boolean
            is_speci: boolean
            time: date and time of the METAR
            wind: tuple containing (direction, strength, gusting, is_variable).  Direction of -1 means variable
            temperature: temp in degrees centigrade
            dew_point: dewpoint temp in degrees centigrade (integer, so M01 is shown as -01)
            QNH: QNH in hPa
            body: full body of the METAR
            coords: co-ord pair for the aerodrome - LONG, LAT in decimal degrees
            
            If no data found, returns: {'error': 'No data found'}
    
    """

    metars = read_metar_ZA(current_app.config['WEATHER_METAR_URL_ZA'], date_as_ISO_text=True)
    

    filter_aerodrome = None
    
    if request.method == 'GET':
        # Get the aerodrome to filter by
        try:
            filter_aerodrome = request.args.get('aerodrome')
        except:
            filter_aerodrome = None
    
    # Process the request's data
    if request.method == 'POST':
        # Get data in JSON format
        req_data = request.get_json()

        # If there is request data then process it
        if req_data:
            # Get the aerodrome to filter by
            try:
                filter_aerodrome = req_data.get('aerodrome')
            except:
                filter_aerodrome = None
        
    #If we have an aerodrome to filter by
    if filter_aerodrome:    
        metar_filter = filter(lambda met: met['aerodrome'] == filter_aerodrome, metars)
        metars = list(metar_filter)
        
    #If nothing returned, then error
    if len(metars) == 0: 
        return json.dumps([])
            
    # Return the metars
    return json.dumps(metars)
