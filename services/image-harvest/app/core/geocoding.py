from dataclasses import dataclass
from typing import Optional, List, Dict
import logging
from requests import Session

from streetlevel.lookaround import Authenticator
from ..proto import PlaceRequest_pb2, PlaceResponse_pb2, Shared_pb2
from ..proto.PlaceRequest_pb2 import PlaceRequest
from ..proto.Shared_pb2 import RequestType, MapsResultType

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class Coordinate:
    lat: float
    lng: float  # Changed from lon to lng

@dataclass
class ValidationWarning:
    input_address: str
    found_address: str
    message: str

def _build_pb_request(lat: float, lng: float, display_languages: List[str]) -> PlaceRequest:  # Changed from lon to lng
    """Build protobuf request for reverse geocoding."""
    pr = PlaceRequest()
    pr.display_language.extend(display_languages)
    pr.client_metadata.supported_maps_result_type.append(MapsResultType.MAPS_RESULT_TYPE_PLACE)
    pr.request_type = RequestType.REQUEST_TYPE_REVERSE_GEOCODING
    pr.place_request_parameters.reverse_geocoding_parameters.preserve_original_location = True
    pr.place_request_parameters.reverse_geocoding_parameters.extended_location.lat_lng.lat = lat
    pr.place_request_parameters.reverse_geocoding_parameters.extended_location.lat_lng.lng = lng  # Changed from lon to lng
    pr.place_request_parameters.reverse_geocoding_parameters.extended_location.vertical_accuracy = -1
    pr.place_request_parameters.reverse_geocoding_parameters.extended_location.heading = -1

    rc = PlaceRequest_pb2.ComponentInfo()
    rc.type = Shared_pb2.ComponentType.ADDRESS_OBJECT
    rc.count = 1
    pr.request_component.append(rc)
    return pr

def reverse_geocode(lat: float, lng: float, display_language: List[str], session: Session = None) -> Dict[str, str]:  # Changed from lon to lng
    """
    Reverse geocode coordinates using Apple Maps.
    
    Args:
        lat: Latitude
        lng: Longitude  # Changed from lon to lng
        display_language: List of language codes (e.g., ["en-US"])
        session: Optional requests session
        
    Returns:
        Dictionary containing address components
    """
    try:
        auth = Authenticator()  # Use the same authenticator as for panoramas
        pb_request = _build_pb_request(lat, lng, display_language)  # Changed from lon to lng
        pb_response = auth.make_ticket_request(pb_request.SerializeToString(), session)
        response = PlaceResponse_pb2.PlaceResponse()
        response.ParseFromString(pb_response)
        address = response.maps_result.place.component[0].value[0].address_object.address_object.place.address
        
        return {
            "formatted": list(address.formatted_address),
            "city": address.address_components.locality,
            "country": address.address_components.country,
            "country_code": address.address_components.country_code,
            "administrative_area": address.address_components.administrative_area,
        }
    except Exception as e:
        logger.error(f"Error in reverse geocoding: {str(e)}")
        return None

def normalize_address(address: str) -> str:
    """
    Normalize address string for comparison by removing common differences.
    
    Args:
        address: Address string to normalize
        
    Returns:
        Normalized address string
    """
    # Convert to lowercase
    normalized = address.lower()
    
    # Remove common abbreviations
    replacements = {
        'avenue': 'ave',
        'street': 'st',
        'road': 'rd',
        'boulevard': 'blvd',
        'drive': 'dr',
        'lane': 'ln',
        'court': 'ct',
        'circle': 'cir',
        'highway': 'hwy',
        'parkway': 'pkwy',
    }
    
    for full, abbr in replacements.items():
        normalized = normalized.replace(full, abbr)
        normalized = normalized.replace(f"{abbr}.", abbr)
    
    # Remove punctuation except commas (needed for address parts)
    normalized = ''.join(c for c in normalized if c.isalnum() or c.isspace() or c == ',')
    
    # Remove extra whitespace
    normalized = ' '.join(normalized.split())
    
    return normalized

def validate_coordinates(coord: Coordinate, original_address: str) -> Optional[ValidationWarning]:
    """
    Validates coordinates by reverse geocoding with Apple's service and comparing addresses.
    
    Args:
        coord: The coordinates to validate
        original_address: The original input address to compare against
        
    Returns:
        ValidationWarning if addresses don't match, None if they match or can't validate
    """
    try:
        # Use Apple's reverse geocoding to get address
        apple_address = reverse_geocode(coord.lat, coord.lng, display_language=["en-US"])  # Changed from lon to lng
        if not apple_address:
            return None
            
        formatted_apple_address = ", ".join(apple_address["formatted"])
        
        # Normalize both addresses for comparison
        normalized_input = normalize_address(original_address)
        normalized_apple = normalize_address(formatted_apple_address)
        
        # Compare normalized addresses
        if normalized_input != normalized_apple:
            # Check if at least the city and state match
            input_parts = normalized_input.split(',')
            apple_parts = normalized_apple.split(',')
            
            # Extract city and state from both addresses (assuming they're in the last parts)
            input_location = ','.join(input_parts[-2:]) if len(input_parts) >= 2 else normalized_input
            apple_location = ','.join(apple_parts[-2:]) if len(apple_parts) >= 2 else normalized_apple
            
            # If even the city/state don't match, return a warning
            if input_location.strip() != apple_location.strip():
                return ValidationWarning(
                    input_address=original_address,
                    found_address=formatted_apple_address,
                    message="Address mismatch detected between input and Apple's reverse geocoding"
                )
        
        return None
        
    except Exception as e:
        logger.error(f"Error validating coordinates: {str(e)}")
        return None 