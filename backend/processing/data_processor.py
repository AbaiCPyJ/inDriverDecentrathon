# processing/data_processor.py
from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN

# ------------------------- Helpers -------------------------------------------
def _meters_per_degree(lat_deg: float) -> Tuple[float, float]:
    """Return (m_per_deg_lon, m_per_deg_lat) at given latitude."""
    lat = np.radians(lat_deg)
    m_per_deg_lat = 111_132.92 - 559.82*np.cos(2*lat) + 1.175*np.cos(4*lat)
    m_per_deg_lon = 111_412.84*np.cos(lat) - 93.5*np.cos(3*lat)
    return float(m_per_deg_lon), float(m_per_deg_lat)

def _bearing_deg(dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    """Bearing degrees from point i to j; 0=N, 90=E (y is north, x is east)."""
    ang = np.degrees(np.arctan2(dx, dy)) % 360.0
    return ang

def _ang_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Smallest absolute difference between two bearings in degrees."""
    d = np.abs((a - b + 180.0) % 360.0 - 180.0)
    return d

# ------------------------- Configs -------------------------------------------
@dataclass
class PathReconstructionConfig:
    k_neighbors: int = 6
    max_link_m: float = 160.0        # hard cap for step length
    heading_tol_deg: float = 35.0    # acceptable azimuth deviation
    expected_step_s: float = 10.0    # typical time between pings (sec), used as heuristic
    min_speed_kmh: float = 1.0       # we suppress nearly-static points
    random_seed: int = 42

# ------------------------- Processor -----------------------------------------
class DataProcessor:
    """
    High-performance data processor for time-free geotrack points with azimuth.
    Key features:
    - Deterministic thinning (max rows) while preserving per-vehicle coverage
    - Azimuth-aware path reconstruction (nearest-neighbor chaining)
    - Meter-based aggregation and clustering
    - Distance & GHG calculation
    """

    def __init__(self, ef_kg_per_km: float = 0.192, max_rows: int = 50_000):
        self.ef_kg_per_km = float(ef_kg_per_km)
        self.max_rows = int(max_rows)
        np.random.seed(42)

    # ---------- filters / sampling ----------
    def apply_filters(self, df: pd.DataFrame, filters: Dict[str, Any]):
        if not filters:
            return df
        out = df
        if "vehicleIds" in filters and "randomized_id" in out:
            out = out[out["randomized_id"].isin(filters["vehicleIds"])]
        if "bbox" in filters and all(k in out for k in ("lat","lng")):
            a,b,c,d = filters["bbox"]  # [minLat, minLng, maxLat, maxLng]
            out = out[(out["lat"].between(a, c)) & (out["lng"].between(b, d))]
        return out

    def safe_sample(self, df: pd.DataFrame) -> pd.DataFrame:
        """Deterministic thin if rows exceed cap; preserve per-vehicle representation."""
        n = len(df)
        if n <= self.max_rows:
            return df
        if "randomized_id" not in df:
            return df.sample(n=self.max_rows, random_state=42)
        # stratified by vehicle
        vids = df["randomized_id"].dropna().unique()
        per = max(1, self.max_rows // max(1, len(vids)))
        def take(g):
            m = min(len(g), per)
            return g.sample(n=m, random_state=42)
        return df.groupby("randomized_id", group_keys=False).apply(take)

    # ---------- enrichment ----------
    def ensure_speed_kmh(self, df: pd.DataFrame):
        if "spd" in df.columns:
            df["speed_kmh"] = pd.to_numeric(df["spd"], errors="coerce").astype(float) * 3.6
        else:
            df["speed_kmh"] = np.nan

    # ---------- meters projection ----------
    def _to_xy(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, float, float, float, float]:
        """Add x_m,y_m columns using a local planar approximation centered on mean lat/lng."""
        lat0 = float(df["lat"].mean())
        lng0 = float(df["lng"].mean())
        mx, my = _meters_per_degree(lat0)        # meters per degree lon/lat
        x_m = (df["lng"].values - lng0) * mx
        y_m = (df["lat"].values - lat0) * my
        out = df.copy()
        out["x_m"] = x_m; out["y_m"] = y_m
        return out, lat0, lng0, mx, my

    # ---------- path reconstruction ----------
    def reconstruct_paths(self, df: pd.DataFrame, cfg: PathReconstructionConfig) -> pd.DataFrame:
        """
        Build directed chains per vehicle using nearest-neighbor edges that:
        - are within max_link_m,
        - align with source azimuth within heading_tol_deg,
        - prefer distance close to expected_step (speed * expected_step_s).
        Returns a segments DataFrame with columns:
        ['randomized_id','lat1','lng1','lat2','lng2','dist_km','segment_kg_co2e','x1','y1','x2','y2']
        """
        if len(df) == 0:
            return pd.DataFrame(columns=[
                "randomized_id","lat1","lng1","lat2","lng2",
                "dist_km","segment_kg_co2e","x1","y1","x2","y2"
            ])
        # basic guards
        if not {"lat","lng","randomized_id","azm"}.issubset(df.columns):
            raise ValueError("reconstruct_paths requires columns: randomized_id, lat, lng, azm")

        segments = []
        for vid, g in df.groupby("randomized_id", sort=False):
            g = g.reset_index(drop=True).copy()
            # suppress near-static points to reduce ambiguity
            if "speed_kmh" in g:
                g = g[g["speed_kmh"].fillna(0) >= cfg.min_speed_kmh].reset_index(drop=True)
            if len(g) < 2:
                continue

            g_xy, lat0, lng0, mx, my = self._to_xy(g)
            X = g_xy[["x_m","y_m"]].values
            azm = g_xy["azm"].astype(float).values
            spd = g_xy["speed_kmh"].astype(float).values if "speed_kmh" in g_xy else np.zeros(len(g_xy))

            # KNN in meters
            knn = NearestNeighbors(n_neighbors=min(cfg.k_neighbors+1, len(g_xy)), algorithm="auto").fit(X)
            nn_dist, nn_idx = knn.kneighbors(X, return_distance=True)

            # For each node pick at most one successor that maximizes a composite score
            succ = np.full(len(g_xy), -1, dtype=int)
            pred = np.full(len(g_xy), -1, dtype=int)
            max_d = cfg.max_link_m

            for i in range(len(g_xy)):
                # candidates skip self at index 0
                cand_idx = nn_idx[i, 1:]
                cand_dist = nn_dist[i, 1:]
                if cand_idx.size == 0: 
                    continue
                # compute geometric features
                dx = X[cand_idx,0] - X[i,0]
                dy = X[cand_idx,1] - X[i,1]
                bearing = _bearing_deg(dx, dy)
                ang = _ang_diff(azm[i], bearing)
                # masks
                ok = (cand_dist <= max_d) & (ang <= cfg.heading_tol_deg)
                if not np.any(ok): 
                    continue
                cand_idx = cand_idx[ok]; cand_dist = cand_dist[ok]; ang = ang[ok]
                # expected step from speed (fallback to half max_d)
                expected = np.clip((spd[i] / 3.6) * cfg.expected_step_s, 0.25*max_d, 0.8*max_d)
                # score: prefer small angle + distance near expected
                score = 0.7*(1.0 - ang/cfg.heading_tol_deg) + 0.3*(1.0 - np.abs(cand_dist-expected)/max_d)
                j = int(cand_idx[np.argmax(score)])
                # ensure each node has <=1 succ and each target has <=1 pred (best wins)
                if pred[j] != -1:
                    # compare existing edge with new one; keep better angular alignment
                    j_prev = np.where(succ == j)[0]
                    old_ok = False
                    if j_prev.size:
                        old_i = j_prev[0]
                        # recompute old angle score
                        dx_old = X[j,0]-X[old_i,0]; dy_old = X[j,1]-X[old_i,1]
                        old_ang = _ang_diff(azm[old_i], _bearing_deg(np.array([dx_old]), np.array([dy_old])))[0]
                        if old_ang <= cfg.heading_tol_deg and old_ang <= np.min(ang):
                            old_ok = True
                    if old_ok:
                        continue  # keep existing pred
                    else:
                        # detach old predecessor
                        if j_prev.size:
                            succ[j_prev[0]] = -1
                succ[i] = j
                pred[j] = i

            # Extract chains (acyclic by construction)
            visited = np.zeros(len(g_xy), dtype=bool)
            for i in range(len(g_xy)):
                if visited[i] or pred[i] != -1:  # start only from heads
                    continue
                path = [i]
                visited[i] = True
                cur = i
                while succ[cur] != -1 and not visited[succ[cur]]:
                    nxt = succ[cur]
                    path.append(nxt)
                    visited[nxt] = True
                    cur = nxt
                # convert path to segments
                if len(path) >= 2:
                    p = np.array(path, dtype=int)
                    x1 = X[p[:-1],0]; y1 = X[p[:-1],1]
                    x2 = X[p[1:],0];  y2 = X[p[1:],1]
                    d_m = np.hypot(x2-x1, y2-y1)
                    d_km = d_m / 1000.0
                    kg = d_km * self.ef_kg_per_km
                    lat1 = g_xy["lat"].values[p[:-1]]; lng1 = g_xy["lng"].values[p[:-1]]
                    lat2 = g_xy["lat"].values[p[1:]];  lng2 = g_xy["lng"].values[p[1:]]
                    seg = pd.DataFrame({
                        "randomized_id": vid,
                        "lat1": lat1, "lng1": lng1, "lat2": lat2, "lng2": lng2,
                        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "dist_km": d_km, "segment_kg_co2e": kg
                    })
                    segments.append(seg)

        if not segments:
            return pd.DataFrame(columns=[
                "randomized_id","lat1","lng1","lat2","lng2",
                "dist_km","segment_kg_co2e","x1","y1","x2","y2"
            ])
        return pd.concat(segments, ignore_index=True)

    # ---------- stats ----------
    def calculate_statistics(self, df: pd.DataFrame, segments: Optional[pd.DataFrame], analysis_type: str) -> Dict[str, Any]:
        stats = {
            "totalRecords": int(len(df)),
            "uniqueVehicles": int(df["randomized_id"].nunique()) if "randomized_id" in df else 0,
            "avgSpeed": round(float(df["speed_kmh"].mean()) if "speed_kmh" in df else 0.0, 2),
            "maxSpeed": round(float(df["speed_kmh"].max()) if "speed_kmh" in df else 0.0, 2),
            "minSpeed": round(float(df["speed_kmh"].min()) if "speed_kmh" in df else 0.0, 2),
        }
        if analysis_type in {"popular-routes","trajectories","endpoints","ghg"} and segments is not None:
            total_km = float(segments["dist_km"].sum())
            stats["totalDistanceKm"] = round(total_km, 2)
            if analysis_type == "ghg":
                stats["totalEmissionsKgCO2e"] = round(float(segments["segment_kg_co2e"].sum()), 2)
                vid = df["randomized_id"].nunique() if "randomized_id" in df else 1
                stats["emissionsPerVehicleKgCO2e"] = round(stats["totalEmissionsKgCO2e"] / max(1, vid), 2)
        if analysis_type == "speed":
            s = df["speed_kmh"].dropna()
            if len(s):
                stats["speedPercentiles"] = {
                    "p25": round(float(s.quantile(0.25)), 2),
                    "p50": round(float(s.quantile(0.50)), 2),
                    "p75": round(float(s.quantile(0.75)), 2),
                    "p95": round(float(s.quantile(0.95)), 2),
                }
                # low-speed hotspots (cluster count)
                low = df[df["speed_kmh"] < max(5.0, float(s.quantile(0.25)))]
                if len(low) >= 5:
                    lat0 = float(low["lat"].mean())
                    mx, my = _meters_per_degree(lat0)
                    eps_m = 120.0
                    eps_deg = eps_m / ((mx + my)/2)  # rough, ok for clustering
                    labels = DBSCAN(eps=eps_deg, min_samples=8).fit(low[["lat","lng"]].values).labels_
                    stats["congestionAreas"] = int(len(set(labels)) - (1 if -1 in labels else 0))
                else:
                    stats["congestionAreas"] = 0
        return stats