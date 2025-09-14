# main.py
from __future__ import annotations
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np
import json, os, uuid, logging, traceback, asyncio
from datetime import datetime
from pathlib import Path

from processing.data_processor import DataProcessor, PathReconstructionConfig
from processing.heatmap_generator import HeatmapGenerator, LegendSpec

# ----------------------------- App boot ---------------------------------------
app = FastAPI(title="InDrive Geotracks API", version="2.0.0")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("indrive-api")

# CORS
origins = os.environ.get("ALLOW_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Folders
UPLOAD_DIR = Path("uploads"); UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR = Path("results"); RESULTS_DIR.mkdir(exist_ok=True)

# In-memory job store (swap for Redis/DB in prod)
jobs_db: Dict[str, Dict[str, Any]] = {}
# Optional: concurrency guard so we don't overload the box
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "2"))
job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

# ----------------------------- Models ----------------------------------------
class JobConfig(BaseModel):
    analysisType: str
    filters: Optional[Dict[str, Any]] = {}
    visualization: Optional[Dict[str, Any]] = {}

class JobResponse(BaseModel):
    id: str
    status: str
    config: JobConfig
    createdAt: str
    startedAt: Optional[str] = None
    completedAt: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[int] = 0
    results: Optional[Dict[str, Any]] = None

# ----------------------------- Endpoints -------------------------------------
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "max_process_rows": int(os.environ.get("MAX_PROCESS_ROWS", "50000")),
        "ef_kg_per_km": float(os.environ.get("EF_KG_PER_KM", "0.192")),
        "active_jobs": len([j for j in jobs_db.values() if j.get("status") == "running"])
    }

@app.post("/api/jobs", response_model=JobResponse)
async def create_job(
    analysisType: str = Form(...),      # "popular-routes" | "endpoints" | "trajectories" | "speed" | "ghg"
    csvFile: UploadFile = File(...),
    filters: Optional[str] = Form("{}"),
    visualization: Optional[str] = Form("{}"),
    maxProcessRows: Optional[int] = Form(None)  # Optional override for max processing rows
):
    # minimal file/type checks + streamed write
    if not (csvFile.filename.endswith(".csv") or "csv" in (csvFile.content_type or "")):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    job_id = f"job_{uuid.uuid4().hex[:8]}"
    file_path = UPLOAD_DIR / f"{job_id}_{csvFile.filename}"

    MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "200"))
    size = 0
    with open(file_path, "wb") as f:
        while chunk := await csvFile.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                raise HTTPException(status_code=413, detail="CSV too large")
            f.write(chunk)

    try:
        filters_dict = json.loads(filters) if filters else {}
        visualization_dict = json.loads(visualization) if visualization else {}
    except json.JSONDecodeError:
        filters_dict, visualization_dict = {}, {}

    job = {
        "id": job_id,
        "status": "pending",
        "config": {"analysisType": analysisType, "filters": filters_dict, "visualization": visualization_dict, "maxProcessRows": maxProcessRows},
        "createdAt": datetime.utcnow().isoformat(),
        "startedAt": None,
        "completedAt": None,
        "error": None,
        "progress": 0,
        "results": None,
        "file_path": str(file_path)
    }
    jobs_db[job_id] = job

    asyncio.create_task(process_job(job_id))
    logger.info("Job %s created", job_id)
    return JobResponse(**job)

async def process_job(job_id: str):
    def cancelled() -> bool:
        return jobs_db.get(job_id, {}).get("status") == "cancelled"

    async with job_semaphore:
        try:
            job = jobs_db[job_id]
            job.update(status="running", startedAt=datetime.utcnow().isoformat(), progress=10)
            logger.info("Starting job %s", job_id)

            # Read CSV; keep only columns we use for speed
            usecols = ["randomized_id","lat","lng","spd","azm","alt"]
            df = pd.read_csv(job["file_path"], usecols=lambda c: c in usecols or True)
            cols = [c for c in usecols if c in df.columns]
            df = df[cols] if cols else df  # be permissive
            if cancelled(): return

            # Configure processing with optional override
            max_rows = job["config"].get("maxProcessRows") or int(os.environ.get("MAX_PROCESS_ROWS", "50000"))
            processor = DataProcessor(
                ef_kg_per_km=float(os.environ.get("EF_KG_PER_KM", "0.192")),
                max_rows=max_rows,
            )

            # Filter/sampling
            df = processor.apply_filters(df, job["config"]["filters"])
            df = processor.safe_sample(df)  # deterministic thinning if needed
            job["progress"] = 30
            if cancelled(): return

            # Enrich (speed_kmh etc.)
            processor.ensure_speed_kmh(df)

            analysis_type = job["config"]["analysisType"].strip().lower()
            generator = HeatmapGenerator()

            # Reconstruct paths ONCE when needed (popular-routes, endpoints, ghg, trajectories)
            segments = None
            if analysis_type in {"popular-routes","endpoints","trajectories","ghg"}:
                cfg = PathReconstructionConfig()  # default tuned params
                segments = processor.reconstruct_paths(df, cfg)   # edges with distances & emissions
                job["progress"] = 55
                if cancelled(): return

            # Generate maps
            if analysis_type == "popular-routes":
                map_html = generator.generate_route_density_map(
                    df=df, segments=segments, title="Popular Routes (Azimuth-aware)",
                    legend=LegendSpec(title="Route Density", unit="km length per cell", notes="Meter-based grid; azimuth-aware path reconstruction")
                )
            elif analysis_type == "endpoints":
                map_html = generator.generate_endpoints_map(
                    df=df, segments=segments, title="Trip Endpoints (Green=Pickup, Red=Dropoff)",
                    legend=LegendSpec(title="Endpoints", unit="clustered points", notes="Derived from azimuth-aware path reconstruction")
                )
            elif analysis_type == "speed":
                # Choose the semantics you want:
                # A) Average speed per location (street): red=fast (highways), green=slow
                map_html = generator.generate_avg_speed_map(
                    df=df,
                    title="Average Speed Heat Map (Red = Fast)",
                    legend=LegendSpec(title="Average Speed", unit="km/h",
                                    notes="Per 80 m cell; colors clipped to 5th–95th percentile"),
                    cell_m=80.0,
                    red_is_fast=True   # set False if you want red=slow
                )
            elif analysis_type == "trajectories":
                map_html = generator.generate_trajectory_demand_map(
                    df=df, segments=segments, title="Demand Density (Presence + Endpoints)",
                    legend=LegendSpec(title="Demand Density", unit="normalized presence", notes="Meter-based grid with endpoint boosting")
                )
            elif analysis_type == "ghg":
                if segments is None or "dist_km" not in segments.columns:
                    raise ValueError("GHG requires path reconstruction to compute distance")
                map_html = generator.generate_ghg_map(
                    segments=segments, title="GHG Emissions Heat Map (acid palette)",
                    legend=LegendSpec(title="GHG Emissions", unit="kg CO₂e per cell", notes=f"EF={processor.ef_kg_per_km:.3f} kg/km; meter-based grid")
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unknown analysis type: {analysis_type}")

            job["progress"] = 80

            # Save map
            map_path = RESULTS_DIR / f"{job_id}.html"
            with open(map_path, "w", encoding="utf-8") as f:
                f.write(map_html)

            # Stats
            stats = processor.calculate_statistics(df, segments, analysis_type)
            job["status"] = "completed"
            job["completedAt"] = datetime.utcnow().isoformat()
            job["progress"] = 100
            job["results"] = {"mapUrl": f"/api/maps/{job_id}.html", "statistics": stats}
            logger.info("Job %s completed", job_id)

        except Exception as e:
            logger.error("Job %s failed: %s", job_id, e)
            logger.error(traceback.format_exc())
            job = jobs_db.get(job_id, {})
            job["status"] = "failed"
            job["error"] = str(e)
            job["completedAt"] = datetime.utcnow().isoformat()

@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**jobs_db[job_id])

@app.get("/api/jobs", response_model=List[JobResponse])
async def list_jobs():
    return [JobResponse(**job) for job in jobs_db.values()]

@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs_db[job_id]
    if job["status"] in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed job")
    job["status"] = "cancelled"
    job["completedAt"] = datetime.utcnow().isoformat()
    return {"success": True}

@app.get("/api/maps/{filename}")
async def get_map(filename: str):
    candidate = (RESULTS_DIR / filename).resolve()
    if RESULTS_DIR.resolve() not in candidate.parents and candidate != RESULTS_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Map not found")
    return FileResponse(candidate, media_type="text/html")

@app.get("/api/traffic-analysis")
async def analyze_traffic(
    lat: float,
    lng: float,
    radius_m: float = 100,
    time_window_sec: int = 30,
    job_id: Optional[str] = None
):
    """
    Analyze traffic congestion at a specific location.
    Returns count of vehicles that stayed in the area for at least time_window_sec.
    """
    try:
        # If job_id provided, use that job's data file
        if job_id and job_id in jobs_db:
            csv_path = jobs_db[job_id].get("file_path")
            if not csv_path or not Path(csv_path).exists():
                raise HTTPException(status_code=404, detail="Job data file not found")
        else:
            # Find the most recent CSV file for analysis
            csv_files = list(UPLOAD_DIR.glob("*.csv"))
            if not csv_files:
                return {"vehicleCount": 0, "message": "No data available"}
            csv_path = max(csv_files, key=lambda p: p.stat().st_mtime)
        
        # Read the CSV data
        df = pd.read_csv(csv_path)
        
        # Log data info for debugging
        logger.info(f"Traffic analysis: CSV has {len(df)} rows, columns: {list(df.columns)}")
        
        # Ensure we have required columns
        required_cols = ["lat", "lng", "randomized_id"]
        if not all(col in df.columns for col in required_cols):
            logger.warning(f"Missing columns. Available: {list(df.columns)}, Required: {required_cols}")
            return {"vehicleCount": 0, "message": "Insufficient data columns", "availableColumns": list(df.columns)}
        
        # Calculate distance from click point to all data points using Haversine formula
        from math import radians, cos, sin, asin, sqrt
        
        def haversine_distance(lat1, lon1, lat2, lon2):
            # Convert to radians
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            
            # Haversine formula
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            r = 6371000  # Radius of Earth in meters
            return c * r
        
        # Calculate distances for all points
        df["distance_m"] = df.apply(
            lambda row: haversine_distance(lat, lng, row["lat"], row["lng"]),
            axis=1
        )
        
        # Filter points within radius
        nearby_df = df[df["distance_m"] <= radius_m].copy()
        
        logger.info(f"Found {len(nearby_df)} points within {radius_m}m of ({lat}, {lng})")
        
        if len(nearby_df) == 0:
            # Try with a larger radius to see if there's any data nearby
            larger_radius = 500
            nearby_larger = df[df["distance_m"] <= larger_radius]
            logger.info(f"No data within {radius_m}m, but {len(nearby_larger)} points within {larger_radius}m")
            
            return {
                "vehicleCount": 0,
                "radius": radius_m,
                "timeWindow": time_window_sec,
                "message": f"No vehicles within {radius_m}m (nearest data is beyond this radius)",
                "debug": {
                    "clickLat": lat,
                    "clickLng": lng,
                    "totalDataPoints": len(df),
                    "nearbyIn500m": len(nearby_larger)
                }
            }
        
        # Group by vehicle ID and calculate time spent in area
        vehicle_groups = nearby_df.groupby("randomized_id")
        
        # Count vehicles that have multiple data points (stayed in area)
        # More balanced criteria for "staying" in an area
        vehicles_stayed = 0
        total_vehicles = len(vehicle_groups)
        
        # Track distribution of points per vehicle for debugging
        point_counts = []
        
        for vehicle_id, group in vehicle_groups:
            # Count vehicles based on number of GPS points in the area
            # More points = stayed longer
            points_count = len(group)
            point_counts.append(points_count)
            
            # More balanced criteria - vehicles with multiple readings stayed
            if time_window_sec == 30 and points_count >= 2:  # At least 2 points for 30 seconds
                vehicles_stayed += 1
            elif time_window_sec == 60 and points_count >= 3:  # At least 3 points for 1 minute
                vehicles_stayed += 1
            elif time_window_sec == 300 and points_count >= 5:  # At least 5 points for 5 minutes
                vehicles_stayed += 1
        
        # Log statistics for debugging
        if point_counts:
            max_points = max(point_counts)
            avg_points = sum(point_counts) / len(point_counts)
            logger.info(f"Point distribution: max={max_points}, avg={avg_points:.1f}, total_vehicles={total_vehicles}")
        
        logger.info(f"Analysis result: {vehicles_stayed} vehicles stayed (≥{time_window_sec}s) out of {total_vehicles} total")
        
        # Determine congestion level with more realistic thresholds
        congestion_level = "light"
        if time_window_sec == 30:
            if vehicles_stayed > 15:
                congestion_level = "heavy"
            elif vehicles_stayed > 5:
                congestion_level = "moderate"
        elif time_window_sec == 60:
            if vehicles_stayed > 10:
                congestion_level = "heavy"
            elif vehicles_stayed > 3:
                congestion_level = "moderate"
        elif time_window_sec == 300:
            if vehicles_stayed > 5:
                congestion_level = "heavy"
            elif vehicles_stayed > 1:
                congestion_level = "moderate"
        
        # If no vehicles stayed but some passed through, show that
        if vehicles_stayed == 0 and total_vehicles > 0:
            # Count vehicles that at least passed through (have any data points)
            vehicles_passed = total_vehicles
            
            return {
                "vehicleCount": vehicles_stayed,
                "vehiclesPassed": vehicles_passed,
                "totalVehiclesInArea": total_vehicles,
                "radius": radius_m,
                "timeWindow": time_window_sec,
                "congestionLevel": "none",
                "centerLat": lat,
                "centerLng": lng,
                "message": f"{vehicles_passed} vehicles passed through (none stayed ≥{time_window_sec}s)",
                "avgPointsPerVehicle": avg_points if point_counts else 0
            }
        
        return {
            "vehicleCount": vehicles_stayed,
            "totalVehiclesInArea": total_vehicles,
            "radius": radius_m,
            "timeWindow": time_window_sec,
            "congestionLevel": congestion_level,
            "centerLat": lat,
            "centerLng": lng,
            "avgPointsPerVehicle": avg_points if point_counts else 0
        }
        
    except Exception as e:
        logger.error(f"Traffic analysis error: {e}")
        return {
            "vehicleCount": 0,
            "error": str(e),
            "message": "Error analyzing traffic data"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)