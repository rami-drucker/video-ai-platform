"""
Data models for the Image Harvest Service.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

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

class RouteRequest(BaseModel):
    """Request model for route-based image harvesting."""
    start_address: str = Field(..., description="Starting street address")
    end_address: str = Field(..., description="Ending street address")

class RouteResponse(BaseModel):
    """Response model for route-based harvested images."""
    file_paths: List[str]
    metadata: Dict[str, dict] 