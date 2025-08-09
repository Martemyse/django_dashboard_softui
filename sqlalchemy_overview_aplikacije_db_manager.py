# -*- coding: utf-8 -*-
"""
Utility for initializing a demo database. Values are environment-driven.
"""

# import collections
import os
import pandas as pd
from datetime import timedelta, date
from datetime import datetime
from dateutil.relativedelta import relativedelta
import numpy as np
import itertools
import glob
import re
from collections import Counter
import time
import functools
from calendar import monthrange
import locale
import json
import io
import base64
import flask
import random
import textwrap
import requests
from requests.auth import HTTPBasicAuth
from sqlalchemy import create_engine, MetaData, text, between, and_, union_all
# from dash_extensions.enrich import DashProxy
from flask import send_from_directory
from flask import request, jsonify
import logging
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from sqlalchemy.exc import SQLAlchemyError
import uuid

#%%
from sqlalchemy import create_engine, text, update
from sqlalchemy.exc import ProgrammingError
import os

def terminate_database_sessions(engine, database_name):
    # Terminate all active connections to the database
    with engine.connect() as conn:
        conn.execute(text(f"""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{database_name}'
          AND pid <> pg_backend_pid();
        """))
        print(f"All active sessions for database {database_name} have been terminated.")

def drop_and_create_database(database_url, database_name):
    # Connect to the default 'postgres' database to issue the drop and create database commands
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        conn.execute(text("COMMIT"))  # Close any existing transaction
        
        # Terminate all active sessions to the target database
        terminate_database_sessions(engine, database_name)
        
        # Drop the database if it exists
        try:
            conn.execute(text(f"DROP DATABASE IF EXISTS {database_name}"))
            print(f"Database {database_name} dropped successfully.")
        except ProgrammingError as e:
            print(f"Error dropping database {database_name}: {e}")
        
        # Create the database
        # try:
        #     conn.execute(text(f"CREATE DATABASE {database_name}"))
        #     print(f"Database {database_name} created successfully.")
        # except ProgrammingError as e:
        #     if 'already exists' in str(e):
        #         print(f"Database {database_name} already exists.")
        #     else:
        #         raise

# Usage
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/postgres')

if os.getenv('ALLOW_DB_DROP', '0') == '1':
    drop_and_create_database(DATABASE_URL, os.getenv('POSTGRES_DB', 'django_overview_aplikacije'))


#%%
debug = True
# Default users data

default_user_roles = [
 
]


role_group_mappings_data = [
            {'role_group': 'roles_default', 'app_role': 'admin', 'user_role_mapping': 'admin'},
            {'role_group': 'roles_default', 'app_role': 'supervisor', 'user_role_mapping': 'supervisor'},
            {'role_group': 'roles_default', 'app_role': 'basic', 'user_role_mapping': 'basic'},
            {'role_group': 'roles_sledenje_akcij', 'app_role': 'admin', 'user_role_mapping': 'admin'},
            {'role_group': 'roles_sledenje_akcij', 'app_role': 'supervisor', 'user_role_mapping': 'supervisor'},
            {'role_group': 'roles_sledenje_akcij', 'app_role': 'assigner', 'user_role_mapping': ''},
            {'role_group': 'roles_sledenje_akcij', 'app_role': 'assignee', 'user_role_mapping': 'basic'},
            {'role_group': 'roles_tehnicna_cistost', 'app_role': 'admin', 'user_role_mapping': 'admin'},
            {'role_group': 'roles_tehnicna_cistost', 'app_role': 'supervisor', 'user_role_mapping': 'supervisor'},
            {'role_group': 'roles_tehnicna_cistost', 'app_role': 'projektni_vodja', 'user_role_mapping': ''},
            {'role_group': 'roles_tehnicna_cistost', 'app_role': 'vodja_ekologija', 'user_role_mapping': ''},
            {'role_group': 'roles_tehnicna_cistost', 'app_role': 'tehnolog_cistosti', 'user_role_mapping': ''},
            {'role_group': 'roles_tehnicna_cistost', 'app_role': 'guest', 'user_role_mapping': 'basic'},
        ]
#%% DatabaseManager
# Database URL setup
DATABASE_URL = os.getenv('APP_DATABASE_URL', os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/django_overview_aplikacije'))
    
from sqlalchemy import create_engine, Column, String, Integer, ForeignKey, UniqueConstraint, Text, DateTime, Boolean
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, validates
from sqlalchemy.sql import func
from uuid import uuid4
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()

# Define ObratiOddelki table
class ObratiOddelki(Base):
    __tablename__ = 'obrati_oddelki'
    obrati_oddelki_id = Column(Integer, primary_key=True, autoincrement=True)
    obrat = Column(String(50), nullable=False)
    oddelek = Column(String(50), nullable=False)

    __table_args__ = (UniqueConstraint('obrat', 'oddelek', name='unique_obrat_oddelek'),)

# Define Users table
class Users(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    user_role = Column(String(50), nullable=False)
    obrat_oddelek_id = Column(Integer, ForeignKey('obrati_oddelki.obrati_oddelki_id'), nullable=True)
    is_active = Column(Boolean, default=True)
    is_staff = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)
    password = Column(String(128), default='!', nullable=False)

    # Relationship with ObratiOddelki
    obrat_oddelek = relationship("ObratiOddelki", backref="users_obrati_oddelki")

    # Establishes a relationship with UserAppRoles
    app_roles = relationship("UserAppRoles", back_populates="user", cascade="all, delete-orphan")


# Define RoleGroups table
class RoleGroups(Base):
    __tablename__ = 'role_groups'
    role_group_id = Column(Integer, primary_key=True, autoincrement=True)
    role_group = Column(String(255), unique=True, nullable=False)


# Define RoleGroupMappings table
class RoleGroupMappings(Base):
    __tablename__ = 'role_group_mappings'
    role_group_mapping_id = Column(Integer, primary_key=True, autoincrement=True)
    role_group_id = Column(Integer, ForeignKey('role_groups.role_group_id'), nullable=False)
    app_role = Column(String(50), nullable=False)
    user_role_mapping = Column(String(50), nullable=True)


# Define AplikacijeObratiOddelki table with role_group assignment
class AplikacijeObratiOddelki(Base):
    __tablename__ = 'aplikacije_obrati_oddelki'
    aplikacije_obrati_oddelki_id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(255), unique=True, nullable=False)
    aplikacija = Column(String(50), nullable=False)
    role_group_id = Column(Integer, ForeignKey('role_groups.role_group_id'), nullable=False)
    obrat_oddelek_id = Column(Integer, ForeignKey('obrati_oddelki.obrati_oddelki_id'), nullable=False)

    # Relationship with ObratiOddelki
    obrat_oddelek = relationship("ObratiOddelki", backref="aplikacije_obrati_oddelki")

    __table_args__ = (UniqueConstraint('url', 'obrat_oddelek_id', name='unique_url_obrat_oddelek'),)


# Define UserAppRoles table
class UserAppRoles(Base):
    __tablename__ = 'user_app_roles'
    user_app_roles_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), ForeignKey('users.username'))
    app_url_id = Column(Integer, ForeignKey('aplikacije_obrati_oddelki.aplikacije_obrati_oddelki_id'))
    app_url = Column(String(255), nullable=True)
    role_name = Column(String(50), nullable=False)

    # Defines the relationship back to Users
    user = relationship("Users", back_populates="app_roles")
    # Defines the relationship back to AplikacijeObratiOddelki
    app = relationship("AplikacijeObratiOddelki", back_populates="user_roles")

# Relationships
Users.app_roles = relationship("UserAppRoles", back_populates="user", cascade="all, delete-orphan")
AplikacijeObratiOddelki.user_roles = relationship("UserAppRoles", back_populates="app", cascade="all, delete-orphan")


# Define the DatabaseManager class
class DatabaseManager:
    def __init__(self, database_url):
        self.engine = create_engine(database_url, echo=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def setup_database(self, reinitialize=False):
        if reinitialize:
            # Drop all tables in the correct order to avoid foreign key issues
            with self.engine.connect() as connection:
                connection.execute(text("DROP TABLE IF EXISTS user_app_roles CASCADE"))
                connection.execute(text("DROP TABLE IF EXISTS stepper CASCADE"))
                connection.execute(text("DROP TABLE IF EXISTS task_step CASCADE"))
                connection.execute(text("DROP TABLE IF EXISTS action CASCADE"))
                connection.execute(text("DROP TABLE IF EXISTS users CASCADE"))
                connection.execute(text("DROP TABLE IF EXISTS obrati_oddelki CASCADE"))
                connection.execute(text("DROP TABLE IF EXISTS role_group_mappings CASCADE"))
                connection.execute(text("DROP TABLE IF EXISTS role_groups CASCADE"))

        Base.metadata.create_all(self.engine)

    def get_session(self):
        return self.SessionLocal()

    def populate_initial_data(self, session):
        # Add role groups
        role_groups_data = [
            {'role_group': 'roles_default'},
            {'role_group': 'roles_sledenje_akcij'},
            {'role_group': 'roles_tehnicna_cistost'},
        ]
        role_groups = [RoleGroups(**rg) for rg in role_groups_data]
        session.bulk_save_objects(role_groups)
        session.commit()
    
        # Create a mapping of role_group names to their corresponding IDs
        role_group_map = {rg.role_group: rg.role_group_id for rg in session.query(RoleGroups).all()}
    
        # Create a unique list of obrati and oddelki combinations
        obrati_oddelki_data = [
            {'obrat': user['obrat'], 'oddelek': user['oddelek']}
            for user in default_user_roles
        ]
    
        obrati_oddelki_data = obrati_oddelki_data + [
            {'obrat': 'Škofja Loka', 'oddelek': 'Obdelava'},
            {'obrat': 'Trata', 'oddelek': 'Razvoj'},
            {'obrat': 'Benkovac', 'oddelek': 'Ekologija'},
            {'obrat': 'Ohrid', 'oddelek': 'Ekologija'},
            {'obrat': 'Čakovec', 'oddelek': 'Ekologija'},
            {'obrat': 'LTH', 'oddelek': 'Ekologija'},
        ]
    
        # Remove duplicates
        obrati_oddelki_data = [dict(t) for t in {tuple(d.items()) for d in obrati_oddelki_data}]
    
        # Add unique combinations to ObratiOddelki
        obrati_oddelki = [ObratiOddelki(**obrat) for obrat in obrati_oddelki_data]
        session.bulk_save_objects(obrati_oddelki)
        session.commit()
    
        # Create a mapping of obrat/oddelek combinations to their IDs
        obrati_oddelki_map = {f"{oo.obrat}-{oo.oddelek}": oo.obrati_oddelki_id for oo in session.query(ObratiOddelki).all()}

    
        # Add applications and departments
        default_obrati_oddelki_data = [
            {'url': 'lj_aktivnosti/tehno_obd/pregled', 'obrat': 'Ljubljana', 'oddelek': 'Tehnologija obdelave', 'aplikacija': 'LTH Pregled aktivnosti', 'role_group_id': role_group_map['roles_sledenje_akcij']},
            {'url': 'lj_aktivnosti/obd/pregled', 'obrat': 'Ljubljana', 'oddelek': 'Obdelava', 'aplikacija': 'LTH Pregled aktivnosti', 'role_group_id': role_group_map['roles_sledenje_akcij']},
            {'url': 'lj_aktivnosti/var/pregled', 'obrat': 'Ljubljana', 'oddelek': 'Varnost', 'aplikacija': 'LTH Pregled aktivnosti', 'role_group_id': role_group_map['roles_sledenje_akcij']},
            {'url': 'lj_aktivnosti/liv/pregled', 'obrat': 'Ljubljana', 'oddelek': 'Livarna', 'aplikacija': 'LTH Pregled aktivnosti', 'role_group_id': role_group_map['roles_sledenje_akcij']},
            {'url': 'lj_aktivnosti/vzd/pregled', 'obrat': 'Ljubljana', 'oddelek': 'Vzdrževanje', 'aplikacija': 'LTH Pregled aktivnosti', 'role_group_id': role_group_map['roles_sledenje_akcij']},
            {'url': 'sl_aktivnosti/obd/pregled', 'obrat': 'Škofja Loka', 'oddelek': 'Obdelava', 'aplikacija': 'LTH Pregled aktivnosti', 'role_group_id': role_group_map['roles_sledenje_akcij']},
            {'url': 'tr_aktivnosti/razoj/pregled', 'obrat': 'Trata', 'oddelek': 'Razvoj', 'aplikacija': 'LTH Pregled aktivnosti', 'role_group_id': role_group_map['roles_sledenje_akcij']},
            {'url': 'lth_aktivnosti/lth/pregled', 'obrat': 'LTH', 'oddelek': 'LTH', 'aplikacija': 'LTH Pregled aktivnosti', 'role_group_id': role_group_map['roles_sledenje_akcij']},
            {'url': 'lj_tc/pregled', 'obrat': 'Ljubljana', 'oddelek': 'Ekologija', 'aplikacija': 'Tehnična čistost', 'role_group_id': role_group_map['roles_tehnicna_cistost']},
            {'url': 'sl_tc/pregled', 'obrat': 'Škofja Loka', 'oddelek': 'Ekologija', 'aplikacija': 'Tehnična čistost', 'role_group_id': role_group_map['roles_tehnicna_cistost']},
            {'url': 'be_tc/pregled', 'obrat': 'Benkovac', 'oddelek': 'Ekologija', 'aplikacija': 'Tehnična čistost', 'role_group_id': role_group_map['roles_tehnicna_cistost']},
            {'url': 'oh_tc/pregled', 'obrat': 'Ohrid', 'oddelek': 'Ekologija', 'aplikacija': 'Tehnična čistost', 'role_group_id': role_group_map['roles_tehnicna_cistost']},
            {'url': 'ck_tc/pregled', 'obrat': 'Čakovec', 'oddelek': 'Ekologija', 'aplikacija': 'Tehnična čistost', 'role_group_id': role_group_map['roles_tehnicna_cistost']},
            {'url': 'lj_ekologija/pregled', 'obrat': 'Ljubljana', 'oddelek': 'Ekologija', 'aplikacija': 'Sredstva & Energenti', 'role_group_id': role_group_map['roles_default']},
            {'url': 'sl_ekologija/pregled', 'obrat': 'Škofja Loka', 'oddelek': 'Ekologija', 'aplikacija': 'Sredstva & Energenti', 'role_group_id': role_group_map['roles_default']},
            {'url': 'be_ekologija/pregled', 'obrat': 'Benkovac', 'oddelek': 'Ekologija', 'aplikacija': 'Sredstva & Energenti', 'role_group_id': role_group_map['roles_default']},
            {'url': 'oh_ekologija/pregled', 'obrat': 'Ohrid', 'oddelek': 'Ekologija', 'aplikacija': 'Sredstva & Energenti', 'role_group_id': role_group_map['roles_default']},
            {'url': 'ck_ekologija/pregled', 'obrat': 'Čakovec', 'oddelek': 'Ekologija', 'aplikacija': 'Sredstva & Energenti', 'role_group_id': role_group_map['roles_default']},
            {'url': 'lth_ekologija/pregled', 'obrat': 'LTH', 'oddelek': 'Ekologija', 'aplikacija': 'Sredstva & Energenti', 'role_group_id': role_group_map['roles_default']},
        ]
    
        default_aplikacije_obrati_oddelki = [
            {
                'url': app_data['url'],
                'aplikacija': app_data['aplikacija'],
                'role_group_id': app_data['role_group_id'],
                'obrat_oddelek_id': obrati_oddelki_map[f"{app_data['obrat']}-{app_data['oddelek']}"]
            }
            for app_data in default_obrati_oddelki_data
        ]
    
        aplikacije_obrati_oddelki = [AplikacijeObratiOddelki(**app_data) for app_data in default_aplikacije_obrati_oddelki]
        session.bulk_save_objects(aplikacije_obrati_oddelki)
        session.commit()
    
        # Create a mapping of URLs to their corresponding IDs
        aplikacije_obrati_oddelki_map = {app.url: app.aplikacije_obrati_oddelki_id for app in session.query(AplikacijeObratiOddelki).all()}
    
        # Add role group mappings
        role_group_mappings_data = [
            {'role_group_id': role_group_map['roles_default'], 'app_role': 'admin', 'user_role_mapping': 'admin'},
            {'role_group_id': role_group_map['roles_default'], 'app_role': 'supervisor', 'user_role_mapping': 'supervisor'},
            {'role_group_id': role_group_map['roles_default'], 'app_role': 'basic', 'user_role_mapping': 'basic'},
            {'role_group_id': role_group_map['roles_sledenje_akcij'], 'app_role': 'admin', 'user_role_mapping': 'admin'},
            {'role_group_id': role_group_map['roles_sledenje_akcij'], 'app_role': 'supervisor', 'user_role_mapping': 'supervisor'},
            {'role_group_id': role_group_map['roles_sledenje_akcij'], 'app_role': 'assigner', 'user_role_mapping': ''},
            {'role_group_id': role_group_map['roles_sledenje_akcij'], 'app_role': 'assignee', 'user_role_mapping': 'basic'},
            {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'admin', 'user_role_mapping': 'admin'},
            {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'supervisor', 'user_role_mapping': 'supervisor'},
            {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'projektni_vodja', 'user_role_mapping': ''},
            {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'vodja_ekologija', 'user_role_mapping': ''},
            {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'tehnolog_cistosti', 'user_role_mapping': ''},
            {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'guest', 'user_role_mapping': 'basic'},
        ]
    
        role_group_mappings = [RoleGroupMappings(**rgm) for rgm in role_group_mappings_data]
        session.bulk_save_objects(role_group_mappings)
        session.commit()
    
        # Add default users
        default_users = []
        for user_data in default_user_roles:
            obrat_oddelek_key = f"{user_data['obrat']}-{user_data['oddelek']}"
            obrat_oddelek_id = obrati_oddelki_map.get(obrat_oddelek_key)
            
            if obrat_oddelek_id:
                user = Users(
                    username=user_data['username'],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    email=user_data['email'],
                    user_role=user_data['user_role'],
                    obrat_oddelek_id=obrat_oddelek_id,  # Assign obrat_oddelek_id from the map
                )
                default_users.append(user)
        
        session.bulk_save_objects(default_users)
        session.commit()


        # Automatically assign roles to users for each app
        default_user_app_roles = []
        if aplikacije_obrati_oddelki:  # Check if the aplikacije_obrati_oddelki list is not empty
            for user in default_users:
                if user.obrat_oddelek:  # Ensure that obrat_oddelek is not None
                    for app in aplikacije_obrati_oddelki:
                        if app.obrat_oddelek and user.obrat_oddelek:  # Ensure app.obrat_oddelek is not None
                            if user.obrat_oddelek.obrat == 'LTH' or user.obrat_oddelek.obrat == app.obrat_oddelek.obrat:
                                if user.obrat_oddelek.oddelek == 'LTH' or user.obrat_oddelek.oddelek == app.obrat_oddelek.oddelek:
                                    role_group_id = app.role_group_id
                                    mapped_role = session.query(RoleGroupMappings).filter_by(role_group_id=role_group_id, user_role_mapping=user.user_role).first()
                                    if mapped_role:
                                        default_user_app_roles.append(UserAppRoles(
                                            username=user.username,
                                            app_url_id=aplikacije_obrati_oddelki_map.get(app.url, None),  # Use get to avoid KeyError
                                            app_url=app.url,
                                            role_name=mapped_role.app_role))
                                    else:
                                        default_user_app_roles.append(UserAppRoles(
                                            username=user.username,
                                            app_url_id=aplikacije_obrati_oddelki_map.get(app.url, None),  # Use get to avoid KeyError
                                            app_url=app.url,
                                            role_name='basic'))
                                else:
                                    # Assign 'basic' role if oddelek does not match
                                    default_user_app_roles.append(UserAppRoles(
                                        username=user.username,
                                        app_url_id=aplikacije_obrati_oddelki_map.get(app.url, None),  # Use get to avoid KeyError
                                        app_url=app.url,
                                        role_name='basic'))
                            else:
                                # Assign 'basic' role if obrat does not match
                                default_user_app_roles.append(UserAppRoles(
                                    username=user.username,
                                    app_url_id=aplikacije_obrati_oddelki_map.get(app.url, None),  # Use get to avoid KeyError
                                    app_url=app.url,
                                    role_name='basic'))
                        else:
                            print(f"App '{app}' or user.obrat_oddelek is None, skipping assignment for user '{user.username}'")
                else:
                    # Assign 'basic' role if user.obrat_oddelek is None
                    default_user_app_roles.append(UserAppRoles(
                        username=user.username,
                        app_url_id=None,  # Set None explicitly if obrat_oddelek is None
                        app_url=None,
                        role_name='basic'))
        
            session.bulk_save_objects(default_user_app_roles)
            session.commit()
        else:
            print("No applications found in 'aplikacije_obrati_oddelki'. Skipping role assignment.")



    
        # Update the user_app_roles with the correct mapped roles
        subquery = (
            session.query(UserAppRoles.username, UserAppRoles.app_url_id, RoleGroupMappings.app_role)
            .join(AplikacijeObratiOddelki, UserAppRoles.app_url_id == AplikacijeObratiOddelki.aplikacije_obrati_oddelki_id)
            .join(RoleGroupMappings, and_(
                RoleGroupMappings.role_group_id == AplikacijeObratiOddelki.role_group_id,
                RoleGroupMappings.user_role_mapping == UserAppRoles.role_name
            ))
            .subquery()
        )
    
        session.execute(
            update(UserAppRoles)
            .values(role_name=subquery.c.app_role)
            .where(and_(
                UserAppRoles.username == subquery.c.username,
                UserAppRoles.app_url_id == subquery.c.app_url_id
            ))
        )
        session.commit()


# Initialize the DatabaseManager
db_manager = DatabaseManager(DATABASE_URL)

# Reinitialize the database and populate with data
db_manager.setup_database(reinitialize=True)

# Create a session and populate initial data
session = db_manager.get_session()
db_manager.populate_initial_data(session)
session.close()
#%%
engine = create_engine(DATABASE_URL)
# Assuming you already have your engine and Base defined
Session = sessionmaker(bind=engine)
session = Session()

# Query all entries from Users table
users_df = pd.read_sql(session.query(Users).statement, session.bind)
# print(users_df)

# Query all entries from AplikacijeObratiOddelki table
obrati_oddelki_df = pd.read_sql(session.query(AplikacijeObratiOddelki).statement, session.bind)
# print(obrati_oddelki_df)

# Query all entries from UserAppRoles table
user_app_roles_df = pd.read_sql(session.query(UserAppRoles).statement, session.bind)
# print(user_app_roles_df)

# Query all entries from TaskStep table
role_groups_df = pd.read_sql(session.query(RoleGroups).statement, session.bind)
# print(role_groups_df)

# Query all entries from Action table
role_group_mappings_df = pd.read_sql(session.query(RoleGroupMappings).statement, session.bind)

obrat_oddelk_df = pd.read_sql(session.query(ObratiOddelki).statement, session.bind)
# print(role_group_mappings_df)
session.close()

