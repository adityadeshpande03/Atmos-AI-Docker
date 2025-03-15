from fastapi import FastAPI, HTTPException, Body, Request
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from groq import Groq
import os
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import logging
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Weather Forecast Generator",
              description="API for generating weather forecasts using Groq LLM and MongoDB data")

# Get the directory where the script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Add this near the top with other initializations
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Mount static files BEFORE any routes
frontend_path = os.path.join(os.path.dirname(BASE_DIR), "frontend")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic model for request
class ForecastRequest(BaseModel):
    date: str
    style: Optional[str] = "balanced"  # balanced, detailed, casual, broadcast
    report_length: Optional[int] = 200  # Default to 200 words
    
# Pydantic model for response
class ForecastResponse(BaseModel):
    date: str
    forecast: str
    data_used: Dict[str, Any]

# Startup event to initialize connections
@app.on_event("startup")
async def startup_db_client():
    # Set up Groq API key
    app.groq_api_key = os.getenv("GROQ_API_KEY", "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")
    if not app.groq_api_key:
        raise ValueError("Missing Groq API key. Set GROQ_API_KEY as an environment variable.")
    
    # Initialize Groq client
    app.groq_client = Groq(api_key=app.groq_api_key)
    
    try:
        # Connect to MongoDB Atlas
        mongo_uri = os.getenv("MONGODB_URI", "mongodb+srv://adityadeshpande03:Predator1734@atmosai.ghtdw.mongodb.net/?retryWrites=true&w=majority&appName=AtmosAI")
        app.mongodb_client = MongoClient(mongo_uri, server_api=ServerApi('1'))
        
        # Test the connection
        app.mongodb_client.admin.command('ping')
        app.db = app.mongodb_client["weather_data"]
        
        # Ensure the collection exists
        if "weather_data" not in app.db.list_collection_names():
            app.db.create_collection("weather_data")
            logger.warning("Created 'weather_data' collection as it did not exist")
        
        logger.info("Connected to MongoDB Atlas and initialized Groq client")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB Atlas: {str(e)}")
        # Continue running without MongoDB for testing/development
        app.mongodb_client = None
        app.db = None

# Shutdown event to close connections
@app.on_event("shutdown")
async def shutdown_db_client():
    if hasattr(app, 'mongodb_client') and app.mongodb_client:
        app.mongodb_client.close()
        logger.info("Closed MongoDB connection")

# Main endpoint to generate forecast
@app.post("/api/generate_forecast")
async def generate_forecast(request: ForecastRequest):
    logger.info(f"Received request: {request}")
    try:
        # Validate and format date
        try:
            parsed_date = datetime.strptime(request.date, '%Y-%m-%d')
            formatted_date = parsed_date.strftime('%Y-%m-%d')  # Ensure consistent YYYY-MM-DD format
            logger.info(f"Formatted date: {formatted_date}")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Check MongoDB connection
        if not hasattr(app, 'db') or app.db is None:
            raise HTTPException(status_code=503, detail="Database connection is not available")
        
        # Query MongoDB with exact date match
        collection = app.db["weather_data"]
        query = {"date": {"$regex": f"^{formatted_date}"}}  # Matches any time on the given date
        fields = {
            "_id": 0,
            "date": 1,
            "temperature_2m": 1,
            "relative_humidity_2m": 1,
            "dew_point_2m": 1,
            "apparent_temperature": 1,
            "precipitation": 1,
            "rain": 1,
            "snowfall": 1,
            "snow_depth": 1,
            "pressure_msl": 1,
            "surface_pressure": 1,
            "cloud_cover": 1,
            "cloud_cover_low": 1,
            "cloud_cover_mid": 1,
            "cloud_cover_high": 1,
            "wind_speed_10m": 1,
            "wind_speed_100m": 1,
            "wind_direction_10m": 1,
            "wind_direction_100m": 1,
            "wind_gusts_10m": 1,
        }
        logger.info(f"MongoDB query: {query}")
        
        weather_data = collection.find_one(query, fields)
        logger.info(f"MongoDB result: {weather_data}")
        
        if not weather_data:
            logger.warning(f"No weather data found for date: {formatted_date}")
            raise HTTPException(status_code=404, detail=f"No weather data found for {formatted_date}")

        # Determine style instruction based on request
        style_instructions = {
            "balanced": "Vary the summary format. Sometimes make it detailed and scientific, other times casual and conversational.",
            "detailed": "Make the forecast detailed and scientific with technical meteorological information.",
            "casual": "Make the forecast casual and conversational, as if talking to a friend.",
            "broadcast": "Format the forecast like a professional weather reporter's broadcast script."
        }
        
        style_text = style_instructions.get(request.style, style_instructions["balanced"])
        
        # Construct the dynamic prompt with specific word count instruction
        prompt = f"""
        Generate a weather forecast for {request.date} that is EXACTLY {request.report_length} words long.
        Base the forecast on the following weather data.
        Do not mention "today" or "tomorrow"—just focus on the future weather for this date.
        {style_text}
        Make sure the response is engaging and natural.
        
        Weather data:
        - Temperature: {weather_data.get('temperature_2m', 'N/A')}°C (Feels like {weather_data.get('apparent_temperature', 'N/A')}°C)
        - Humidity: {weather_data.get('relative_humidity_2m', 'N/A')}%
        - Dew Point: {weather_data.get('dew_point_2m', 'N/A')}°C
        - Precipitation: {weather_data.get('precipitation', 'N/A')} mm (Rain: {weather_data.get('rain', 'N/A')} mm, Snowfall: {weather_data.get('snowfall', 'N/A')} mm)
        - Snow Depth: {weather_data.get('snow_depth', 'N/A')} mm
        - Pressure: {weather_data.get('pressure_msl', 'N/A')} hPa (Surface: {weather_data.get('surface_pressure', 'N/A')} hPa)
        - Cloud Cover: {weather_data.get('cloud_cover', 'N/A')}% (Low: {weather_data.get('cloud_cover_low', 'N/A')}%, Mid: {weather_data.get('cloud_cover_mid', 'N/A')}%, High: {weather_data.get('cloud_cover_high', 'N/A')}%)
        - Wind: {weather_data.get('wind_speed_10m', 'N/A')} km/h at 10m, gusting to {weather_data.get('wind_gusts_10m', 'N/A')} km/h
        
        Remember: The response must be EXACTLY {request.report_length} words. Not more, not less.
        Make the forecast natural and engaging while maintaining accuracy.
        """

        # Send the prompt to Groq's LLM with adjusted temperature for more consistent length
        logger.info(f"Sending prompt to Groq's LLM")
        try:
            completion = app.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": f"You are a weather forecaster. Generate forecasts that are exactly {request.report_length} words long."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1024,
                top_p=0.9,
            )
            
            # Extract the generated forecast
            forecast = completion.choices[0].message.content
            logger.info("Successfully received forecast from Groq")
        except Exception as e:
            logger.error(f"Error from Groq API: {str(e)}")
            raise HTTPException(status_code=502, detail=f"Error from language model service: {str(e)}")
        
        # Return response with forecast and data used
        return ForecastResponse(
            date=request.date,
            forecast=forecast,
            data_used=weather_data
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as they already have status codes
        raise
    except Exception as e:
        logger.error(f"Error generating forecast: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating forecast: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    db_status = "connected" if (hasattr(app, 'mongodb_client') and app.mongodb_client) else "disconnected"
    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }