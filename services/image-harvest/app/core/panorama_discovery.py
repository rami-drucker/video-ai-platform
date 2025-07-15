"""
Panorama Discovery Module - Fetches and processes panoramas from multiple tiles.
"""
import logging
from typing import List, Tuple
from streetlevel import lookaround
from streetlevel.lookaround import CoverageTile, LookaroundPanorama
from app.core.utils import calculate_distance

logger = logging.getLogger(__name__)

def fetch_adaptive_tiles(selected_tiles: List[Tuple[int, int]]) -> List[CoverageTile]:
    """
    Fetch panoramas from selected tiles with detailed logging.
    
    Args:
        selected_tiles: List of tile coordinates (x, y) to search
        
    Returns:
        List of CoverageTile objects with panorama data
    """
    coverage_tiles = []
    
    try:
        logger.info(f"Fetching panoramas from {len(selected_tiles)} tiles: {selected_tiles}")
        
        for i, (tile_x, tile_y) in enumerate(selected_tiles):
            try:
                # Fetch coverage tile using streetlevel API
                coverage = lookaround.get_coverage_tile(tile_x, tile_y)
                
                # Log detailed coverage response (matching original visibility)
                if i == 0:  # First tile is typically the center tile
                    logger.info(f"Center tile coverage response: {coverage}")
                else:
                    logger.info(f"Adjacent tile ({tile_x}, {tile_y}) coverage response: {coverage}")
                
                if coverage and coverage.panos:
                    coverage_tiles.append(coverage)
                    logger.info(f"Tile ({tile_x}, {tile_y}): Found {len(coverage.panos)} panoramas")
                else:
                    logger.warning(f"Tile ({tile_x}, {tile_y}): No panoramas found")
                    
            except Exception as e:
                logger.error(f"Error fetching tile ({tile_x}, {tile_y}): {str(e)}")
                # Continue with other tiles - don't fail the entire request
        
        if not coverage_tiles:
            logger.error("No coverage tiles found or no panoramas in any tile")
            raise Exception("No coverage tiles found at this location")
        
        logger.info(f"Successfully fetched {len(coverage_tiles)} tiles with panoramas")
        return coverage_tiles
        
    except Exception as e:
        logger.error(f"Error in fetch_adaptive_tiles: {str(e)}")
        raise

def aggregate_panoramas(coverage_tiles: List[CoverageTile]) -> List[LookaroundPanorama]:
    """
    Aggregate panoramas from multiple coverage tiles.
    
    Args:
        coverage_tiles: List of CoverageTile objects
        
    Returns:
        List of all LookaroundPanorama objects from all tiles
    """
    try:
        all_panoramas = []
        total_panoramas = 0
        
        for coverage_tile in coverage_tiles:
            if coverage_tile.panos:
                all_panoramas.extend(coverage_tile.panos)
                total_panoramas += len(coverage_tile.panos)
        
        logger.info(f"Aggregated {total_panoramas} panoramas from {len(coverage_tiles)} tiles")
        
        if not all_panoramas:
            logger.error("No panoramas found in any coverage tile")
            raise Exception("No panoramas found at this location")
        
        return all_panoramas
        
    except Exception as e:
        logger.error(f"Error aggregating panoramas: {str(e)}")
        raise

def rank_panoramas_by_distance(panoramas: List[LookaroundPanorama], 
                              target_coord, 
                              max_distance: float) -> List[LookaroundPanorama]:
    """
    Rank panoramas by distance from target coordinate and filter by maximum distance.
    
    Args:
        panoramas: List of LookaroundPanorama objects
        target_coord: Target coordinate (with lat, lng attributes)
        max_distance: Maximum distance in meters
        
    Returns:
        List of panoramas ranked by distance, filtered by max_distance
    """
    try:
        logger.info(f"Ranking {len(panoramas)} panoramas by distance (max: {max_distance}m)")
        
        # Calculate distances and filter panoramas
        panorama_distances = []
        for pano in panoramas:
            distance = calculate_distance(target_coord.lat, target_coord.lng, pano.lat, pano.lon)
            logger.info(f"Found panorama at ({pano.lat}, {pano.lon}), distance: {distance:.2f}m")
            
            if distance <= max_distance:
                panorama_distances.append((pano, distance))
        
        if not panorama_distances:
            logger.error(f"No panoramas found within {max_distance} meters of the location")
            raise Exception(f"No panoramas found within {max_distance} meters of the location")
        
        # Sort by distance (closest first)
        panorama_distances.sort(key=lambda x: x[1])
        
        # Extract panoramas in ranked order
        ranked_panoramas = [pano for pano, distance in panorama_distances]
        
        logger.info(f"Ranked {len(ranked_panoramas)} panoramas within {max_distance}m")
        if ranked_panoramas:
            closest_distance = panorama_distances[0][1]
            logger.info(f"Closest panorama distance: {closest_distance:.2f}m")
        
        return ranked_panoramas
        
    except Exception as e:
        logger.error(f"Error ranking panoramas by distance: {str(e)}")
        raise 