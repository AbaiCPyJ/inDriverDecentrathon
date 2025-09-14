# main.py
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import uuid
from pathlib import Path
import logging
import traceback

from processing.data_processor import DataProcessor
from processing.heatmap_generator import HeatmapGenerator
# -------------------------------------------

app = FastAPI(title="InDrive Geotracks API", version="1.1.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CORS from env (comma-separated)
origins = os.environ.get("ALLOW_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads"); UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR = Path("results"); RESULTS_DIR.mkdir(exist_ok=True)

jobs_db: Dict[str, Dict] = {}

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

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "max_process_rows": int(os.environ.get('MAX_PROCESS_ROWS', '50000')),
        "ef_kg_per_km": float(os.environ.get("EF_KG_PER_KM", "0.192")),
        "active_jobs": len([j for j in jobs_db.values() if j["status"] == "running"])
    }

@app.post("/api/jobs", response_model=JobResponse)
async def create_job(
    analysisType: str = Form(...),                       # "popular-routes" | "endpoints" | "trajectories" | "speed" | "ghg"
    csvFile: UploadFile = File(...),
    filters: Optional[str] = Form("{}"),
    visualization: Optional[str] = Form("{}")
):
    try:
        # quick CSV validation + streaming write
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
            "config": {"analysisType": analysisType, "filters": filters_dict, "visualization": visualization_dict},
            "createdAt": datetime.utcnow().isoformat(),
            "startedAt": None,
            "completedAt": None,
            "error": None,
            "progress": 0,
            "results": None,
            "file_path": str(file_path)
        }
        jobs_db[job_id] = job

        import asyncio
        asyncio.create_task(process_job(job_id))
        logger.info(f"Job {job_id} created")
        return JobResponse(**job)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_job failed")
        raise HTTPException(status_code=500, detail=str(e))

async def process_job(job_id: str):
    def cancelled() -> bool:
        return jobs_db.get(job_id, {}).get("status") == "cancelled"

    try:
        logger.info(f"Starting job {job_id}")
        job = jobs_db[job_id]
        job["status"] = "running"
        job["startedAt"] = datetime.utcnow().isoformat()
        job["progress"] = 10

        processor = DataProcessor(ef_kg_per_km=float(os.environ.get("EF_KG_PER_KM", "0.192")))
        df = pd.read_csv(job["file_path"])
        if cancelled(): return

        # optional filters (bbox, vehicleIds, dateFrom/dateTo)
        df = processor.apply_filters(df, job["config"]["filters"])
        if cancelled(): return

        original_size = len(df)
        MAX_ROWS = int(os.environ.get('MAX_PROCESS_ROWS', '50000'))
        if original_size > MAX_ROWS:
            df = processor.safe_sample(df, MAX_ROWS)
        job["progress"] = 30

        # speed (m/s -> km/h) based on your schema
        if "spd" in df.columns:
            df["speed_kmh"] = df["spd"].astype(float) * 3.6
        else:
            df["speed_kmh"] = np.nan

        analysis_type = job["config"]["analysisType"]
        if analysis_type == "ghg":
            df = processor.add_segment_distance_and_emissions(df)

        job["progress"] = 50

        generator = HeatmapGenerator()
        if analysis_type == "popular-routes":
            map_html = generator.generate_popular_routes_heatmap(df)
        elif analysis_type == "endpoints":
            map_html = generator.generate_endpoints_heatmap(df)
        elif analysis_type == "speed":
            map_html = generator.generate_speed_heatmap(df)
        elif analysis_type == "trajectories":
            map_html = generator.generate_demand_density_heatmap(df)  # trajectories summary
        elif analysis_type == "ghg":
            map_html = generator.generate_ghg_emissions_heatmap(df)
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")

        job["progress"] = 80

        map_path = RESULTS_DIR / f"{job_id}.html"
        with open(map_path, "w", encoding="utf-8") as f:
            f.write(map_html)

        stats = processor.calculate_statistics(df, analysis_type)
        if original_size > MAX_ROWS:
            stats["note"] = f"Data sampled from {original_size} to {len(df)} rows for performance"

        job["status"] = "completed"
        job["completedAt"] = datetime.utcnow().isoformat()
        job["progress"] = 100
        job["results"] = {"mapUrl": f"/api/maps/{job_id}.html", "statistics": stats}
        logger.info(f"Job {job_id} completed")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
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
    # stop path traversal
    candidate = (RESULTS_DIR / filename).resolve()
    if RESULTS_DIR.resolve() not in candidate.parents and candidate != RESULTS_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Map not found")
    return FileResponse(candidate, media_type="text/html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)