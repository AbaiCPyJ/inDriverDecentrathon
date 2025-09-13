# InDrive Geotracks Dashboard

A full-stack application for visualizing and analyzing GPS tracking data with various heatmap visualizations.

## Features

The application provides four main types of heatmap analyses:

### 1️⃣ Popular Routes Heat Map
- Shows where most vehicles travel
- Identifies high-traffic corridors and important connectors
- Each GPS point contributes to intensity values

### 2️⃣ Trip Endpoints (Pickup & Drop-off) Heat Map
- Highlights the most common start and end points of trips
- Uses DBSCAN clustering to locate dense pickup/drop-off zones
- Green markers for pickups, red markers for drop-offs

### 3️⃣ Speed Heat Map
- Maps average/median speed at each location
- Reveals traffic conditions (red = congestion, green = free flow)
- Automatically converts speed from m/s to km/h

### 4️⃣ Demand Density Heat Map
- Combines route popularity and endpoints
- Shows overall trip density across the service area
- Useful for expansion strategy and identifying underserved areas

## Project Structure

```
inDriverDecentrathon/
├── frontend/          # Next.js frontend application
│   ├── app/          # App router pages
│   ├── components/   # React components
│   └── lib/          # API client and utilities
├── backend/          # FastAPI backend
│   ├── main.py      # Main API server
│   └── processing/   # Data processing modules
└── sample-data.csv   # Sample geodata file
```

## Quick Start

### Prerequisites
- Node.js 16+ and npm/pnpm
- Python 3.8-3.11 (Python 3.13 not supported yet due to pandas compatibility)
- Modern web browser

### Option 1: Run with Virtual Environment (Recommended)

```bash
# From project root
./run-dev.sh
```

This script will:
- Create a Python virtual environment
- Install all dependencies
- Start both frontend and backend servers

### Option 2: Run with System Python

```bash
# From project root
./run-dev-simple.sh
```

This uses your system Python installation without creating a virtual environment.

### Option 3: Manual Setup with Virtual Environment

#### Backend with venv
```bash
cd backend

# Create virtual environment with Python 3.10 or 3.11
python3.10 -m venv venv  # or python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run the server
python main.py
```

#### Frontend
```bash
cd frontend
npm install  # or pnpm install
npm run dev  # or pnpm dev
```

### Option 4: Run Services with System Python

#### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```

#### Frontend
```bash
cd frontend
npm install  # or pnpm install
npm run dev  # or pnpm dev
```

## Usage

1. Open http://localhost:3000 in your browser
2. Upload a CSV file using the sidebar
3. Select the type of analysis (Popular Routes, Endpoints, Speed, etc.)
4. Click "Run Analysis" to process the data
5. View the generated heatmap visualization

## CSV File Format

The CSV file must contain the following columns:
- `randomized_id` - Unique identifier for each vehicle
- `lat` - Latitude
- `lng` - Longitude  
- `alt` - Altitude
- `spd` - Speed in m/s (automatically converted to km/h)
- `azm` - Azimuth/bearing

Example:
```csv
randomized_id,lat,lng,alt,spd,azm
7637058049336049989,51.09546,71.42753,350.53102,0.20681,13.60168
```

## API Documentation

The backend API is documented at http://localhost:8000/docs when running.

Key endpoints:
- `POST /api/jobs` - Create analysis job
- `GET /api/jobs/{job_id}` - Get job status
- `GET /api/maps/{filename}` - Get generated map

## Technologies Used

### Frontend
- Next.js 14 with App Router
- React with TypeScript
- Tailwind CSS for styling
- shadcn/ui components
- Folium maps embedded in iframes

### Backend
- FastAPI for REST API
- Pandas for data processing
- Folium for map generation
- Scikit-learn for clustering (DBSCAN)
- Geopy for geographic calculations

## Development Notes

- The backend processes data asynchronously using FastAPI's background tasks
- Maps are generated as standalone HTML files using Folium
- Speed is converted from m/s to km/h by multiplying by 3.6
- CORS is configured for local development on ports 3000 and 3001
