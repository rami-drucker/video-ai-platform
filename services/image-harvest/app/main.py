"""
Image Harvest Service - Extracts street-view panorama images based on geographic location.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Union, Dict
import sys
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

# Import new adaptive search modules
from app.core.boundary_analysis import calculate_boundary_distances, determine_search_strategy, select_adaptive_tiles
from app.core.panorama_discovery import fetch_adaptive_tiles, aggregate_panoramas, rank_panoramas_by_distance
from app.config import MAX_DISTANCE
from app.config import (
    ROUTE_HEADING_SECTOR_DEGREES, 
    ROUTE_MAX_PANORAMAS, 
    ROUTE_PROXIMITY_THRESHOLD, 
    ROUTE_CONFIDENCE_THRESHOLD
)
from app.core.utils import calculate_distance
from app.route_processor import process_route_request
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup session-specific file logging
from pathlib import Path
from datetime import datetime
from app.config import LOG_DIR, LOG_SESSION_FORMAT

# Create session-specific log file
session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = Path(LOG_DIR) / LOG_SESSION_FORMAT.format(timestamp=session_timestamp)

# Configure file handler with same format as terminal
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(message)s'))  # Same as terminal

# Add file handler to root logger
logging.getLogger().addHandler(file_handler)

logger.info(f"Session started - Log file: {log_file}")

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
            from heic2rgb import decode_heic  # type: ignore
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

from app.models import Coordinate, LocationRequest, ImageResponse, RouteRequest, RouteResponse

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

def download_lookaround_panorama(coord: Coordinate, session_id: str = None) -> tuple[str, dict]:
    """
    Download Apple Look Around panorama for a given coordinate and convert from HEIC to JPG.
    Downloads all 6 faces (BACK, LEFT, FRONT, RIGHT, TOP, BOTTOM) and returns FRONT face path.
    Returns tuple of (file_path, metadata)
    """
    try:
        # Find panoramas near the coordinate using adaptive boundary-based search
        try:
            logger.info(f"Searching for panoramas at coordinates: ({coord.lat}, {coord.lng})")
            
            # Calculate boundary distances and determine search strategy
            boundary_distances = calculate_boundary_distances(coord.lat, coord.lng)
            search_strategy = determine_search_strategy(boundary_distances)
            selected_tiles = select_adaptive_tiles(search_strategy, boundary_distances)
            
            logger.info(f"Boundary analysis: {boundary_distances}")
            logger.info(f"Search strategy: {search_strategy}")
            logger.info(f"Selected tiles: {selected_tiles}")
            
            # Fetch panoramas from selected tiles
            coverage_tiles = fetch_adaptive_tiles(selected_tiles)
            if not coverage_tiles:
                logger.error("No coverage tiles found")
                raise Exception("No coverage tiles found at this location")
            
            # Aggregate panoramas from all tiles
            all_panoramas = aggregate_panoramas(coverage_tiles)
            if not all_panoramas:
                logger.error("No panoramas found in selected tiles")
                raise Exception("No panoramas found at this location")
            
            logger.info(f"Found {len(all_panoramas)} panoramas across {len(selected_tiles)} tiles")
            
            # Rank panoramas by distance and select the best one
            ranked_panoramas = rank_panoramas_by_distance(all_panoramas, coord, MAX_DISTANCE)
            
            if not ranked_panoramas:
                raise Exception(f"No panoramas found within {MAX_DISTANCE} meters of the location")
            
            pano = ranked_panoramas[0]  # Best panorama (closest within distance limit)
            min_distance = calculate_distance(coord.lat, coord.lng, pano.lat, pano.lon)
            
            logger.info(f"Selected panorama at ({pano.lat}, {pano.lon}), distance: {min_distance:.2f}m")
                
        except Exception as e:
            logger.error(f"Error getting panorama: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get panorama: {str(e)}")

        # Download the panorama
        try:
            # Simple session support
            if session_id:
                output_dir = os.path.join("output", session_id)
            else:
                output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Download all 6 faces following streetlevel pattern
            for face_idx in range(6):
                heic_path = os.path.join(output_dir, f"pano_{timestamp}_{face_idx}.heic")
                jpg_path = os.path.join(output_dir, f"pano_{timestamp}_{face_idx}.jpg")
                
                # Download face using streetlevel pattern
                lookaround.download_panorama_face(pano, heic_path, face_idx, 0, auth)
                
                # Convert HEIC to JPG
                img = Image.open(heic_path)
                img.save(jpg_path, "JPEG")
                os.remove(heic_path)
            
            # Return front face path for backward compatibility (face_idx=2 is FRONT)
            front_jpg_path = os.path.join(output_dir, f"pano_{timestamp}_2.jpg")
            
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
            
            return front_jpg_path, metadata
            
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

@app.post("/harvest/route", response_model=RouteResponse)
async def harvest_route_images(route: RouteRequest):
    """
    Harvest street-view panorama images along a route between two addresses.
    """
    try:
        logger.info(f"Route request received: {route.start_address} to {route.end_address}")
        
        # Use route processor with function references
        file_paths, metadata = process_route_request(
            route.start_address, 
            route.end_address,
            geocode_address,
            download_lookaround_panorama
        )
        
        return RouteResponse(file_paths=file_paths, metadata=metadata)
        
    except Exception as e:
        logger.error(f"Error harvesting route images: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 