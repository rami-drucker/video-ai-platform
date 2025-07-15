"""
Configuration settings for the Image Harvest Service.
"""

# Geocoding service configuration
GEOCODING_SERVICE = "apple"  # "apple" or "nominatim"

# Nominatim settings
NOMINATIM_URL = "https://nominatim.openstreetmap.org"  # Base URL for Nominatim service
NOMINATIM_USER_AGENT = "VideoAIPlatform/1.0 (image-harvest-service)"  # Required by Nominatim ToS
NOMINATIM_RATE_LIMIT = 1  # Rate limit in seconds for Nominatim API

# Location settings
MAX_DISTANCE = 50  # Maximum distance in meters to search for panoramas

# Adaptive boundary-based search settings
BOUNDARY_CENTER_THRESHOLD = 75  # meters - threshold for center-only search
BOUNDARY_ADJACENT_THRESHOLD = 50  # meters - threshold for including adjacent tiles
MAX_ADAPTIVE_TILES = 5  # maximum tiles to search in adaptive mode

# Output settings
OUTPUT_DIR = "output"  # Directory for storing downloaded images

# Image settings
FACE_ZOOM_LEVEL = 2  # Zoom level for panorama faces (0-4, higher is more detailed) 