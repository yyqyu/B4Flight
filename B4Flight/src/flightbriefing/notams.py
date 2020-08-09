"""Handles NOTAM-parsing related Functionality

This module contains functions to 
- parse CAA Notam Text Files
- get new and deleted Notams since a specific date
- generate GEOJSON features for a list of notams
 
"""

import re
from datetime import datetime, timedelta
from flask import current_app, session
from geojson import Polygon, Point, Feature

from sqlalchemy import func, and_

from . import helpers    
from .db import Briefing, Notam, UserHiddenNotam
from .data_handling import sqa_session    #sqa_session is the Session object for the site



def tidy_notam(notam):
    """ A few manipulations on the Notam object to tidy it up, calc a few derived fields 

    Parameters
    ----------
    notam : Notam
        Notam Object to be tidied

    Returns
    -------
    nothing - notam obkect returned by reference
    """
    
    #---Following 2 Regular expressions are to extract co-ordinates of bounded areas within NOTAM description:
    # Eg. POWER STATION AIRFIELD (260538S 0292717E), MPUMALANGA (260150S 0292048E, 260527S 0292655E, 260748S 0292611E, 260249S 0291845E ) : REMOTELY PILOTED AIRCRAFT SYSTEMS (RPAS) (400FT AGL) OPS TAKING PLACE BEYOND VISUAL LINE OF SIGHT.
    # First, we want to ignore any single pairs of co-ordinates (eg. in the above, the co-ord of the airfield)
    regIgnoreCoord = re.compile(r'(\([ ]*\d{6,6}[N,S][ ,]+\d{7,7}[E,W][ ]*\))')

    # Then remove decimals - some co-ordinates are written with 2 decimals eg 260527.32S 0292655.24E
    regIgnoreDecimals = re.compile(r'(\d[.]\d{0,3}[NSEW])')

    # Then we want to extract pairs of lat/lon - eg.(260150S 0292048E, 260527S 0292655E, 260748S 0292611E, 260249S 0291845E )
    regAreaCoord = re.compile(r'(?P<coord_lat>\d{6,6}[N,S])[ ]+(?P<coord_lon>\d{7,7}[E,W])')
    
    #----Try to extract bounded co-ordinates if they exist, but not for Obstacles
    sCoords = ''

    if notam.Q_Code_2_3 != 'OB':  # Obstacles are identified by first 2 letters in QCode = "OB"
        # First are there any single co-ord pairs?  If so, remove them from the text 
        tempText = notam.Notam_Text
        reFound=regIgnoreCoord.findall(tempText)
        for x in reFound:
            tempText=tempText.replace(x,"") # remove by replacing with blanks
    
        # Second remove any decimals
        reFound = regIgnoreDecimals.findall(tempText)
        for x in reFound:
            tempText = tempText.replace(x[1:-1],"") # remove by replacing with blanks
        
        # Now try to find 3-or-more co-ord pairs in the remaining string (less than 3 is not a polygon)
        reBoundedCoords= regAreaCoord.findall(tempText)
        if len(reBoundedCoords)>=3:
            for x in reBoundedCoords:
                sCoords = sCoords + f"{x[0]},{x[1]} " #add the next set of coords on
            
            # If the polygon is not closed - i.e. first coords do not equal the last - then close it
            if reBoundedCoords[0] != reBoundedCoords[-1]: 
                sCoords = sCoords + f"{reBoundedCoords[0][0]},{reBoundedCoords[0][1]} " #add the first set of coords at the end
                reBoundedCoords.append(reBoundedCoords[0])
            
            sCoords = sCoords.strip() #removing trailing space
            
    notam.Bounded_Area = sCoords
    
    # Determine the final Lower Level - use the "F" field if exists, otherwise the lower level from Q field
    if notam.Level_Lower is not None:
        if notam.Level_Lower.find('GND')>=0 or notam.Level_Lower.find('000')>=0:
            notam.Level_Lower = 'GND'
        else:
            notam.Level_Lower = 'FL' + notam.Level_Lower
    else:
        if  notam.Q_Level_Lower.find('000')>=0:
            notam.Level_Lower = 'GND'
        else:
            notam.Level_Lower = 'FL' + notam.Q_Level_Lower

    # Determine the final Upper Level - use the "G" field if exists, otherwise the lower level from Q field
    if notam.Level_Upper is not None:
        if notam.Level_Upper.find('AMSL')>=0:
            notam.Level_Upper = notam.Level_Upper[:notam.Level_Upper.find('FT')+2]
        #If Notam is AGL, leave it as is, otherwise add FL:
        elif notam.Level_Upper.find('AGL')<0:
            notam.Level_Upper = 'FL' + notam.Level_Upper
    else:
        notam.Level_Upper = 'FL' + notam.Q_Level_Upper

    if notam.E_Coord_Lat is not None:
        notam.Coord_Lat = notam.E_Coord_Lat
    else:
        notam.Coord_Lat = notam.Q_Coord_Lat
    
    if notam.E_Coord_Lon is not None:
        notam.Coord_Lon = notam.E_Coord_Lon
    else:
        notam.Coord_Lon = notam.Q_Coord_Lon

    # Below is unique ID to allow grouping of similar NOTAMS based on lat+lon+radius
    notam.Unique_Geo_ID = notam.Coord_Lat + '_' + notam.Coord_Lon + '_' + notam.Radius



def parse_notam_text_file(filename, country_code):
    """ Opens and parses a text file containing NOTAMs, placing details into one Briefing and multiple Notam objects
    Text file is a text version of the CAA Notam Summary:
        http://www.caa.co.za/Notam%20Summaries%20and%20PIB/Summary.pdf

    Parameters
    ----------
    filename : str
        Filename of the Text file to process
    country_code : str
        Country Code the Notams are for - currently only ZA, but may expand in future

    Returns
    -------
    Briefing 
        Object containing briefing and Notams - None means parsing failed
    
    """
    
    
    briefing_date_format = {'ZA':'%d%b%y'}
    briefing_time_format = {'ZA':'%H%M'}
    
    # Initialise Variables
    processing_notam = False  # Are we processing a NOTAM currently?
    processing_D_line = False  # Are we processing a "D" line in a NOTAM currently - these can be multi-line?
    processing_E_line = False  # Are we processing an "E" line in a NOTAM currently - these can be multi-line?
    raw_notam = '' # Raw text of NOTAM
    
    notam_ref = ''  # NOTAM Reference Number
    
    
    #Create the empty list for notam objects
    notams = []
    # Create a new Briefing object
    this_briefing = Briefing()
    # Create a new Notam object
    this_notam = Notam()
    
    #-------Regular Expressions to extract details from NOTAMs
    
    # Identify the NOTAM heading - e.g.: C4544/19 NOTAMN
    regNotamMatch = re.compile('[A-Z][0-9]+/[0-9]+ NOTAM')
    # Extract details from the "Q" Line - e.g.: Q) FAJA/QWCLW/IV/M/W/000/002/2949S03100E001
    regQLine =  re.compile(r'^Q\) (?P<FIR>\w+)/Q(?P<QCode>\w+)/(?P<FlightRule>\w+)/(?P<Purpose>\w+)/(?P<AD_ER>\w+)/(?P<LevelLower>\d+)/(?P<LevelUpper>\d+)/(?P<Coords>\w{11,11})(?P<Radius>\d+)')
    # Extract details from the "A, B, C" Line - e.g.: A) FAJA B) 2001010700 C) 2003301600 EST
    regABCLine = re.compile(r'^A\) (?P<A_Location>[\w\s]+)\s+B\) (?P<FromDate>\w+)\s+C\) (?P<ToDate>[\w,\s]+)\n')
    # Extract details from the "F, G" Line - e.g.: F) GND G) 181FT AMSL
    regFGLine = re.compile(r'^F\) (?P<F_FL_Lower>\w+)\s+G\) (?P<G_FL_Upper>[\w\s]+)\n')
    # Extractco-ordinates from the "E" Line - e.g.: EASTERN CAPE (325416S 0260602E): WND MNT MAST(394FT AGL) ERECTED.
    regACoord = re.compile(r'\((?P<coord_lat>\d{6,6}[N,S])[ ,]+(?P<coord_lon>\d{7,7}[E,W])\)')
    
    
    # Open and parse the text file line by line
    with open(filename) as notam_file:

        for in_line in notam_file:
            # Tidy the line up
            in_line = in_line.replace(chr(12),"")  #Remove any form feed/new page character - ASCII code 12
            in_line = in_line.lstrip() # Remove spaced and non-printables from left

            # Repeatedly remove double-spaces
            while in_line.find("  ") > 0:
                in_line = in_line.replace("  ", " ")  #PDF File may have double-spacing, and remove leading & trailing spaces
            
            # Extract the Date and Time of the NOTAM Briefing
            if in_line[0:9] == 'Date/Time':
                this_briefing.Briefing_Country = country_code
                this_briefing.Briefing_Date = datetime.strptime(in_line[10:17],briefing_date_format[country_code]).date()
                this_briefing.Briefing_Time = datetime.strptime(in_line[18:22],briefing_time_format[country_code]).time()
                this_briefing.Import_DateTime = datetime.utcnow()
                
                footer_date_time = in_line[10:22]
            
            # Extract the NOTAM Briefing ID
            if in_line[0:11] == 'Briefing Id':
                this_briefing.Briefing_Ref = in_line[12:].strip()


            # If this is the first line of a NOTAM - i.e. matches the format similar to C4544/19 NOTAMN
            #OR if it's the "End of Document"
            #OR if it's the start of a new series sections
            if regNotamMatch.match(in_line) != None or in_line.upper().find('END OF DOCUMENT')>=0 or in_line.upper()[0:5] == 'SERIE':

                # if we are already processing another NOTAM, close it off
                if processing_notam == True:
                    
                    # Extract more accurate co-ordinates from the "E" line
                    try:
                        reACoord = regACoord.search(this_notam.Notam_Text)
                    except:
                        print(f'Q-Line for NOTAM #{len(notams)+1} not correctly formatted:')
                        print(in_line)
                        current_app.logger.error(f'Q-Line for NOTAM #{len(notams)+1} not correctly formatted: {in_line}')
                        return None
                        
                    if reACoord is not None:
                        this_notam.E_Coord_Lat = reACoord['coord_lat']
                        this_notam.E_Coord_Lon = reACoord['coord_lon']
                    
                    this_notam.Raw_Text = raw_notam
                    this_notam.Briefing = this_briefing
                    tidy_notam(this_notam)
                    notams.append(this_notam)

                    # Reset all flags and variables
                    processing_D_line = False
                    processing_E_line = False
                    processing_notam = False
                    raw_notam = ''
                    
                    # Create new NOTAM object
                    this_notam = Notam()

                #if this is not the end of document, and not the "SERIE" line then start a new NOTAM
                if in_line.upper().find('END OF DOCUMENT') < 0 and in_line.upper()[0:5] != 'SERIE':
                    notam_ref = in_line[0:in_line.find("NOTAM")-1]  #Extract NOTAM ref number
                    this_notam.Notam_Series = notam_ref[0:1]
                    this_notam.Notam_Number = notam_ref
                    raw_notam += in_line
                    processing_notam = True #Flag that we are processing a NOTAM

            # If this is not the first line of the NOTAM, and we are currently processing one
            elif processing_notam == True:

                raw_notam += in_line #Text verison of NOTAM - to be used as comparison to check the NOTAM was decoded correctly

                if in_line[0:3] == 'Q) ':   #If this is a "Q" line

                    #Perform Regular Expression match on the line
                    reResult = regQLine.match(in_line)

                    #Extract the elements of the Q line that were matched.  This is inside a "try" to pickup any format anomalies
                    try:
                        #Q) FAJA/QWCLW/IV/M/W/000/002/2949S03100E001   is broken down as follows:
                        this_notam.FIR = reResult['FIR']  #FAJA
                        this_notam.Q_Code_2_3 = reResult['QCode'][:2]  #WC(LW)
                        this_notam.Q_Code_4_5 = reResult['QCode'][2:]  #(WC)LW
                        this_notam.Flightrule_Code = reResult['FlightRule']  #IV
                        this_notam.Purpose_Code = reResult['Purpose']  #M

                        this_notam.Scope_Code = reResult['AD_ER']
                        this_notam.Scope_Aerodrome = 'A' in this_notam.Scope_Code
                        this_notam.Scope_EnRoute = 'E' in this_notam.Scope_Code
                        this_notam.Scope_Nav_Warning = 'W' in this_notam.Scope_Code
                        this_notam.Scope_Checklist = 'K' in this_notam.Scope_Code

                        this_notam.Q_Level_Lower = reResult['LevelLower']  #000
                        this_notam.Q_Level_Upper = reResult['LevelUpper']  #002
                        this_notam.Q_Coord_Lat = reResult['Coords'][0:5]  #2949S03100E
                        this_notam.Q_Coord_Lon = reResult['Coords'][5:]  #2949S03100E
                        this_notam.Radius = reResult['Radius']  #001
                    except:
                        print(f'Q-Line for NOTAM #{len(notams)+1} not correctly formatted:')
                        print(in_line)
                        current_app.logger.error(f'Q-Line for Notam #{len(notams)+1} not correctly formatted: {in_line}')
                        return None

                if in_line[0:3] == 'A) ':  # If this is an "A, B, C" line

                    #Perform Regular Expression match on the line
                    reResult = regABCLine.match(in_line)

                    #Extract the elements of the A,B,C line that were matched.  This is inside a "try" to pickup any format anomalies
                    try:
                        #A) FAJA B) 2001010700 C) 2003301600 EST   is broken down as follows:

                        this_notam.A_Location = reResult['A_Location']  #FAJA
                        this_notam.From_Date = datetime.strptime(reResult['FromDate'],'%y%m%d%H%M')  #2001010700
                        this_notam.To_Date_Estimate = False
                        this_notam.To_Date_Permanent = False

                        to_date = reResult['ToDate'].strip()
                        if to_date == 'PERM':
                            this_notam.To_Date = datetime(datetime.utcnow().year+10,12,31,23,59)
                            this_notam.To_Date_Permanent = True
                        elif to_date[-3:] == 'EST':
                            this_notam.To_Date = datetime.strptime(to_date[:-4],'%y%m%d%H%M') #2003301600 EST
                            this_notam.To_Date_Estimate = True
                        else:
                            this_notam.To_Date = datetime.strptime(to_date,'%y%m%d%H%M') #2003301600    

                    except:
                        print(f'ABC-Line for NOTAM #{len(notams)} not correctly formatted:')
                        print(in_line)
                        current_app.logger.error(f'ABC-Line for NOTAM #{len(notams)} not correctly formatted: {in_line}')
                        return None

                if in_line[0:3] == 'D) ':  #If this is a "D" Line
                    processing_D_line = True  #Flag to allow for multi-line processing
                    this_notam.Duration = in_line[3:-1]  #Extract text excluding the "D) " at start of line

                elif processing_D_line == True and not in_line[0:3] == 'E) ':  #If we are processing "D" Line, and not yet on an "E" Line
                    this_notam.Duration += ' ' + in_line[:-1]  #Append the line to the current "D" Line (adding space, removing NEWLINE)

                elif in_line[0:3] == 'E) ':  #If this is an "E" line
                    #Need to prevent the footer appearing in the Text
                    if footer_date_time not in in_line:
                        this_notam.Notam_Text = in_line[3:-1]  #Extract text excluding the "E) " at start of line
                        processing_D_line = False  #We are no longer processing "D" (incase we were)
                        processing_E_line = True  #We are now processing E line - very likely multi-line

                elif processing_E_line == True and not in_line[0:3] == 'F) ':  #If we are processing "E" Line, and not yet on an "F" Line
                    if footer_date_time not in in_line:
                        this_notam.Notam_Text += ' ' + in_line[:-1]  #Append the line to the current "E" Line (adding space, removing NEWLINE)

                
                if in_line[0:3] == 'F) ':  #If this is an "F" line
                    processing_D_line = False #Not processing a D Line
                    processing_E_line = False #Not processing an E Line
                    #Perform Regular Expression match on the line
                    reResult = regFGLine.match(in_line)
                    #Extract the elements of the F,G line that were matched.  This is inside a "try" to pickup any format anomalies
                    try:
                        #F) GND G) 181FT AMSL   is broken down as follows:
                        this_notam.Level_Lower = reResult['F_FL_Lower']  #GND
                        this_notam.Level_Upper = reResult['G_FL_Upper']  #181FT AMSL
                    except:
                        print(f'FG-Line for NOTAM #{len(notams)} not correctly formatted:')
                        print(in_line)
                        current_app.logger.error(f'FG-Line for NOTAM #{len(notams)} not correctly formatted: {in_line}')
                        return None

    #We have finished processing the file, so check if we need to write the final NOTAM in the file
    if processing_notam == True:
        this_notam.Raw_Text = raw_notam
        this_notam.Briefing = this_briefing
        tidy_notam(this_notam)
        notams.append(this_notam)
    
    return this_briefing #return the Briefing Object (which contains all the notams)


def get_hidden_notams(briefing_id):
    """ Function to return a list of permanently hidden NOTAMS for a specific Briefing.
    The User is able to choose to permanently hide specific notams - this returns these
    Search is against a specific Briefing to limit the list of hidden NOTAMS returns, by only
    returning those relevant to this query/briefing

    Parameters
    ----------
    briefing_id : int
        The briefing to match the hidden NOTAMS from.

    Returns
    -------
    list
        List of Notam Numbers
    """

    # Connect
    sqa_sess = sqa_session()

    # Query the database, filtering by briefing and user
    hidden_list = sqa_sess.query(Notam, UserHiddenNotam.Notam_Number).filter(
        and_(Notam.BriefingID == briefing_id, UserHiddenNotam.UserID == session['userid'])
        ).join(UserHiddenNotam, Notam.Notam_Number == UserHiddenNotam.Notam_Number).all()

    # Turn the results into a list of Notam Numbers
    hidden = [x.Notam_Number for x in hidden_list]
    
    return hidden


def get_new_deleted_notams(since_date=datetime.utcnow().date() - timedelta(days=7), briefing_id=None, return_count_only=True):
    """ Function to return the New and Deleted NOTAMS since a specific date, or since a specific Briefing.  
    Returns either a list of notams or a count of Notams

    Parameters
    ----------
    since_date : date, default=today-7
        Date to be compared to
    briefing_id : int, default=None
        Briefing to be compared to
    return_count_only : bool, default=True
        Only return a count of Notams; otherwise return a list

    Returns
    -------
    tuple
        previous briefing object - the historic briefing being compared to
        new notams: either a count (int) or a list of notams added since prev briefing
        deleted noteams: either a count (int) or a list of notams deleted since prev briefing
    """

    sqa_sess = sqa_session()
    
    # Get latest briefing
    latest_brief_id = sqa_sess.query(func.max(Briefing.BriefingID)).first()[0]

    # If a specific previous briefing ID was supplied use that
    if briefing_id:
        prev_briefing_id = briefing_id
    # Otherwise get the first briefing prior to since_date
    else:
        prev_briefing_id = sqa_sess.query(func.max(Briefing.BriefingID)).filter(Briefing.Briefing_Date <= since_date).first()[0]
        
    # Load the prev briefing
    prev_briefing = sqa_sess.query(Briefing).get(prev_briefing_id)
    
    # Get the notams for current briefing and prev briefing
    latest_notams = sqa_sess.query(Notam.Notam_Number).filter(Notam.BriefingID == latest_brief_id)
    prev_notams = sqa_sess.query(Notam.Notam_Number).filter(Notam.BriefingID == prev_briefing_id)
    
    # Compare Notams...
    # If we must only return the count...
    if return_count_only == True:
        # Compare and get new/deleted notams
        new_notams = latest_notams.filter(~Notam.Notam_Number.in_(prev_notams)).count()
        deleted_notams = prev_notams.filter(~Notam.Notam_Number.in_(latest_notams)).count()
    
    # Otherwise return the detailed notams...
    else:
        new_notam_nos = latest_notams.filter(~Notam.Notam_Number.in_(prev_notams))
        deleted_notam_nos = prev_notams.filter(~Notam.Notam_Number.in_(latest_notams))
        
        new_notams = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == latest_brief_id, Notam.Notam_Number.in_(new_notam_nos))).order_by(Notam.Notam_Number).all()
        deleted_notams = sqa_sess.query(Notam).filter(and_(Notam.BriefingID == prev_briefing_id, Notam.Notam_Number.in_(deleted_notam_nos))).order_by(Notam.Notam_Number).all()


    return prev_briefing, new_notams, deleted_notams


def generate_notam_geojson(notam_list, hide_user_notams=False):
    """ Function to create a list of GEOJSON features based on the list of Notams passed  
    The NOTAMS grouped into GEOJSON Features using the QCode_2_3_Lookup.Grouping 
    Each Feature will form a layer on the map - this allows for easy filtering of layers.
    The function also returns a list of the Groups applicable to these NOTAMS, and a list of map layers
    The Map layers differ from the simple Groups, as each layer only contains one type of geometry.
    
    Eg. Groups could be: ['Hazards','Aerodromes'...]
    Layers could be: ['Hazards_polygon','Hazards_circle', 'Aerodromes_polygon','Aerodromes_circle' ...]
    
    If hide_user_notams == True: mark specifically hidden NOTAMS by setting flags, and modifying the layer-name to prevent it being shown
    
    Parameters
    ----------
    notam_list : list
        list of Notam objects to create the GEOJSON Features from
    hide_user_notams : bool
        If the User has chosen to permanently hide NOTAMS, should we hide them?
        
    Returns
    -------
    tuple
        notam_features: list of GEOJSON Feature strings - each element in the list includes Notams for a specific QCode_2_3_Lookup.Grouping
        used_groups: list of QCode_2_3_Lookup.Grouping items that were used/applicable to the Notams in the original list - eg. ['Hazards','Aerodromes'...]
        used_layers: list of Layer names structred as "Group_Geometry" - eg. ['Hazards_polygon','Hazards_circle', 'Aerodromes_polygon','Aerodromes_circle' ...]
    """

    # Initialise Variables
    used_groups = []  #contains applicable groupings for use on the web page (i.e. it excludes groupings that do not appear) - used to filter layers on the map
    used_layers = []  #contains layer groupings in form: used_group+_+geometry (poly/circle) - used to separate layers on the map
    notam_features = []

    # If we need to hide user notams:
    if hide_user_notams == True:
        # Get the briefingID from the first NOTAM in the list
        briefingid = notam_list[0].BriefingID
        # Use this briefing ID to get a list of hidden NOTAMS
        hidden_notams = get_hidden_notams(briefingid)
    # Otherwise an empty list
    else:
        hidden_notams = []

    # Create a GEOJSON Feature for each Notam - Feature contains specific Notam attributes
    for ntm in notam_list:
        
        # If this NOTAM is permanently hidden, set flag and create suffix 
        if ntm.Notam_Number in hidden_notams:
            hidden = True
            hide_suffix = '-permhide'
        else:
            hidden = False
            hide_suffix = ''
        
        # Date Notam applies from
        ntm_from = datetime.strftime(ntm.From_Date,"%Y-%m-%d %H:%M") 
        # Date Notam applies to - take into account Perm and Est dates
        if ntm.To_Date_Permanent == True:
            ntm_to = 'Perm'
        else:
            ntm_to = datetime.strftime(ntm.To_Date,"%Y-%m-%d %H:%M")
            ntm_to += " Est" if ntm.To_Date_Estimate == True else ""
        
        # If this Notam has a bounded area, then create a GEOJSON polygon object
        if ntm.Bounded_Area:
            # Convert from Degrees Minutes Seconds to Decimal Degrees, for the bounded area and reverse coords to Lon, Lat
            coords = helpers.convert_bounded_dms_to_dd(ntm.Bounded_Area, reverse_coords=True)
            # Create the GeoJson Polygon
            geojson_geom=Polygon([coords])
            type_suffix = '_polygon'

        # If this Notam is a circle, then also create a GEOJSON polygon object
        elif ntm.is_circle():
            coords = helpers.convert_bounded_dms_to_dd(ntm.circle_bounded_area(), reverse_coords=True)
            geojson_geom=Polygon([coords])
            type_suffix = '_polygon'

        # Otherwise this Notam is a point with no radius, so create a GEOJSON circle object 
        else:
            coords = (helpers.convert_dms_to_dd(ntm.Coord_Lon), helpers.convert_dms_to_dd(ntm.Coord_Lat))
            geojson_geom=Point(coords)
            type_suffix = '_circle'
        
        # Get the Notam Duration if it exists
        if ntm.Duration:
            ntm_duration = ntm.Duration
        else:
            ntm_duration = ''
        
        # Get the Colour for this QCode Group, and extract the RGB channels from the Hex colour code
        if current_app.config['MAP_USE_CATEGORY_COLOURS'] == '0':
            colr = current_app.config['MAP_DEFAULT_CATEGORY_COLOUR']
        else:
            colr = ntm.QCode_2_3_Lookup.Group_Colour
            
        col_r = int(colr[1:3],16)
        col_g = int(colr[3:5],16)
        col_b = int(colr[5:7],16)
        
        # Create the Fill Colour attribute - opacity of 0.4
        fill_col=f'rgba({col_r},{col_g},{col_b},0.4)'
        # Create the Line Colour attribute - opacity of 1
        line_col=f'rgba({col_r},{col_g},{col_b},1)'
        
        # Append this Feature to the collection, setting the various Notam attributes as properties
        notam_features.append(Feature(geometry=geojson_geom, properties={'fill':fill_col, 'line':line_col, 
                                                                 'group': ntm.QCode_2_3_Lookup.Grouping,
                                                                 'layer_group': ntm.QCode_2_3_Lookup.Grouping + type_suffix + hide_suffix, 
                                                                 'notam_number': ntm.Notam_Number,
                                                                 'notam_location': ntm.A_Location,
                                                                 'from_date': ntm_from,
                                                                 'to_date' : ntm_to,
                                                                 'duration' : ntm_duration,
                                                                 'radius': ntm.Radius,
                                                                 'permanently_hidden' : hidden,
                                                                 'notam_text': ntm.Notam_Text}))

        # Add this group+geometry combination to the list, so the map knows to split out a layer for it.
        if (ntm.QCode_2_3_Lookup.Grouping + type_suffix) not in used_layers:
            used_layers.append(ntm.QCode_2_3_Lookup.Grouping + type_suffix)

        # Add the Notam Grouping to the collection of used groups
        if ntm.QCode_2_3_Lookup.Grouping not in used_groups:
            used_groups.append(ntm.QCode_2_3_Lookup.Grouping)
        
        # Sort groups alphabetically for better display on the map
        used_groups.sort()
        used_layers.sort()
        
    return notam_features, used_groups, used_layers

