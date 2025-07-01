# Image Harvest Service

A microservice for fetching panoramic street images from Apple Look Around and converting them to JPG format.

## Features

- Fetch panoramic images from Apple Look Around
- Support for coordinates, addresses, and routes
- Automatic HEIC to JPG conversion
- Platform-specific optimizations for HEIC decoding
- Geocoding support for addresses
- Comprehensive test coverage

## Dependencies

The service uses different HEIC decoders based on the platform:

- **macOS**: Uses `pyheif` (faster) with `pillow-heif` as fallback
- **Linux**: Uses `heic2rgb` (fastest) with `pyheif` as second choice and `pillow-heif` as fallback
- **Windows**: Uses `heic2rgb` with `pillow-heif` as fallback

## Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
.\venv\Scripts\activate   # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Platform-specific optimizations:

For macOS:
```bash
brew install libheif
pip install pyheif
```

For Linux/Windows (optional, for better performance):
```bash
pip install heic2rgb
```

## Usage

### Running the Service

1. Start the service:
```bash
python -m uvicorn app.main:app --reload
```

2. The service will be available at `http://localhost:8000`

### API Endpoints

#### Health Check
```
GET /health
```

#### Harvest Images
```
POST /harvest
```

Request body formats:

1. Single coordinate:
```json
{
    "coordinates": {
        "lat": 37.7749,
        "lng": -122.4194
    }
}
```

2. Address:
```json
{
    "address": "1600 Amphitheatre Parkway, Mountain View, CA"
}
```

3. Route:
```json
{
    "route": [
        {
            "lat": 37.7749,
            "lng": -122.4194
        },
        "1600 Amphitheatre Parkway, Mountain View, CA"
    ]
}
```

Response format:
```json
{
    "file_paths": [
        "/app/images/raw/123e4567-e89b-12d3-a456-426614174000.jpg"
    ],
    "metadata": {
        "/app/images/raw/123e4567-e89b-12d3-a456-426614174000.jpg": {
            "pano_id": "ABC123",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "timestamp": "2024-03-15T12:00:00",
            "heading": 180.0,
            "source_format": "heic",
            "output_format": "jpg",
            "decoder_used": "pyheif",
            "quality": 95
        }
    }
}
```

## Testing Documentation

### Server Management

1. Starting the Server:
```bash
# Navigate to service directory and activate virtual environment
cd services/image-harvest
source venv/bin/activate

# Start server with auto-reload (development)
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start server without auto-reload (production)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

2. Server Health Checks:
   - Via Browser: Navigate to `http://localhost:8000/health`
   - Via cURL: `curl http://localhost:8000/health`
   - Via Swagger UI: Access `http://localhost:8000/docs` and try the /health endpoint
   - Expected Response: `{"status": "healthy", "timestamp": "..."}`

3. Server Management:
   - Check if server is running: `lsof -i :8000`
   - Kill existing server: `kill -9 $(lsof -t -i:8000)`
   - Change ports if needed: Use `--port 8001` or other available port
   - Monitor logs: Server logs are output to console in real-time

### Testing Methods

1. Swagger UI Testing (GUI):
   - Access Swagger interface at `http://localhost:8000/docs`
   - Expand the POST /harvest endpoint
   - Click "Try it out"
   - Input test data:
     ```json
     {
       "coordinates": {
         "lat": 37.7749,
         "lng": -122.4194
       }
     }
     ```
     or
     ```json
     {
       "address": "57 Pantano Dr, Thornhill, ON L4J 0B2, Canada"
     }
     ```
   - Click "Execute"
   - Check response status and body

2. cURL Testing (CLI):
```bash
# Test with coordinates
curl -X 'POST' \
  'http://localhost:8000/harvest' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "coordinates": {
      "lat": 37.7749,
      "lng": -122.4194
    }
  }'

# Test with address
curl -X 'POST' \
  'http://localhost:8000/harvest' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "address": "57 Pantano Dr, Thornhill, ON L4J 0B2, Canada"
  }'
```

3. Python Testing:
```python
import requests
import json

# Test coordinates
response = requests.post(
    'http://localhost:8000/harvest',
    json={
        'coordinates': {
            'lat': 37.7749,
            'lng': -122.4194
        }
    }
)
print(json.dumps(response.json(), indent=2))

# Test address
response = requests.post(
    'http://localhost:8000/harvest',
    json={
        'address': '57 Pantano Dr, Thornhill, ON L4J 0B2, Canada'
    }
)
print(json.dumps(response.json(), indent=2))
```

### Troubleshooting

1. Common Issues:
   - "Address already in use": Another instance is running on the port
     - Solution: Kill existing process or use different port
   - "Command not found: python": Virtual environment not activated
     - Solution: Run `source venv/bin/activate`
   - HEIC decoder errors: Missing system dependencies
     - Solution: Install libheif (`brew install libheif` on macOS)

2. Verifying Results:
   - Check output directory for downloaded images
   - Verify image metadata in response
   - Confirm image format conversion (HEIC → JPG)
   - Validate coordinates in metadata match request

3. Performance Testing:
   - Monitor response times
   - Check memory usage during image processing
   - Verify cleanup of temporary HEIC files
   - Test concurrent requests

## Testing

Run the test suite:
```bash
pytest tests/
```

## Docker

Build and run with Docker:

```bash
docker build -t image-harvest .
docker run -p 8000:8000 image-harvest
```

## Notes

- Images are stored in the `/app/images/raw` directory
- The service automatically selects the best HEIC decoder for your platform
- All images are converted to high-quality JPG (quality=95)
- Address geocoding uses OpenStreetMap's Nominatim service 