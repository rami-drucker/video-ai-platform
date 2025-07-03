# Video AI Platform

An AI-powered video generation platform that creates interactive video experiences from street-view panoramas and geographic locations.

## Architecture

The platform consists of several microservices:

### Core Services

#### [`image-harvest`](services/image-harvest/README.md)
A critical service that fetches high-quality panoramic street images from various providers:
- Supports Apple Look Around (primary) and Google Street View (planned)
- Handles single locations (coordinates/addresses) and multi-point routes
- Platform-optimized image processing with HEIC decoding
- Detailed metadata including precise heading and positioning
- [View detailed documentation](services/image-harvest/README.md)

#### Other Services
- `image-enhance`: Pre-processes and enhances raw images
- `gis-extract`: Obtains location metadata and GIS data
- `video-generator`: Generates video clips using Gen-3/DynamiCrafter
- `video-qa-service`: Performs quality verification using LLM
- `prompt-optimizer`: Refines text prompts and modifies keyframes
- `video-assembler`: Post-processes and concatenates video clips
- `storage-service`: Manages video and metadata storage
- `api-gateway`: Serves REST/GraphQL API and handles auth
- `multimodal-orchestrator`: Orchestrates workflow across services
- `job-scheduler`: Manages async jobs and retries

Frontend applications:
- `backoffice-ui`: Admin dashboard
- `client-ui`: User dashboard
- `video-viewer`: Interactive video/panorama viewer

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 18+
- OpenAI API key (for GPT-4V)
- Google Maps API key (for street view)

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/video-ai-platform.git
cd video-ai-platform
```

2. Copy example environment file:
```bash
cp .env.example .env
```

3. Update environment variables in `.env`

4. Start the services:
```bash
docker-compose up -d
```

5. Visit:
- Client UI: http://localhost:3000
- Admin UI: http://localhost:3001
- API docs: http://localhost:8000/docs

## Development

### Backend Services

Each service follows a standard structure:
```
service-name/
├── app/
│   ├── main.py
│   ├── api/
│   ├── core/
│   └── models/
├── tests/
├── Dockerfile
└── requirements.txt
```

### Frontend Applications

Frontend apps use Vite + React + TypeScript + Tailwind CSS:
```
frontend-app/
├── src/
│   ├── components/
│   ├── pages/
│   └── App.tsx
├── package.json
└── vite.config.ts
```

### Running Tests

```bash
# Backend tests
make test-backend

# Frontend tests
make test-frontend
```

## API Documentation

- REST API docs: http://localhost:8000/docs
- GraphQL playground: http://localhost:8000/graphql

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 