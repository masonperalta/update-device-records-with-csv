#!/usr/bin/env python3
import os
import requests
import sys
import base64
import json
import time
import datetime
import logging
from pathlib import Path
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
load_dotenv()


def init_vars():
    # initialize the environmental variables for this session
    jss_url = os.environ.get("JSS")
    jss_api_user = os.environ.get("JSSUSER")
    jss_api_pw = os.environ.get("JSSPASS")
    eaname = os.environ.get("EANAME")
    server_type = os.environ.get("SERVERTYPE")
    home = str(Path.home())
    if server_type == "windows":
        output_main_path = f"{home}\\JamfAPI-Update-MobileDevices\\"
        output_log_folder_path = f"{output_main_path}\\Logs\\"
        csv_file_path = f"{output_main_path}\\serial_numbers.csv"
    else:
        output_main_path = f"{home}/JamfAPI-Update-MobileDevices/"
        output_log_folder_path = f"{output_main_path}/Logs/"
        csv_file_path = f"{output_main_path}/serial_numbers.csv"
    logging_level = "debug"
    return jss_url, jss_api_user, jss_api_pw, eaname, output_main_path, output_log_folder_path, csv_file_path, logging_level


def generate_auth_token():
    # generate api token
    global api_token_valid_start_epoch
    global api_token

    credentials = api_user + ":" + api_pw
    credentials_bytes = credentials.encode('ascii')
    base64_bytes = base64.b64encode(credentials_bytes)
    encoded_credentials = base64_bytes.decode('ascii')
    # api call details
    jss_token_url = jss + "/api/v1/auth/token"
    payload = {}

    headers = {
        'Authorization': 'Basic ' + encoded_credentials
    }

    response = requests.request("POST", jss_token_url, headers=headers, data=payload)
    check_response_code(str(response), jss_token_url)
    # parse the json from the request
    response_data_dict = json.loads(response.text)
    # assign variable as global to be used in other functions
    api_token = response_data_dict['token']
    # Token is valid for 30 minutes. Setting timestamp to check for renewal
    api_token_valid_start_epoch = int(time.time())

    return api_token


def check_token_expiration_time():
    """api_token_valid_start_epoch is created globally when token is generated and api_token_valid_check_epoch is created locally to generate
    api_token_valid_duration_seconds which determines how long the token has been active"""
    api_token_valid_check_epoch = int(time.time())
    api_token_valid_duration_seconds = api_token_valid_check_epoch - api_token_valid_start_epoch
    # Renew token if necessary
    if api_token_valid_duration_seconds >= 1500:
        logging.info(f"UPDATE: API auth token is {api_token_valid_duration_seconds} seconds old. Token will now be renewed to continue API access.....")
        generate_auth_token()


def check_response_code(response_code: str, api_call: str):
    response_code = str(response_code)
    response_code = response_code[11:14]
    if response_code != "200" and response_code != "201":
        logging.error(f"response returned for {api_call} [{response_code}]")
        print(f"ERROR: response returned [{response_code}]")

        if response_code == "404" and "/JSSResource/mobiledevices/serialnumber/" in api_call:
            logging.error(f"ERROR: 404 returned for object record. Continuing......")
            print(f"ERROR: no Jamf object at {api_call} [continuing]")
            return "404_continue"
        else:
            sys.exit(1)
    # else:
        # logging.debug(f"http response for {api_call} [{response_code}]")
        

def now_date_time():
    now = str(datetime.datetime.now())
    # splits string into a list with 2 entries
    now = now.split(".", 1)
    # assign index 0 of the new list (as a string) to now
    now_formatted = str(now[0])

    char_to_replace = {':': '', ' ': '-'}
    # Iterate over all key-value pairs in dictionary
    for key, value in char_to_replace.items():
        # Replace key character with value character in string
        now_formatted = now_formatted.replace(key, value)

    return now_formatted


def script_duration(start_or_stop, number_of_devices_updated, number_of_update_errors):
    # this function calculates script duration
    days = 0; hours = 0; mins = 0; secs = 0
    global start_script_epoch

    if start_or_stop == "start":
        print("[SCRIPT START]")
        start_script_epoch = int(time.time())  # converting to int for simplicity
    else:
        stop_script_epoch = int(time.time())
        script_duration_in_seconds = stop_script_epoch - start_script_epoch

        if script_duration_in_seconds > 59:
            secs = int(script_duration_in_seconds % 60)
            script_duration_in_seconds = int(script_duration_in_seconds / 60)

            if script_duration_in_seconds > 59:
                mins = int(script_duration_in_seconds % 60)
                script_duration_in_seconds = script_duration_in_seconds / 60

                if script_duration_in_seconds > 23:
                    hours = int(script_duration_in_seconds % 24)
                    days = int(script_duration_in_seconds / 24)
                else:
                    hours = int(script_duration_in_seconds)
            else:
                mins = int(script_duration_in_seconds)
        else:
            secs = int(script_duration_in_seconds)

        logging.info(f"\n\n\n---------------\nSUCCESS: script completed! Mobile device records updated [{number_of_devices_updated}]\nERRORS: [{number_of_update_errors}]")
        logging.info(f"SCRIPT DURATION: {days} day(s) {hours} hour(s) {mins} minute(s) {secs} second(s)")
        print("[SCRIPT COMPLETE!]")


def create_script_directory(days_ago_to_delete_logs):
    # Check whether the specified path exists or not
    path_exists = os.path.exists(log_folder_path)

    if not path_exists:
        # Create a new directory because it does not exist
        os.makedirs(log_folder_path)
        configure_logging(now_formatted, log_level)
        logging.info(f"[CREATED] new directory {log_folder_path} created!")
        # write_to_logfile(f"CREATE: new directory {log_folder_path} created!", now_formatted, "debug")
    else:
        configure_logging(now_formatted, log_level)
        logging.info(f"The directory {log_folder_path} already exists")
        # write_to_logfile(f"INFO: the directory {log_folder_path} already exists", now_formatted, "debug")

        x_days_ago = time.time() - (days_ago_to_delete_logs * 86400)
        logging.info(f"Deleting log files older than {days_ago_to_delete_logs} days")
        # write_to_logfile(f"DELETE: deleting log files older than {days_ago_to_delete_logs} days", now_formatted, "debug")

        for i in os.listdir(log_folder_path):
            path = os.path.join(log_folder_path, i)

            if os.stat(path).st_mtime <= x_days_ago and os.path.isfile(path):
                os.remove(path)
                logging.info(f"[DELETE] {path}")
                # write_to_logfile(f"DELETE: [{path}]", now_formatted, "std")


def update_device_record(all_serial_numbers):
    """First determine the mobile_device_ID by using Classic API to return XML of deviced based on serial number
    Second, use API patch call to update record"""
    device_update_count = 0
    update_error_count = 0
    for sn in all_serial_numbers:
        logging.info(f"finding device record for {sn}")
        api_url = f"{jss}/JSSResource/mobiledevices/serialnumber/{sn}"
        payload = {}
        headers = {
            'accept': 'application/xml',
            'Authorization': 'Bearer ' + api_token
        }
        response = requests.request("GET", api_url, headers=headers, data=payload)
        # check_response_code will also handle if an object has been deleted in Jamf Pro after the script starts
        # or if the serial number entered is incorrect
        # we'll use the "404_continue" string to identify the scenario and bypass the rest of the function
        response_validation = check_response_code(str(response), api_url)
        if response_validation == "404_continue":
            # use "continue" here to return to the top of the loop when an incorrect serial number is encountered
            logging.error(f"no Jamf object found for device with serial number [{sn}]")
            update_error_count += 1
            continue

        # parse mobile device info to get mobile device ID
        root = ET.fromstring(response.content)
        for a in root.findall('.//general'):
            mobile_device_id = getattr(a.find('id'), 'text', None)

        data = all_serial_numbers[sn]
        asset_tag = data[0]
        ea = data[1]

        """Now, make PATCH API call to update the device record"""
        logging.info(f"updating device record for {sn} with ID: {mobile_device_id} [asset tag: {asset_tag}]")
        api_url = f"{jss}/api/v2/mobile-devices/{mobile_device_id}"
        payload = {
                    "updatedExtensionAttributes": [
                        {
                            "value": [
                                ea
                            ],
                            "name": ea_name,
                            "type": "STRING"
                        }
                    ],
                    "assetTag": asset_tag
                }
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json; charset=utf-8',
            'Authorization': 'Bearer ' + api_token
        }
        response = requests.patch(api_url, json=payload, headers=headers)
        check_response_code(str(response), api_url)
        check_token_expiration_time()
        requests.request("GET", api_url, headers=headers, data=payload)
        device_update_count += 1
    return device_update_count, update_error_count


def configure_logging(timestamp, debug_or_std):
    if debug_or_std == "std":
        logging.basicConfig(filename=log_folder_path + "/JamfAPI-Update-MobileDevices-" + timestamp + ".log", filemode='a+', level=logging.INFO)
    else:
        logging.basicConfig(filename=log_folder_path + "/JamfAPI-Update-MobileDevices-" + timestamp + ".log", filemode='a+', level=logging.DEBUG)


def convert_csv_to_dictionary(path_to_csv):
    all_data_from_csv = {}
    with open(path_to_csv, "r", encoding='utf-8') as csv_dict:
        for row in csv_dict:
            csv_dict_without_line_breaks = row.rstrip('\n')
            split_line = csv_dict_without_line_breaks.split(", ")
            sn = split_line[0]
            atag = split_line[1]
            ea = split_line[2]
            row_to_append = {sn: [atag, ea]}
            all_data_from_csv.update(row_to_append)
            # all_data_from_csv[]
    print(all_data_from_csv)
    csv_dict.close()
    return all_data_from_csv


if __name__ == "__main__":
    script_duration("start", 0, 0)
    now_formatted = now_date_time()
    jss, api_user, api_pw, ea_name, main_path, log_folder_path, csv_path, log_level = init_vars()
    create_script_directory(14)
    api_token = generate_auth_token()
    serial_number_asset_tag_dict = convert_csv_to_dictionary(csv_path)
    devices_updated_count, device_update_error_count = update_device_record(serial_number_asset_tag_dict)
    script_duration("stop", devices_updated_count, device_update_error_count)
