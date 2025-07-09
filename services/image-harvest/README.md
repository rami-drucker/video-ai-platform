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
   - Note: Version 0.12.3 or higher required

2. **lookaround-map** ([GitHub](https://github.com/sk-zk/lookaround-map)):
   - Reference implementation for Apple Look Around integration
   - Address translation and geocoding
   - Panorama downloading capabilities

3. **HEIC Decoders** (Platform-specific optimization):
   - **macOS**: 
     1. `pillow-heif` (primary decoder, works on all platforms)
     2. `pyheif` (faster alternative, requires libheif)
     3. `heic2rgb` (alternative decoder)
   - **Linux**:
     1. `pillow-heif` (primary decoder)
     2. `pyheif` (faster alternative, requires libheif)
     3. `heic2rgb` (fastest alternative)
   - **Windows**:
     1. `pillow-heif` (primary decoder)
     2. `heic2rgb` (alternative decoder)

## Installation

1. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
.\venv\Scripts\activate   # On Windows
```

2. Install base dependencies:
```bash
pip install -r requirements.txt
```

3. Install HEIC decoder(s):

macOS:
```bash
# Option 1: Basic setup (recommended for most users)
pip install pillow-heif  # Primary decoder, works everywhere

# Option 2: Performance optimized setup
brew install libheif     # Required for pyheif
pip install pyheif       # Faster alternative

# Option 3: Alternative decoder
pip install heic2rgb     # Another alternative
```

Linux:
```bash
# Option 1: Basic setup (recommended for most users)
pip install pillow-heif  # Primary decoder

# Option 2: Performance optimized setup
apt-get install libheif-dev  # Required for pyheif
pip install pyheif          # Faster alternative

# Option 3: Alternative decoder
pip install heic2rgb        # Fastest alternative
```

Windows:
```bash
# Option 1: Basic setup (recommended for most users)
pip install pillow-heif  # Primary decoder

# Option 2: Alternative decoder
pip install heic2rgb     # Alternative
```

## Coverage Limitations

Please note that this service currently uses Apple Look Around as its primary source. Not all locations have Look Around coverage. You can verify coverage for a location by:

1. Checking the location in Apple Maps and looking for the binoculars icon
2. Using nearby street addresses if the exact location doesn't have coverage
3. Using the API's error messages which will indicate if coverage is not available

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
        "lat": 37.33264,
        "lng": -122.00500
    }
}
```

2. Single Location (Address):
```json
{
    "address": "10600 N Tantau Ave, Cupertino, CA 95014"
}
```

Response Format:
```json
{
    "file_paths": [
        "output/pano_20250709_164332.jpg"
    ],
    "metadata": {
        "output/pano_20250709_164332.jpg": {
            "id": 9074420710046177000,
            "build_id": 2147484711,
            "coordinates": {
                "lat": 37.331488105514744,
                "lng": -122.0058334013995
            },
            "heading_degrees": 358.025925143304,
            "heading_radians": 0.03445410593018052,
            "elevation": 50.54765059317637,
            "date": "2024-04-06T18:51:11.829000+00:00",
            "source_format": "heic",
            "output_format": "jpg",
            "distance_meters": 12.073362544840592
        }
    }
}
```

### Understanding Heading Values

The service provides heading information in two formats:

1. `heading_degrees` (0-360°, clockwise from North):
   - 0° = North
   - 90° = East
   - 180° = South
   - 270° = West

   This format matches what you see in Apple Maps and most mapping applications. For example, a value of 358.025925° (as seen in the example response) means the camera is facing almost directly North, slightly towards the East.

2. `heading_radians` (0-2π radians):
   - 0 rad = North
   - π/2 rad ≈ 1.57 rad = East
   - π rad ≈ 3.14 rad = South
   - 3π/2 rad ≈ 4.71 rad = West

   This is the raw value from the Look Around API. For example, a value of 0.03445410593018052 radians (as seen in the example response) corresponds to approximately 1.97 degrees, meaning the camera is facing almost directly North.

Note: The heading values are always provided in both formats for convenience, and they represent the same direction. You can convert between them using:
- Degrees to Radians: `radians = degrees * (π/180)`
- Radians to Degrees: `degrees = radians * (180/π)`

## Storage Structure

Images are stored in the following directory structure:

```
/output/          # Output directory for panorama images
    ├── *.jpg     # Converted panorama images
    └── *.heic    # Temporary HEIC files (automatically cleaned up)
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

3. **Reset Environment** (if needed):
```bash
# Deactivate current virtual environment (if active)
deactivate

# Clean temporary files (optional but recommended for fresh start)
rm -rf output/*         # Clear downloaded images
rm -rf __pycache__     # Clear Python cache
rm -rf .pytest_cache   # Clear pytest cache

# Reactivate virtual environment
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

### Testing with Swagger UI

1. Start the server as described above
2. Open http://localhost:8000/docs in your browser
3. Try the /harvest endpoint with these sample locations:
   ```json
   {
       "address": "10600 N Tantau Ave, Cupertino, CA 95014"
   }
   ```
   or
   ```json
   {
       "coordinates": {
           "lat": 37.33264,
           "lng": -122.00500
       }
   }
   ```

### Troubleshooting

Common issues and solutions:

- **"No panoramas found" Error**:
  - Cause: No street-level imagery available at the location
  - Solution: Try a nearby street address or verify coverage in the area

- **HEIC Decoder Errors**:
  - Cause: Missing system dependencies
  - Solution 1: Ensure pillow-heif is installed (primary decoder)
  - Solution 2: Try installing pyheif (Linux/Mac) or heic2rgb as alternatives
  - Solution 3: Check system dependencies (libheif) if using pyheif

- **Server Not Responding**:
  - Cause: Server process may be hung
  - Solution: Follow server management steps above for a complete restart

- **"Address already in use" Error**:
  - Cause: Server is already running
  - Solution: Follow steps 1-2 above to check status and stop server

- **"Command not found: python"**:
  - Cause: Virtual environment not activated
  - Solution: Follow step 3 above to reset environment

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
# Test with coordinates (Apple Park Visitor Center)
curl -X POST http://localhost:8000/harvest \
  -H "Content-Type: application/json" \
  -d '{"coordinates":{"lat":37.33264,"lng":-122.00500}}'

# Test with address
curl -X POST http://localhost:8000/harvest \
  -H "Content-Type: application/json" \
  -d '{"address":"10600 N Tantau Ave, Cupertino, CA 95014"}'

# Test health endpoint
curl http://localhost:8000/health
```

Expected responses:

1. Health Check:
```json
{
    "status": "ok"
}
```

2. Successful Harvest:
```json
{
    "file_paths": [
        "output/pano_20250709_164332.jpg"
    ],
    "metadata": {
        "output/pano_20250709_164332.jpg": {
            "id": 9074420710046177000,
            "build_id": 2147484711,
            "coordinates": {
                "lat": 37.331488105514744,
                "lng": -122.0058334013995
            },
            "heading_degrees": 358.025925143304,
            "heading_radians": 0.03445410593018052,
            "elevation": 50.54765059317637,
            "date": "2024-04-06T18:51:11.829000+00:00",
            "source_format": "heic",
            "output_format": "jpg",
            "distance_meters": 12.073362544840592
        }
    }
}
```

3. No Coverage Error:
```json
{
    "detail": "No panoramas found within 50 meters of the location"
}
```

4. No Panoramas Error:
```json
{
    "detail": "No panoramas found at this location"
}
```

Note: The actual values in the response (coordinates, heading, etc.) will vary based on the exact location and available panoramas.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Insert License Information] 