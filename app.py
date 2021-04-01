""" Copyright (c) 2020 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
           https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied. 
"""

# Import Section
from flask import Flask, render_template, request, url_for, redirect, session
import backend
from time import ctime, sleep
from threading import Thread
from flask_sqlalchemy import SQLAlchemy


# Global Variables
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
db = SQLAlchemy(app)


class User(db.Model):
    """ Create user table"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(80))

    def __init__(self, username, password):
        self.username = username
        self.password = password


# Methods
def convert_voucher_list(voucher_list):
    '''
    This function will receive a voucher list with MAC addresses (in "the cisco way" format) 
    and expire timestamps (in seconds since the epoch, in UTC) and convert it 
    to MAC addresses (in the format xx:xx:xx:xx:xx:xx) and expire dates (as strings in local time).
    In: {"xxxx.xxxx.xxxx": 1613129301.6337228, "xxxx.xxxx.xxxx": 1613129332.6337228}
    Out:[{'MACAddress': 'xx:xx:xx:xx:xx:xx', 'ExpDate': 'Fri Feb 12 12:28:21 2021'},
        {'MACAddress': 'xx:xx:xx:xx:xx:xx', 'ExpDate': 'Fri Feb 12 18:28:21 2021'}]
    '''
    converted_voucher_list = []

    for key, value in voucher_list.items():

        dot_free_mac = key.replace('.', '')
        mac_address = ':'.join(dot_free_mac[i:i+2] for i in range(0, 12, 2))
        exp_date = ctime(value)
        converted_voucher_list.append(
            {"MACAddress": mac_address, "ExpDate": exp_date})

    return converted_voucher_list


def propagate_backend_exception(backend_response):
    '''
    This function checks the backend response for ERROR indictors to raise an frontend 
    exception and thereby display a customized error message in case of an backend error.
    '''
    if 'ERROR' in str(backend_response):
        raise Exception(str(backend_response))


def voucher_cleanup_loop():
    while True:
        backend.voucher_cleanup(backend.voucher_group_name)
        sleep(10*60)


# Routes
@app.route('/', methods=['GET', 'POST'])
def index():
    '''
    This function will show all NAD devices in a table (GET request) and
    redirect to the specific query page of a device (POST request). The redirection 
    can be manually triggered by a "Query Device" link in each table row and thereby 
    for each NAD device.
    '''
    try:
        if request.method == 'GET':

            device_list = backend.get_all_NADs()
            propagate_backend_exception(device_list)

            return render_template('deviceList.html', device_list=device_list)

        elif request.method == 'POST':

            ip_address = request.form.get("ip_address")
            relevant_sessions = backend.get_device_auth_sessions(ip_address)
            propagate_backend_exception(relevant_sessions)

            print(relevant_sessions)
            print(ip_address)

            return render_template('deviceQuery.html', post_request_done=True, ip_address=ip_address, relevant_sessions=relevant_sessions)

    except Exception as e:
        print(e)
        return render_template('deviceList.html', error=True, errorcode=e, reloadlink='/')


@app.route('/deviceQuery', methods=['GET', 'POST'])
def deviceQuery():
    '''
    This function shows an empty page with IP query field and button (GET) 
    or a list of queried devices with associated session information (POST).
    '''
    try:
        if request.method == 'GET':

            return render_template('deviceQuery.html', post_request_done=False, ip_address='', relevant_sessions={})

        elif request.method == 'POST':

            ip_address = request.form.get("ip_address")
            relevant_sessions = backend.get_device_auth_sessions(ip_address)
            propagate_backend_exception(relevant_sessions)

            return render_template('deviceQuery.html', post_request_done=True, ip_address=ip_address, relevant_sessions=relevant_sessions)

    except Exception as e:
        print(e)
        return render_template('deviceQuery.html', error=True, errorcode=e)


@app.route('/voucher', methods=['GET', 'POST'])
def voucher():

    if session.get('logged_in'):

        try:
            if request.method == 'GET':

                voucher_list = convert_voucher_list(
                    backend.read_voucher_json())
                propagate_backend_exception(voucher_list)

                return render_template('voucher.html', voucher_list=voucher_list, new_voucher=False)

            elif request.method == 'POST':

                submit_type = request.form.get("voucher_sumbit")
                row_mac_address = request.form.get("voucher_sumbit")
                form_mac_address = request.form.get("mac_address_field")
                voucher_duration = request.form.get("voucher_duration")

                if(submit_type == "Add"):

                    add_response = backend.add_voucher(
                        form_mac_address, int(voucher_duration))
                    propagate_backend_exception(add_response)
                    voucher_list = convert_voucher_list(
                        backend.read_voucher_json())
                    propagate_backend_exception(voucher_list)

                    return render_template('voucher.html', voucher_list=voucher_list, new_voucher=True)

                else:  # Revoke

                    revoke_response = backend.revoke_voucher(row_mac_address)
                    propagate_backend_exception(revoke_response)
                    voucher_list = convert_voucher_list(
                        backend.read_voucher_json())
                    propagate_backend_exception(voucher_list)

                    return render_template('voucher.html', voucher_list=voucher_list, deleted_voucher=True)
        except Exception as e:
            print(e)
            return render_template('voucher.html', error=True, errorcode=e)
        else:
            return redirect(url_for('login'))


@app.route('/endpointQuery', methods=['GET', 'POST'])
def endpointQuery():
    '''
    This function shows an empty page with MAC address query field and button (GET) 
    or a list of queried endpoint devices with associated auth status (POST).
    '''
    try:
        if request.method == 'GET':

            return render_template('endpointQuery.html', post_request_done=False, endpoint_list={}, mac_address='')

        elif request.method == 'POST':

            mac_address = request.form.get("mac_address")
            endpoint_list = backend.check_ise_auth_status(mac_address)
            propagate_backend_exception(endpoint_list)

            return render_template('endpointQuery.html', post_request_done=True, endpoint_list=endpoint_list, mac_address=mac_address)

    except Exception as e:
        print(e)
        return render_template('endpointQuery.html', error=True, errorcode=e)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login Form"""
    if request.method == 'GET':
        return render_template('login.html')
    else:
        name = request.form['username']
        passw = request.form['password']
        try:
            data = User.query.filter_by(username=name, password=passw).first()
            if data is not None:
                session['logged_in'] = True
                return redirect(url_for('index'))
            else:
                return 'Dont Login'
        except:
            return "Dont Login"


@app.route('/register/', methods=['GET', 'POST'])
def register():
    """Register Form"""
    if request.method == 'POST':
        new_user = User(
            username=request.form['username'],
            password=request.form['password'])
        db.session.add(new_user)
        db.session.commit()
        return render_template('login.html')
    return render_template('register.html')


@app.route("/logout")
def logout():
    """Logout Form"""
    session['logged_in'] = False
    return redirect(url_for('index'))


# Main Function
if __name__ == "__main__":
    t = Thread(target=voucher_cleanup_loop)
    t.start()
    app.run(host='0.0.0.0', debug=True, threaded=True)
