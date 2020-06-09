'''
Module to import NOTAMS (NOtice To AirMen) from CAA source(s) and store in a structured class.

@author: aretallack
'''

#SQLAlchemy used as the ORM to manage notam classes
#from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Date, Time, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship

import re
import sys
from datetime import datetime


#SQLAlchemny - A declarative base class  
Base = declarative_base() 
eng = ''


class QCode_2_3_Lookup(Base):
    __tablename__ = "QCodes_2_3_Lookup"
    
    Code = Column(String(2), primary_key=True)
    Description = Column(String)
    Abbreviation = Column(String)
    
    Notams = relationship("Notam")


class QCode_4_5_Lookup(Base):
    __tablename__ = "QCodes_4_5_Lookup"
    
    Code = Column(String(2), primary_key=True)
    Description = Column(String)
    Abbreviation = Column(String)
    
    Notams = relationship("Notam")


class Briefing(Base):
    '''
    Stores details of daily briefing.  Once briefing contains many Notams
    '''
    __tablename__ = "Briefings"
    
    BriefingID = Column(Integer, primary_key = True)
    Briefing_Country = Column(String(2)) #ICAO Country Code
    Briefing_Ref = Column(String(20)) #CAA-assigned Briefing Reference
    Briefing_Date = Column(Date) #Date CAA releases the briefing
    Briefing_Time = Column(Time) #Time CAA releases the briefing
    Import_DateTime = Column(DateTime) #Date & Time the briefing was imported
    
    Notams = relationship("Notam", back_populates='Briefing')


class Notam(Base):
    '''
    Stores a single NOTAM ((NOtice To AirMen)
    '''
    
    __tablename__ = "Notams"
    
    NotamID = Column(Integer, primary_key=True) #Unique ID for each record
    BriefingID = Column(Integer, ForeignKey("Briefings.BriefingID"))
    Notam_Number = Column(String(20)) #CAA-assigned Notam number - e.g. A1543/20
    Notam_Series = Column(String(1)) #Notam Series - e.g. A/B/C/D
    Raw_Text = Column(String) #The raw NOTAM text - primarily for troubleshooting
    FIR = Column(String(4)) #ICAO FIR Notam applies to
    Q_Code_2_3 = Column(String(2), ForeignKey("QCodes_2_3_Lookup.Code")) #Q-code letters 2+3 from the Q) field in Notam
    Q_Code_4_5 = Column(String(2), ForeignKey("QCodes_4_5_Lookup.Code")) #Q-code letters 4+5 from the Q) field in Notam
    Flightrule_Code = Column(String(4)) #Flightrule - I/V/K or combination
    Purpose_Code = Column(String(4)) #ICAO code describing the purpose of NOTAM 
    Scope_Code = Column(String(3)) #Scope of NOTAM - A(erodrome) / E(n-route) / W(Nav Warning) / K(Checklist)
    Scope_Aerodrame = Column(Boolean) #Is scope for Aerodrome?
    Scope_EnRoute = Column(Boolean) #Is Scope for En-Route?
    Scope_Nav_Warning = Column(Boolean) #Is scope for Nav Warning?
    Scope_Checklist = Column(Boolean) #Is scopt for Checklist?
    Q_Level_Lower = Column(String(10)) #Lower Level from Q Code
    Q_Level_Upper = Column(String(10)) #Upper Level from Q Code
    Q_Coord_Lat = Column(String(7)) #Latitude from Q Code
    Q_Coord_Lon = Column(String(8)) #Longitude from Q Code
    Radius = Column(Integer) #Radius from Q Code
    A_Location = Column(String(20)) #Locations from A) section of Notam
    From_Date = Column(DateTime) #Date Notam applies From - B) section of Notam
    To_Date = Column(DateTime) #Date Notam applies To - C) Section of Notam
    To_Date_Estimate = Column(Boolean) #Is the To Date an Estimated To Date?
    To_Date_Permanent = Column(Boolean) #Is the To Date Permanent?
    Notam_Text = Column(String) #Text of the Notam - E) section of Notam
    Duration = Column(String(50)) #Duration of Notam - D) section of Notam
    Level_Lower = Column(String(10)) #Lower Level for Notam - combines F) section and Q) section
    Level_Upper = Column(String(10)) #Upper Level for Notam - combines G) section, Q) section E) Secion (text)
    E_Coord_Lat = Column(String(7)) #Co-ordinates extracted from the E) section (text)
    E_Coord_Lon = Column(String(8)) #Co-ordinates extracted from the E) section (text)
    Coord_Lat = Column(String(8)) #Final co-ordinates to use for the Notam Mapping
    Coord_Lon = Column(String(8)) #Final co-ordinates to use for the Notam Mapping
    Bounded_Area = Column(String) # Co-ordinates of a bounded area defined in the Notam
    Unique_Geo_ID = Column(String(25)) #Combination of Lat + Lon + Radius to allow grouping of 
        
    Briefing = relationship("Briefing", back_populates='Notams')
    QCode_2_3_Lookup = relationship("QCode_2_3_Lookup")
    QCode_4_5_Lookup = relationship("QCode_4_5_Lookup")
    

def init_db(sql_eng):
    #The declarative Base is bound to the database engine.
    eng = sql_eng
    Base.metadata.bind = eng

def create_new_db():
    import csv

    #Create defined tables
    Base.metadata.create_all()
    
    print('----------Initialising Database for Initial Use----------')
    print('Created Data Tables')
    
    Session = sessionmaker(bind=eng)
    ses = Session()
    
    with open('sql/Q_Code_2_3.csv') as imp_file:
        csv_reader = csv.DictReader(imp_file)
        for row in csv_reader:
            ref = QCode_2_3_Lookup(Code = row['Code'], Description = row['Description'], Abbreviation = row['Abbreviation'])
            ses.add(ref)
    print('Imported QCode Lookups: QCode_2_3_Lookup')

    with open('sql/Q_Code_4_5.csv') as imp_file:
        csv_reader = csv.DictReader(imp_file)
        for row in csv_reader:
            ref = QCode_4_5_Lookup(Code = row['Code'], Description = row['Description'], Abbreviation = row['Abbreviation'])
            ses.add(ref)
    
    print('Imported QCode Lookups: QCode_4_5_Lookup')

    ses.commit()
    print('----------Committed and Completed----------')


'''---------------------------------------
 tidy_notam(notam)

 PURPOSE: A few manipulations on the Notam object to tidy it up, calc 
          a few derived fields 

 INPUT: notam = The notam Object

 RETURNS: nothing - notam obkect returned by reference

---------------------------------------'''    
def tidy_notam(notam):

    #---Following 2 Regular expressions are to extract co-ordinates of bounded areas within NOTAM description:
    #Eg. POWER STATION AIRFIELD (260538S 0292717E), MPUMALANGA (260150S 0292048E, 260527S 0292655E, 260748S 0292611E, 260249S 0291845E ) : REMOTELY PILOTED AIRCRAFT SYSTEMS (RPAS) (400FT AGL) OPS TAKING PLACE BEYOND VISUAL LINE OF SIGHT.
    #First, we want to ignore any single pairs of co-ordinates (eg. in the above, the co-ord of the airfield)
    regIgnoreCoord = re.compile(r'(\([ ]*\d{6,6}[N,S][ ,]+\d{7,7}[E,W][ ]*\))')
    #Then remove decimals - some co-ordinates are written with 2 decimals eg 260527.32S 0292655.24E
    regIgnoreDecimals = re.compile(r'(\d[.]\d{0,3}[NSEW])')
    #Then we want to extract pairs of lat/lon - eg.(260150S 0292048E, 260527S 0292655E, 260748S 0292611E, 260249S 0291845E )
    regAreaCoord = re.compile(r'(?P<coord_lat>\d{6,6}[N,S])[ ]+(?P<coord_lon>\d{7,7}[E,W])')
    
    #----Try to extract bounded co-ordinates if they exist, but not for Obstacles
    sCoords = ''
#    sSortedCoods = ''
    if notam.Q_Code_2_3 != 'OB':  #Obstacles are identified by first 2 letters in QCode = "OB"
        #First are there any single co-ord pairs?  If so, remove them from the text 
        tempText = notam.Notam_Text
        reFound=regIgnoreCoord.findall(tempText)
        for x in reFound:
            tempText=tempText.replace(x,"") #remove by replacing with blanks
    
        #Second remove any decimals
        reFound = regIgnoreDecimals.findall(tempText)
        for x in reFound:
            tempText = tempText.replace(x[1:-1],"") #remove by replacing with blanks
        
        #Now try to find 3-or-more co-ord pairs in the remaining string (less than 3 is not a polygon)
        reBoundedCoords= regAreaCoord.findall(tempText)
        if len(reBoundedCoords)>=3:
            for x in reBoundedCoords:
                sCoords = sCoords + f"{x[0]},{x[1]} " #add the next set of coords on
            
            #If the polygon is not closed - i.e. first coords do not equal the last - then close it
            if reBoundedCoords[0] != reBoundedCoords[-1]: 
                sCoords = sCoords + f"{reBoundedCoords[0][0]},{reBoundedCoords[0][1]} " #add the first set of coords at the end
                reBoundedCoords.append(reBoundedCoords[0])
            
            sCoords = sCoords.strip() #removing trailing space
#            reBoundedCoords = sortPolygonPoints(reBoundedCoords)
#            for x in reBoundedCoords:
#                sSortedCoods  = sSortedCoods  + f"{x[0]},{x[1]} " #add the next set of coords on
#            sSortedCoods = sSortedCoods.strip()
        
            
    notam.Bounded_Area = sCoords
    
##    if 'Duration' not in notamDict:
##        notamDict['Duration'] = ''

    #Determine the final Lower Level - use the "F" field if exists, otherwise the lower level from Q field
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

    #Determine the final Upper Level - use the "G" field if exists, otherwise the lower level from Q field
    if notam.Level_Upper is not None:
        if notam.Level_Upper.find('AMSL')>=0:
            notam.Level_Upper = notam.Level_Upper[:notam.Level_Upper.find('FT')+2]
        else:
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

    #Below is unique ID to allow grouping of similar NOTAMS based on lat+lon+radius
    notam.Unique_Geo_ID = notam.Coord_Lat + '_' + notam.Coord_Lon + '_' + notam.Radius
    
#    #Generate either a bounded "Shapely" polygon, circle or point for this NOTAM 
#    if len(notamDict['Bounded_Area']) > 0:
#        notamShape = Polygon(switchLatLon(reBoundedCoords, True)) #Use the co-ordinates from earlier
#    elif notamDict['Radius'] == 1:
#        #long then lat
#        notamShape = Point(convertDmsToDd(notamDict['FinalCoord_Lon']), convertDmsToDd(notamDict['FinalCoord_Lat'])) #Shapely Point
#    else:
#        notamShape = generateCircleShapely(notamDict['FinalCoord_Lat'], notamDict['FinalCoord_Lon'], int(notamDict['Radius']))
#    
#    notamDict['Shapely'] = notamShape



'''---------------------------------------
 parseNotamTextFile(filename)

 PURPOSE: Opens and parses a text file containing NOTAMs, placing details into XML format
          Text file is a text version of the CAA Notam Summary:
           http://www.caa.co.za/Notam%20Summaries%20and%20PIB/Summary.pdf

 INPUT: sFileName = path and name of text file

 RETURNS: Briefing Object, list of Notam Objects
---------------------------------------'''
    
def parseNotamTextFile(filename, country_code):
    
    briefing_date_format = {'ZA':'%d%b%y'}
    briefing_time_format = {'ZA':'%H%M'}
    
    
    processing_notam = False  #Are we processing a NOTAM currently?
    processing_D_line = False  #Are we processing a "D" line in a NOTAM currently - these can be multi-line?
    processing_E_line = False  #Are we processing an "E" line in a NOTAM currently - these can be multi-line?
##    notam_text = ''  #Text for the current NOTAM
    raw_notam = '' #Raw text of NOTAM
    
    notam_ref = ''  #NOTAM Reference Number
    
##    dictNotam = {}  #Dictionary of details for current NOTAM being processed
##    dictHeader = {}  #Dictionary of header details: Date & Time, Briefing ID

##    decode_notam_scope={'A':'Aerodrome','E':'En-Route','W':'Nav Warning','K':'Checklist'}
    
    #Create the empty list for notam objects
    notams = []
    this_briefing = Briefing()
    this_notam = Notam()
    
##    xmlNotam = ET.Element('NOTAM_BRIEFING')
    
    #-------Regular Expressions to extract details from NOTAMs
    
    #Identify the NOTAM heading - e.g.: C4544/19 NOTAMN
    regNotamMatch = re.compile('[A-Z][0-9]+/[0-9]+ NOTAM')
    #Extract details from the "Q" Line - e.g.: Q) FAJA/QWCLW/IV/M/W/000/002/2949S03100E001
    regQLine =  re.compile(r'^Q\) (?P<FIR>\w+)/Q(?P<QCode>\w+)/(?P<FlightRule>\w+)/(?P<Purpose>\w+)/(?P<AD_ER>\w+)/(?P<LevelLower>\d+)/(?P<LevelUpper>\d+)/(?P<Coords>\w{11,11})(?P<Radius>\d+)')
    #Extract details from the "A, B, C" Line - e.g.: A) FAJA B) 2001010700 C) 2003301600 EST
    regABCLine = re.compile(r'^A\) (?P<A_Location>[\w\s]+)\s+B\) (?P<FromDate>\w+)\s+C\) (?P<ToDate>[\w,\s]+)\n')
    #Extract details from the "F, G" Line - e.g.: F) GND G) 181FT AMSL
    regFGLine = re.compile(r'^F\) (?P<F_FL_Lower>\w+)\s+G\) (?P<G_FL_Upper>[\w\s]+)\n')
    #Extractco-ordinates from the "E" Line - e.g.: EASTERN CAPE (325416S 0260602E): WND MNT MAST(394FT AGL) ERECTED.
    regACoord = re.compile(r'\((?P<coord_lat>\d{6,6}[N,S])[ ,]+(?P<coord_lon>\d{7,7}[E,W])\)')
    
    
    #Open and parse teh text file line by line
    with open(filename) as notam_file:

        for in_line in notam_file:
            in_line = in_line.replace(chr(12),"")  #PDF File may have form feed/new page character - ASCII code 12
            
            #Extract the Date and Time of the NOTAM Briefing
            if in_line[0:9] == 'Date/Time':
##                dictHeader['Date'] = in_line[10:17]
##                dictHeader['Time'] = in_line[18:22]
                this_briefing.Briefing_Country = country_code
                this_briefing.Briefing_Date = datetime.strptime(in_line[10:17],briefing_date_format[country_code]).date()
                this_briefing.Briefing_Time = datetime.strptime(in_line[18:22],briefing_time_format[country_code]).time()
                this_briefing.Import_DateTime = datetime.now()
                
                footer_date_time = in_line[10:22]
##                xmlNotam.set('Date', dictHeader['Date'])
##                xmlNotam.set('Time', dictHeader['Time'])
            
            #Extract the NOTAM Briefing ID
            if in_line[0:11] == 'Briefing Id':
##                dictHeader['Briefing_Id'] = in_line[12:-1]
##                xmlNotam.set('Briefing_ID',dictHeader['Briefing_Id'])
                this_briefing.Briefing_Ref = in_line[12:-1]


            #if this is the first line of a NOTAM - i.e. matches the format similar to C4544/19 NOTAMN
            #OR if it's the "End of Document"
            if regNotamMatch.match(in_line) != None or in_line.upper().find('END OF DOCUMENT')>=0:

                #if we are already processing another NOTAM, close it off
                if processing_notam == True:
                    
                    #Extract more accurate co-ordinates from the "E" line
##                    reACoord = regACoord.search(dictNotam['Text'])
                    reACoord = regACoord.search(this_notam.Notam_Text)
                    if reACoord is not None:
##                        dictNotam['AccurateCoord_Lat'] = reACoord['coord_lat']
##                        dictNotam['AccurateCoord_Lon'] = reACoord['coord_lon']
                        this_notam.E_Coord_Lat = reACoord['coord_lat']
                        this_notam.E_Coord_Lon = reACoord['coord_lon']
                    
                    this_notam.Raw_Text = raw_notam
                    this_notam.Briefing = this_briefing
                    tidy_notam(this_notam)
##                    createNotamXML(xmlNotam, dictNotam) #Add Notam to XML structure
                    notams.append(this_notam)
                    #reset all flags and variables
                    processing_D_line = False
                    processing_E_line = False
                    processing_notam = False
                    raw_notam = ''
##                    dictNotam = {}
##                    notam_text = ''
                    #Create new NOTAM object
                    this_notam = Notam()

                #if this is not the end of document, then start a new NOTAM
                if in_line.upper().find('END OF DOCUMENT') < 0:
                    notam_ref = in_line[0:in_line.find("NOTAM")-1]  #Extract NOTAM ref number
##                    dictNotam['Notam_Series'] = notam_ref[0:1]
##                    dictNotam['Notam_Number'] = notam_ref
                    this_notam.Notam_Series = notam_ref[0:1]
                    this_notam.Notam_Number = notam_ref
                    raw_notam += in_line
                    processing_notam = True #Flag that we are processing a NOTAM

            #If this is not the first line of the NOTAM, and we are currently processing one
            elif processing_notam == True:

##                notam_text += in_line #Text verison of NOTAM - to be used as comparison to check the NOTAM was decoded correctly
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

##                        dictNotam['FIR'] = reResult['FIR']  #FAJA
##                        dictNotam['QCode'] = reResult['QCode']  #WCLW
##                        dictNotam['FlightRule'] = reResult['FlightRule']  #IV
##                        dictNotam['Purpose'] = reResult['Purpose']  #M
                        
##                        dictNotam['ADrome_ERoute']=""
##                        for x in reResult['AD_ER']:
##                            if len(dictNotam['ADrome_ERoute'])>0: dictNotam['ADrome_ERoute'] += ' / '
##                            dictNotam['ADrome_ERoute'] += decode_notam_scope[x]   #W
                        this_notam.Scope_Code = reResult['AD_ER']
                        this_notam.Scope_Aerodrome = 'A' in this_notam.Scope_Code
                        this_notam.Scope_EnRoute = 'E' in this_notam.Scope_Code
                        this_notam.Scope_Nav_Warning = 'W' in this_notam.Scope_Code
                        this_notam.Scope_Checklist = 'K' in this_notam.Scope_Code

##                        dictNotam['LevelLower'] = reResult['LevelLower']  #000
##                        dictNotam['LevelUpper'] = reResult['LevelUpper']  #002
##                        dictNotam['Coord_Lat'] = reResult['Coords'][0:5]  #2949S03100E
##                        dictNotam['Coord_Lon'] = reResult['Coords'][5:]  #2949S03100E
##                        dictNotam['Radius'] = reResult['Radius']  #001

                        this_notam.Q_Level_Lower = reResult['LevelLower']  #000
                        this_notam.Q_Level_Upper = reResult['LevelUpper']  #002
                        this_notam.Q_Coord_Lat = reResult['Coords'][0:5]  #2949S03100E
                        this_notam.Q_Coord_Lon = reResult['Coords'][5:]  #2949S03100E
                        this_notam.Radius = reResult['Radius']  #001
                    except:
                        print('****Q-Line for NOTAM not correctly formatted*****')
                        print(in_line)
                        sys.exit()

                if in_line[0:3] == 'A) ':  #If this is an "A, B, C" line

                    #Perform Regular Expression match on the line
                    reResult = regABCLine.match(in_line)

                    #Extract the elements of the A,B,C line that were matched.  This is inside a "try" to pickup any format anomalies
                    try:
                        #A) FAJA B) 2001010700 C) 2003301600 EST   is broken down as follows:
##                        dictNotam['A_Location'] = reResult['A_Location']  #FAJA
##                        dictNotam['FromDate'] = reResult['FromDate']  #2001010700
##                        dictNotam['ToDate'] = reResult['ToDate']  #2003301600 EST

                        this_notam.A_Location = reResult['A_Location']  #FAJA
                        this_notam.From_Date = datetime.strptime(reResult['FromDate'],'%y%m%d%H%M')  #2001010700
                        this_notam.To_Date_Estimate = False
                        this_notam.To_Date_Permanent = False

                        to_date = reResult['ToDate'].strip()
                        if to_date == 'PERM':
                            this_notam.To_Date = datetime(datetime.now().year+10,12,31,23,59)
                            this_notam.To_Date_Permanent = True
                        elif to_date[-3:] == 'EST':
                            this_notam.To_Date = datetime.strptime(to_date[:-4],'%y%m%d%H%M') #2003301600 EST
                            this_notam.To_Date_Estimate = True
                        else:
                            this_notam.To_Date = datetime.strptime(to_date,'%y%m%d%H%M') #2003301600    

                    except:
                        print('****ABC-Line for NOTAM not correctly formatted*****')
                        print(in_line)
                        sys.exit()

                if in_line[0:3] == 'D) ':  #If this is a "D" Line
                    processing_D_line = True  #Flag to allow for multi-line processing
##                    dictNotam['Duration'] = in_line[3:-1]  #Extract text excluding the "D) " at start of line
                    this_notam.Duration = in_line[3:-1]  #Extract text excluding the "D) " at start of line

                elif processing_D_line == True and not in_line[0:3] == 'E) ':  #If we are processing "D" Line, and not yet on an "E" Line
##                    dictNotam['Duration'] += ' ' + in_line[:-1]  #Append the line to the current "D" Line (adding space, removing NEWLINE)
                    this_notam.Duration += ' ' + in_line[:-1]  #Append the line to the current "D" Line (adding space, removing NEWLINE)

                elif in_line[0:3] == 'E) ':  #If this is an "E" line
                    #Need to prevent the footer appearing in the Text
                    if footer_date_time not in in_line:
##                        dictNotam['Text'] = in_line[3:-1]  #Extract text excluding the "E) " at start of line
                        this_notam.Notam_Text = in_line[3:-1]  #Extract text excluding the "E) " at start of line
                        processing_D_line = False  #We are no longer processing "D" (incase we were)
                        processing_E_line = True  #We are now processing E line - very likely multi-line

                elif processing_E_line == True and not in_line[0:3] == 'F) ':  #If we are processing "E" Line, and not yet on an "F" Line
                    if footer_date_time not in in_line:
##                        dictNotam['Text'] += ' ' + in_line[:-1]  #Append the line to the current "E" Line (adding space, removing NEWLINE)
                        this_notam.Notam_Text += ' ' + in_line[:-1]  #Append the line to the current "E" Line (adding space, removing NEWLINE)

                
                if in_line[0:3] == 'F) ':  #If this is an "F" line
                    processing_D_line = False #Not processing a D Line
                    processing_E_line = False #Not processing an E Line
                    #Perform Regular Expression match on the line
                    reResult = regFGLine.match(in_line)
                    #Extract the elements of the F,G line that were matched.  This is inside a "try" to pickup any format anomalies
                    try:
                        #F) GND G) 181FT AMSL   is broken down as follows:
##                        dictNotam['F_FL_Lower'] = reResult['F_FL_Lower']  #GND
##                        dictNotam['G_FL_Upper'] = reResult['G_FL_Upper']  #181FT AMSL
                        this_notam.Level_Lower = reResult['F_FL_Lower']  #GND
                        this_notam.Level_Upper = reResult['G_FL_Upper']  #181FT AMSL
                    except:
                        print('****FG-Line for NOTAM not correctly formatted*****')
                        print(in_line)
                        sys.exit()

    #We have finished processing the file, so check if we need to write the final NOTAM in the file
    if processing_notam == True:
##        tidy_notam(dictNotam)
        this_notam.Raw_Text = raw_notam
        this_notam.Briefing = this_briefing
        tidy_notam(this_notam)
##                    createNotamXML(xmlNotam, dictNotam) #Add Notam to XML structure
        notams.append(this_notam)
    
    return this_briefing, notams #return the full XML Tree Structure
