from dataclasses import dataclass
from typing import Optional, List, Dict
import logging
from requests import Session
import requests  # ADD THIS IMPORT
import io  # ADD THIS IMPORT
import struct

# Remove this line: from streetlevel.lookaround import Authenticator
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

# Add the ticket system (copied from lookaround-map viewer)
@dataclass
class TicketRequestHeader:
    version_maybe: int = 1
    locale: str = "en"
    app_identifier: str = "com.apple.geod"
    os_version: str = "11.7.5.20G1225"
    unknown: int = 60

# Add these classes after the existing dataclasses
@dataclass
class TicketResponseHeader:
    version_maybe: int
    unknown: int

@dataclass
class TicketResponse:
    header: TicketResponseHeader
    payload: bytes

# Add BinaryReader class after BinaryWriter
class BinaryReader:
    def __init__(self, base_stream: io.BytesIO):
        self.bs = base_stream

    def read(self, size: int) -> bytes:
        return self.bs.read(size)

    def read_uint2_be(self) -> int:
        return int.from_bytes(self.bs.read(2), byteorder="big", signed=False)

    def read_uint4_be(self) -> int:
        return int.from_bytes(self.bs.read(4), byteorder="big", signed=False)


class BinaryWriter:
    def __init__(self, base_stream: io.BytesIO):
        self.bs = base_stream

    @property
    def content(self) -> bytes:
        return self.bs.getvalue()

    def write(self, b: bytes):
        self.bs.write(b)

    def write_uint2_be(self, n: int):
        self.bs.write(struct.pack(">H", n))

    def write_uint4_be(self, n: int):
        self.bs.write(struct.pack(">I", n))

def _write_pascal_string_be(writer: BinaryWriter, value: str, encoding: str = "utf-8") -> None:
    value_bytes = value.encode(encoding)
    writer.write_uint2_be(len(value_bytes))
    writer.write(value_bytes)

def serialize_ticket_request(header: TicketRequestHeader, payload: bytes) -> bytes:
    w = BinaryWriter(io.BytesIO())
    w.write_uint2_be(header.version_maybe)
    _write_pascal_string_be(w, header.locale)
    _write_pascal_string_be(w, header.app_identifier)
    _write_pascal_string_be(w, header.os_version)
    w.write_uint4_be(header.unknown)
    w.write_uint4_be(len(payload))
    w.write(payload)
    return w.content

# Add this function after serialize_ticket_request
def deserialize_ticket_response(response: bytes) -> TicketResponse:
    """
    Deserializes a ticket response.
    """
    r = BinaryReader(io.BytesIO(response))
    header = TicketResponseHeader(
        version_maybe=r.read_uint2_be(),
        unknown=r.read_uint4_be()
    )
    length = r.read_uint4_be()
    payload = r.read(length)
    return TicketResponse(header=header, payload=payload)

# Update the make_ticket_request function
def make_ticket_request(payload: bytes, session: Session = None) -> bytes:
    """
    Makes a request against dispatcher.arpc with the given payload.
    """
    header = TicketRequestHeader()
    request_body = serialize_ticket_request(header, payload)
    requester = session if session else requests
    http_response = requester.post("https://gsp-ssl.ls.apple.com/dispatcher.arpc", data=request_body)
    # Change this line to properly deserialize the response
    response_ticket = deserialize_ticket_response(http_response.content)
    return response_ticket.payload  # Return the payload, not the raw content

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
        # Remove this line: auth = Authenticator()  # Use the same authenticator as for panoramas
        pb_request = _build_pb_request(lat, lng, display_language)  # Changed from lon to lng
         # Change this line: pb_response = auth.make_ticket_request(pb_request.SerializeToString(), session)
        pb_response = make_ticket_request(pb_request.SerializeToString(), session)
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

from .utils import normalize_address

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