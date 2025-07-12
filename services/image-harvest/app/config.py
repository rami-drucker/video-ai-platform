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

# Output settings
OUTPUT_DIR = "output"  # Directory for storing downloaded images

# Image settings
FACE_ZOOM_LEVEL = 2  # Zoom level for panorama faces (0-4, higher is more detailed) 