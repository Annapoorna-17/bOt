# Multi-tenant RAG Service

Multi-tenant RAG (Retrieval Augmented Generation) service built with FastAPI. The system allows multiple companies (tenants) to upload various document formats, scrape websites, and query them using OpenAI embeddings + Pinecone vector search, with strict tenant isolation.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file with your credentials:
```env
# Required
OPENAI_API_KEY=your_openai_key
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=your_index_name

# Database (MySQL)
DATABASE_URL=mysql+pymysql://user:password@host:port/dbname
# OR
DB_USER=your_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=rag_db

# Optional
SUPERADMIN_TOKEN=your_custom_token
```

### 3. Run the Application

**Easiest method** - Just run on port 8000:
```bash
# Windows
run.bat

# Linux/Mac
./run.sh

# Or directly
python run.py
```

The application will start on **http://localhost:8000** by default.

**Custom configuration**:
```bash
# Run on different port
PORT=8080 python run.py

# Disable auto-reload for production
RELOAD=false PORT=8000 python run.py
```

### 4. Access the API

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/healthz

## Features

- **Multi-format document support**: PDF, DOCX, XLSX, PPTX, CSV, TXT, MD, and more
- **GPT-4o Vision integration**: Extracts text from images, charts, and diagrams
- **Website scraping**: Full content and image analysis
- **Multi-tenant isolation**: Company-level data separation
- **Role-based access control**: Admin and user roles
- **Refined answer generation**: Clean, formatted responses

## API Usage

See [CLAUDE.md](CLAUDE.md) for detailed API documentation and testing examples.

### Quick Example

1. Create a company (superadmin):
```bash
curl -X POST http://localhost:8000/superadmin/companies \
  -H "Authorization: Bearer B946C6F2747914D24C1F6C74F5AB5291" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Corp", "tenant_code": "test1"}'
```

2. Upload a document:
```bash
curl -X POST http://localhost:8000/t/test1/documents/upload \
  -H "X-User-Code: test1-user1" \
  -H "X-API-Key: <your_api_key>" \
  -F "file=@document.pdf"
```

3. Query:
```bash
curl -X POST http://localhost:8000/t/test1/query \
  -H "X-User-Code: test1-user1" \
  -H "X-API-Key: <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this about?", "top_k": 5}'
```

## Deployment

The application is configured to run on **port 8000** by default, making it easy to deploy.

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build and run manually
docker build -t rag-service .
docker run -p 8000:8000 --env-file .env rag-service
```

The service will be available at http://localhost:8000

### Cloud Deployment

- **AWS/GCP/Azure**: The app runs on port 8000 by default
- **Environment**: Copy `.env.example` to `.env` and configure
- **Health check**: Use `/healthz` endpoint
- **Reverse proxy**: Forward to port 8000

### Production Settings

```bash
# Disable auto-reload for production
RELOAD=false python run.py

# Or set in .env
RELOAD=false
```

## Documentation

- [CLAUDE.md](CLAUDE.md) - Complete architecture and API documentation
- [/docs](http://localhost:8000/docs) - Interactive API documentation (Swagger UI)
