'''
Created on 11 Jun 2020

@author: aretallack
'''
import requests
from requests.auth import HTTPBasicAuth
import logging
from datetime import datetime
import time
import os
import shutil
import sys


from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker

from flightbriefing import helpers
from flightbriefing import notams


def read_settings_ZA():
    import configparser
    settings = {}
    
    cfg = configparser.ConfigParser()
    cfg.read('flightbriefing.ini')
    settings['working_folder'] = cfg.get('application','working_folder')
    settings['archive_folder'] = cfg.get('notam_import_ZA', 'archive_folder')
    settings['file_name_base'] = cfg.get('notam_import_ZA', 'file_name_base')
    settings['api_key'] = cfg.get('notam_import_ZA', 'key')
    settings['caa_notam_url'] = cfg.get('notam_import_ZA', 'caa_notam_url')
    settings['check_url'] = cfg.get('notam_import_ZA', 'convert_check_url')
    settings['upload_url'] = cfg.get('notam_import_ZA', 'convert_upload_url')
    settings['status_url'] = cfg.get('notam_import_ZA', 'convert_status_url')
    settings['download_url'] = cfg.get('notam_import_ZA', 'convert_download_url')
    settings['sql_script_folder'] = cfg.get('database', 'sql_script_folder')
    
    return settings


def download_notam_file_ZA(caa_notam_url, file_name):

    endpoint = caa_notam_url
    #Download the NOTAM Summary file from teh CAA website
    res = requests.get(endpoint, stream=True)

    #Save it to "file_name"
    try:
        with open(file_name, 'wb') as f:
            for chunk in res.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
    
        logging.info(f"Downloaded NOTAM pdf, saved to {file_name}")
        print(f"Downloaded NOTAM pdf, saved to {file_name}")
    
    except IOError:
        logging.error(f"Downloading NOTAM pdf from {endpoint}: {res.status_code} - {res.reason}")
        print(f"Error downloading NOTAM pdf from {endpoint}")
        sys.exit()



def check_api(api_key, check_url):
    
    endpoint = check_url
    
    res = requests.get(endpoint, auth=HTTPBasicAuth(api_key, ''))
    logging.info(res.json())
    print(res.json())


def upload_conv_file(api_key, upload_url, source_file):

    endpoint = upload_url
    target_format = "txt"
    
    #Upload the PDF file for conversion to txt
    file_content = {'source_file': open(source_file, 'rb')}
    data_content = {'target_format': target_format}
    res = requests.post(endpoint, data=data_content, files=file_content, auth=HTTPBasicAuth(api_key, ''))
    
    #Expect result to be 201
    if res.status_code != 201:
        logging.error(f'Failed to upload {source_file}: {res.status_code} - {res.reason}')
        return -1

    logging.info(f'Upload Succeeded: {res.json()}')
    logging.info(f'Credits Remaining: {res.headers["Zamzar-Credits-Remaining"]}')
    return res.json()['id']
    

def check_conv_status(api_key, status_url, job_id):

    #Add the Job ID into the URL
    endpoint = status_url.format(job_id)
    
    #Check the job status
    res = requests.get(endpoint, auth=HTTPBasicAuth(api_key, ''))
    
    logging.info(f"Checking job status - status is {res.json()['status']}")
    
    #If status is not successful, could still be in progress.  Log it, return "0" as indicator need to retry
    if res.json()['status'] != 'successful':
        logging.info(res.json())
        return 0
    else:
        #job succeeded - return the fil_id so we can retrieve it
        return res.json()['target_files'][0]['id'] 


def download_conv_file(api_key, download_url, local_filename, file_id):

    #Add the File ID into the URL
    endpoint = download_url.format(file_id)
    
    #Send request to server
    res = requests.get(endpoint, stream=True, auth=HTTPBasicAuth(api_key, ''))
    
    #Download the converted file
    try:
        with open(local_filename, 'wb') as f:
            for chunk in res.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
    
        logging.info(f"Downloaded converted txt to {local_filename}")
        print(f"Downloaded converted txt to {local_filename}")
    
    except IOError:
        logging.info(f"Downloaded converted txt to {local_filename} - {res.status_code} - {res.reason}")
        print(f"Downloaded converted txt to {local_filename}")



def create_notam_db():

    settings = read_settings_ZA()

    #Get database connection string
    db_connect = helpers.read_db_connect()
    #create SQLAlchemy engine
    sqa_engine = create_engine(db_connect)

    #initialise notams module with the engine
    notams.init_db(sqa_engine)
    #create the database structure
    notams.create_new_db(settings['sql_script_folder'])



def import_notam_ZA(sqa_engine=None, overwrite_existing=False):

    #Read settings from INI file
    settings = read_settings_ZA()
    #date suffix
    file_date = datetime.strftime(datetime.utcnow(),'%Y-%m-%d')
    
    #build the filenames for the PDF download file, and the converted text file
    pdf_file_name = os.path.join(settings['working_folder'], f'ZA_{settings["file_name_base"]}_{file_date}.pdf')
    txt_file_name = os.path.join(settings['working_folder'], f'ZA_{settings["file_name_base"]}_{file_date}.txt')

    #Check that the working folder and the archive folder exist - if not, create them
    if os.path.exists(settings['working_folder']) == False:
        os.mkdir(settings['working_folder'])

    if os.path.exists(settings['working_folder']) == False:
        os.mkdir(settings['working_folder'])
    
    #Setup the logging
    log_file = os.path.join(settings['archive_folder'], 'pdf_convert.log')
    logging.basicConfig(filename=log_file, level=logging.INFO, format='%(levelname)s - %(funcName)s - %(asctime)s - %(message)s')
    

    #First, does the import file already exist?  It may have already been imported
    if os.path.isfile(txt_file_name) == True:
        #If user has specified we must overwrite, then delete and re-import.  May be needed if errors occur, or if updated NOTAM released
        if overwrite_existing == True:
            logging.warning(f'Text File already exists, deleting - {txt_file_name}')
            print(f'Text File already exists, deleting - {txt_file_name}')
            os.remove(txt_file_name)
            if os.path.isfile(pdf_file_name) == True:
                logging.warning(f'PDF File already exists, deleting - {pdf_file_name}')
                print(f'PDF File already exists, deleting - {pdf_file_name}')
                os.remove(pdf_file_name)

        #Otherwise log and error and terminate
        else:
            logging.error(f'Text File already exists, import aborted - {txt_file_name}')
            print(f'Text File already exists, import aborted - {txt_file_name}')
            sys.exit()

    #Download the Notam File from the CAA website
    download_notam_file_ZA(settings['caa_notam_url'], pdf_file_name)
    
    #Upload the PDF file for conversion
    jobid = upload_conv_file(settings['api_key'], settings['upload_url'], pdf_file_name)
    
    fileid = 0
    retry_count = 0
    #Check the status of the conversion job, allowing for retries at intervals
    while fileid == 0 and retry_count < 5:
        fileid = check_conv_status(settings['api_key'], settings['status_url'], jobid)
        #FileID of 0 means job not yet successful
        if fileid == 0: 
            retry_count += 1
            print(f"file not ready - retrying.  Retry count {retry_count}")
            logging.info(f"file not ready - retrying.  Retry count {retry_count}")
            time.sleep(5) #Give it 5 secs to process the file

    #If after retries, still no FileID then there must be a problem
    if fileid == 0:
        logging.error(f"Conversions Job did not complete in {retry_count} attempts")
        print(f"Conversions Job did not complete in {retry_count} attempts.  Terminating")
        sys.exit()

    #Otherwise download the converted file    
    else:
        download_conv_file(settings['api_key'], settings['download_url'], txt_file_name, fileid)


    #------------------------
    #Now we parse the NOTAMS, and write to DB
    #------------------------
    if sqa_engine is None:
        #Get database connection string
        db_connect = helpers.read_db_connect()
        #create SQLAlchemy engine
        sqa_engine = create_engine(db_connect)

    #initialise sqlalchemy db
    notams.init_db(sqa_engine)
    
    #parse the notam text file, returning a Briefing Object
    brf = notams.parse_notam_text_file(txt_file_name, 'ZA')
    
    #Create a SQL Alchemy session 
    Session = sessionmaker(bind=sqa_engine)
    session = Session()
    
    rs = session.query(notams.Briefing).filter(and_(notams.Briefing.Briefing_Ref == brf.Briefing_Ref, notams.Briefing.Briefing_Country == brf.Briefing_Country))
    if rs.count() > 0:
        logging.error(f'This Briefing already exists in the database: Briefing Ref = {brf.Briefing_Ref}')
        print(f'This Briefing already exists in the database: Briefing Ref = {brf.Briefing_Ref}')

        #delete the files
        os.remove(pdf_file_name)
        os.remove(txt_file_name)

        session.close()
        sys.exit()
    
    
    #Write the briefing and attached NOTAMS to teh DB
    session.add(brf)
    session.commit()
    
    logging.info(f'Database Import Completed - written {len(brf.Notams)} NOTAMS')
    print(f'Database Import Completed - written {len(brf.Notams)} NOTAMS')
    
    session.close()
    
    #Copy the files to the archive
    shutil.copy(pdf_file_name, settings['archive_folder'])
    shutil.copy(txt_file_name, settings['archive_folder'])
    #delete the originals
    os.remove(pdf_file_name)
    os.remove(txt_file_name)


if __name__ == "__main__":
#    create_notam_db()
    import_notam_ZA(overwrite_existing=True)
