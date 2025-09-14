# data_processing.py
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from sklearn.cluster import DBSCAN

class DataProcessor:
    """Process geodata for various analyses"""

    def __init__(self, ef_kg_per_km: float = 0.192):
        self.earth_radius_km = 6371.0
        self.ef_kg_per_km = ef_kg_per_km  # constant emission factor (kg CO2e / km)

    # ---------- utilities ----------
    def _sort_by_time(self, g: pd.DataFrame) -> pd.DataFrame:
        for col in ("timestamp", "time", "ts", "datetime"):
            if col in g.columns:
                return g.sort_values(col)
        return g.sort_index()

    def _haversine_km(self, lat1, lon1, lat2, lon2) -> float:
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        return float(self.earth_radius_km * c)

    # ---------- filters / sampling ----------
    def apply_filters(self, df: pd.DataFrame, filters: Dict[str, Any]):
        if not filters:
            return df
        if "vehicleIds" in filters:
            df = df[df["randomized_id"].isin(filters["vehicleIds"])]
        if "bbox" in filters:  # [minLat, minLng, maxLat, maxLng]
            a, b, c, d = filters["bbox"]
            df = df[(df["lat"].between(a, c)) & (df["lng"].between(b, d))]
        if "dateFrom" in filters or "dateTo" in filters:
            for col in ("timestamp", "time", "ts", "datetime"):
                if col in df.columns:
                    t = pd.to_datetime(df[col], errors="coerce", utc=True)
                    if "dateFrom" in filters:
                        df = df[t >= pd.to_datetime(filters["dateFrom"], utc=True)]
                    if "dateTo" in filters:
                        df = df[t <= pd.to_datetime(filters["dateTo"], utc=True)]
                    break
        return df

    def safe_sample(self, df: pd.DataFrame, max_rows: int) -> pd.DataFrame:
        vehicle_ids = df["randomized_id"].dropna().unique()
        if len(vehicle_ids) == 0:
            return df.sample(n=min(len(df), max_rows))
        per = max(1, max_rows // max(1, len(vehicle_ids)))
        if per < 2:
            vcount = min(len(vehicle_ids), max(1, max_rows // 10))
            sample_vehicles = np.random.choice(vehicle_ids, size=vcount, replace=False)
            return df[df["randomized_id"].isin(sample_vehicles)]
        return (df.groupby("randomized_id", group_keys=False)
                  .apply(lambda x: x.sample(n=min(len(x), per), replace=False)))

    # ---------- emissions ----------
    def add_segment_distance_and_emissions(self, df: pd.DataFrame) -> pd.DataFrame:
        def per_vehicle(g: pd.DataFrame) -> pd.DataFrame:
            g = self._sort_by_time(g)
            lat = g["lat"].to_numpy()
            lng = g["lng"].to_numpy()
            seg = np.zeros(len(g))
            if len(g) > 1:
                lat1, lon1, lat2, lon2 = lat[:-1], lng[:-1], lat[1:], lng[1:]
                rlat1, rlon1, rlat2, rlon2 = map(np.radians, [lat1, lon1, lat2, lon2])
                dlat = rlat2 - rlat1; dlon = rlon2 - rlon1
                a = np.sin(dlat/2)**2 + np.cos(rlat1)*np.cos(rlat2)*np.sin(dlon/2)**2
                c = 2*np.arcsin(np.sqrt(a))
                seg[1:] = self.earth_radius_km * c
            g = g.copy()
            g["segment_km"] = seg
            g["segment_kg_co2e"] = seg * self.ef_kg_per_km
            return g
        return df.groupby("randomized_id", group_keys=False).apply(per_vehicle)

    # ---------- stats ----------
    def calculate_statistics(self, df: pd.DataFrame, analysis_type: str) -> Dict[str, Any]:
        stats = {
            "totalRecords": int(len(df)),
            "uniqueVehicles": int(df["randomized_id"].nunique()),
            "avgSpeed": round(float(df["speed_kmh"].mean()) if "speed_kmh" in df else 0.0, 2),
            "maxSpeed": round(float(df["speed_kmh"].max()) if "speed_kmh" in df else 0.0, 2),
            "minSpeed": round(float(df["speed_kmh"].min()) if "speed_kmh" in df else 0.0, 2),
        }

        if analysis_type == "popular-routes":
            stats["totalDistanceKm"] = self._total_distance(df)
            stats["routeDensity"] = self._route_density(df)
        elif analysis_type == "endpoints":
            trips = self._extract_endpoints(df)
            stats["totalTrips"] = len(trips)
            stats["uniquePickupPoints"] = len(set((p[0], p[1]) for p, _ in trips))
            stats["uniqueDropoffPoints"] = len(set((d[0], d[1]) for _, d in trips))
        elif analysis_type == "speed":
            q = df["speed_kmh"].quantile if "speed_kmh" in df else (lambda _: 0)
            stats["speedPercentiles"] = {
                "25th": round(float(q(0.25)), 2),
                "50th": round(float(q(0.50)), 2),
                "75th": round(float(q(0.75)), 2),
                "95th": round(float(q(0.95)), 2),
            }
            stats["congestionAreas"] = int(self._congestion_clusters(df))
        elif analysis_type == "trajectories":
            stats["coverageAreaKm2"] = self._coverage_area(df)
            stats["demandHotspots"] = int(self._demand_hotspots(df))
        elif analysis_type == "ghg":
            total_kg = float(df.get("segment_kg_co2e", pd.Series(dtype=float)).sum())
            stats["totalEmissionsKgCO2e"] = round(total_kg, 2)
            stats["emissionsPerVehicleKgCO2e"] = round(total_kg / max(1, df["randomized_id"].nunique()), 2)
        return stats

    # --- helpers used by stats ---
    def _total_distance(self, df: pd.DataFrame) -> float:
        total = 0.0
        for vid in df["randomized_id"].unique():
            g = self._sort_by_time(df[df["randomized_id"] == vid])
            if len(g) > 1:
                for i in range(1, len(g)):
                    total += self._haversine_km(g.iloc[i-1]["lat"], g.iloc[i-1]["lng"], g.iloc[i]["lat"], g.iloc[i]["lng"])
        return round(total, 2)

    def _route_density(self, df: pd.DataFrame) -> Dict[str, int]:
        lat_bins = pd.cut(df["lat"], bins=20)
        lng_bins = pd.cut(df["lng"], bins=20)
        density = df.groupby([lat_bins, lng_bins]).size()
        return {
            "highDensityCells": int((density > density.quantile(0.75)).sum()),
            "mediumDensityCells": int((density > density.quantile(0.50)).sum()),
            "lowDensityCells": int((density > 0).sum())
        }

    def _extract_endpoints(self, df: pd.DataFrame) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        endpoints = []
        for vid in df["randomized_id"].unique():
            g = self._sort_by_time(df[df["randomized_id"] == vid])
            if len(g) > 1:
                endpoints.append(((g.iloc[0]["lat"], g.iloc[0]["lng"]), (g.iloc[-1]["lat"], g.iloc[-1]["lng"])))
        return endpoints

    def _congestion_clusters(self, df: pd.DataFrame) -> int:
        if "speed_kmh" not in df: return 0
        congestion = df[df["speed_kmh"] < 20.0]
        if congestion.empty: return 0
        coords = congestion[["lat", "lng"]].values
        clustering = DBSCAN(eps=0.001, min_samples=5).fit(coords)  # ~100 m near equator
        return len(set(clustering.labels_)) - (1 if -1 in clustering.labels_ else 0)

    def _coverage_area(self, df: pd.DataFrame) -> float:
        lat_range = df["lat"].max() - df["lat"].min()
        lng_range = df["lng"].max() - df["lng"].min()
        avg_lat = df["lat"].mean()
        lat_km = lat_range * 111.0
        lng_km = lng_range * 111.0 * np.cos(np.radians(avg_lat))
        return round(lat_km * lng_km, 2)

    def _demand_hotspots(self, df: pd.DataFrame) -> int:
        sample_size = min(10000, len(df))
        sampled = df.sample(n=sample_size) if len(df) > sample_size else df
        coords = sampled[["lat", "lng"]].values
        clustering = DBSCAN(eps=0.002, min_samples=10).fit(coords)
        return len(set(clustering.labels_)) - (1 if -1 in clustering.labels_ else 0)