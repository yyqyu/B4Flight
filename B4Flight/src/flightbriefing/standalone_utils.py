"""Contains various standalone functions used across the application

- extract_ATNS_data : Extract ATNS aerodromes, nav beacons, significant points from KML file 

"""



from xml.etree.ElementTree import ElementTree as ET
import csv


def extract_ATNS_data(filename, csv_filename):
    """Parses a KML file provided by ZA ATNS (https://www.atns.com/aim.php  -> RSA Airspace in 3d)
    extracting Aerodromes, Helistops, VOR, NDB, Waypoints, and writing to a CSV file.
    This CSV file can then be imported into B4Flight 
    
    Parameters
    ----------
    filename : str
        The KML Filename to parse
    csv_filename: str
        The CSV output filename
    
    Returns
    -------
    Nothing
    
    """
    
    aip_data = []
    
    tree = ET()
    tree.parse(filename)
    
    root = tree.getroot()
    
    if root.tag.find('{') > -1:
        ns_name=root.tag[root.tag.find('{')+1:root.tag.find('}')]
    else:
        ns_name=''
    
    ns={'ns':ns_name}
    
    base = root.find('ns:Document', ns)
    base = base.find('ns:Folder', ns)
    folders = base.findall('ns:Folder', ns)
    
    for category in folders:
        category_name = category[0].text
        
        if category_name not in ['Aerodromes', 'Helistops', 'VOR', 'NDB', 'Waypoints']:
            break
        
        extract_ATNS_items(ns, category, category_name, aip_data)
        
        csv_columns = ['Category','ID', 'Description', 'Longitude', 'Latitude']
        
        with open(csv_filename, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for data in aip_data:
                writer.writerow(data)
        print(f'Written to filename {csv_filename}')


def extract_ATNS_items(ns, branch, category_name, data_list):
    """Processes a single branch from a KML file, extracting the Description, ID, Co-ordinates
    for each of the items in that branch, and appending them to the "data_list" provided
    
    
    Parameters
    ----------
    ns: str
        The Namespace in the KML Filename
    branch: str
        The branch in the KML file
    category_name: str
        The category being processed
    data_list: array of Dictionaries
        The data list to append the processed items to
    
    Returns
    -------
    Nothing
    
    """
    
    sub_items = branch.findall('ns:Placemark', ns)
    for this_item in sub_items:
        x={}
        x['Category'] = category_name
        x['ID'] = this_item.find('ns:name', ns).text
        try:
            x['Description'] = this_item.find('ns:description', ns).text
        except:
            x['Description'] = x['ID']
            print(f'No Description for {category_name} -- {x["ID"]}')
            
        point = this_item.find('ns:Point', ns)
        coords = point.find('ns:coordinates', ns).text.split(',')
        x['Longitude'] = coords[0]
        x['Latitude'] = coords[1]
        data_list.append(x)
    
    sub_folders = branch.findall('ns:Folder', ns)
    for fldr in sub_folders:
        extract_ATNS_items(ns, fldr, category_name, data_list)

#extract_ATNS_data('C:/Users/aretallack/git/B4Flight/navdata_working/RSA DATA - 22APR2021.kml', 'C:/Users/aretallack/git/B4Flight/navdata_working/RSA DATA - 22Apr2021.csv')


