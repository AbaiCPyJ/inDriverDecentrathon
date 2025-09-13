from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
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

from processing.heatmap_generator import HeatmapGenerator
from processing.data_processor import DataProcessor

app = FastAPI(title="InDrive Geotracks API", version="1.0.0")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create necessary directories
UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("results")
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# In-memory job storage (in production, use a database)
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
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "max_process_rows": int(os.environ.get('MAX_PROCESS_ROWS', '50000')),
        "active_jobs": len([j for j in jobs_db.values() if j["status"] == "running"])
    }

@app.post("/api/jobs", response_model=JobResponse)
async def create_job(
    analysisType: str = Form(...),
    csvFile: UploadFile = File(...),
    filters: Optional[str] = Form("{}"),
    visualization: Optional[str] = Form("{}")
):
    """Create a new analysis job"""
    try:
        # Validate CSV file
        if not csvFile.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV")
        
        # Generate job ID
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        
        # Save uploaded file
        file_path = UPLOAD_DIR / f"{job_id}_{csvFile.filename}"
        content = await csvFile.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Parse filters and visualization settings
        try:
            filters_dict = json.loads(filters)
            visualization_dict = json.loads(visualization)
        except json.JSONDecodeError:
            filters_dict = {}
            visualization_dict = {}
        
        # Create job entry
        job = {
            "id": job_id,
            "status": "pending",
            "config": {
                "analysisType": analysisType,
                "filters": filters_dict,
                "visualization": visualization_dict
            },
            "createdAt": datetime.utcnow().isoformat(),
            "startedAt": None,
            "completedAt": None,
            "error": None,
            "progress": 0,
            "results": None,
            "file_path": str(file_path)
        }
        
        jobs_db[job_id] = job
        
        # Process the job asynchronously (in production, use a task queue)
        import asyncio
        asyncio.create_task(process_job(job_id))
        
        logger.info(f"Job {job_id} created and processing started")
        
        return JobResponse(**job)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def process_job(job_id: str):
    """Process the analysis job"""
    try:
        logger.info(f"Starting job {job_id}")
        job = jobs_db[job_id]
        job["status"] = "running"
        job["startedAt"] = datetime.utcnow().isoformat()
        job["progress"] = 10
        
        # Load and process data
        logger.info(f"Loading CSV file: {job['file_path']}")
        processor = DataProcessor()
        
        # Read CSV and check size
        df = pd.read_csv(job["file_path"])
        original_size = len(df)
        logger.info(f"Loaded {original_size} rows")
        
        # Sample data if too large (configurable via env var)
        MAX_ROWS = int(os.environ.get('MAX_PROCESS_ROWS', '50000'))
        if original_size > MAX_ROWS:
            logger.info(f"Dataset too large ({original_size} rows), sampling to {MAX_ROWS} rows")
            # Take a stratified sample by vehicle ID to preserve trajectories
            vehicle_ids = df['randomized_id'].unique()
            sample_size_per_vehicle = MAX_ROWS // len(vehicle_ids)
            if sample_size_per_vehicle < 2:
                # If too many vehicles, sample vehicles instead
                sample_vehicles = np.random.choice(vehicle_ids, size=MAX_ROWS // 10, replace=False)
                df = df[df['randomized_id'].isin(sample_vehicles)]
            else:
                # Sample points from each vehicle
                df = df.groupby('randomized_id').apply(
                    lambda x: x.sample(n=min(len(x), sample_size_per_vehicle))
                ).reset_index(drop=True)
            logger.info(f"Sampled to {len(df)} rows")
        
        # Convert speed from m/s to km/h
        df['speed_kmh'] = df['spd'] * 3.6
        
        job["progress"] = 30
        logger.info("Data preprocessing complete")
        
        # Generate heatmap based on analysis type
        generator = HeatmapGenerator()
        analysis_type = job["config"]["analysisType"]
        logger.info(f"Generating {analysis_type} heatmap")
        
        if analysis_type == "popular-routes":
            map_html = generator.generate_popular_routes_heatmap(df)
        elif analysis_type == "endpoints":
            map_html = generator.generate_endpoints_heatmap(df)
        elif analysis_type == "speed":
            map_html = generator.generate_speed_heatmap(df)
        elif analysis_type == "trajectories":
            map_html = generator.generate_demand_density_heatmap(df)
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
        
        job["progress"] = 80
        logger.info("Heatmap generation complete")
        
        # Save map HTML
        map_path = RESULTS_DIR / f"{job_id}.html"
        with open(map_path, "w") as f:
            f.write(map_html)
        logger.info(f"Map saved to {map_path}")
        
        # Calculate statistics
        stats = processor.calculate_statistics(df, analysis_type)
        if original_size > MAX_ROWS:
            stats["note"] = f"Data sampled from {original_size} to {len(df)} rows for performance"
        
        # Update job with results
        job["status"] = "completed"
        job["completedAt"] = datetime.utcnow().isoformat()
        job["progress"] = 100
        job["results"] = {
            "mapUrl": f"/api/maps/{job_id}.html",
            "statistics": stats
        }
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}")
        logger.error(traceback.format_exc())
        job["status"] = "failed"
        job["error"] = str(e)
        job["completedAt"] = datetime.utcnow().isoformat()

@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get job details"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**jobs_db[job_id])

@app.get("/api/jobs", response_model=List[JobResponse])
async def list_jobs():
    """List all jobs"""
    return [JobResponse(**job) for job in jobs_db.values()]

@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a job"""
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
    """Serve generated map HTML"""
    map_path = RESULTS_DIR / filename
    if not map_path.exists():
        raise HTTPException(status_code=404, detail="Map not found")
    
    with open(map_path, "r") as f:
        content = f.read()
    
    return HTMLResponse(content=content)

@app.get("/api/data/stats")
async def get_data_stats():
    """Get data statistics"""
    total_records = 0
    unique_ids = set()
    
    for job in jobs_db.values():
        if job["status"] == "completed" and "file_path" in job:
            try:
                df = pd.read_csv(job["file_path"])
                total_records += len(df)
                unique_ids.update(df["randomized_id"].unique())
            except:
                pass
    
    return {
        "totalRecords": total_records,
        "uniqueIds": len(unique_ids),
        "fileSize": 0,  # Placeholder
        "lastUpdated": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
