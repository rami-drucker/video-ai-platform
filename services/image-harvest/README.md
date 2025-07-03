# Image Harvest Service

## Service Overview

The Image Harvest Service is a microservice designed to fetch panoramic street images from various street-level imagery services, starting with Apple Look Around and expanding to include Google Street View. It serves as a critical component of the Video AI Platform by providing high-quality source imagery for video generation.

## Key Features

1. **Multi-Source Image Collection**:
   - Apple Look Around panoramas (primary source)
   - Google Street View (planned)
   - Support for additional providers in future

2. **Flexible Location Input**:
   - Single location via coordinates `[lat, lng]`
   - Address-based location lookup
   - Route-based collection with multiple waypoints
   - Support for mixed input types in routes

3. **Image Processing**:
   - Platform-optimized HEIC decoding
   - Automatic format conversion
   - Metadata preservation
   - Unique filename generation

4. **Integration Support**:
   - RESTful API interface
   - Swagger/OpenAPI documentation
   - Comprehensive error handling
   - Detailed response metadata

## Technical Architecture

### Core Dependencies

The service is built on several key libraries:

1. **streetlevel** ([GitHub](https://github.com/sk-zk/streetlevel)):
   - Primary library for accessing street-level imagery
   - No API keys required (uses internal APIs)
   - Supports multiple imagery services
   - Note: May require updates due to API changes

2. **lookaround-map** ([GitHub](https://github.com/sk-zk/lookaround-map)):
   - Reference implementation for Apple Look Around integration
   - Address translation and geocoding
   - Panorama downloading capabilities

3. **HEIC Decoders** (Platform-specific optimization):
   - **macOS**: 
     1. `pyheif` (preferred, faster)
     2. `pillow-heif` (fallback)
   - **Linux**:
     1. `heic2rgb` (fastest)
     2. `pyheif`
     3. `pillow-heif` (fallback)
   - **Windows**:
     1. `heic2rgb` (preferred)
     2. `pillow-heif` (fallback)

## Installation

1. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
.\venv\Scripts\activate   # On Windows
```

2. Install base dependencies:
```bash
pip install -r requirements.txt
```

3. Install platform-specific HEIC decoder:

macOS:
```bash
brew install libheif
pip install pyheif
```

Linux:
```bash
# Option 1 (Recommended)
pip install heic2rgb

# Option 2
apt-get install libheif-dev
pip install pyheif
```

Windows:
```bash
# Option 1 (Recommended)
pip install heic2rgb

# Option 2
pip install pillow-heif
```

## API Reference

### Endpoints

#### Health Check
```
GET /health
```

#### Harvest Images
```
POST /harvest
```

Request Formats:

1. Single Location (Coordinates):
```json
{
    "coordinates": {
        "lat": 37.7749,
        "lng": -122.4194
    }
}
```

2. Single Location (Address):
```json
{
    "address": "1600 Amphitheatre Parkway, Mountain View, CA"
}
```

3. Route (Mixed Format):
```json
{
    "route": [
        {
            "lat": 37.7749,
            "lng": -122.4194
        },
        "1600 Amphitheatre Parkway, Mountain View, CA",
        {
            "lat": 37.4220,
            "lng": -122.0841
        }
    ]
}
```

Response Format:
```json
{
    "file_paths": [
        "/app/images/raw/123e4567-e89b-12d3-a456-426614174000.jpg"
    ],
    "metadata": {
        "/app/images/raw/123e4567-e89b-12d3-a456-426614174000.jpg": {
            "id": "ABC123",
            "build_id": "123456",
            "coordinates": {
                "lat": 37.7749,
                "lng": -122.4194
            },
            "heading_degrees": 340.40,
            "heading_radians": 0.3421,
            "elevation": 224.069,
            "date": "2024-03-15T12:00:00",
            "source_format": "heic",
            "output_format": "jpg",
            "distance_meters": 7.65
        }
    }
}
```

## Storage Structure

Images are stored in the following directory structure:

```
/images/
  └── raw/          # Raw downloaded images
      ├── *.jpg     # Converted panorama images
      └── *.meta    # Associated metadata files
```

## Testing

### Server Management

Follow these steps in order when you need to restart the server to reflect changes:

1. **Check Server Status**:
```bash
# Check if server is running on port 8000
lsof -i :8000  # On macOS/Linux
netstat -ano | findstr :8000  # On Windows

# If running, you'll see output like:
# macOS/Linux: Python  1234 user   TCP *:8000
# Windows: TCP    127.0.0.1:8000    0.0.0.0:0    LISTENING    1234
```

2. **Stop Running Server** (if one is found):
```bash
# Stop the server using the process ID (PID)
kill -9 $(lsof -t -i:8000)  # On macOS/Linux
taskkill /PID <PID> /F  # On Windows, replace <PID> with actual process ID
```

3. **Reset Environment**:
```bash
# Deactivate current virtual environment (if active)
deactivate

# Clean temporary files (optional)
rm -rf images/raw/*  # Clear downloaded images
rm -rf __pycache__   # Clear Python cache

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
.\venv\Scripts\activate   # On Windows
```

4. **Start Server**:
```bash
# Navigate to service directory (if not already there)
cd services/image-harvest

# Start server with auto-reload for development
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. **Verify Server Health**:
```bash
# Check server health
curl http://localhost:8000/health

# Expected response:
{"status": "healthy", "timestamp": "..."}
```

### Troubleshooting

Common issues and solutions:

- **"Address already in use" Error**:
  - Cause: Server is already running
  - Solution: Follow steps 1-2 above to check status and stop server

- **"Command not found: python"**:
  - Cause: Virtual environment not activated
  - Solution: Follow step 3 above to reset environment

- **HEIC Decoder Errors**:
  - Cause: Missing system dependencies
  - Solution: See Installation section for your OS-specific decoder setup

- **Server Not Responding**:
  - Cause: Server process may be hung
  - Solution: Follow all steps 1-5 above for a complete restart

### Unit Tests

Run the test suite:
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests with coverage
pytest tests/ --cov=app --cov-report=term-missing
```

### Integration Tests

1. Start the service:
```bash
python -m uvicorn app.main:app --reload
```

2. Use Swagger UI for manual testing:
   - Access: http://localhost:8000/docs
   - Try the /harvest endpoint with sample payloads

3. Use cURL for automated testing:
```bash
# Test with coordinates
curl -X POST http://localhost:8000/harvest \
  -H "Content-Type: application/json" \
  -d '{"coordinates":{"lat":37.7749,"lng":-122.4194}}'

# Test with address
curl -X POST http://localhost:8000/harvest \
  -H "Content-Type: application/json" \
  -d '{"address":"1600 Amphitheatre Parkway, Mountain View, CA"}'
```

## Understanding Heading Values

The service provides heading information in two formats:

1. `heading_degrees` (0-360°, clockwise from North):
   - 0° = North
   - 90° = East
   - 180° = South
   - 270° = West
   This matches what you see in Apple Maps and most mapping applications.

2. `heading_radians` (0-2π radians, counter-clockwise from North):
   - 0 rad = North
   - π/2 rad ≈ 1.57 rad = West
   - π rad ≈ 3.14 rad = South
   - 3π/2 rad ≈ 4.71 rad = East
   This is the raw value from the Look Around API.

## Development Notes

1. **API Stability**:
   - streetlevel library uses internal APIs
   - Monitor for API changes and updates
   - Consider implementing API change detection

2. **Performance Optimization**:
   - Use platform-specific HEIC decoders
   - Implement caching for frequently accessed areas
   - Consider parallel downloads for route-based requests

3. **Error Handling**:
   - Implement retries for transient failures
   - Cache successful responses
   - Log detailed error information

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Insert License Information] 