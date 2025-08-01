from typing import List, Dict, Tuple
from app.models import Coordinate

def apply_street_heuristics_func(candidates: list, start_street: str, current_head_coord: Coordinate, end_coord: Coordinate, current_heading: float, config: dict, logger) -> list:
    """
    Filter and score candidates using proximity, heading, and progression.
    Returns filtered list with confidence scores.
    """
    try:
        from app.street_heuristics import apply_street_heuristics
        from app.core.utils import calculate_distance
        import math
        
        # OPTIMIZATION: Early termination - find first candidate that meets all criteria
        if current_heading is not None:
            heading_sector = config.get("ROUTE_HEADING_SECTOR_DEGREES", 60)
            
            for pano in candidates:  # Already sorted by distance (closest first)
                if hasattr(pano, 'heading'):
                    # Convert pano.heading from radians to degrees for comparison
                    # Apply same coordinate system conversion as in main.py
                    heading_degrees_ccw = math.degrees(pano.heading) % 360  # Counter-clockwise
                    pano_heading_degrees = (360 - heading_degrees_ccw) % 360  # Convert to clockwise
                    heading_diff = abs((pano_heading_degrees - current_heading + 180) % 360 - 180)
                    
                    if heading_diff <= heading_sector:
                        logger.info(f"EARLY TERMINATION: Found perfect match - {pano.id} at distance {calculate_distance(current_head_coord.lat, current_head_coord.lng, pano.lat, pano.lon):.1f}m")
                        logger.info(f"Heading aligned: {pano_heading_degrees:.1f}° vs {current_heading:.1f}° (diff: {heading_diff:.1f}°)")
                        return [pano]  # Return single candidate for immediate selection
                    else:
                        logger.info(f"Rejected {pano.id}: {pano_heading_degrees:.1f}° vs {current_heading:.1f}° (diff: {heading_diff:.1f}°)")
                else:
                    # If no heading info, include the candidate
                    logger.info(f"EARLY TERMINATION: Found candidate without heading info - {pano.id}")
                    return [pano]  # Return single candidate for immediate selection
            
            logger.info("No candidates passed heading alignment - will use fallback scoring")
            return []  # No early match found, fallback to current scoring
        else:
            logger.info("No current heading available - will use fallback scoring")
            return candidates  # Return all candidates for fallback scoring
        
        # FALLBACK: Apply additional street heuristics if no early termination
        if candidates:  # Only apply if we have candidates from early termination
            filtered = apply_street_heuristics(candidates, start_street, current_head_coord, end_coord)
            logger.info(f"FALLBACK: Applied street heuristics, {len(filtered)} candidates remain.")
            return filtered
        else:
            logger.info("FALLBACK: No candidates from early termination, returning empty list")
            return []
    except Exception as e:
        logger.error(f"Error in apply_street_heuristics_func: {str(e)}")
        return candidates


def select_next_panorama_func(filtered_candidates: list, current_coord: Coordinate, current_heading: float, end_coord: Coordinate, start_street: str, ambiguity_state: dict, config: dict, logger) -> tuple:
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
            from app.core.utils import normalize_address
            import requests
            for pano in top_candidates:
                # Reverse geocode pano location
                url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={pano.lat}&lon={pano.lon}&zoom=18&addressdetails=1"
                resp = requests.get(url, headers={"User-Agent": "image-harvest-service"}, timeout=5)
                api_calls += 1
                if resp.status_code == 200:
                    data = resp.json()
                    street = data.get("address", {}).get("road", "")
                    if street and normalize_address(street) == normalize_address(start_street):
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

def find_nearby_panoramas_func(current_coord: Coordinate, search_radius: float, visited_set: set, config: dict, logger) -> list:
    """
    Find all panoramas within a given radius of the current position.
    Reuse tile search logic if no panos found in initial radius.
    Exclude already visited panos.
    Returns: List of panorama candidates.
    """
    try:
        from app.core.boundary_analysis import (
            calculate_boundary_distances,
            determine_search_strategy,
            select_adaptive_tiles
        )
        from app.core.panorama_discovery import (
            fetch_adaptive_tiles,
            aggregate_panoramas,
            rank_panoramas_by_distance
        )
        from app.core.utils import calculate_distance
        
        logger.info(f"Searching for nearby panoramas at ({current_coord.lat}, {current_coord.lng}) with radius {search_radius}m")
        
        # Calculate boundary distances and determine search strategy
        boundary_distances = calculate_boundary_distances(current_coord.lat, current_coord.lng)
        search_strategy = determine_search_strategy(boundary_distances)
        selected_tiles = select_adaptive_tiles(search_strategy, boundary_distances)
        
        # Fetch panoramas from selected tiles
        coverage_tiles = fetch_adaptive_tiles(selected_tiles)
        if not coverage_tiles:
            logger.warning("No coverage tiles found")
            return []
        
        # Aggregate panoramas from all tiles
        all_panoramas = aggregate_panoramas(coverage_tiles)
        if not all_panoramas:
            logger.warning("No panoramas found in selected tiles")
            return []
        
        logger.info(f"Found {len(all_panoramas)} total panoramas across {len(selected_tiles)} tiles")
        
        # Filter by distance and exclude visited
        candidates = []
        for pano in all_panoramas:
            distance = calculate_distance(current_coord.lat, current_coord.lng, pano.lat, pano.lon)
            pano_id = f"{pano.id}_{pano.build_id}"
            
            if distance <= search_radius and pano_id not in visited_set:
                candidates.append(pano)
                logger.info(f"Found candidate: {pano_id} at distance {distance:.2f}m")
        
        logger.info(f"Found {len(candidates)} unvisited candidates within {search_radius}m")
        
        # OPTIMIZATION: Sort candidates by distance (closest first)
        candidates.sort(key=lambda pano: calculate_distance(current_coord.lat, current_coord.lng, pano.lat, pano.lon))
        logger.info(f"Sorted {len(candidates)} candidates by distance (closest first)")
        
        return candidates
        
    except Exception as e:
        logger.error(f"Error in find_nearby_panoramas_func: {str(e)}")
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
    Orchestrate the collection of panoramas along a route from start to end.
    Returns:
        file_paths: List of downloaded panorama file paths.
        metadata_dict: Dict mapping file paths to panorama metadata.
        summary: Dict with route summary (distance, panos, API calls, etc.)
    """
    logger.info(f"Starting progress_along_route from ({start_coord.lat}, {start_coord.lng}) to ({end_coord.lat}, {end_coord.lng})")
    
    # Initialize state
    file_paths = []
    metadata_dict = {}
    visited_set = set()
    current_coord = start_coord
    current_heading = None
    pano_count = 0
    total_distance = 0.0
    api_calls = 0
    ambiguity_skips = 0
    ambiguity_state = {"api_calls": 0, "skips": 0}
    
    try:
        # Download and store the first panorama
        logger.info("Downloading initial panorama at start location")
        file_path, metadata = download_func(start_coord)
        file_paths.append(file_path)
        metadata_dict[file_path] = metadata
        
        # Extract heading from first panorama if available
        if isinstance(metadata, dict) and 'heading_degrees' in metadata and metadata['heading_degrees'] is not None:
            current_heading = metadata['heading_degrees']
            logger.info(f"Initial heading: {current_heading} degrees")
        
        # Add to visited set
        pano_id = f"{metadata.get('id', 'unknown')}_{metadata.get('build_id', 'unknown')}"
        visited_set.add(pano_id)
        pano_count += 1
        
        # FIX: Update current_coord to first panorama location
        if isinstance(metadata, dict) and 'coordinates' in metadata:
            current_coord = Coordinate(
                lat=metadata['coordinates']['lat'], 
                lng=metadata['coordinates']['lng']
            )
            logger.info(f"Updated current_coord to first panorama location: ({current_coord.lat}, {current_coord.lng})")
        
        # Main loop: find, filter, select, download, update state
        while not should_terminate_route(current_coord, end_coord, pano_count, ambiguity_skips, config):
            logger.info(f"Iteration {pano_count}: Current position ({current_coord.lat}, {current_coord.lng})")
            
            # Find nearby panoramas
            search_radius = config.get("ROUTE_SEARCH_RADIUS", 200)
            candidates = find_nearby_panoramas_func(current_coord, search_radius, visited_set, config, logger)
            
            if not candidates:
                logger.warning("No nearby panoramas found, terminating route")
                break
            
            # Apply street heuristics
            filtered_candidates = apply_street_heuristics_func(
                candidates, start_street, current_coord, end_coord, current_heading, config, logger
            )
            
            if not filtered_candidates:
                logger.warning("No candidates passed street heuristics, terminating route")
                break
            
            # Select next panorama
            next_pano, updated_ambiguity_state = select_next_panorama_func(
                filtered_candidates, current_coord, current_heading, end_coord, start_street, ambiguity_state, config, logger
            )
            
            # Update ambiguity state
            ambiguity_state = updated_ambiguity_state
            ambiguity_skips = ambiguity_state.get("skips", 0)
            api_calls = ambiguity_state.get("api_calls", 0)
            
            if next_pano is None:
                logger.warning("No panorama selected, skipping iteration")
                ambiguity_skips += 1
                continue
            
            # Download the selected panorama
            try:
                pano_coord = Coordinate(lat=next_pano.lat, lng=next_pano.lon)
                file_path, metadata = download_func(pano_coord)
                file_paths.append(file_path)
                metadata_dict[file_path] = metadata
                
                # Update state
                pano_id = f"{next_pano.id}_{next_pano.build_id}"
                visited_set.add(pano_id)
                pano_count += 1
                
                # Update current position and heading
                from app.core.utils import calculate_distance
                distance_to_previous = calculate_distance(current_coord.lat, current_coord.lng, next_pano.lat, next_pano.lon)
                total_distance += distance_to_previous
                current_coord = pano_coord
                
                # Update heading if available - use metadata heading_degrees (in degrees)
                if isinstance(metadata, dict) and 'heading_degrees' in metadata and metadata['heading_degrees'] is not None:
                    current_heading = metadata['heading_degrees']
                    logger.info(f"Updated heading from metadata: {current_heading} degrees")
                
                logger.info(f"Downloaded panorama {pano_count}: {file_path} (distance: {distance_to_previous:.2f}m)")
                
            except Exception as e:
                logger.error(f"Error downloading panorama: {str(e)}")
                ambiguity_skips += 1
                continue
        
        # Log summary
        summary = {
            "panoramas_collected": pano_count,
            "total_distance_m": total_distance,
            "api_calls": api_calls,
            "ambiguity_skips": ambiguity_skips,
            "file_paths": file_paths,
            "route_completed": pano_count > 1,  # More than just the initial panorama
            "termination_reason": "max_panos" if pano_count >= config.get("ROUTE_MAX_PANORAMAS", 50) else
                                "proximity_to_end" if should_terminate_route(current_coord, end_coord, pano_count, ambiguity_skips, config) else
                                "no_more_candidates"
        }
        
        logger.info(f"Route collection completed: {pano_count} panoramas, {total_distance:.2f}m total distance")
        logger.info(f"Summary: {summary}")
        
        return file_paths, metadata_dict, summary
        
    except Exception as e:
        logger.error(f"Error in progress_along_route: {str(e)}")
        # Return partial results
        summary = {
            "panoramas_collected": pano_count,
            "total_distance_m": total_distance,
            "api_calls": api_calls,
            "ambiguity_skips": ambiguity_skips,
            "file_paths": file_paths,
            "route_completed": False,
            "error": str(e)
        }
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