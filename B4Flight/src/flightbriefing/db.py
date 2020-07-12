'''
Created on 23 Jun 2020

@author: aretallack
'''

from datetime import datetime, timedelta

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Float, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.hybrid import hybrid_property

from werkzeug.security import check_password_hash, generate_password_hash
import jwt

from flask import current_app
from flightbriefing.data_handling import sqa_session

#SQLAlchemny - A declarative base class  
Base = declarative_base() 

class User(Base):
    __tablename__ = 'Users'
    UserID = Column(Integer(), primary_key = True)
    Username = Column(String(50), nullable=False, unique=True)
    _password = Column("Password", String(50), nullable=False)
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
            id = jwt.decode(activation_token, current_app.config['SECRET_KEY'], 'HS256')['activate_user']
        except:
            return 

        sqa_sess = sqa_session()
        usr = sqa_sess.query(User).get(id)
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


    
def init_db(sqa_engine):
    #The declarative Base is bound to the database engine.
    Base.metadata.bind = sqa_engine

def create_new_db():

    print('----------Initialising Database for Initial Use----------')

    #Create defined tables
    Base.metadata.create_all()

    print('----------Created Data Tables----------')


def create_admin_user(admin_email, admin_user='b4admin', admin_pass='b4admin'):

    Session = sessionmaker(bind=Base.metadata.bind)
    ses = Session()
    
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
