"""
Street Heuristics Module - Smart filtering to minimize API calls.
"""
import logging
import re
from typing import List, Dict, Tuple
from app.models import Coordinate
from app.config import ROUTE_PROXIMITY_THRESHOLD, ROUTE_CONFIDENCE_THRESHOLD
from app.core.utils import calculate_distance

logger = logging.getLogger(__name__)

def extract_street_name(address: str) -> str:
    """
    Extract street name from address without API call.
    Examples:
    "1001 Lombard St, San Francisco, CA" → "Lombard St"
    "10600 N Tantau Ave, Cupertino, CA 95014" → "N Tantau Ave"
    "123 Main Street, New York, NY" → "Main Street"
    """
    try:
        # Remove any extra whitespace
        address = address.strip()
        
        # Split by comma to get address parts
        parts = [part.strip() for part in address.split(',')]
        
        # First part contains the street address
        street_part = parts[0]
        
        # Split by space to separate number from street name
        street_components = street_part.split()
        
        # Skip the first component (house number)
        # Keep the rest as street name
        street_name_components = street_components[1:]
        
        # Join back together
        street_name = ' '.join(street_name_components)
        
        logger.debug(f"Extracted street name '{street_name}' from address '{address}'")
        return street_name
        
    except Exception as e:
        logger.error(f"Error extracting street name from '{address}': {str(e)}")
        return ""

def apply_street_heuristics(panoramas: List, start_street: str, current_head_coord: Coordinate, end_coord: Coordinate) -> List:
    """
    Apply heuristics to filter panoramas by street, minimizing API calls.
    
    Args:
        panoramas: List of panoramas from initial discovery
        start_street: Street name extracted from start address
        current_head_coord: Current head panorama coordinates
        end_coord: Ending coordinates
        
    Returns:
        List of panoramas filtered by street heuristics
    """
    try:
        logger.info(f"Applying street heuristics to {len(panoramas)} panoramas")
        logger.info(f"Target street: {start_street}")
        logger.info(f"Current head position: ({current_head_coord.lat}, {current_head_coord.lng})")
        
        filtered_panoramas = []
        
        for pano in panoramas:
            # Calculate confidence score
            confidence_score = calculate_confidence_score(pano, current_head_coord, end_coord)
            
            # Apply confidence threshold
            if confidence_score >= ROUTE_CONFIDENCE_THRESHOLD:
                filtered_panoramas.append(pano)
                logger.debug(f"Panorama at ({pano.lat}, {pano.lon}) accepted with score {confidence_score}")
            else:
                logger.debug(f"Panorama at ({pano.lat}, {pano.lon}) rejected with score {confidence_score}")
        
        logger.info(f"Filtered to {len(filtered_panoramas)} panoramas using heuristics")
        return filtered_panoramas
        
    except Exception as e:
        logger.error(f"Error applying street heuristics: {str(e)}")
        return panoramas  # Return all panoramas if heuristics fail

def calculate_confidence_score(pano, current_head_coord: Coordinate, end_coord: Coordinate) -> int:
    """
    Calculate confidence score for panorama being on same street.
    
    Args:
        pano: Panorama object with lat, lon attributes
        current_head_coord: Current head panorama coordinates
        end_coord: End destination coordinates
        
    Returns:
        Confidence score (0-10, higher is more confident)
    """
    score = 0
    
    # Proximity check (distance from current head)
    distance_from_head = calculate_distance(
        current_head_coord.lat, current_head_coord.lng,
        pano.lat, pano.lon
    )
    
    if distance_from_head < 50:
        score += 3  # High confidence
    elif distance_from_head < 100:
        score += 2  # Medium confidence
    elif distance_from_head < 150:
        score += 1  # Low confidence
    
    # Distance progression check (closer to end)
    distance_to_end = calculate_distance(pano.lat, pano.lon, end_coord.lat, end_coord.lng)
    distance_head_to_end = calculate_distance(current_head_coord.lat, current_head_coord.lng, end_coord.lat, end_coord.lng)
    
    if distance_to_end < distance_head_to_end:
        score += 2  # Moving toward end
    
    # Heading alignment check (if heading available)
    if hasattr(pano, 'heading'):
        # TODO: Add heading-based scoring in future step
        pass
    
    return score 