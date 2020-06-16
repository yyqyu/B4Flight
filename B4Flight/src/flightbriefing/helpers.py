'''
Created on 07 Jun 2020

@author: aretallack
'''

def read_db_connect():
    import configparser
    
    print("Configuring the application")
    cfg = configparser.ConfigParser()
    cfg.read('flightbriefing.ini')
    db_connect = cfg.get('database','connect_string')
    print(db_connect)

    return db_connect


'''---------------------------------------
 convert_dms_to_dd(coord_DMS):

 PURPOSE: converts a co-ordinate from Degrees-Minutes-Seconds to Decimal Degrees
          Accepts formats: ddmmS ddmmN dddmmE dddmmW ddmmssS ddmmssN dddmmssE dddmmssW

 INPUT: coord_DMS

 RETURNS: Decimal Degrees (Float)
---------------------------------------'''
        
def convert_dms_to_dd(coord_DMS):
    
    coord_DD = 0.0 #start with 0
    
    workingCoord = coord_DMS[:-1] #Strip the N/S/E/W off the end
    
    #Get the Degrees first - 2 digits for Lat and 3 for Lon
    if len(workingCoord) == 4 or len(workingCoord) == 6:
        coord_DD = float(workingCoord[0:2])
        workingCoord = workingCoord[2:]
    else:
        coord_DD = float(workingCoord[0:3])
        workingCoord = workingCoord[3:]
        
    #Now the minutes
    coord_DD += float(workingCoord[:2])/60.0
    
    #If there are seconds
    if len(workingCoord) == 4:
        coord_DD += float(workingCoord[2:])/60.0/60.0
    
    #South and West are negative
    if coord_DMS[-1] == 'S' or coord_DMS[-1] == 'W':
        coord_DD *= -1

    return coord_DD

def convert_bounded_dms_to_dd(bounded_coords, lat_lon_separator=",", coord_group_separator=" ", return_as_tuples=True, reverse_coords=False):
    if return_as_tuples == True:
        converted_coords = []
    else:
        converted_coords = ""
    
    if reverse_coords == True:
        ordr = [1,0]
    else:
        ordr = [0,1]
        
    for coord_grp in bounded_coords.split(coord_group_separator):
        coord_split = coord_grp.split(lat_lon_separator)

        if return_as_tuples == True:
            converted_coords.append((convert_dms_to_dd(coord_split[ordr[0]]),convert_dms_to_dd(coord_split[ordr[1]])))
        else:
            if len(converted_coords) > 0: converted_coords += coord_group_separator
            converted_coords += f'{convert_dms_to_dd(coord_split[ordr[0]])}{lat_lon_separator}{convert_dms_to_dd(coord_split[ordr[1]])}'
        
    return converted_coords

def convert_rgb_to_hex(r,g,b):
    hex_colour='#'
    hex_colour += hex(r)[2:]
    hex_colour += hex(g)[2:]
    hex_colour += hex(b)[2:]
    
    return hex_colour
    
    