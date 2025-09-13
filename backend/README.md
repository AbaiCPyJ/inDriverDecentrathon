# InDrive Geotracks Backend

A simple Python-based backend for processing and visualizing GPS tracking data with various heatmap analyses.

## Features

1. **Popular Routes Heat Map** - Shows high-traffic corridors based on GPS point density
2. **Trip Endpoints Heat Map** - Highlights common pickup and drop-off zones using DBSCAN clustering
3. **Speed Heat Map** - Maps traffic conditions with congestion visualization (red = slow, green = fast)
4. **Demand Density Heat Map** - Combined view showing overall trip density across the service area

## Setup

### Using Virtual Environment (Recommended)

1. Create and activate virtual environment:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

3. Run the server:
```bash
python main.py
```

### Without Virtual Environment

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Run the server:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

## API Endpoints

- `POST /api/jobs` - Create a new analysis job by uploading a CSV file
- `GET /api/jobs/{job_id}` - Get job status and results
- `GET /api/jobs` - List all jobs
- `DELETE /api/jobs/{job_id}` - Cancel a job
- `GET /api/maps/{filename}` - Get generated map HTML
- `GET /api/health` - Health check
- `GET /api/data/stats` - Get data statistics

## CSV Format

The CSV file should have the following columns:
- `randomized_id` - Unique identifier for each vehicle
- `lat` - Latitude
- `lng` - Longitude
- `alt` - Altitude
- `spd` - Speed in m/s (automatically converted to km/h)
- `azm` - Azimuth/bearing

## Data Processing

- Speed is automatically converted from m/s to km/h (multiplied by 3.6)
- Trajectories are reconstructed by grouping points by vehicle ID
- Various clustering algorithms (DBSCAN) are used to identify high-density areas
- Heatmaps are generated using Folium with different color gradients for each analysis type

## Performance Optimizations

For large datasets (>50,000 rows), the backend automatically samples the data to ensure reasonable processing times. You can configure this limit:

```bash
# Set maximum rows to process (default: 50000)
export MAX_PROCESS_ROWS=100000
python main.py
```

The sampling preserves vehicle trajectories by:
1. First trying to sample points from each vehicle equally
2. If too many vehicles, sampling a subset of vehicles instead

## Development

The backend uses:
- FastAPI for the REST API
- Pandas for data processing
- Folium for map generation
- Scikit-learn for clustering algorithms
- CORS is configured for localhost:3000 and localhost:3001

## Troubleshooting

If processing seems stuck:
1. Check the server logs for progress updates
2. For very large files (>800k rows), consider:
   - Reducing the file size before upload
   - Increasing MAX_PROCESS_ROWS (requires more memory)
   - Using a subset of the data
