import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app, Coordinate, LocationRequest, download_lookaround_panorama
from PIL import Image
import io

client = TestClient(app)

@pytest.fixture
def mock_streetlevel():
    with patch('streetlevel.lookaround.get_coverage_tile_by_latlon') as mock_coverage, \
         patch('streetlevel.lookaround.get_panorama_face') as mock_face:
        
        # Mock coverage tile response
        mock_pano = MagicMock()
        mock_pano.id = "123"
        mock_pano.build_id = "456"
        mock_pano.lat = 37.7749
        mock_pano.lon = -122.4194
        mock_pano.heading = 180
        mock_pano.elevation = 10
        mock_pano.date = None

        mock_coverage_tile = MagicMock()
        mock_coverage_tile.panoramas = [mock_pano]
        mock_coverage.return_value = mock_coverage_tile

        # Mock panorama face response
        mock_face.return_value = b"fake_heic_data"
        
        yield (mock_coverage, mock_face)

def test_download_lookaround_panorama(mock_streetlevel):
    mock_coverage, mock_face = mock_streetlevel
    
    # Create a test coordinate
    coord = Coordinate(lat=37.7749, lng=-122.4194)

    # Mock PIL Image operations
    with patch('PIL.Image.open') as mock_image_open:
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image

        # Call the function
        file_path, metadata = download_lookaround_panorama(coord)

        # Verify the function called the API correctly
        mock_coverage.assert_called_once_with(37.7749, -122.4194)
        mock_face.assert_called_once()

        # Verify metadata
        assert metadata["id"] == "123"
        assert metadata["build_id"] == "456"
        assert metadata["coordinates"]["lat"] == 37.7749
        assert metadata["coordinates"]["lng"] == -122.4194
        assert metadata["heading"] == 180
        assert metadata["elevation"] == 10
        assert metadata["date"] is None
        assert metadata["source_format"] == "heic"
        assert metadata["output_format"] == "jpg"

def test_harvest_endpoint(mock_streetlevel):
    with patch('PIL.Image.open') as mock_image_open:
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image

        # Test with coordinates
        response = client.post(
            "/harvest",
            json={"coordinates": {"lat": 37.7749, "lng": -122.4194}}
        )
        assert response.status_code == 200
        assert "file_path" in response.json()
        assert "metadata" in response.json()

        # Test with address
        response = client.post(
            "/harvest",
            json={"address": "123 Main St"}
        )
        assert response.status_code == 200
        assert "file_path" in response.json()
        assert "metadata" in response.json()

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_harvest_with_coordinates(mock_streetlevel):
    request = LocationRequest(
        coordinates=Coordinate(lat=37.7749, lng=-122.4194)
    )
    response = client.post("/harvest", json=request.model_dump())
    assert response.status_code == 200
    data = response.json()
    assert "file_paths" in data
    assert "metadata" in data
    assert len(data["file_paths"]) == 1
    assert data["metadata"][data["file_paths"][0]]["source_format"] == "heic"
    assert data["metadata"][data["file_paths"][0]]["output_format"] == "jpg"

def test_harvest_with_address(mock_streetlevel):
    with patch('geocoder.osm') as mock_geocoder:
        # Mock the geocoder response
        mock_location = Mock()
        mock_location.ok = True
        mock_location.lat = 37.7749
        mock_location.lng = -122.4194
        mock_geocoder.return_value = mock_location
        
        request = LocationRequest(
            address="1600 Amphitheatre Parkway, Mountain View, CA"
        )
        response = client.post("/harvest", json=request.model_dump())
        assert response.status_code == 200
        data = response.json()
        assert "file_paths" in data
        assert "metadata" in data
        assert len(data["file_paths"]) == 1

def test_harvest_with_route(mock_streetlevel):
    with patch('geocoder.osm') as mock_geocoder:
        # Mock the geocoder response
        mock_location = Mock()
        mock_location.ok = True
        mock_location.lat = 37.7749
        mock_location.lng = -122.4194
        mock_geocoder.return_value = mock_location
        
        request = LocationRequest(
            route=[
                Coordinate(lat=37.7749, lng=-122.4194),
                "1600 Amphitheatre Parkway, Mountain View, CA"
            ]
        )
        response = client.post("/harvest", json=request.model_dump())
        assert response.status_code == 200
        data = response.json()
        assert "file_paths" in data
        assert "metadata" in data
        assert len(data["file_paths"]) == 2

def test_invalid_request():
    request = LocationRequest()  # Empty request
    response = client.post("/harvest", json=request.model_dump())
    assert response.status_code == 400
    assert "Must provide either coordinates, address, or route" in response.json()["detail"]

def test_geocoding_failure():
    with patch('geocoder.osm') as mock_geocoder:
        # Mock geocoding failure
        mock_location = Mock()
        mock_location.ok = False
        mock_geocoder.return_value = mock_location
        
        request = LocationRequest(
            address="Invalid Address That Should Fail"
        )
        response = client.post("/harvest", json=request.model_dump())
        assert response.status_code == 400
        assert "Could not geocode address" in response.json()["detail"]

def test_no_panoramas_found(mock_streetlevel):
    # Configure mock to return no panoramas
    mock_streetlevel.return_value.get_panoramas_by_location.return_value = []
    
    request = LocationRequest(
        coordinates=Coordinate(lat=37.7749, lng=-122.4194)
    )
    response = client.post("/harvest", json=request.model_dump())
    assert response.status_code == 500
    assert "No panoramas found at this location" in response.json()["detail"] 