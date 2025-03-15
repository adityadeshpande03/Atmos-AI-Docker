from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from groq import Groq
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Settings:
    MONGO_URI = "mongodb+srv://adityadeshpande03:Predator1734@atmosai.ghtdw.mongodb.net/?retryWrites=true&w=majority&appName=AtmosAI"
    DB_NAME = "weather_data"
    COLLECTION_NAME = "weather_data"
    GROQ_API_KEY = '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'

def get_db():
    """Creates database connection"""
    try:
        client = MongoClient(Settings.MONGO_URI, server_api=ServerApi('1'))
        db = client[Settings.DB_NAME]
        collection = db[Settings.COLLECTION_NAME]
        return client, collection
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

# Initialize clients
client_groq = Groq(api_key=Settings.GROQ_API_KEY)
mongo_client, collection = get_db()

def format_date(date_str: str) -> str:
    """Format YYYY-MM-DD to include default time"""
    return f"{date_str} 23:00:00+00:00"

def check_mongo_connection():
    """Check if MongoDB connection is alive and reconnect if needed"""
    global mongo_client, collection
    try:
        if mongo_client is None or not mongo_client.is_primary:
            logger.warning("MongoDB connection lost, attempting to reconnect...")
            mongo_client, collection = get_db()
        return mongo_client is not None
    except:
        return False

def format_date_with_default_time(date_str: str) -> str:
    """Add default time to YYYY-MM-DD date format"""
    return f"{date_str} 23:00:00+00:00"

# Update how we get weather data
def get_weather_data(date_str: str):
    """Get weather data for a specific date"""
    query_date = format_date_with_default_time(date_str)
    return collection.find_one({"date": query_date}, {"_id": 0})

# Define the target date (ensure format matches your MongoDB storage format)
target_date = "2025-02-28"

# Retrieve weather data from MongoDB
if not check_mongo_connection():
    print("Failed to connect to MongoDB.")
    exit()

weather_data = get_weather_data(target_date)

if not weather_data:
    print(f"No weather data found for {target_date}.")
    exit()

# Construct the dynamic prompt
prompt = f"""
Generate a **full-day weather forecast** for {target_date} based on the following data.
Do not mention "today" or "tomorrow"—just focus on the future weather for this date.

Vary the summary format every time. Sometimes make it **detailed and scientific**, 
other times **casual and conversational**, or even **like a weather reporter's broadcast**. 
Make sure the response feels **unique, natural, and engaging** each time.

Here is the predicted weather data:

- **Temperature:** {weather_data['temperature_2m']}°C (Feels like {weather_data['apparent_temperature']}°C)
- **Humidity:** {weather_data['relative_humidity_2m']}%
- **Dew Point:** {weather_data['dew_point_2m']}°C
- **Precipitation:** {weather_data['precipitation']} mm (Rain: {weather_data['rain']} mm, Snowfall: {weather_data['snowfall']} mm)
- **Snow Depth:** {weather_data['snow_depth']} mm
- **Atmospheric Pressure:** {weather_data['pressure_msl']} hPa (Surface Pressure: {weather_data['surface_pressure']} hPa)
- **Cloud Cover:** {weather_data['cloud_cover']}% (Low: {weather_data['cloud_cover_low']}%, Mid: {weather_data['cloud_cover_mid']}%, High: {weather_data['cloud_cover_high']}%)
- **Wind Speed:** {weather_data['wind_speed_10m']} km/h at 10m, {weather_data['wind_speed_100m']} km/h at 100m
- **Wind Direction:** {weather_data['wind_direction_10m']}° at 10m, {weather_data['wind_direction_100m']}° at 100m
- **Wind Gusts:** {weather_data['wind_gusts_10m']} km/h

Make sure the response is **not boring** and feels like a real forecast.
"""

# Send the prompt to Groq's LLM
completion = client_groq.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": prompt}],
    temperature=1,
    max_completion_tokens=1024,
    top_p=1,
    stream=True
)

# Stream the response properly
print("\n📡 Future Weather Forecast:\n")
for chunk in completion:
    if hasattr(chunk, "choices") and chunk.choices:  # Ensure chunk has choices
        content = chunk.choices[0].delta.content
        if content:  # Avoid printing None or empty content
            print(content, end="", flush=True)

# Close MongoDB connection
if mongo_client:
    mongo_client.close()