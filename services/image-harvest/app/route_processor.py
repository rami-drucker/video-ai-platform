"""
Route Processing Module - Orchestrates route-based panorama collection.
"""
import logging
from typing import List, Dict, Tuple
from app.models import Coordinate
from app.config import ROUTE_MAX_PANORAMAS

logger = logging.getLogger(__name__)

def process_route_request(start_address: str, end_address: str, geocode_func, download_func) -> Tuple[List[str], Dict[str, dict]]:
    """
    Process a route request and return collected panoramas.
    
    Args:
        start_address: Starting street address
        end_address: Ending street address
        geocode_func: Function to geocode addresses
        download_func: Function to download panoramas
        
    Returns:
        Tuple of (file_paths, metadata)
    """
    try:
        logger.info(f"Processing route: {start_address} to {end_address}")
        
        # Step 1: Geocode both addresses
        start_coord = geocode_func(start_address)
        end_coord = geocode_func(end_address)
        
        logger.info(f"Start coordinates: ({start_coord.lat}, {start_coord.lng})")
        logger.info(f"End coordinates: ({end_coord.lat}, {end_coord.lng})")
        
        # Step 2: Get initial panorama at start location
        file_path, metadata = download_func(start_coord)
        
        logger.info(f"Initial panorama downloaded: {file_path}")
        
        # TODO: Implement route progression logic
        # For now, return just the start panorama
        
        file_paths = [file_path]
        metadata_dict = {file_path: metadata}
        
        return file_paths, metadata_dict
        
    except Exception as e:
        logger.error(f"Error processing route: {str(e)}")
        raise 