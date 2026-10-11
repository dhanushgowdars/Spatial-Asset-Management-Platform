<!-- GEOINSIGHT_REVIEWER_LANDING_V1 -->
# GeoInsight — Geospatial File Measurement & Spatial Analysis

**Aereo internship assignment | FastAPI + React | Live, reproducible GIS measurements**

**[Open the live GeoInsight application](https://geoinsight-aereo.onrender.com/geospatial)** · **[REST API documentation](https://geoinsight-aereo.onrender.com/docs)** · **[Health check](https://geoinsight-aereo.onrender.com/health)**

> **Reviewer note:** This section documents the **GeoInsight Aereo assessment** deployed from the `feature/aereo-geospatial-measurements` branch. The earlier Spatial Asset Management Platform is a distinct legacy project in the same repository; its architecture and authentication claims do **not** describe the public GeoInsight assessment API.

## Assessment objective

Import KML or a zipped ESRI Shapefile, identify feature geometries and attributes, and calculate metric **polygon area (m²)** and **line length (m)** in an appropriate **projected CRS**. Preserve Point features without inventing area or length; report missing CRS, invalid coordinates and invalid geometries explicitly. Return inspectable results through a documented REST API.

The implementation also supports GeoJSON and KMZ, quality reporting, interactive maps, survey change detection, parcel topology checks, route/zone intersections and downloadable evidence.

## What to try (3-minute reviewer walkthrough)

| Step | Open | What to check |
| --- | --- | --- |
| 1 | [Measure](https://geoinsight-aereo.onrender.com/geospatial) | Upload the provided KML or zipped Shapefile sample; inspect polygon area, line length, source CRS and projected CRS. |
| 2 | [Survey quality](https://geoinsight-aereo.onrender.com/geospatial/quality) | Inspect successful polygons, non-applicable Points and failed invalid-coordinate records. |
| 3 | [Compare surveys](https://geoinsight-aereo.onrender.com/geospatial/compare) | Compare baseline/current polygon samples: approximately 5,000 m² each of added, removed and unchanged area. |
| 4 | [Topology](https://geoinsight-aereo.onrender.com/geospatial/topology) | Inspect overlapping parcels; optionally add a separate site-reference polygon to evaluate outside/uncovered area. |
| 5 | [Routes & zones](https://geoinsight-aereo.onrender.com/geospatial/routes) | Inspect a 140 m route crossing a zone: 40 m inside and 100 m outside. |
| 6 | [About & guide](https://geoinsight-aereo.onrender.com/geospatial/guide) | See supported formats, methods, limitations and reviewer guidance. |

The browser's bundled examples use the same live backend endpoints as manual file uploads; the displayed numbers are not hard-coded measurement results.

## Architecture and measurement flow

```text
KML / ZIP Shapefile / GeoJSON / KMZ
           |
     FastAPI validation
           |
   Geometry extraction + CRS
           |
  pyproj projection + Shapely
           |
  Metric area/length + QA/evidence
           |
  SQLAlchemy -> PostgreSQL (public deployment)
           |
   REST JSON / CSV / GeoJSON
           |
      React + Leaflet UI
```

- **Frontend:** React and Vite, Leaflet-based interactive mapping.
- **API:** Python 3.11, FastAPI, documented OpenAPI endpoints.
- **Spatial processing:** Shapely, pyproj and supporting vector-file readers; operations are computed in Python, **not PostGIS** for this assessment.
- **Persistence:** SQLAlchemy; PostgreSQL on Render for the public demonstration. Local Docker can use a named SQLite volume when no PostgreSQL URL is supplied.
- **Deployment:** Multi-stage `aereo/Dockerfile` builds React assets and serves frontend/API from one origin with Uvicorn.

**Coordinate-system distinction:** source files may use geographic coordinates such as `EPSG:4326`. Measurements use a suitable *local projected* metric CRS (for the known-size fixtures, `EPSG:32643`); map-ready GeoJSON is expressed in WGS84. Distortion and source-data quality still matter.

## Main API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/files/` | Multipart `file` upload (`.kml`, `.zip` Shapefile, `.geojson`, `.kmz`). |
| `GET` | `/api/files/{file_id}/` | Uploaded-file metadata. |
| `GET` | `/api/files/{file_id}/measurements/` | Feature-level geometry, CRS, measurement and status. |
| `GET` | `/api/files/{file_id}/quality/` | Validation findings and measurement eligibility. |
| `GET` | `/api/files/{file_id}/summary/` | Aggregated dataset summary. |
| `GET` | `/api/files/{file_id}/geojson/` | Map-ready GeoJSON. |
| `GET` | `/api/files/{file_id}/export/?format=csv` | Download CSV (or `format=geojson`). |
| `POST` | `/api/analysis/compare` | Two stored polygon datasets: added/removed/overlap. |
| `POST` | `/api/analysis/topology` | Survey overlap and optional reference boundary check. |
| `POST` | `/api/analysis/route-zones` | Stored route/zone intersection and inside/outside lengths. |
| `GET` | `/health` | Health check that also queries the database. |

Open the [interactive Swagger API docs](https://geoinsight-aereo.onrender.com/docs) for request bodies and response schemas.

### Example: upload from PowerShell

From the repository root, with the live demo URL:

```powershell
$base = 'https://geoinsight-aereo.onrender.com'
$sample = (Resolve-Path '.\frontend\public\samples\c4a_baseline.geojson').Path
$created = curl.exe -fsS -F "file=@$sample" "$base/api/files/" | ConvertFrom-Json
$created.id
Invoke-RestMethod "$base/api/files/$($created.id)/measurements/"
```

Expected for this synthetic 100 m × 100 m sample: **10,000 m²**, **400 m perimeter**, measured status, projected calculation CRS **EPSG:32643**.

## Run locally with Docker

From the repository root:

```powershell
docker build -f aereo/Dockerfile -t geoinsight:release .
docker run --name geoinsight-preview --rm -p 18140:8000 -v geoinsight-results:/data geoinsight:release
```

Open `http://localhost:18140/geospatial`, `http://localhost:18140/docs` and `http://localhost:18140/health`. For managed PostgreSQL, supply `AEREO_DATABASE_URL` securely via the hosting service's environment settings; **never commit connection URLs or credentials**.

## Verification evidence (11 October 2026)

- **81/81** Aereo backend pytest tests passed in the developer's environment.
- **14/14** frontend logic/presentation tests passed in the last reported local run; lint and Vite build passed.
- **37/37** live local API acceptance checks passed using known-size synthetic GIS fixtures, including KML, zipped Shapefile, KMZ, GeoJSON, CRS/QA, comparison, topology, route analysis and export parity.
- Public Render deployment served all **seven** tested page/documentation routes with HTTP 200, and `/health` returned `healthy`.
- Public GeoJSON upload reported `COMPLETED`; CSV exported **10,000 m²** and **400 m**, and the same persisted file ID remained retrievable **after a Render service restart**.
- See test cases in `aereo_tests/`, frontend test modules and included sample datasets. These are verification results for the tested fixtures, not a certificate of field-survey accuracy.

Commands:

```powershell
python -m pytest aereo_tests -q
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend audit --omit=dev --audit-level=high
```

## Scope, security and limitations

- **Public demonstration API:** The GeoInsight assessment endpoints do **not** implement account authentication, access control or application-level rate limiting. Do **not** upload confidential/private surveys. Uploaded result records are accessible using their file IDs. The older asset-management project's JWT/RBAC features do not protect this GeoInsight API.
- Input sizes are limited to **10 MiB** per upload and additional geometry limits are enforced. This is a portfolio/assessment deployment, **not** a multi-tenant production file service.
- Render's free web service can spin down when idle, causing cold-start delays. The free PostgreSQL database is short-lived (30-day expiry) and does not include managed backups.
- Measurements use 2D projected vector geometry. They do **not** provide certified cadastral boundaries, geodesic precision across large regions, raster/DEM processing, drone image reconstruction or enterprise load guarantees.
- Missing coordinate references, invalid geometries and projection issues should be reviewed via QA warnings rather than treated as measured observations.

## Design decisions and future work

A standalone Aereo API preserves the assessment's required endpoints without interfering with the original asset-management backend. Explicit projected-CRS metadata and source-record evidence make results inspectable. Follow-up production work would add authentication, per-user isolation, rate limiting, retention/deletion controls, background jobs, larger-data benchmarking and durable managed backups. Survey accuracy in operational use would require external field/GIS validation.

---

## Previous project documentation

Below is the original **Spatial Asset Management Platform** documentation retained for repository history. It describes a separate backend service and should not be confused with the GeoInsight reviewer deployment above.

# 🌍 Spatial Asset Management Platform

> **A production-ready backend platform for managing, tracking, and analyzing geographically distributed assets using FastAPI, PostgreSQL, and PostGIS.**

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/PostgreSQL-16+-336791?logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/PostGIS-Spatial%20Database-4CAF50" alt="PostGIS" />
  <img src="https://img.shields.io/badge/SQLAlchemy-ORM-D71F00" alt="SQLAlchemy" />
  <img src="https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/Pytest-Tested-0A9EDC" alt="Pytest" />
  <img src="https://img.shields.io/badge/Auth-JWT-orange" alt="JWT" />
  <img src="https://img.shields.io/badge/API-REST-success" alt="REST API" />
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License" />
</p>

---

## Table of Contents

- [Overview](#overview)
- [Project Status](#project-status)
- [Key Highlights](#key-highlights)
- [Objectives](#objectives)
- [Real-World Applications](#real-world-applications)
- [Why This Project](#why-this-project)
- [Feature Showcase](#feature-showcase)
- [Technology Stack](#technology-stack)
- [Design Principles](#design-principles)
- [System Architecture & Workflows](#system-architecture--workflows)
- [Database Design](#database-design)
- [Project Structure](#project-structure)
- [API Documentation](#api-documentation)
- [Getting Started](#getting-started)
- [Project Preview](#project-preview)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Future Enhancements](#future-enhancements)
- [Contributing](#contributing)
- [Author](#author)
- [License](#license)
- [Acknowledgements](#acknowledgements)
- [Support](#support)

---

## Overview

The **Spatial Asset Management Platform** is an enterprise-style backend application designed to manage, monitor, and analyze geographically distributed assets such as **vehicles, drones, IoT devices, sensors, and field equipment**.

Modern organizations increasingly rely on location-aware systems to manage assets like delivery vehicles, drones, surveillance cameras, and sensors — and these systems need more than basic CRUD operations. They need secure access control, accurate geospatial analysis, historical tracking, and a backend architecture that can scale. This platform is built to address exactly that.

It combines secure authentication, geospatial intelligence, asset lifecycle management, analytics, audit logging, and location history into a scalable RESTful backend, following a clean **Layered Architecture** (`API → Service → Repository → Database`). Business logic is fully separated from database operations, keeping the codebase modular, maintainable, and easy to test.

Unlike a typical asset management CRUD app, this platform's spatial capabilities are powered by **PostGIS**, enabling nearby-asset discovery, nearest-asset lookup, geofence detection, buffer analysis, route calculations, polygon operations, and distance measurement — all executed efficiently inside PostgreSQL.

The current implementation is backend-only, but the API is designed to integrate cleanly with any modern frontend framework (React, Angular, Vue), making the platform suitable for full-stack applications in logistics, fleet management, smart cities, agriculture, industrial monitoring, and IoT ecosystems.

**Current Version:** `v1.0.0` &nbsp;|&nbsp; **Project Type:** Backend REST API &nbsp;|&nbsp; **Architecture:** Layered (API → Service → Repository → Database) &nbsp;|&nbsp; **Status:** Production-ready backend

---

## Project Status

| Module                |     Status     |
| --------------------- | :------------: |
| Backend Development   |  ✅ Complete   |
| Authentication & RBAC |  ✅ Complete   |
| Asset Management      |  ✅ Complete   |
| Spatial Operations    |  ✅ Complete   |
| Dashboard APIs        |  ✅ Complete   |
| Analytics APIs        |  ✅ Complete   |
| Audit Logging         |  ✅ Complete   |
| Location History      |  ✅ Complete   |
| Automated Testing     |  ✅ Complete   |
| Docker Support        |  ✅ Complete   |
| Frontend Dashboard    | 🚧 In Progress |

---

## Key Highlights

- ✅ JWT Authentication & Role-Based Access Control (RBAC)
- 📦 Complete asset lifecycle management
- 🌍 Advanced spatial analysis using PostGIS
- ✅ Nearby, nearest & geofence search
- ✅ Buffer, polygon & route analysis
- 📊 Dashboard & analytics APIs
- ✅ Audit logging system
- 🛰️ Location history tracking
- ✅ Pagination, filtering & sorting
- ✅ Comprehensive automated testing with Pytest
- ✅ Dockerized deployment
- 🏗️ Clean, layered architecture

---

## Objectives

The primary goals of this project are to:

- Build a production-style backend using modern Python technologies.
- Design scalable RESTful APIs following industry best practices.
- Demonstrate clean software architecture using the Layered Architecture pattern.
- Integrate PostgreSQL with PostGIS for advanced geospatial processing.
- Implement secure authentication and authorization using JWT and RBAC.
- Develop reusable, maintainable business logic through service and repository layers.
- Perform efficient spatial analysis using optimized PostGIS queries.
- Track asset movement with historical location records.
- Record important system events through audit logging.
- Validate application behavior with comprehensive automated testing.
- Containerize the application with Docker for consistent deployment.

---

## Real-World Applications

The platform is designed to support location-aware systems across multiple industries.

| Industry                   | Example Use Cases                                                 |
| -------------------------- | ----------------------------------------------------------------- |
| Logistics & Transportation | Fleet tracking, delivery vehicle monitoring, route optimization   |
| Drone Operations           | Drone fleet management, mission planning, nearest-drone discovery |
| IoT & Smart Cities         | Sensor monitoring, smart infrastructure management                |
| Industrial Operations      | Equipment tracking across manufacturing facilities                |
| Agriculture                | Farm machinery and field sensor monitoring                        |
| Emergency Services         | Locating the nearest ambulance, police vehicle, or fire engine    |
| Telecommunications         | Monitoring geographically distributed network infrastructure      |

---

## Why This Project

This project was built to demonstrate backend engineering skills that go beyond a traditional CRUD application. Instead of focusing only on database operations, it combines secure authentication, scalable architecture, advanced geospatial processing, analytical APIs, audit trails, and automated testing into a single production-style backend platform.

Key engineering concepts demonstrated:

- REST API design
- Layered architecture
- Repository pattern
- Dependency injection
- JWT authentication & role-based authorization
- Geospatial query processing
- SQLAlchemy ORM
- Docker-based development
- Automated integration testing
- Clean, scalable code organization

---

## Feature Showcase

The platform combines secure authentication, geospatial intelligence, asset lifecycle management, analytics, and enterprise backend practices into a single production-style REST API.

### 🔐 Authentication & Security

- JWT (JSON Web Token) based authentication
- Secure password hashing with Passlib & BCrypt
- Role-Based Access Control (RBAC)
- Protected endpoints with a current-user dependency
- User registration & login APIs
- Admin-only route protection
- Token validation on every protected request

### 📦 Asset Management

- Create, retrieve, update, and soft-delete assets
- Asset ownership and status management
- Asset type classification: **Drone, Vehicle, Camera, Sensor, Infrastructure, Other**
- Status tracking: **Online, Offline, Maintenance**
- Search, filtering, sorting, and pagination

### 🌍 Spatial Operations (PostGIS)

- Nearby asset search & nearest asset search
- Distance calculation
- Bounding box search
- Polygon geofence search
- Buffer analysis
- Polygon area & centroid calculation
- Route length & route intersection analysis
- Built on PostGIS functions: `ST_DWithin`, `ST_Distance`, `ST_MakePoint`, `ST_Buffer`, `ST_Area`, `ST_Centroid`, `ST_Length`, `ST_Intersects`, `ST_Contains`

### 📊 Dashboard & Analytics

- Total / online / offline / maintenance asset counts
- Asset type and status distribution
- User-specific and aggregated statistics

### ✅ Audit Logging

- Automatically logs asset creation, updates, and deletions
- Each record stores operation type, asset ID, user ID, timestamp, and event details

### 🛰️ Location History

- Stores previous and updated coordinates with timestamps
- Enables chronological, historical location retrieval

### 🏗️ Backend Architecture

- Layered architecture, repository pattern, service layer, dependency injection
- SQLAlchemy ORM, Pydantic validation, Alembic migrations
- Environment-based configuration, structured exception handling, full type hinting

### 🐳 DevOps & Deployment

- Docker & Docker Compose for PostgreSQL + PostGIS
- Environment-variable driven configuration
- Consistent, reproducible development environment

### 🧪 Automated Testing

- Integration tests covering auth, RBAC, asset CRUD, dashboard, analytics, audit logs, location history, geospatial operations, and health checks
- Built with Pytest and FastAPI's `TestClient`

---

## Technology Stack

| Category           | Technology                     | Purpose                                                                        |
| ------------------ | ------------------------------ | ------------------------------------------------------------------------------ |
| Backend Framework  | **FastAPI**                    | High-performance REST API framework with automatic docs & dependency injection |
| Language           | **Python 3.11+**               | Primary language for backend logic and geospatial operations                   |
| Database           | **PostgreSQL 16+**             | Stores users, assets, analytics, audit logs, and location history              |
| Spatial Database   | **PostGIS**                    | Spatial extension enabling advanced geospatial queries                         |
| ORM                | **SQLAlchemy**                 | Database modeling, relationships, query building, transactions                 |
| Data Validation    | **Pydantic**                   | Request/response validation, type safety, serialization                        |
| Authentication     | **JWT**                        | Stateless, industry-standard authentication                                    |
| Password Security  | **Passlib + BCrypt**           | Password hashing and verification                                              |
| Database Migration | **Alembic**                    | Schema versioning and migration management                                     |
| API Documentation  | **Swagger UI, ReDoc**          | Auto-generated interactive API documentation                                   |
| Testing            | **Pytest, FastAPI TestClient** | Automated integration testing                                                  |
| Containerization   | **Docker, Docker Compose**     | Portable development & deployment environments                                 |
| Version Control    | **Git, GitHub**                | Source control, collaboration, project management                              |
| Dev Server         | **Uvicorn**                    | ASGI server for running the FastAPI app                                        |

### Why These Technologies?

- **FastAPI** — high performance, automatic docs, dependency injection, type safety, async support.
- **PostgreSQL + PostGIS** — enterprise-grade relational database with efficient spatial indexing and accurate geographic calculations.
- **SQLAlchemy** — clean database abstraction, relationship management, and reusable query logic.
- **JWT** — stateless authentication that's easy to integrate with any frontend.
- **Docker** — a consistent environment that eliminates "works on my machine" issues.
- **Pytest** — reliable, fixture-driven integration testing that keeps the backend stable as it grows.

---

## Design Principles

The project was built following modern backend engineering principles:

| Principle              | Implementation                                            |
| ---------------------- | --------------------------------------------------------- |
| Layered Architecture   | `API → Service → Repository → Database`                   |
| Repository Pattern     | Database logic fully separated from business logic        |
| Service Layer          | Centralized business rules, validation, and orchestration |
| Dependency Injection   | FastAPI's built-in dependency system                      |
| Separation of Concerns | Independent, single-responsibility layers                 |
| Modular Design         | Feature-based, organized project structure                |
| RESTful APIs           | Resource-oriented, predictable endpoints                  |
| Type Safety            | Pydantic request/response models throughout               |
| Authentication         | JWT-based security                                        |
| Authorization          | Role-Based Access Control (RBAC)                          |
| Spatial Processing     | PostGIS functions for all geographic operations           |
| Automated Testing      | Pytest integration tests across every module              |
| Containerization       | Docker & Docker Compose                                   |

---

## System Architecture & Workflows

The platform follows a **Layered Architecture**, separating the application into independent layers responsible for request handling, business logic, data access, and persistence. This improves scalability, maintainability, readability, and testability while keeping business logic isolated from infrastructure concerns.

### High-Level Architecture

```mermaid
flowchart TD
    Client[Client<br/>Swagger / Postman / Future Frontend]
    FastAPIApp[FastAPI Application]
    Auth[JWT Authentication]
    Router[API Routers]
    Service[Service Layer]
    Repository[Repository Layer]
    ORM[SQLAlchemy ORM]
    DB[(PostgreSQL + PostGIS)]

    Client --> FastAPIApp --> Auth --> Router --> Service --> Repository --> ORM --> DB
    DB --> ORM --> Repository --> Service --> Router --> Client
```

### The Four Layers

| Layer            | Responsibility                           |
| ---------------- | ---------------------------------------- |
| API Layer        | Handles HTTP requests and responses      |
| Service Layer    | Implements business logic and validation |
| Repository Layer | Performs all database operations         |
| Database Layer   | Stores relational and spatial data       |

**Request lifecycle:**

1. The client sends an HTTP request to an API router.
2. The request passes through JWT authentication and role-based authorization.
3. The router calls the relevant service method.
4. The service layer applies business logic and calls the repository layer.
5. The repository executes SQLAlchemy / PostGIS queries against PostgreSQL.
6. The result flows back up through repository → service → router.
7. The API returns a JSON response to the client.

### Authentication Workflow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Database

    User->>API: Login Request
    API->>Database: Verify User
    Database-->>API: User Found
    API-->>User: JWT Access Token
    User->>API: Protected Request (Bearer token)
    API->>API: Verify JWT
    API->>API: Validate Role
    API-->>User: Requested Resource
```

### Asset Management Workflow

```mermaid
flowchart LR
    A[Create Asset] --> B[Validate Input] --> C[Authenticate User] --> D[Business Validation] --> E[Save Asset] --> F[Create Audit Log] --> G[Return Response]
```

### Spatial Query Workflow

All geospatial operations are powered by PostGIS:

```mermaid
flowchart TD
    A[Client] --> B[Spatial API] --> C[Service Layer] --> D[Repository Layer] --> E[PostGIS Query] --> F[Matching Assets] --> G[API Response]
```

### Audit Logging Workflow

```mermaid
flowchart LR
    A[Create / Update / Delete Asset] --> B[Service Layer] --> C[Audit Log Repository] --> D[(Audit Logs Table)]
```

### Location History Workflow

```mermaid
flowchart LR
    A[Update Asset] --> B[Save Previous Coordinates] --> C[Update Current Coordinates] --> D[Store History] --> E[Return Response]
```

### Dashboard & Analytics Workflow

```mermaid
flowchart LR
    A[Dashboard / Analytics Request] --> B[Repository Queries] --> C[Aggregate Statistics] --> D[API Response]
```

### Testing Workflow

```mermaid
flowchart TD
    A[Pytest] --> B[TestClient] --> C[FastAPI] --> D[Test Database] --> E[Assertions] --> F[Pass / Fail]
```

---

## Database Design

The platform uses **PostgreSQL** as its primary relational database and **PostGIS** as its spatial extension for storing and querying geographic data. The schema supports secure user management, asset lifecycle operations, spatial analysis, historical location tracking, and audit logging while maintaining data integrity and scalability.

### Entity-Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ ASSETS : owns
    USERS ||--o{ AUDIT_LOGS : performs
    ASSETS ||--o{ AUDIT_LOGS : generates
    ASSETS ||--o{ LOCATION_HISTORY : tracks

    USERS {
        int id PK
        string username
        string email
        string hashed_password
        enum role
        datetime created_at
    }

    ASSETS {
        int id PK
        string serial_number
        string name
        string description
        enum asset_type
        enum status
        float latitude
        float longitude
        geometry location
        int owner_id FK
        datetime created_at
        datetime updated_at
        datetime deleted_at
    }

    AUDIT_LOGS {
        int id PK
        int user_id FK
        int asset_id FK
        string action
        datetime timestamp
    }

    LOCATION_HISTORY {
        int id PK
        int asset_id FK
        float latitude
        float longitude
        datetime recorded_at
    }
```

### Tables

| Table                | Purpose                                         |
| -------------------- | ----------------------------------------------- |
| **Users**            | Stores user accounts and authentication details |
| **Assets**           | Stores geographically distributed assets        |
| **Audit Logs**       | Records important asset-related operations      |
| **Location History** | Stores historical asset locations               |

**Users**

| Field             | Description                |
| ----------------- | -------------------------- |
| `id`              | Primary key                |
| `username`        | Unique username            |
| `email`           | User email                 |
| `hashed_password` | BCrypt-hashed password     |
| `role`            | User role (Admin / User)   |
| `created_at`      | Account creation timestamp |

**Assets**

| Field                       | Description                                               |
| --------------------------- | --------------------------------------------------------- |
| `id`                        | Primary key                                               |
| `serial_number`             | Unique asset identifier                                   |
| `name`                      | Asset name                                                |
| `description`               | Asset description                                         |
| `asset_type`                | Drone, Vehicle, Camera, Sensor, Infrastructure, Other     |
| `status`                    | Online, Offline, Maintenance                              |
| `latitude` / `longitude`    | Human-readable coordinates                                |
| `location`                  | PostGIS geometry point, used for all spatial calculations |
| `owner_id`                  | Foreign key → Users                                       |
| `created_at` / `updated_at` | Timestamps                                                |
| `deleted_at`                | Soft-delete timestamp                                     |

**Audit Logs**

| Field       | Description                   |
| ----------- | ----------------------------- |
| `id`        | Primary key                   |
| `user_id`   | User who performed the action |
| `asset_id`  | Related asset                 |
| `action`    | Operation performed           |
| `timestamp` | Event timestamp               |

**Location History**

| Field                    | Description          |
| ------------------------ | -------------------- |
| `id`                     | Primary key          |
| `asset_id`               | Related asset        |
| `latitude` / `longitude` | Previous coordinates |
| `recorded_at`            | Time of update       |

### Spatial Data

Instead of storing only latitude and longitude, every asset also stores a **PostGIS geometry point**:

```text
POINT(longitude latitude)

-- Example
POINT(76.6394 12.2958)
```

This enables efficient execution of advanced spatial operations directly inside PostgreSQL — reducing application-side computation and improving performance. Supported operations include `ST_DWithin`, `ST_Distance`, `ST_Buffer`, `ST_Area`, `ST_Centroid`, `ST_Length`, `ST_Contains`, and `ST_Intersects`.

### Entity Relationships

- **Users → Assets**: one user can own many assets.
- **Users → Audit Logs**: one user can generate many audit records.
- **Assets → Audit Logs**: one asset can generate many audit events.
- **Assets → Location History**: one asset can have many historical location records.

### Soft Delete Strategy

Assets are never permanently deleted. Instead, the platform uses a soft-delete flag:

- `deleted_at = NULL` → asset is active
- `deleted_at = <timestamp>` → asset is soft-deleted

This preserves historical information while hiding deleted assets from normal queries.

### Database Design Goals

- Maintain data integrity through relational design
- Support advanced geospatial operations using PostGIS
- Preserve historical information through soft deletion
- Record system activity with audit logging
- Track asset movement using location history
- Enable scalable querying through normalized relationships
- Provide a strong foundation for future frontend and analytics integrations

---

## Project Structure

The platform follows a modular, layered project structure that separates business logic, API routing, data access, validation, authentication, and configuration into independent components — improving maintainability, scalability, and readability.

### Directory Structure

```text
Spatial-Asset-Management-Platform/
│
├── alembic/                      # Database migration files
│
├── app/
│   ├── api/                      # REST API routes
│   ├── auth/                     # Authentication & authorization
│   ├── config/                   # Application configuration
│   ├── core/                     # Enums, pagination, shared utilities
│   ├── database/                 # Database connection & session
│   ├── models/                   # SQLAlchemy ORM models
│   ├── repositories/             # Database access layer
│   ├── schemas/                  # Pydantic request/response models
│   ├── services/                 # Business logic
│   ├── utils/                    # Helper utilities
│   └── main.py                   # FastAPI application entry point
│
├── tests/                        # Integration tests
│
├── .env.example
├── .gitignore
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── README.md
└── LICENSE
```

### Folder Responsibilities

| Folder              | Responsibility                                                                                                                                                                                     |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/api/`          | REST endpoints (e.g. `users.py`, `assets.py`) — request validation, calling services, returning responses                                                                                          |
| `app/auth/`         | JWT generation & verification, password hashing, current-user dependency, RBAC                                                                                                                     |
| `app/config/`       | Environment variables, app settings, secret keys, database configuration                                                                                                                           |
| `app/core/`         | Shared enums (`AssetType`, `AssetStatus`, `UserRole`), pagination, sorting, constants                                                                                                              |
| `app/database/`     | SQLAlchemy engine, session management, declarative base                                                                                                                                            |
| `app/models/`       | ORM models — `User`, `Asset`, `AuditLog`, `LocationHistory`                                                                                                                                        |
| `app/repositories/` | All database/query logic (CRUD + PostGIS spatial queries) — **no business logic**                                                                                                                  |
| `app/schemas/`      | Pydantic request/response models for validation & serialization                                                                                                                                    |
| `app/services/`     | Business logic, authorization checks, workflow orchestration, audit logging, location history creation                                                                                             |
| `app/utils/`        | Reusable helper functions                                                                                                                                                                          |
| `app/main.py`       | FastAPI entry point — router registration, middleware, health endpoints                                                                                                                            |
| `tests/`            | Automated integration tests (`test_auth.py`, `test_assets.py`, `test_geospatial.py`, `test_dashboard.py`, `test_analytics.py`, `test_audit_logs.py`, `test_location_history.py`, `test_health.py`) |

### Module Dependency Flow

```mermaid
flowchart LR
    API --> Services --> Repositories --> Models
    Repositories --> Database
    Schemas --> API
    Schemas --> Services
    Auth --> API
    Config --> Database
    Core --> API
    Core --> Services
    Utils --> Services
```

### Why This Structure?

The layered architecture was chosen for separation of concerns, better code organization, easier debugging, improved scalability, reusable business logic, easier testing, and simplified long-term maintenance.

---

## API Documentation

The platform exposes a comprehensive RESTful API for secure asset management, advanced geospatial analysis, dashboard reporting, analytics, audit logging, and historical location tracking. The API follows REST principles, exchanges data in JSON, and is automatically documented via **Swagger UI** and **ReDoc**.

### Authentication

All protected endpoints require a **JWT** access token, obtained via login and sent on subsequent requests:

```
Authorization: Bearer <access_token>
```

### API Modules

| Module           | Description                                                       |
| ---------------- | ----------------------------------------------------------------- |
| Users            | Registration, authentication, profile management, role validation |
| Assets           | Asset lifecycle management and geospatial operations              |
| Dashboard        | Summary statistics                                                |
| Analytics        | Asset analytics and statistical reports                           |
| Audit Logs       | Asset activity history                                            |
| Location History | Historical asset location tracking                                |

### Users API — `/users`

| Method | Endpoint    | Access     | Description                                       |
| ------ | ----------- | ---------- | ------------------------------------------------- |
| POST   | `/register` | Public     | Register a new user                               |
| POST   | `/login`    | Public     | Authenticate and receive a JWT access token       |
| GET    | `/me`       | Protected  | Retrieve the current authenticated user's profile |
| GET    | `/admin`    | Admin only | Verify administrator access                       |

### Assets API — `/assets`

| Method | Endpoint      | Access    | Description                     |
| ------ | ------------- | --------- | ------------------------------- |
| POST   | `/`           | Protected | Create a new asset              |
| GET    | `/`           | Protected | Retrieve a paginated asset list |
| GET    | `/{asset_id}` | Protected | Retrieve a single asset         |
| PUT    | `/{asset_id}` | Protected | Update an existing asset        |
| DELETE | `/{asset_id}` | Protected | Soft-delete an asset            |

The listing endpoint (`GET /assets/`) supports the following query parameters:

| Parameter    | Description                                   |
| ------------ | --------------------------------------------- |
| `asset_type` | Filter by asset type                          |
| `status`     | Filter by operational status                  |
| `search`     | Search by name, serial number, or description |
| `sort_by`    | Field to sort by                              |
| `order`      | `ASC` or `DESC`                               |
| `limit`      | Maximum records per request                   |
| `offset`     | Pagination offset                             |

### Geospatial APIs — `/assets`

All endpoints below are **Protected** and powered by PostGIS.

| Operation            | Method | Endpoint                      | Key Parameters                                                   | Description                                          |
| -------------------- | ------ | ----------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------- |
| Nearby Assets        | GET    | `/assets/nearby`              | `latitude`, `longitude`, `radius_km`, `limit`, `offset`          | Retrieve assets within a search radius               |
| Nearest Asset        | GET    | `/assets/nearest`             | `latitude`, `longitude`                                          | Retrieve the nearest asset to a location             |
| Distance Calculation | GET    | `/assets/{asset_id}/distance` | `asset_id`, `latitude`, `longitude`                              | Calculate distance between an asset and a coordinate |
| Bounding Box Search  | GET    | `/assets/bbox`                | `min_latitude`, `min_longitude`, `max_latitude`, `max_longitude` | Retrieve assets inside a rectangular area            |
| Geofence Search      | POST   | `/assets/geofence`            | polygon body                                                     | Retrieve assets located inside a custom polygon      |
| Buffer Generation    | GET    | `/assets/{asset_id}/buffer`   | `asset_id`, `radius_m`                                           | Generate a spatial buffer around an asset            |
| Polygon Area         | POST   | `/assets/polygon/area`        | polygon body                                                     | Calculate the area enclosed by a polygon             |
| Polygon Centroid     | POST   | `/assets/polygon/centroid`    | polygon body                                                     | Calculate the centroid of a polygon                  |
| Route Length         | POST   | `/assets/route/length`        | route body                                                       | Calculate the total length of a route                |
| Route Intersection   | POST   | `/assets/route/intersects`    | route + polygon body                                             | Determine whether a route intersects a polygon       |

### Dashboard API — `/dashboard`

| Method | Endpoint   | Access    | Description                                                      |
| ------ | ---------- | --------- | ---------------------------------------------------------------- |
| GET    | `/summary` | Protected | Total, online, offline, and maintenance asset counts and summary |

### Analytics API — `/analytics`

| Method | Endpoint   | Access    | Description                                                                |
| ------ | ---------- | --------- | -------------------------------------------------------------------------- |
| GET    | `/summary` | Protected | Asset type distribution, status distribution, and user-specific statistics |

### Audit Logs API — `/audit-logs`

| Method | Endpoint | Access                            | Description                                                 |
| ------ | -------- | --------------------------------- | ----------------------------------------------------------- |
| GET    | `/`      | Public _(current implementation)_ | Retrieve audit log records (user, asset, action, timestamp) |

> **Note:** In the current implementation this endpoint is publicly accessible. In a production deployment it should be restricted to administrators.

### Location History API — `/location-history`

| Method | Endpoint      | Access    | Description                              |
| ------ | ------------- | --------- | ---------------------------------------- |
| GET    | `/{asset_id}` | Protected | Retrieve an asset's historical locations |

### API Access Summary

| Endpoint Category          | Access Level                      |
| -------------------------- | --------------------------------- |
| User Registration / Login  | Public                            |
| User Profile               | Protected                         |
| Admin Endpoint             | Admin only                        |
| Asset Management APIs      | Protected                         |
| Geospatial APIs            | Protected                         |
| Dashboard / Analytics APIs | Protected                         |
| Location History APIs      | Protected                         |
| Audit Log APIs             | Public _(current implementation)_ |

### Common HTTP Status Codes

| Status Code                 | Meaning                                  |
| --------------------------- | ---------------------------------------- |
| `200 OK`                    | Request completed successfully           |
| `201 Created`               | Resource created successfully            |
| `400 Bad Request`           | Invalid request data                     |
| `401 Unauthorized`          | Authentication required or invalid token |
| `403 Forbidden`             | Insufficient permissions                 |
| `404 Not Found`             | Requested resource does not exist        |
| `422 Unprocessable Entity`  | Validation error                         |
| `500 Internal Server Error` | Unexpected server error                  |

### Interactive API Documentation

| Documentation | URL      |
| ------------- | -------- |
| Swagger UI    | `/docs`  |
| ReDoc         | `/redoc` |

---

## Getting Started

Follow the steps below to set up and run the platform locally.

### Prerequisites

| Software       | Recommended Version |
| -------------- | ------------------- |
| Python         | 3.11 or later       |
| PostgreSQL     | 16 or later         |
| PostGIS        | Latest              |
| Docker         | Latest              |
| Docker Compose | Latest              |
| Git            | Latest              |

### 1. Clone the Repository

```bash
git clone https://github.com/dhanushgowdars/Spatial-Asset-Management-Platform.git
cd Spatial-Asset-Management-Platform
```

### 2. Create a Virtual Environment

**Windows**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the provided example file:

**Windows**

```bash
copy .env.example .env
```

**Linux / macOS**

```bash
cp .env.example .env
```

Then update `.env` with your local PostgreSQL configuration:

```env
# Database Configuration
DATABASE_URL=postgresql://geouser:yourpassword@localhost:5432/geoasset_db

# JWT Configuration
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# PostgreSQL Configuration
POSTGRES_USER=geouser
POSTGRES_PASSWORD=yourpassword
POSTGRES_DB=geoasset_db
```

> **Important:** Never commit your `.env` file. Only commit `.env.example` with placeholder values.

### 5. Start PostgreSQL + PostGIS with Docker

```bash
docker compose up -d      # start
docker ps                 # verify the container is running
docker compose logs       # view logs
docker compose down       # stop
```

### 6. Apply Database Migrations

```bash
alembic upgrade head
```

### 7. Run the Application

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`, with interactive docs at `http://127.0.0.1:8000/docs` (Swagger UI) and `http://127.0.0.1:8000/redoc` (ReDoc).

### 8. Try It Out

1. Register a new user via `/users/register`.
2. Log in via `/users/login` to receive a JWT.
3. Authorize in Swagger UI with `Bearer <access_token>`.
4. Create assets, run spatial queries, and explore the dashboard/analytics endpoints.

### Development Workflow (Quick Reference)

```text
Clone Repository → Create Virtual Environment → Install Dependencies
→ Configure Environment Variables → Start Docker Container
→ Run Alembic Migrations → Start FastAPI Server → Open Swagger UI
→ Register User → Login → Access Protected APIs
```

### Setup Checklist

- [ ] Repository cloned
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] `.env` created from `.env.example`
- [ ] Docker container running
- [ ] PostgreSQL connected
- [ ] PostGIS enabled
- [ ] Database migrations applied
- [ ] FastAPI server running
- [ ] Swagger UI accessible
- [ ] User registered & logged in
- [ ] JWT token generated
- [ ] Protected APIs accessible
- [ ] Tests passing

---

## Project Preview

Since the frontend hasn't been built yet, this section reflects the project's current, honest state: a fully functional backend with interactive API documentation.

**Swagger UI** — `http://127.0.0.1:8000/docs`

- Interactive API testing, request/response schemas, JWT auth support, full endpoint documentation

**ReDoc** — `http://127.0.0.1:8000/redoc`

- Clean, readable API reference with request and response models

> A dedicated frontend application is planned. Once it's built, screenshots and usage examples (home page, login/register, dashboard, asset map, analytics) will be added here.

---

## Testing

The project includes automated integration tests covering the core backend functionality:

- Authentication
- Authorization (RBAC)
- Asset CRUD operations
- Search, filtering & pagination
- Dashboard APIs
- Analytics APIs
- Audit log APIs
- Location history APIs
- Geospatial operations
- Health check endpoints

```bash
pytest                                          # run the full suite
pytest -v                                       # verbose output
pytest tests/test_assets.py                     # run a specific file
pytest tests/test_assets.py::test_create_asset  # run a specific test
```

---

## Troubleshooting

**PostgreSQL connection failed**

- Verify PostgreSQL is running and the PostGIS extension is installed.
- Double-check `DATABASE_URL` in `.env`.

**Docker container not running**

```bash
docker ps
docker compose up -d
```

**Migration errors**

```bash
alembic upgrade head
```

**Missing Python packages**

```bash
pip install -r requirements.txt
```

**Port already in use**

```bash
uvicorn app.main:app --reload --port 8001
```

---

## Future Enhancements

**Frontend**

- Responsive web interface with interactive asset map visualization
- User dashboard, authentication pages, asset management screens, analytics dashboard

**Backend**

- API versioning
- Rate limiting
- Refresh token support
- Enhanced role-based permissions
- Bulk asset import/export
- Background task processing
- Performance optimizations
- CI/CD pipeline

**Geospatial**

- Route optimization
- Heat maps & cluster visualization
- Real-time asset tracking
- Spatial reports

---

## Contributing

Contributions, suggestions, and improvements are welcome.

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push the branch
5. Open a Pull Request

---

## Author

**Dhanush R S**
Computer Science (Data Science) Student
Backend Developer | Python | FastAPI | PostgreSQL | PostGIS

- GitHub: [github.com/dhanushgowdars](https://github.com/dhanushgowdars)
- LinkedIn: www.linkedin.com/in/dhanush-r-s-207105382

---

## License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.

---

## Acknowledgements

Built to explore modern backend engineering practices using FastAPI, PostgreSQL, PostGIS, SQLAlchemy, Docker, Alembic, and Pytest. Thanks to the open-source community for the tools that made this project possible.

---

## Support

If you found this project useful, consider giving it a ⭐ on GitHub.
