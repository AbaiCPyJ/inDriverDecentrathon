import folium
from folium import plugins
import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Any
from sklearn.cluster import DBSCAN
import json

class HeatmapGenerator:
    """Generate various types of heatmaps for geodata visualization"""
    
    def __init__(self):
        # Default map center (Astana, Kazakhstan based on sample data)
        self.default_center = [51.0954, 71.4275]
        self.default_zoom = 12
    
    def generate_popular_routes_heatmap(self, df: pd.DataFrame) -> str:
        """
        Generate a heatmap showing popular routes based on GPS density
        Each GPS point contributes to intensity value
        """
        # Create base map
        m = folium.Map(
            location=self._get_map_center(df),
            zoom_start=self.default_zoom,
            tiles='OpenStreetMap'
        )
        
        # Prepare heatmap data
        heat_data = []
        
        # Group by small grid cells to aggregate nearby points
        df['lat_round'] = df['lat'].round(4)
        df['lng_round'] = df['lng'].round(4)
        
        # Count frequency of each location
        location_counts = df.groupby(['lat_round', 'lng_round']).size().reset_index(name='count')
        
        # Create weighted heatmap data
        for _, row in location_counts.iterrows():
            # Weight based on frequency (normalized)
            weight = min(row['count'] / location_counts['count'].max(), 1.0)
            heat_data.append([row['lat_round'], row['lng_round'], weight])
        
        # Add heatmap layer
        plugins.HeatMap(
            heat_data,
            name='Popular Routes',
            min_opacity=0.3,
            max_zoom=18,
            radius=25,
            blur=20,
            gradient={
                0.0: 'blue',
                0.25: 'cyan',
                0.5: 'lime',
                0.75: 'yellow',
                1.0: 'red'
            }
        ).add_to(m)
        
        # Add route lines for each vehicle
        unique_vehicles = df['randomized_id'].unique()
        # Limit vehicles shown based on dataset size
        max_vehicles = min(50, len(unique_vehicles))
        sample_vehicles = np.random.choice(unique_vehicles, size=max_vehicles, replace=False)
        
        for vehicle_id in sample_vehicles:
            vehicle_data = df[df['randomized_id'] == vehicle_id].sort_index()
            if len(vehicle_data) > 1:
                route_coords = vehicle_data[['lat', 'lng']].values.tolist()
                folium.PolyLine(
                    route_coords,
                    color='blue',
                    weight=1,
                    opacity=0.3
                ).add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add title
        self._add_map_title(m, "Popular Routes Heat Map")
        
        return m._repr_html_()
    
    def generate_endpoints_heatmap(self, df: pd.DataFrame) -> str:
        """
        Generate a heatmap showing trip start and end points
        Uses DBSCAN clustering to identify dense pickup/dropoff zones
        """
        m = folium.Map(
            location=self._get_map_center(df),
            zoom_start=self.default_zoom,
            tiles='OpenStreetMap'
        )
        
        # Extract endpoints
        pickups = []
        dropoffs = []
        
        for vehicle_id in df['randomized_id'].unique():
            vehicle_data = df[df['randomized_id'] == vehicle_id].sort_index()
            if len(vehicle_data) > 1:
                # First point is pickup
                pickups.append([vehicle_data.iloc[0]['lat'], vehicle_data.iloc[0]['lng']])
                # Last point is dropoff
                dropoffs.append([vehicle_data.iloc[-1]['lat'], vehicle_data.iloc[-1]['lng']])
        
        # Create separate heatmaps for pickups and dropoffs
        if pickups:
            plugins.HeatMap(
                pickups,
                name='Pickup Points',
                min_opacity=0.4,
                max_zoom=18,
                radius=30,
                blur=25,
                gradient={
                    0.0: 'blue',
                    0.5: 'cyan',
                    0.75: 'lightgreen',
                    1.0: 'green'
                }
            ).add_to(m)
        
        if dropoffs:
            plugins.HeatMap(
                dropoffs,
                name='Dropoff Points',
                min_opacity=0.4,
                max_zoom=18,
                radius=30,
                blur=25,
                gradient={
                    0.0: 'yellow',
                    0.5: 'orange',
                    0.75: 'darkorange',
                    1.0: 'red'
                }
            ).add_to(m)
        
        # Add clustered markers for high-density areas
        if pickups:
            self._add_cluster_markers(m, pickups, 'Pickup Cluster', 'green')
        if dropoffs:
            self._add_cluster_markers(m, dropoffs, 'Dropoff Cluster', 'red')
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add title
        self._add_map_title(m, "Trip Endpoints Heat Map (Green: Pickups, Red: Dropoffs)")
        
        return m._repr_html_()
    
    def generate_speed_heatmap(self, df: pd.DataFrame) -> str:
        """
        Generate a heatmap based on vehicle speeds
        Low speeds create strong signals (indicating congestion)
        """
        m = folium.Map(
            location=self._get_map_center(df),
            zoom_start=self.default_zoom,
            tiles='OpenStreetMap'
        )
        
        # Create congestion heatmap (inverse speed - lower speed = higher intensity)
        congestion_data = []
        
        for _, row in df.iterrows():
            # Inverse weight: lower speeds get higher weights
            # Normalize speed to 0-1 range (assuming max reasonable speed is 100 km/h)
            normalized_speed = min(row['speed_kmh'] / 100.0, 1.0)
            # Invert for congestion representation
            congestion_weight = 1.0 - normalized_speed
            
            if congestion_weight > 0.3:  # Only show areas with some congestion
                congestion_data.append([row['lat'], row['lng'], congestion_weight])
        
        # Add congestion heatmap
        if congestion_data:
            plugins.HeatMap(
                congestion_data,
                name='Traffic Congestion',
                min_opacity=0.4,
                max_zoom=18,
                radius=20,
                blur=15,
                gradient={
                    0.0: 'green',
                    0.3: 'yellow',
                    0.6: 'orange',
                    0.8: 'red',
                    1.0: 'darkred'
                }
            ).add_to(m)
        
        # Add speed markers for a sample of points
        sample_size = min(500, len(df))
        sampled_df = df.sample(n=sample_size)
        
        for _, row in sampled_df.iterrows():
            color = self._get_speed_color(row['speed_kmh'])
            folium.CircleMarker(
                location=[row['lat'], row['lng']],
                radius=3,
                popup=f"Speed: {row['speed_kmh']:.1f} km/h",
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.6
            ).add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add title and legend
        self._add_map_title(m, "Speed Heat Map (Red: Congestion, Green: Free Flow)")
        self._add_speed_legend(m)
        
        return m._repr_html_()
    
    def generate_demand_density_heatmap(self, df: pd.DataFrame) -> str:
        """
        Generate a combined heatmap showing overall trip density
        Blends route popularity and endpoints
        """
        m = folium.Map(
            location=self._get_map_center(df),
            zoom_start=self.default_zoom,
            tiles='OpenStreetMap'
        )
        
        # Combine all data points with weights
        demand_data = []
        
        # Add route points with base weight
        for _, row in df.iterrows():
            demand_data.append([row['lat'], row['lng'], 0.5])
        
        # Add extra weight for endpoints
        for vehicle_id in df['randomized_id'].unique():
            vehicle_data = df[df['randomized_id'] == vehicle_id].sort_index()
            if len(vehicle_data) > 1:
                # Higher weight for start/end points
                demand_data.append([vehicle_data.iloc[0]['lat'], vehicle_data.iloc[0]['lng'], 1.0])
                demand_data.append([vehicle_data.iloc[-1]['lat'], vehicle_data.iloc[-1]['lng'], 1.0])
        
        # Create demand density heatmap
        plugins.HeatMap(
            demand_data,
            name='Demand Density',
            min_opacity=0.3,
            max_zoom=18,
            radius=25,
            blur=20,
            gradient={
                0.0: 'blue',
                0.25: 'cyan',
                0.5: 'yellow',
                0.75: 'orange',
                1.0: 'red'
            }
        ).add_to(m)
        
        # Identify and mark high-demand zones
        self._add_demand_zones(m, df)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add title
        self._add_map_title(m, "Demand Density Heat Map (Combined Activity)")
        
        return m._repr_html_()
    
    def _get_map_center(self, df: pd.DataFrame) -> List[float]:
        """Calculate map center from data"""
        return [df['lat'].mean(), df['lng'].mean()]
    
    def _add_cluster_markers(self, m: folium.Map, points: List[List[float]], 
                           label_prefix: str, color: str):
        """Add cluster markers using DBSCAN"""
        if len(points) < 5:
            return
        
        # Cluster endpoints
        coords = np.array(points)
        clustering = DBSCAN(eps=0.002, min_samples=5).fit(coords)
        
        # Add markers for each cluster center
        for cluster_id in set(clustering.labels_):
            if cluster_id == -1:  # Skip noise points
                continue
            
            cluster_points = coords[clustering.labels_ == cluster_id]
            center = cluster_points.mean(axis=0)
            
            folium.Marker(
                location=center.tolist(),
                popup=f"{label_prefix} {cluster_id + 1}<br>Points: {len(cluster_points)}",
                icon=folium.Icon(color=color, icon='info-sign')
            ).add_to(m)
    
    def _get_speed_color(self, speed_kmh: float) -> str:
        """Get color based on speed"""
        if speed_kmh < 20:
            return 'red'
        elif speed_kmh < 40:
            return 'orange'
        elif speed_kmh < 60:
            return 'yellow'
        else:
            return 'green'
    
    def _add_demand_zones(self, m: folium.Map, df: pd.DataFrame):
        """Identify and mark high-demand zones"""
        # Create grid cells
        lat_bins = pd.cut(df['lat'], bins=10)
        lng_bins = pd.cut(df['lng'], bins=10)
        
        # Count points in each cell
        grid_counts = df.groupby([lat_bins, lng_bins]).size().reset_index(name='count')
        
        # Find high-demand cells (top 20%)
        threshold = grid_counts['count'].quantile(0.8)
        high_demand = grid_counts[grid_counts['count'] > threshold]
        
        for _, cell in high_demand.iterrows():
            # Get cell boundaries
            lat_interval = cell[0]
            lng_interval = cell[1]
            
            if pd.notna(lat_interval) and pd.notna(lng_interval):
                # Draw rectangle for high-demand zone
                bounds = [
                    [lat_interval.left, lng_interval.left],
                    [lat_interval.right, lng_interval.right]
                ]
                
                folium.Rectangle(
                    bounds=bounds,
                    color='purple',
                    fill=True,
                    fillColor='purple',
                    fillOpacity=0.2,
                    weight=2,
                    popup=f"High Demand Zone<br>Activity Count: {cell['count']}"
                ).add_to(m)
    
    def _add_map_title(self, m: folium.Map, title: str):
        """Add title to map"""
        title_html = f'''
        <div style="position: fixed; 
                    top: 10px; left: 50%; transform: translateX(-50%);
                    width: auto; height: auto;
                    background-color: white; border: 2px solid grey;
                    border-radius: 5px; padding: 10px;
                    font-size: 16px; font-weight: bold;
                    z-index: 9999;">
            {title}
        </div>
        '''
        m.get_root().html.add_child(folium.Element(title_html))
    
    def _add_speed_legend(self, m: folium.Map):
        """Add speed color legend to map"""
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: auto; height: auto;
                    background-color: white; border: 2px solid grey;
                    border-radius: 5px; padding: 10px;
                    font-size: 14px; z-index: 9999;">
            <p style="margin: 0; font-weight: bold;">Speed Legend</p>
            <p style="margin: 2px;"><span style="color: red;">●</span> &lt; 20 km/h (Congested)</p>
            <p style="margin: 2px;"><span style="color: orange;">●</span> 20-40 km/h (Slow)</p>
            <p style="margin: 2px;"><span style="color: yellow;">●</span> 40-60 km/h (Moderate)</p>
            <p style="margin: 2px;"><span style="color: green;">●</span> &gt; 60 km/h (Free Flow)</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
