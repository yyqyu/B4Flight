"""Handles NOTAM Import-related Functionality

This module contains functions to download CAA PDF Briefing, 
convert to text using web API Zamzar
Parse the text file
Create NOTAM and Briefing object and import to database

Expected to be run from the command line:
 - import-notams
 - import-notam-text-file <text_file_name>
 
"""

import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import time
import os
import shutil
import sys
import configparser


from sqlalchemy import and_

import click
from flask import current_app
from flask.cli import with_appcontext

from .notams import parse_notam_text_file
from .db import Briefing, Notam
from .data_handling import sqa_session


def read_settings_ZA():
    """Reads the settings needed to process Notams, from the config file

    Returns
    -------
    dictionary 
        Settings in a dictionary
    """
    settings = {}
    
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(current_app.root_path, 'flightbriefing.ini'))
    settings['file_name_base'] = cfg.get('notam_import_ZA', 'file_name_base')
    settings['api_key'] = cfg.get('notam_import_ZA', 'key')
    settings['caa_notam_url'] = cfg.get('notam_import_ZA', 'caa_notam_url')
    settings['caa_briefing_page_url'] = cfg.get('notam_import_ZA', 'caa_updated_url')
    settings['check_url'] = cfg.get('notam_import_ZA', 'convert_check_url')
    settings['upload_url'] = cfg.get('notam_import_ZA', 'convert_upload_url')
    settings['status_url'] = cfg.get('notam_import_ZA', 'convert_status_url')
    settings['download_url'] = cfg.get('notam_import_ZA', 'convert_download_url')
    settings['pool_recycle'] = int(cfg.get('database', 'pool_recycle'))
    
    
    return settings


def get_latest_CAA_briefing_date_ZA(caa_webpage_url=None):
    """Checks the CAA website for the latest briefing date, and returns that date.
    Used to avoid downloading and parsing the PDF file to check if latest B4Flight briefing is current
    
    Parameters
    ----------
    caa_webpage_url : str
        full url to the CAA webpage containing the briefing download docs
        If NONE will get the page from the setting file
    
    Returns
    -------
    date
        date of the latest briefing
    OR
    None
        if the action failed, returns None
    """
    
    # If we don't have a URL then retrieve one from the flightbriefing.ini settings file
    if caa_webpage_url is None:
        cfg = configparser.ConfigParser()
        cfg.read(os.path.join(current_app.root_path, 'flightbriefing.ini'))
        update_url = cfg.get('notam_import_ZA', 'caa_updated_url')
    else:
        update_url = caa_webpage_url
    
    # Start with the result being None
    updated_date = None
    
    # Check the URL, streaming it to limit impact
    resp = requests.get(update_url, stream=True)
    
    # Did we succeed in retrieving the page?  200=success
    if resp.status_code == 200:
        
        # How is page encoded?
        enc = resp.encoding
        
        # Process page one line at a time to conserve resources
        for line in resp.iter_lines():
            # Does the line contain the text 'Last update'?
            if 'LAST UPDATE' in line.decode(enc).upper():
                start = line.decode(enc).upper().find('LAST UPDATE')
                end = line.decode(enc).upper().find('</SPAN>', start)
                found = line.decode(enc)[start:end]
                
                # Typical contents of variable "found":
                # Last update&#58;&#160;&#160;25 <span lang="EN-US" style="font-family&#58;calibri, sans-serif;font-size&#58;11pt;">September 2020
                # Extract the day of month - in this case the "25": &#160;25 <span
                dom = found[:found.upper().rfind('<SPAN')]
                dom = dom[dom.upper().rfind(';')+1:].strip()
                # Extract the Month + Year:
                month_year = found[found.rfind('>')+1:]
                month, year = month_year.split(' ')
                updated_date = datetime.strptime(f'{dom} {month} {year}', '%d %B %Y')
                updated_date_str = datetime.strftime(updated_date, '%Y-%m-%d')
                resp.close()
                break

    return updated_date


def download_notam_file_ZA(caa_notam_url, file_name):
    """Downloads PDF Briefing file from the CAA website
    
    Parameters
    ----------
    caa_notam_url : str
        full url to the PDF briefing file
    file_name : str
        filename that teh pdf file is saved to on local server
    
    """

    
    # Download the NOTAM Summary file from the CAA website
    res = requests.get(caa_notam_url, stream=True)

    # Save it to "file_name"
    try:
        with open(file_name, 'wb') as f:
            for chunk in res.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
    
        # Note the success.  Print is used to print to the terminal the command is run from
        current_app.logger.info(f"Downloaded NOTAM pdf, saved to {file_name}")
        print(f"Downloaded NOTAM pdf, saved to {file_name}")
    
    # If there is an error log it and exit
    except IOError:
        current_app.logger.error(f"Downloading NOTAM pdf from {caa_notam_url}: {res.status_code} - {res.reason}")
        print(f"Downloading NOTAM pdf from {caa_notam_url}: {res.status_code} - {res.reason}")
        sys.exit()


def check_zamzar_api(api_key, check_url):
    """Checks connection can be made to the zamzar API 
    
    Parameters
    ----------
    api_key : str
        API Key
    check_url : str
        API endpoint URL
    
    Returns
    -------
    JSON 
        Server response
    """
    
    endpoint = check_url
    
    res = requests.get(endpoint, auth=HTTPBasicAuth(api_key, ''))
    current_app.logger.info(res.json())
    print(res.json())


def upload_zamzar_conv_file(api_key, upload_url, source_file, target_format='txt'):
    """Uploads the file to convert to zamzar.  
    Zamzar will start to convert the file from one format to another, and return the ID of the conversion job.
    We then need to check back to see the status of the conversion and once done download the converted file.
    The ID is needed for this
    
    Parameters
    ----------
    api_key : str
        API Key
    upload_url : str
        API endpoint URL to upload file to
    source_file : str
        filename of the file to be uploaded
    target_format : str, default='txt'
        The format the file is to be converted to
    
    Returns
    -------
    str 
        ID of the file conversion Job
    """

    endpoint = upload_url
    
    # Upload the PDF file for conversion to txt
    file_content = {'source_file': open(source_file, 'rb')}
    data_content = {'target_format': target_format}
    res = requests.post(endpoint, data=data_content, files=file_content, auth=HTTPBasicAuth(api_key, ''))
    
    # Expect result to be 201
    if res.status_code != 201:
        current_app.logger.error(f'Failed to upload {source_file}: {res.status_code} - {res.reason}')
        return -1
    
    # Log the result
    current_app.logger.info(f'Upload Succeeded: {res.json()}')
    current_app.logger.info(f'Credits Remaining: {res.headers["Zamzar-Credits-Remaining"]}')

    # Return the Job ID
    return res.json()['id']


def check_zamzar_conv_status(api_key, status_url, job_id):
    """Checks the status of the conversion job
    
    Parameters
    ----------
    api_key : str
        API Key
    status_url : str
        API endpoint URL to check status
    job_id : str
        ID of the conversion Job
    
    Returns
    -------
    str 
        ID of file to download; 0 if job not ready
    """

    # Add the Job ID into the URL
    endpoint = status_url.format(job_id)
    
    # Check the job status
    res = requests.get(endpoint, auth=HTTPBasicAuth(api_key, ''))
    
    current_app.logger.info(f"Checking job status - status is {res.json()['status']}")
    
    # If status is not successful, could still be in progress.  Log it, return "0" as indicator need to retry
    if res.json()['status'] != 'successful':
        current_app.logger.info(res.json())
        return 0
    else:
        # Job succeeded - return the file_id so we can retrieve it
        return res.json()['target_files'][0]['id'] 


def download_zamzar_conv_file(api_key, download_url, local_filename, file_id):
    """Downloads the converted file from zamzar
    
    Parameters
    ----------
    api_key : str
        API Key
    download_url : str
        API endpoint URL to download file from
    local_filename : str
        where to store the file locally
    file_id : str
        ID of the file to download
    
    Returns
    -------
    str 
        ID of file to download; 0 if job not ready
    """

    # Add the File ID into the URL
    endpoint = download_url.format(file_id)
    
    # Send request to server
    res = requests.get(endpoint, stream=True, auth=HTTPBasicAuth(api_key, ''))
    
    # Download the converted file
    try:
        with open(local_filename, 'wb') as f:
            for chunk in res.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
    
        current_app.logger.info(f"Downloaded converted txt to {local_filename}")
        print(f"Downloaded converted txt to {local_filename}")
    
    except IOError:
        current_app.logger.info(f"Error downloading converted txt to {local_filename} - {res.status_code} - {res.reason}")
        print(f"Error downloading converted txt to {local_filename} - {res.status_code} - {res.reason}")



def import_notam_ZA(overwrite_existing_file=False):
    """Manages the import of a NOTAM - this would typically be called
    from the command line using "flask import-notams"

    The function does the following:
    - Downloads PDF from CAA website
    - Converts to text
    - Parses the NOTAMs, creating Notam objects
    - Saves Notams and Briefing to the DB
    
    Parameters
    ----------
    overwrite_existing_file : bool, default = False
        If the PDF File already exists, do we overwrite it?
    
    Returns
    -------
    Briefing 
        A Briefing object containing the briefing and downloaded Notams
    """

    # Read settings from INI file
    settings = read_settings_ZA()
    # Set the date suffix for file names
    file_date = datetime.strftime(datetime.utcnow(),'%Y-%m-%d')
    
    
    # Build the filenames for the PDF download file and the converted text file
    pdf_file_name = os.path.join(current_app.config['WORKING_FOLDER'], f'ZA_{settings["file_name_base"]}_{file_date}.pdf')
    txt_file_name = os.path.join(current_app.config['WORKING_FOLDER'], f'ZA_{settings["file_name_base"]}_{file_date}.txt')

    
    # First, does the text import file already exist?  It may have already been imported
    if os.path.isfile(txt_file_name) == True:
        # If user has specified we must overwrite, then delete and re-import.  May be needed if errors occur
        if overwrite_existing_file == True:
            current_app.logger.warning(f'Text File already exists, deleting - {txt_file_name}')
            print(f'Text File already exists, deleting - {txt_file_name}')
            
            # Delete existing text file
            os.remove(txt_file_name)

            # Delete the existing PDF file
            if os.path.isfile(pdf_file_name) == True:
                current_app.logger.warning(f'PDF File already exists, deleting - {pdf_file_name}')
                print(f'PDF File already exists, deleting - {pdf_file_name}')
                os.remove(pdf_file_name)

        # Otherwise log and error and terminate
        else:
            current_app.logger.error(f'Text File already exists, import aborted - {txt_file_name}')
            print(f'Text File already exists, import aborted - {txt_file_name}')
            #sys.exit()
            return None

    # Download the Notam File from the CAA website
    download_notam_file_ZA(settings['caa_notam_url'], pdf_file_name)
    
    # Upload the PDF file for conversion
    jobid = upload_zamzar_conv_file(settings['api_key'], settings['upload_url'], pdf_file_name)
    
    fileid = 0
    retry_count = 0

    # Check the status of the conversion job, allowing for up to 5 retries at intervals
    while fileid == 0 and retry_count < 5:
        fileid = check_zamzar_conv_status(settings['api_key'], settings['status_url'], jobid)

        # FileID of 0 means job not yet successful
        if fileid == 0: 
            retry_count += 1
            print(f"file not ready - retrying.  Retry count {retry_count}")
            current_app.logger.info(f"file not ready - retrying.  Retry count {retry_count}")
            time.sleep(5) #Give it 5 secs to process the file

    # If after 5 retries, still no FileID then there must be a problem
    if fileid == 0:
        current_app.logger.error(f"Conversions Job did not complete in {retry_count} attempts")
        print(f"Conversions Job did not complete in {retry_count} attempts.  Terminating")
        #sys.exit()
        return None

    # Otherwise download the converted file    
    else:
        download_zamzar_conv_file(settings['api_key'], settings['download_url'], txt_file_name, fileid)

    
    #Files are converted - Parse the notam text file, returning a Briefing Object
    brf = parse_notam_text_file(txt_file_name, 'ZA')

    if brf is None: return None
    
    # Create a SQL Alchemy session 
    sess = sqa_session()
    
    # Check the briefing doesn't already exist
    rs = sess.query(Briefing).filter(and_(Briefing.Briefing_Ref == brf.Briefing_Ref, Briefing.Briefing_Country == brf.Briefing_Country))

    # If it exists, log an error and exit.
    if rs.count() > 0:
        current_app.logger.error(f'This Briefing already exists in the database: Briefing Ref = {brf.Briefing_Ref}')
        print(f'This Briefing already exists in the database: Briefing Ref = {brf.Briefing_Ref}')

        # Delete the files
        os.remove(pdf_file_name)
        os.remove(txt_file_name)

        return None
    
    
    # Write the briefing and attached NOTAMS to the DB
    sess.add(brf)
    sess.commit()
    
    # Log the success
    current_app.logger.info(f'Database Import Completed - written {len(brf.Notams)} NOTAMS')
    print(f'Database Import Completed - written {len(brf.Notams)} NOTAMS')
    
    # Copy the files to the archive
    shutil.copy(pdf_file_name, current_app.config['NOTAM_ARCHIVE_FOLDER'])
    shutil.copy(txt_file_name, current_app.config['NOTAM_ARCHIVE_FOLDER'])

    # Delete the originals
    os.remove(pdf_file_name)
    os.remove(txt_file_name)
    
    return brf


@click.command('import-notams')
@with_appcontext
def import_notams_command():
    """Command Line to Import NOTAMS from CAA website, convert, and import into the database
    usage: flask import-notams
    """ 
    click.echo("--- Command Line ready to import NOTAMS ---")
    brf = import_notam_ZA(overwrite_existing_file=True)
    if brf is None:
        click.echo(f"***Briefing import failed - check log files***")
    else:
        click.echo(f"Imported {len(brf.Notams)} NOTAMS from briefing {brf.Briefing_Ref} dated {brf.Briefing_Date}")
    
    click.echo("--- Command-Line Completed ---")


@click.command('import-notam-text-file')
@click.argument('filename')
@with_appcontext
def import_notam_text_command(filename):
    """Import a NOTAM briefing from a specific text file - used to catch-up on past/failed notams
    usage: flask import-notam-text-file <filename>
    
    Parameters
    ----------
    filename : str
        filename and path to the Notam Text file
    """
    click.echo(f'--- Command Line ready to import NOTAM text file: {filename} ---')
    
    # Parse the notam text file, returning a Briefing Object
    brf = parse_notam_text_file(filename, 'ZA')
    if brf is None: return None

    sess = sqa_session()
    
    # Check the Briefing doesn't already exist
    rs = sess.query(Briefing).filter(and_(Briefing.Briefing_Ref == brf.Briefing_Ref, Briefing.Briefing_Country == brf.Briefing_Country))
    if rs.count() > 0:
        click.echo(f'This Briefing already exists in the database: Briefing Ref = {brf.Briefing_Ref}')
        return -1
    
    # Write the briefing and attached NOTAMS to teh DB
    sess.add(brf)
    sess.commit()
    
    click.echo(f'Database Import Completed - written {len(brf.Notams)} NOTAMS')
    click.echo("--- Command-Line Completed ---")


def init_app(app):
    """
    Register the Command-Line commands with the flightbriefing app
    """
    app.cli.add_command(import_notams_command)
    app.cli.add_command(import_notam_text_command)
