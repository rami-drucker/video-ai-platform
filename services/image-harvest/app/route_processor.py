from typing import List, Dict, Tuple
from app.models import Coordinate

def apply_street_heuristics_func(candidates: list, start_street: str, current_head_coord: Coordinate, end_coord: Coordinate, config: dict, logger) -> list:
    """
    Filter and score candidates using proximity, heading, and progression.
    Returns filtered list with confidence scores.
    """
    try:
        from app.street_heuristics import apply_street_heuristics
        filtered = apply_street_heuristics(candidates, start_street, current_head_coord, end_coord)
        logger.info(f"Applied street heuristics, {len(filtered)} candidates remain.")
        return filtered
    except Exception as e:
        logger.error(f"Error in apply_street_heuristics_func: {str(e)}")
        return candidates


def select_next_panorama_func(filtered_candidates: list, current_coord: Coordinate, current_heading: float, end_coord: Coordinate, ambiguity_state: dict, config: dict, logger) -> tuple:
    """
    Select the best next panorama from filtered candidates.
    Handles ambiguity: if multiple candidates are tied, uses Nominatim API if needed, or skips up to 2 times.
    Updates ambiguity state (skips, API calls).
    Returns: (Selected panorama (or None), updated ambiguity state)
    """
    try:
        if not filtered_candidates:
            logger.info("No filtered candidates to select from.")
            return None, ambiguity_state
        # Score by proximity and progression
        from app.core.utils import calculate_distance
        scored = []
        for pano in filtered_candidates:
            dist_to_current = calculate_distance(current_coord.lat, current_coord.lng, pano.lat, pano.lon)
            dist_to_end = calculate_distance(pano.lat, pano.lon, end_coord.lat, end_coord.lng)
            score = 0
            # Closer to current is better
            if dist_to_current < 50:
                score += 2
            elif dist_to_current < 100:
                score += 1
            # Progression toward end
            if dist_to_end < calculate_distance(current_coord.lat, current_coord.lng, end_coord.lat, end_coord.lng):
                score += 2
            # Heading alignment (if available)
            if hasattr(pano, 'heading') and current_heading is not None:
                heading_diff = abs((pano.heading - current_heading + 180) % 360 - 180)
                if heading_diff <= config.get("ROUTE_HEADING_SECTOR_DEGREES", 45):
                    score += 2
            scored.append((score, pano, dist_to_end))
        if not scored:
            logger.info("No scored candidates.")
            return None, ambiguity_state
        # Sort by score (desc), then by progression (closer to end)
        scored.sort(key=lambda x: (-x[0], x[2]))
        top_score = scored[0][0]
        top_candidates = [p for s, p, d in scored if s == top_score]
        if len(top_candidates) == 1:
            logger.info(f"Selected panorama with score {top_score}.")
            return top_candidates[0], ambiguity_state
        # Ambiguity: multiple top candidates
        logger.info(f"Ambiguity: {len(top_candidates)} candidates with top score {top_score}.")
        # Use Nominatim API if available, else skip up to 2 times
        api_calls = ambiguity_state.get("api_calls", 0)
        skips = ambiguity_state.get("skips", 0)
        try:
            from app.street_heuristics import extract_street_name
            import requests
            for pano in top_candidates:
                # Reverse geocode pano location
                url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={pano.lat}&lon={pano.lon}&zoom=18&addressdetails=1"
                resp = requests.get(url, headers={"User-Agent": "image-harvest-service"}, timeout=5)
                api_calls += 1
                if resp.status_code == 200:
                    data = resp.json()
                    street = data.get("address", {}).get("road", "")
                    if street and extract_street_name(street) == extract_street_name(start_street):
                        logger.info(f"Selected panorama after Nominatim check: {street}")
                        ambiguity_state["api_calls"] = api_calls
                        ambiguity_state["skips"] = skips
                        return pano, ambiguity_state
            # If none match, skip
            skips += 1
            logger.info(f"No matching street found via Nominatim. Skipping (skips={skips}).")
            ambiguity_state["api_calls"] = api_calls
            ambiguity_state["skips"] = skips
            return None, ambiguity_state
        except Exception as e:
            skips += 1
            logger.warning(f"Nominatim API error or rate limit: {str(e)}. Skipping (skips={skips}).")
            ambiguity_state["api_calls"] = api_calls
            ambiguity_state["skips"] = skips
            return None, ambiguity_state
    except Exception as e:
        logger.error(f"Error in select_next_panorama_func: {str(e)}")
        return None, ambiguity_state

def find_nearby_panoramas_func(*args, **kwargs):
    """
    Dummy implementation to unblock the service.
    Returns an empty list.
    """
    return []
    
def should_terminate_route(current_coord: Coordinate, end_coord: Coordinate, pano_count: int, ambiguity_skips: int, config: dict) -> bool:
    """
    Checks all termination conditions (proximity to end, max panos, ambiguity skips, dead-ends).
    Returns: Boolean (terminate/continue)
    """
    try:
        from app.core.utils import calculate_distance
        proximity_threshold = config.get("ROUTE_PROGRESSION_THRESHOLD", 30)
        max_panos = config.get("ROUTE_MAX_PANORAMAS", 50)
        max_skips = config.get("ROUTE_MAX_AMBIGUOUS_SKIPS", 2)
        dist_to_end = calculate_distance(current_coord.lat, current_coord.lng, end_coord.lat, end_coord.lng)
        if dist_to_end <= proximity_threshold:
            return True
        if pano_count >= max_panos:
            return True
        if ambiguity_skips > max_skips:
            return True
        return False
    except Exception as e:
        return False 

def progress_along_route(
    start_coord, end_coord, start_street, geocode_func, download_func,
    find_nearby_panoramas_func, apply_street_heuristics_func, select_next_panorama_func,
    config,
    logger
):
    """
    Dummy implementation to unblock the service.
    """
    logger.info(f"Starting progress_along_route from ({start_coord.lat}, {start_coord.lng}) to ({end_coord.lat}, {end_coord.lng})")
    file_paths = []
    metadata_dict = {}
    summary = {}
    try:
        file_path, metadata = download_func(start_coord)
        file_paths.append(file_path)
        metadata_dict[file_path] = metadata
        summary = {
            "panoramas_collected": 1,
            "total_distance_m": 0.0,
            "api_calls": 0,
            "ambiguity_skips": 0,
            "file_paths": file_paths
        }
        logger.info(f"Downloaded initial panorama: {file_path}")
    except Exception as e:
        logger.error(f"Error in progress_along_route: {str(e)}")
    return file_paths, metadata_dict, summary

def process_route_request(start_address, end_address, geocode_func, download_func):
    """
    Entry point for route-based panorama collection.
    Orchestrates geocoding, config, and calls progress_along_route.
    """
    import logging
    from app.street_heuristics import extract_street_name
    logger = logging.getLogger(__name__)
    try:
        logger.info(f"Processing route: {start_address} to {end_address}")
        start_coord = geocode_func(start_address)
        end_coord = geocode_func(end_address)
        logger.info(f"Start coordinates: ({start_coord.lat}, {start_coord.lng})")
        logger.info(f"End coordinates: ({end_coord.lat}, {end_coord.lng})")
        start_street = extract_street_name(start_address)
        logger.info(f"Extracted street name: {start_street}")
        # Prepare config dict
        from app.config import (
            ROUTE_HEADING_SECTOR_DEGREES,
            ROUTE_MAX_PANORAMAS,
            ROUTE_PROXIMITY_THRESHOLD,
            ROUTE_CONFIDENCE_THRESHOLD,
            ROUTE_SEARCH_RADIUS,
            ROUTE_PROGRESSION_THRESHOLD,
            ROUTE_MAX_AMBIGUOUS_SKIPS
        )
        config = {
            "ROUTE_HEADING_SECTOR_DEGREES": ROUTE_HEADING_SECTOR_DEGREES,
            "ROUTE_MAX_PANORAMAS": ROUTE_MAX_PANORAMAS,
            "ROUTE_PROXIMITY_THRESHOLD": ROUTE_PROXIMITY_THRESHOLD,
            "ROUTE_CONFIDENCE_THRESHOLD": ROUTE_CONFIDENCE_THRESHOLD,
            "ROUTE_SEARCH_RADIUS": ROUTE_SEARCH_RADIUS,
            "ROUTE_PROGRESSION_THRESHOLD": ROUTE_PROGRESSION_THRESHOLD,
            "ROUTE_MAX_AMBIGUOUS_SKIPS": ROUTE_MAX_AMBIGUOUS_SKIPS
        }
        # Call progress_along_route
        file_paths, metadata_dict, summary = progress_along_route(
            start_coord,
            end_coord,
            start_street,
            geocode_func,
            download_func,
            find_nearby_panoramas_func,
            apply_street_heuristics_func,
            select_next_panorama_func,
            config,
            logger
        )
        return file_paths, metadata_dict
    except Exception as e:
        logger.error(f"Error processing route: {str(e)}")
        raise 