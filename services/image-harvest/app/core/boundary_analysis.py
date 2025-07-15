"""
Boundary Analysis Module - Calculates tile boundary proximity and determines optimal search strategy.
"""
import logging
from typing import Dict, List, Tuple, Any
from streetlevel import geo
import math
from app.core.utils import calculate_distance
from app.config import BOUNDARY_CENTER_THRESHOLD, BOUNDARY_ADJACENT_THRESHOLD, MAX_ADAPTIVE_TILES

logger = logging.getLogger(__name__)

def calculate_boundary_distances(target_lat: float, target_lon: float) -> Dict[str, float]:
    """
    Calculate distance from target coordinates to each boundary of the center tile.
    
    Args:
        target_lat: Target latitude
        target_lon: Target longitude
        
    Returns:
        Dictionary with distances to north, south, east, west boundaries in meters
    """
    try:
        # Calculate center tile coordinates
        center_x, center_y = geo.wgs84_to_tile_coord(target_lat, target_lon, 17)
        
        # Calculate tile boundary coordinates
        # Northwest corner of the tile
        nw_lat, nw_lon = geo.tile_coord_to_wgs84(center_x, center_y, 17)
        # Southeast corner of the tile  
        se_lat, se_lon = geo.tile_coord_to_wgs84(center_x + 1, center_y + 1, 17)
        
        # Calculate boundary distances using Haversine formula for accuracy
        # North boundary (northern edge of the tile)
        north_distance = calculate_distance(target_lat, target_lon, nw_lat, target_lon)
        
        # South boundary (southern edge of the tile)
        south_distance = calculate_distance(target_lat, target_lon, se_lat, target_lon)
        
        # East boundary (eastern edge of the tile)
        east_distance = calculate_distance(target_lat, target_lon, target_lat, se_lon)
        
        # West boundary (western edge of the tile)
        west_distance = calculate_distance(target_lat, target_lon, target_lat, nw_lon)
        
        boundary_distances = {
            "north": north_distance,
            "south": south_distance,
            "east": east_distance,
            "west": west_distance,
            "center_tile": (center_x, center_y)
        }
        
        logger.debug(f"Boundary distances for ({target_lat}, {target_lon}): {boundary_distances}")
        return boundary_distances
        
    except Exception as e:
        logger.error(f"Error calculating boundary distances: {str(e)}")
        raise

def determine_search_strategy(boundary_distances: Dict[str, float]) -> str:
    """
    Determine optimal search strategy based on boundary proximity.
    
    Args:
        boundary_distances: Dictionary with distances to each boundary
        
    Returns:
        Search strategy string: 'center-only', 'single-direction', 'corner', 'multi-direction'
    """
    try:
        # Extract boundary distances
        north_dist = boundary_distances["north"]
        south_dist = boundary_distances["south"]
        east_dist = boundary_distances["east"]
        west_dist = boundary_distances["west"]
        
        # Count boundaries that are close
        close_boundaries = []
        if north_dist < BOUNDARY_ADJACENT_THRESHOLD:
            close_boundaries.append("north")
        if south_dist < BOUNDARY_ADJACENT_THRESHOLD:
            close_boundaries.append("south")
        if east_dist < BOUNDARY_ADJACENT_THRESHOLD:
            close_boundaries.append("east")
        if west_dist < BOUNDARY_ADJACENT_THRESHOLD:
            close_boundaries.append("west")
        
        # Determine strategy based on number of close boundaries
        if len(close_boundaries) == 0:
            # All boundaries are far - use center-only search
            strategy = "center-only"
        elif len(close_boundaries) == 1:
            # One boundary is close - use single direction
            strategy = "single-direction"
        elif len(close_boundaries) == 2:
            # Two boundaries are close - check if they're adjacent (corner)
            if ("north" in close_boundaries and "east" in close_boundaries) or \
               ("north" in close_boundaries and "west" in close_boundaries) or \
               ("south" in close_boundaries and "east" in close_boundaries) or \
               ("south" in close_boundaries and "west" in close_boundaries):
                strategy = "corner"
            else:
                strategy = "multi-direction"
        else:
            # Multiple boundaries are close - use multi-direction
            strategy = "multi-direction"
        
        logger.info(f"Search strategy determined: {strategy} (close boundaries: {close_boundaries})")
        return strategy
        
    except Exception as e:
        logger.error(f"Error determining search strategy: {str(e)}")
        # Fall back to center-only strategy
        return "center-only"

def select_adaptive_tiles(search_strategy: str, boundary_distances: Dict[str, float]) -> List[Tuple[int, int]]:
    """
    Select tiles to search based on the determined strategy and boundary distances.
    
    Args:
        search_strategy: The search strategy determined by determine_search_strategy
        boundary_distances: Dictionary with boundary distances and center tile coordinates
        
    Returns:
        List of tile coordinates (x, y) to search
    """
    try:
        center_x, center_y = boundary_distances["center_tile"]
        tiles_to_search = [(center_x, center_y)]  # Always include center tile
        
        if search_strategy == "center-only":
            # Search only the center tile
            pass
        elif search_strategy == "single-direction":
            # Add the closest adjacent tile
            closest_boundary = min(
                [("north", boundary_distances["north"]), 
                 ("south", boundary_distances["south"]),
                 ("east", boundary_distances["east"]), 
                 ("west", boundary_distances["west"])],
                key=lambda x: x[1]
            )
            
            if closest_boundary[0] == "north":
                tiles_to_search.append((center_x, center_y - 1))
            elif closest_boundary[0] == "south":
                tiles_to_search.append((center_x, center_y + 1))
            elif closest_boundary[0] == "east":
                tiles_to_search.append((center_x + 1, center_y))
            elif closest_boundary[0] == "west":
                tiles_to_search.append((center_x - 1, center_y))
                
        elif search_strategy == "corner":
            # Add adjacent tiles for corner scenario
            close_boundaries = []
            if boundary_distances["north"] < BOUNDARY_ADJACENT_THRESHOLD:
                close_boundaries.append("north")
            if boundary_distances["south"] < BOUNDARY_ADJACENT_THRESHOLD:
                close_boundaries.append("south")
            if boundary_distances["east"] < BOUNDARY_ADJACENT_THRESHOLD:
                close_boundaries.append("east")
            if boundary_distances["west"] < BOUNDARY_ADJACENT_THRESHOLD:
                close_boundaries.append("west")
            
            # Add adjacent tiles
            for boundary in close_boundaries:
                if boundary == "north":
                    tiles_to_search.append((center_x, center_y - 1))
                elif boundary == "south":
                    tiles_to_search.append((center_x, center_y + 1))
                elif boundary == "east":
                    tiles_to_search.append((center_x + 1, center_y))
                elif boundary == "west":
                    tiles_to_search.append((center_x - 1, center_y))
            
            # Add corner tile if both north/south and east/west boundaries are close
            if len(close_boundaries) >= 2:
                if "north" in close_boundaries and "east" in close_boundaries:
                    tiles_to_search.append((center_x + 1, center_y - 1))
                elif "north" in close_boundaries and "west" in close_boundaries:
                    tiles_to_search.append((center_x - 1, center_y - 1))
                elif "south" in close_boundaries and "east" in close_boundaries:
                    tiles_to_search.append((center_x + 1, center_y + 1))
                elif "south" in close_boundaries and "west" in close_boundaries:
                    tiles_to_search.append((center_x - 1, center_y + 1))
                    
        elif search_strategy == "multi-direction":
            # Add multiple adjacent tiles
            if boundary_distances["north"] < BOUNDARY_ADJACENT_THRESHOLD:
                tiles_to_search.append((center_x, center_y - 1))
            if boundary_distances["south"] < BOUNDARY_ADJACENT_THRESHOLD:
                tiles_to_search.append((center_x, center_y + 1))
            if boundary_distances["east"] < BOUNDARY_ADJACENT_THRESHOLD:
                tiles_to_search.append((center_x + 1, center_y))
            if boundary_distances["west"] < BOUNDARY_ADJACENT_THRESHOLD:
                tiles_to_search.append((center_x - 1, center_y))
        
        # Remove duplicates and limit to maximum tiles
        unique_tiles = list(set(tiles_to_search))
        if len(unique_tiles) > MAX_ADAPTIVE_TILES:
            unique_tiles = unique_tiles[:MAX_ADAPTIVE_TILES]
        
        logger.info(f"Selected tiles for strategy '{search_strategy}': {unique_tiles}")
        return unique_tiles
        
    except Exception as e:
        logger.error(f"Error selecting adaptive tiles: {str(e)}")
        # Fall back to center-only
        center_x, center_y = boundary_distances["center_tile"]
        return [(center_x, center_y)] 