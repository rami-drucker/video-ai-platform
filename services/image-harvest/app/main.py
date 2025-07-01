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

# Import streetlevel modules correctly
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
    """Convert address to coordinates."""
    location = geocoder.osm(
        address,
        headers={
            'User-Agent': 'VideoAIPlatform/1.0 (image-harvest-service)'
        }
    )
    if not location.ok:
        raise HTTPException(status_code=400, detail="Could not geocode address")
    return Coordinate(lat=location.lat, lng=location.lng)

def download_lookaround_panorama(coord: Coordinate) -> tuple[str, dict]:
    """
    Download Apple Look Around panorama for a given coordinate and convert from HEIC to JPG.
    Returns tuple of (file_path, metadata)
    """
    try:
        # Find panoramas near the coordinate
        try:
            # Get the coverage tile to find panoramas
            coverage = lookaround.get_coverage_tile_by_latlon(coord.lat, coord.lng)
            if not coverage or not coverage.panos:
                raise Exception("No panoramas found at this location")
            
            # Get the closest panorama
            pano = coverage.panos[0]
                
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
            metadata = {
                "id": pano.id,
                "build_id": pano.build_id,
                "coordinates": {
                    "lat": pano.lat,
                    "lng": pano.lon
                },
                "heading": pano.heading,
                "elevation": pano.elevation,
                "date": pano.date.isoformat() if pano.date else None,
                "source_format": "heic",
                "output_format": "jpg"
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