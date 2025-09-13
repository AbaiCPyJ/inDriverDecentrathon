import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from sklearn.cluster import DBSCAN
from collections import defaultdict

class DataProcessor:
    """Process geodata for various analyses"""
    
    def __init__(self):
        self.earth_radius_km = 6371.0
    
    def calculate_statistics(self, df: pd.DataFrame, analysis_type: str) -> Dict[str, Any]:
        """Calculate statistics based on analysis type"""
        stats = {
            "totalRecords": len(df),
            "uniqueVehicles": df['randomized_id'].nunique(),
            "avgSpeed": round(df['speed_kmh'].mean(), 2),
            "maxSpeed": round(df['speed_kmh'].max(), 2),
            "minSpeed": round(df['speed_kmh'].min(), 2),
        }
        
        if analysis_type == "popular-routes":
            # Calculate route popularity metrics
            stats["totalDistance"] = self._calculate_total_distance(df)
            stats["routeDensity"] = self._calculate_route_density(df)
            
        elif analysis_type == "endpoints":
            # Calculate endpoint statistics
            endpoints = self._extract_trip_endpoints(df)
            stats["totalTrips"] = len(endpoints)
            stats["uniquePickupPoints"] = len(set((p[0], p[1]) for p, _ in endpoints))
            stats["uniqueDropoffPoints"] = len(set((d[0], d[1]) for _, d in endpoints))
            
        elif analysis_type == "speed":
            # Calculate speed distribution statistics
            stats["speedPercentiles"] = {
                "25th": round(df['speed_kmh'].quantile(0.25), 2),
                "50th": round(df['speed_kmh'].quantile(0.50), 2),
                "75th": round(df['speed_kmh'].quantile(0.75), 2),
                "95th": round(df['speed_kmh'].quantile(0.95), 2),
            }
            stats["congestionAreas"] = self._identify_congestion_areas(df)
            
        elif analysis_type == "trajectories":
            # Calculate demand density statistics
            stats["coverageArea"] = self._calculate_coverage_area(df)
            stats["demandHotspots"] = self._identify_demand_hotspots(df)
        
        return stats
    
    def _calculate_total_distance(self, df: pd.DataFrame) -> float:
        """Calculate total distance traveled by all vehicles"""
        total_distance = 0
        
        for vehicle_id in df['randomized_id'].unique():
            vehicle_data = df[df['randomized_id'] == vehicle_id].sort_index()
            if len(vehicle_data) > 1:
                for i in range(1, len(vehicle_data)):
                    dist = self._haversine_distance(
                        vehicle_data.iloc[i-1]['lat'], vehicle_data.iloc[i-1]['lng'],
                        vehicle_data.iloc[i]['lat'], vehicle_data.iloc[i]['lng']
                    )
                    total_distance += dist
        
        return round(total_distance, 2)
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        return self.earth_radius_km * c
    
    def _calculate_route_density(self, df: pd.DataFrame) -> Dict[str, int]:
        """Calculate route density in grid cells"""
        # Create grid cells (simplified approach)
        lat_bins = pd.cut(df['lat'], bins=20)
        lng_bins = pd.cut(df['lng'], bins=20)
        
        density = df.groupby([lat_bins, lng_bins]).size()
        
        return {
            "highDensityCells": int((density > density.quantile(0.75)).sum()),
            "mediumDensityCells": int((density > density.quantile(0.5)).sum()),
            "lowDensityCells": int((density > 0).sum())
        }
    
    def _extract_trip_endpoints(self, df: pd.DataFrame) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """Extract trip start and end points for each vehicle"""
        endpoints = []
        
        for vehicle_id in df['randomized_id'].unique():
            vehicle_data = df[df['randomized_id'] == vehicle_id].sort_index()
            if len(vehicle_data) > 1:
                start_point = (vehicle_data.iloc[0]['lat'], vehicle_data.iloc[0]['lng'])
                end_point = (vehicle_data.iloc[-1]['lat'], vehicle_data.iloc[-1]['lng'])
                endpoints.append((start_point, end_point))
        
        return endpoints
    
    def _identify_congestion_areas(self, df: pd.DataFrame) -> int:
        """Identify areas with low speed (congestion)"""
        # Consider speeds below 20 km/h as congestion
        congestion_threshold = 20.0
        congested_points = df[df['speed_kmh'] < congestion_threshold]
        
        if len(congested_points) > 0:
            # Use DBSCAN to cluster congested areas
            coords = congested_points[['lat', 'lng']].values
            clustering = DBSCAN(eps=0.001, min_samples=5).fit(coords)
            n_clusters = len(set(clustering.labels_)) - (1 if -1 in clustering.labels_ else 0)
            return n_clusters
        
        return 0
    
    def _calculate_coverage_area(self, df: pd.DataFrame) -> float:
        """Calculate approximate coverage area in km²"""
        lat_range = df['lat'].max() - df['lat'].min()
        lng_range = df['lng'].max() - df['lng'].min()
        
        # Approximate area calculation (simplified)
        avg_lat = df['lat'].mean()
        lat_km = lat_range * 111.0  # 1 degree latitude ≈ 111 km
        lng_km = lng_range * 111.0 * np.cos(np.radians(avg_lat))
        
        return round(lat_km * lng_km, 2)
    
    def _identify_demand_hotspots(self, df: pd.DataFrame) -> int:
        """Identify high-demand areas using density-based clustering"""
        # Sample points to avoid memory issues with large datasets
        sample_size = min(10000, len(df))
        sampled_df = df.sample(n=sample_size) if len(df) > sample_size else df
        
        coords = sampled_df[['lat', 'lng']].values
        clustering = DBSCAN(eps=0.002, min_samples=10).fit(coords)
        n_clusters = len(set(clustering.labels_)) - (1 if -1 in clustering.labels_ else 0)
        
        return n_clusters
    
    def process_trajectories(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Process and reconstruct vehicle trajectories"""
        trajectories = {}
        
        for vehicle_id in df['randomized_id'].unique():
            vehicle_data = df[df['randomized_id'] == vehicle_id].sort_index()
            trajectories[vehicle_id] = vehicle_data[['lat', 'lng', 'speed_kmh', 'azm']].copy()
        
        return trajectories
