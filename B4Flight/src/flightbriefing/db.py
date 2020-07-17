'''
Created on 23 Jun 2020

@author: aretallack
'''

import os

from datetime import datetime, timedelta

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, Time, DateTime, Float, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.hybrid import hybrid_property

from polycircles import polycircles

import jwt
import csv


from werkzeug.security import generate_password_hash

import click
from flask import current_app
from flask.cli import with_appcontext

from .data_handling import sqa_session
from . import helpers

#SQLAlchemny - A declarative base class  
Base = declarative_base() 

class User(Base):
    __tablename__ = 'Users'
    UserID = Column(Integer(), primary_key = True)
    Username = Column(String(50), nullable=False, unique=True)
    _password = Column("Password", String(1024), nullable=False)
    Firstname = Column(String(75))
    Lastname = Column(String(75))
    Email = Column(String(75), nullable=False, unique=True)
    Status_Pending = Column(Boolean(), default=True)
    Status_Active = Column(Boolean(), default=False)
    Access_Admin = Column(Boolean(), default=False)
    Create_Date = Column(DateTime(), default=datetime.utcnow())
    Activation_Mail_Date = Column(DateTime())
    
    FlightPlans = relationship("FlightPlan")
    
    @hybrid_property
    def Password(self):
        return self._password
    
    @Password.setter
    def Password(self, Password):
        self._password = generate_password_hash(Password)

    def get_activation_token(self, expires_hrs=240):
        expry = datetime.utcnow() + timedelta(hours=expires_hrs)
        expry = datetime.strftime(expry,"%Y-%m-%d %H:%M:%S")
        tkn = jwt.encode({'activate_user' : self.UserID, 'expires': expry}, current_app.config['SECRET_KEY'], 'HS256').decode('utf-8')
        return tkn
        
    @staticmethod
    def activate_user(activation_token):
        try:
            usr_id = jwt.decode(activation_token, current_app.config['SECRET_KEY'], 'HS256')['activate_user']
        except:
            return 

        sqa_sess = sqa_session()
        usr = sqa_sess.query(User).get(usr_id)
        usr.Status_Pending = False
        usr.Status_Active = True
        sqa_sess.commit()
        return usr
        


class FlightPlan(Base):
    __tablename__ = 'FlightPlans'
    FlightplanID = Column(Integer(), primary_key=True)
    UserID = Column(Integer(), ForeignKey("Users.UserID"))
    Import_Date = Column(DateTime())
    File_Name = Column(String(255))
    Flight_Date = Column(Date())
    Flight_Name = Column(String(255))
    Flight_Desc = Column(String(255))
    
    User = relationship("User")
    FlightPlanPoints = relationship("FlightPlanPoint", back_populates="FlightPlan")
    
    @property
    def Import_Date_Text(self):
        return self.Import_Date.strftime("%Y-%m-%d")

class FlightPlanPoint(Base):
    __tablename__ = 'FlightPlanPoints'
    ID = Column(Integer(), primary_key=True)
    FlightplanID = Column(Integer(), ForeignKey("FlightPlans.FlightplanID"))
    Latitude = Column(Float())
    Longitude = Column(Float())
    Elevation = Column(Integer())
    Name = Column(String(255))
    
    FlightPlan = relationship("FlightPlan", back_populates="FlightPlanPoints")


class QCode_2_3_Lookup(Base):
    __tablename__ = "QCodes_2_3_Lookup"
    
    Code = Column(String(2), primary_key=True)
    Description = Column(String(512))
    Abbreviation = Column(String(50))
    Grouping = Column(String(50))
    Group_Colour = Column(String(50))
    
    Notams = relationship("Notam")


class QCode_4_5_Lookup(Base):
    __tablename__ = "QCodes_4_5_Lookup"
    
    Code = Column(String(2), primary_key=True)
    Description = Column(String(512))
    Abbreviation = Column(String(50))
    
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
    Raw_Text = Column(Text) #The raw NOTAM text - primarily for troubleshooting
    FIR = Column(String(4)) #ICAO FIR Notam applies to
    Q_Code_2_3 = Column(String(2), ForeignKey("QCodes_2_3_Lookup.Code")) #Q-code letters 2+3 from the Q) field in Notam
    Q_Code_4_5 = Column(String(2), ForeignKey("QCodes_4_5_Lookup.Code")) #Q-code letters 4+5 from the Q) field in Notam
    Flightrule_Code = Column(String(4)) #Flightrule - I/V/K or combination
    Purpose_Code = Column(String(4)) #ICAO code describing the purpose of NOTAM 
    Scope_Code = Column(String(3)) #Scope of NOTAM - A(erodrome) / E(n-route) / W(Nav Warning) / K(Checklist)
    Scope_Aerodrome = Column(Boolean) #Is scope for Aerodrome?
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
    Notam_Text = Column(Text) #Text of the Notam - E) section of Notam
    Duration = Column(String(256)) #Duration of Notam - D) section of Notam
    Level_Lower = Column(String(10)) #Lower Level for Notam - combines F) section and Q) section
    Level_Upper = Column(String(10)) #Upper Level for Notam - combines G) section, Q) section E) Secion (text)
    E_Coord_Lat = Column(String(7)) #Co-ordinates extracted from the E) section (text)
    E_Coord_Lon = Column(String(8)) #Co-ordinates extracted from the E) section (text)
    Coord_Lat = Column(String(8)) #Final co-ordinates to use for the Notam Mapping
    Coord_Lon = Column(String(8)) #Final co-ordinates to use for the Notam Mapping
    Bounded_Area = Column(String(4096)) # Co-ordinates of a bounded area defined in the Notam
    Unique_Geo_ID = Column(String(25)) #Combination of Lat + Lon + Radius to allow grouping of 
        
    Briefing = relationship("Briefing", back_populates='Notams')
    QCode_2_3_Lookup = relationship("QCode_2_3_Lookup")
    QCode_4_5_Lookup = relationship("QCode_4_5_Lookup")
    
    def is_circle(self):
        if self.Radius > 1 and self.Bounded_Area == '':
            return True
        else:
            return False

    def circle_bounded_area(self):
        
        radius_m = self.Radius * 1853 #convert radius from nautical miles to metres
        
        poly_coords = ''
        
        #create the circle
        polycircle = polycircles.Polycircle(latitude=helpers.convert_dms_to_dd(self.Coord_Lat), longitude=helpers.convert_dms_to_dd(self.Coord_Lon), radius=radius_m, number_of_vertices=20)
        circ_coords = polycircle.to_lat_lon()

        #convert circle's decimal degree lat,lon tuples into DMS and convert to string in same format as bounded area (i.e. LAT,LON LAT,LON)
        for coord in circ_coords:
            lat, lon = helpers.convert_dd_to_dms(coord[0], coord[1])
            poly_coords += f'{lat},{lon} '
            
        return poly_coords.strip()


    
def init_db(sqa_engine):
    #The declarative Base is bound to the database engine.
    Base.metadata.bind = sqa_engine

def create_new_db():

    sqa_engine = create_engine(current_app.config['DATABASE_CONNECT_STRING'], pool_recycle = current_app.config['DATABASE_POOL_RECYCLE'])

    #Create defined tables
    Base.metadata.bind = sqa_engine
    Base.metadata.create_all()


def import_ref_tables(csv_script_folder):

    ses = sqa_session()
    
    with open(os.path.join(csv_script_folder, 'Q_Code_2_3.csv')) as imp_file:
        csv_reader = csv.DictReader(imp_file)
        for row in csv_reader:
            ref = QCode_2_3_Lookup(Code = row['Code'], Description = row['Description'], 
                                   Abbreviation = row['Abbreviation'], Grouping = row['Grouping'], Group_Colour = row['Group_Colour'])
            ses.add(ref)
    print('Imported QCode Lookups: QCode_2_3_Lookup')

    with open(os.path.join(csv_script_folder, 'Q_Code_4_5.csv')) as imp_file:
        csv_reader = csv.DictReader(imp_file)
        for row in csv_reader:
            ref = QCode_4_5_Lookup(Code = row['Code'], Description = row['Description'], Abbreviation = row['Abbreviation'])
            ses.add(ref)
    
    print('Imported QCode Lookups: QCode_4_5_Lookup')

    ses.commit()
    print('----------Committed and Completed----------')


def create_admin_user(admin_email, admin_user='b4admin', admin_pass='b4admin'):

    ses = sqa_session()
    
    new_admin = User()
    new_admin.Username = admin_user
    new_admin.Password = admin_pass
    new_admin.Email = admin_email
    new_admin.Status_Active = True
    new_admin.Status_Pending = False
    new_admin.Access_Admin = True 
    new_admin

    ses.add(new_admin)
    ses.commit()

    print('----------Admin User Added----------')

@click.command('create-db')
@with_appcontext
def create_db_command():
    """Create the B4Flight Databases"""
    click.echo("Ready to create the core B4Flight databases")
    create_new_db()
    click.echo("Databases Created")
    
@click.command('import-lookups')
@click.argument('csv_folder')
@with_appcontext
def import_lookup_command(csv_folder):
    """Import the Q-Code lookup CSV Files.  Must be named Q_Code_2_3.csv and Q_Code_4_5.csv. Encoding UTF8"""
    click.echo("Ready to import lookup files")
    import_ref_tables(csv_folder)
    click.echo("Databases Created")

def init_app(app):
    app.cli.add_command(create_db_command)
    app.cli.add_command(import_lookup_command)
    
