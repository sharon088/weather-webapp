# import the Flask library
from flask import Flask, abort,render_template, request,Response,jsonify
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter,generate_latest
from geopy.geocoders import Nominatim
from decimal import Decimal
import openmeteo_requests
import boto3
import os
import json
import logging
import ecs_logging
from botocore.exceptions import ClientError
from day import Day
import requests_cache
from datetime import datetime,timedelta
from retry_requests import retry



logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('/var/log/flask/logs.json')
handler.setFormatter(ecs_logging.StdlibFormatter())
logger.addHandler(handler)
app = Flask(__name__)
metrics = PrometheusMetrics(app)

# static information as metric
metrics.info('app_info', 'Application info', version='1.0.0')
location_counter = Counter('location_count',' Number of requests per location ',['location'])

BUCKET_NAME = 'sharon088staticweb.com'
IMAGE_KEY = 'sky.jpg'
HISTORY_DIR = 'history'

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_server_error(error):
    return render_template('500.html'), 500


def get_client(service_type):
    return client(
        service_type,
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

def convert_to_decimal(data):
    if isinstance(data, dict):
        return {k: convert_to_decimal(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_to_decimal(i) for i in data]
    elif isinstance(data, float):
        return Decimal(str(data))
    else:
        return data


@app.route('/download-image', methods=['GET'])
def download_image():
    logging.info("Download image request received")
    try:
        s3 = get_client('s3')
        file = s3.get_object(Bucket=BUCKET_NAME, Key=IMAGE_KEY)
        logging.info("Image successfully retrieved from S3")
        return Response(
            file['Body'].read(),
            headers={"Content-Disposition": "attachment;filename=sky.jpg"}
        )
    except Exception as e:
        logger.error(f"Error retrieving image from S3: {e}")
        abort(500)

    logger.info("Search history saved for {location_text}")

@app.route('/dynamo-db', methods=['POST'])
def dynamo_db():
    logging.info("DynamoDB data insertion request received")
    try:
        location = request.form.get('location')
        date = request.form.get('date')
        days_list_str = request.form.get('forecast_data')
        days_list = json.loads(days_list_str)
        days_list = convert_to_decimal(days_list)

        dynamodb = boto3.resource('dynamodb',
                   aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                   aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                   region_name='eu-central-1')
        table = dynamodb.Table('WeatherTbl')
        item = {
            'Location': location,
            'Date': date,
            'days_list': days_list
        }
        table.put_item(Item=item)
        logger.info("Data successfully saved to DynamoDB")
        return jsonify({"message": "Data saved successfully"}), 200
    except Exception as e:
        logger.error(f"Error saving data to DynamoDB: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/backup', methods=['GET'])
def backup_tel_aviv():
    logger.info("Backup request for Tel Aviv received")
    try:
        location_geocode = get_location_geocode("tel aviv israel")
        if location_geocode is None:
            logger.warning("Location not found for backup")
            return render_template('location.html', errorx="You choosed wrong location")

        response = get_response_meteo_api_wheater(location_geocode)
        if response is None:
            logger.warning("Weather data not found for backup")
            abort(404)

        hourly = response.Hourly()
        hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
        hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()
        hourly_is_day = hourly.Variables(2).ValuesAsNumpy()
        days_list = []
        parse_response(hourly_temperature_2m, hourly_relative_humidity_2m, hourly_is_day, days_list)
        days_list = convert_to_decimal(days_list)

        dynamodb = boto3.resource('dynamodb',
                   aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                   aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                   region_name='eu-central-1')
        table = dynamodb.Table('WeatherTbl')
        item = {
            'Location': "Tel-Aviv",
            'Date': str(datetime.today().date()),
            'days_list': days_list
        }
        table.put_item(Item=item)
        logger.info("Backup data successfully saved to DynamoDB")
        return render_template('location.html')
    except Exception as e:
        logger.error(f"Error during backup: {e}")
        return render_template('location.html', errorx="An error occurred during backup")

@app.route('/metrics')
def metrics():
    return generate_latest()

@app.route('/', methods=['GET'])
def get_set_request():
    logger.debug("Received GET request to root route")
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)

    
    bg_color = os.getenv('BG_COLOR', '#f0f0f0')
    location_text = request.args.get('location')
    if location_text is None or location_text == '':
        logger.info("No location provided, rendering location.html")
        return render_template('location.html')

    logger.info(f"Location provided: {location_text}")
    location_counter.labels(location=location_text).inc()

    location_geocode = get_location_geocode(location_text)
    if location_geocode is None:
        logger.warning(f"Location not found for: {location_text}")
        return render_template('location.html', errorx="You chose the wrong location")

    logger.info(f"Location geocode obtained: {location_geocode.address}")

    response = get_response_meteo_api_wheater(location_geocode)
    if response is None:
        app.logger.error(f"Weather data not found for location: {location_geocode.address}")
        abort(404)

    logger.debug(f"Weather data successfully retrieved for location: {location_geocode.address}")

    # Process hourly data. The order of variables needs to be the same as requested.
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
    hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()
    hourly_is_day = hourly.Variables(2).ValuesAsNumpy()
    days_list = []
    parse_response(hourly_temperature_2m, hourly_relative_humidity_2m, hourly_is_day, days_list)

    logger.info("Successfully processed hourly data and generated days_list")

    save_weather_data(location_text, days_list)
    history_files = os.listdir(HISTORY_DIR)
    # Pass the results to the HTML template
    return render_template('results.html',
        days_list=days_list,
        history_files=history_files,
        bg_color=bg_color,
        location=location_geocode.address)

def save_weather_data(location, days_list):
    file_path = os.path.join(HISTORY_DIR, f"{location}.json") 
    weather_data = {
        'location': location,
        'days': days_list
    }

    # Save the data to a JSON file
    with open(file_path, 'w') as json_file:
        json.dump(weather_data, json_file, indent=4)
    
    logger.info(f"Weather data saved to {file_path}")


def get_location_geocode(location_text):
    geolocator = Nominatim(user_agent="app.py")
    location_geocode = geolocator.geocode(location_text,language = "en")
    return location_geocode

def get_response_meteo_api_wheater(location_geocode):
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": location_geocode.latitude,
            "longitude": location_geocode.longitude,
            "hourly": ["temperature_2m", "relative_humidity_2m", "is_day"],
            "timezone": "auto"
        }
        responses = openmeteo.weather_api(url, params=params)
        if responses is None:
            abort(404)
        return responses[0]

def parse_response(hourly_temperature_2m,hourly_relative_humidity_2m,hourly_is_day,days_list):
    num_days = 7
    hours_per_day = 24

    start = datetime.today()
    date_list = [str(start.date() + timedelta(days=x)) for x in range(num_days)]
    
    for day in range(num_days):
        # Initialize variables to store sum and count for periods
        day_temp_sum = 0
        day_temp_count = 0
        evening_temp_sum = 0
        evening_temp_count = 0
        daily_humidity_sum = 0
        daily_humidity_count = 0
        day_obj = Day(date_list[day])

        # Iterate over each hour of the day for the current day
        for hour in range(hours_per_day):
            # Calculate the index for the current hour
            index = day * hours_per_day + hour
            temperature = hourly_temperature_2m[index]
            humidity = hourly_relative_humidity_2m[index]
            is_day = hourly_is_day[index]
            
            # Check if the hour is during the day period (05:00 to 20:00)
            if is_day == 1:
                day_temp_sum += temperature
                day_temp_count += 1
                # Check if the hour is during the evening period (20:00 to 05:00)
            else:
                evening_temp_sum += temperature
                evening_temp_count += 1

            # Accumulate daily humidity
            daily_humidity_sum += humidity
            daily_humidity_count += 1

        # Calculate daily temperature and humidity averages
        if day_temp_count > 0:
            avg_day_temp = day_temp_sum / day_temp_count
            day_obj.set_daily_temp(float(avg_day_temp))
        else:
            day_obj.daily_temp = None
            day_obj.set_daily_temp(None)

        if evening_temp_count > 0:
            avg_evening_temp = evening_temp_sum / evening_temp_count
            day_obj.set_evening_temp(float(avg_evening_temp))
        else:
            day_obj.set_evening_temp(None)

            
        # Calculate daily humidity average
        if daily_humidity_count > 0:
            avg_daily_humidity = daily_humidity_sum / daily_humidity_count
            day_obj.set_humidity(float(avg_daily_humidity))
        else:
            day_obj.set_humidity(None)

        days_list.append(day_obj.to_dict())
    

# Start with flask web app with debug as
# True only if this is the starting page
if(__name__ == "__main__"):
    app.run(debug=True)

