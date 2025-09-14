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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)