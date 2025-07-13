"""
Image Harvest Service - Extracts street-view panorama images based on geographic location.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Union, Dict
#import sysl
import platform
from PIL import Image
import logging
from pathlib import Path
import io
import uuid
import geocoder
from datetime import datetime
import os
import requests
import time
import math  # Add at the top with other imports

# Import validate_coordinates function from geocoding module FIRST (loads our protobuf files)
#from .core.geocoding import validate_coordinates

# Import streetlevel modules AFTER our protobuf files are loaded
from streetlevel import lookaround
from streetlevel.lookaround import Face, Authenticator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up HEIC decoder
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_DECODER = 'pillow-heif'
    logger.info("Using pillow-heif for HEIC decoding")
except ImportError:
    try:
        import pyheif
        HEIC_DECODER = 'pyheif'
        logger.info("Using pyheif for HEIC decoding")
    except ImportError:
        try:
            from heic2rgb import decode_heic
            HEIC_DECODER = 'heic2rgb'
            logger.info("Using heic2rgb for HEIC decoding")
        except ImportError:
            logger.error("No HEIC decoder found. Please install pillow-heif, pyheif, or heic2rgb")
            sys.exit(1)

# Create images directory structure
IMAGES_DIR = Path("images/raw")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Initialize the authenticator
auth = Authenticator()

class Coordinate(BaseModel):
    """Model for geographic coordinates."""
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")

class LocationRequest(BaseModel):
    """Request model for location-based image harvesting."""
    coordinates: Optional[Coordinate] = Field(None, description="Latitude and longitude coordinates")
    address: Optional[str] = Field(None, description="Street address to geocode")

class ImageResponse(BaseModel):
    """Response model for harvested images."""
    file_paths: List[str]
    metadata: Dict[str, dict]

def decode_heic_image(heic_data: bytes) -> Image.Image:
    """
    Decode HEIC image data using the best available decoder for the platform.
    """
    if HEIC_DECODER == 'heic2rgb':
        # heic2rgb returns a numpy array
        rgb_array = decode_heic(heic_data)
        return Image.fromarray(rgb_array)
    
    elif HEIC_DECODER == 'pyheif':
        # pyheif workflow
        heif_file = pyheif.read(heic_data)
        image = Image.frombytes(
            heif_file.mode, 
            heif_file.size, 
            heif_file.data,
            "raw",
            heif_file.mode,
            heif_file.stride,
        )
        return image
    
    else:  # pillow-heif
        # pillow-heif workflow
        with io.BytesIO(heic_data) as bio:
            image = Image.open(bio)
            return image.convert('RGB')

def geocode_address(address: str) -> Coordinate:
    """Convert address to coordinates using OpenStreetMap's Nominatim service."""
    url = "https://nominatim.openstreetmap.org/search"
    
    # Try with structured search first
    params = {
        "q": address,
        "format": "json",
        "addressdetails": 1,
        "limit": 1
    }
    
    headers = {
        "User-Agent": "VideoAIPlatform/1.0 (image-harvest-service)"
    }
    
    try:
        time.sleep(1)  # Respect Nominatim usage policy
        
        response = requests.get(url, params=params, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Could not geocode address")
            
        results = response.json()
        if not results:
            raise HTTPException(status_code=400, detail="Address not found")
            
        result = results[0]
        
        # Log the result for debugging
        logger.info(f"Geocoding result for {address}: lat={result['lat']}, lon={result['lon']}")
        
        return Coordinate(
            lat=float(result["lat"]),
            lng=float(result["lon"])
        )
        
    except Exception as e:
        logger.error(f"Geocoding error: {str(e)}")
        raise HTTPException(status_code=400, detail="Could not geocode address")

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points in meters using the Haversine formula.
    """
    R = 6371000  # Earth's radius in meters
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Differences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Haversine formula
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def download_lookaround_panorama(coord: Coordinate) -> tuple[str, dict]:
    """
    Download Apple Look Around panorama for a given coordinate and convert from HEIC to JPG.
    Returns tuple of (file_path, metadata)
    """
    try:
        # Find panoramas near the coordinate
        try:
            # Get the coverage tile to find panoramas
            logger.info(f"Searching for panoramas at coordinates: ({coord.lat}, {coord.lng})")
            coverage = lookaround.get_coverage_tile_by_latlon(coord.lat, coord.lng)
            logger.info(f"Coverage response: {coverage}")
            
            if not coverage or not coverage.panos:
                logger.error("No coverage tile found or no panoramas in tile")
                raise Exception("No panoramas found at this location")
            
            logger.info(f"Found {len(coverage.panos)} panoramas in coverage tile")
            
            # Find the closest panorama within 50 meters
            MAX_DISTANCE = 50  # meters
            closest_pano = None
            min_distance = float('inf')
            
            for pano in coverage.panos:
                distance = calculate_distance(coord.lat, coord.lng, pano.lat, pano.lon)
                logger.info(f"Found panorama at ({pano.lat}, {pano.lon}), distance: {distance:.2f}m")
                
                if distance < min_distance and distance <= MAX_DISTANCE:
                    min_distance = distance
                    closest_pano = pano
            
            if not closest_pano:
                raise Exception(f"No panoramas found within {MAX_DISTANCE} meters of the location")
            
            pano = closest_pano
            logger.info(f"Selected panorama at ({pano.lat}, {pano.lon}), distance: {min_distance:.2f}m")
                
        except Exception as e:
            logger.error(f"Error getting panorama: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get panorama: {str(e)}")

        # Download the panorama
        try:
            # Create output directory if it doesn't exist
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            heic_path = os.path.join(output_dir, f"pano_{timestamp}.heic")
            jpg_path = os.path.join(output_dir, f"pano_{timestamp}.jpg")
            
            # Download and save panorama face
            lookaround.download_panorama_face(pano, heic_path, Face.FRONT, 0, auth)
            
            # Convert HEIC to JPG using pillow-heif
            img = Image.open(heic_path)
            img.save(jpg_path, "JPEG")
            
            # Clean up HEIC file
            os.remove(heic_path)
            
            # Return the JPG path and metadata
            # Convert heading from counter-clockwise (where 90° is West) to clockwise (where 90° is East)
            heading_degrees_ccw = math.degrees(pano.heading) % 360  # Original counter-clockwise value
            heading_degrees = (360 - heading_degrees_ccw) % 360  # Convert to clockwise where 90° is East
            
            metadata = {
                "id": pano.id,
                "build_id": pano.build_id,
                "coordinates": {
                    "lat": pano.lat,
                    "lng": pano.lon
                },
                "heading_degrees": heading_degrees,  # Clockwise: 0°=N, 90°=E, 180°=S, 270°=W
                "heading_radians": pano.heading,  # Original counter-clockwise radians
                "elevation": pano.elevation,
                "date": pano.date.isoformat() if pano.date else None,
                "source_format": "heic",
                "output_format": "jpg",
                "distance_meters": min_distance
            }
            
            return jpg_path, metadata
            
        except Exception as e:
            logger.error(f"Error downloading/converting panorama: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to download/convert panorama: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error harvesting images: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

app = FastAPI(
    title="Image Harvest Service",
    description="Service for extracting street-view panorama images",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.post("/harvest", response_model=ImageResponse)
async def harvest_images(location: LocationRequest):
    """
    Harvest street-view panorama images based on location.
    """
    try:
        file_paths = []
        metadata = {}
        
        # Process single coordinate
        if location.coordinates:
            file_path, meta = download_lookaround_panorama(location.coordinates)
            file_paths.append(file_path)
            metadata[file_path] = meta
            
        # Process address
        elif location.address:
            coord = geocode_address(location.address)
            # Call here validate_coordinates which calls Apple reverse_geocode function in geocoding.py to obtain the actual address
            #validation_result = validate_coordinates(coord, location.address)
            #if validation_result:
            #   meta["validation_warning"] = {
            #   "message": validation_result.message,
            #   "input_address": validation_result.input_address,
            #   "found_address": validation_result.found_address
            #   }

            file_path, meta = download_lookaround_panorama(coord)
            file_paths.append(file_path)
            metadata[file_path] = meta
        
        else:
            raise HTTPException(
                status_code=400,
                detail="Must provide either coordinates or address"
            )
        
        return ImageResponse(file_paths=file_paths, metadata=metadata)
        
    except Exception as e:
        logger.error(f"Error harvesting images: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 