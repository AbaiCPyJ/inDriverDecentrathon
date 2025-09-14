# heatmap_generator.py
import folium
from folium import plugins
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from typing import List

class HeatmapGenerator:
    """Generate various types of heatmaps for geodata visualization"""

    def __init__(self):
        self.default_center = [51.0954, 71.4275]
        self.default_zoom = 12

    def _center(self, df: pd.DataFrame) -> List[float]:
        return [float(df["lat"].mean()), float(df["lng"].mean())]

    def _add_title(self, m: folium.Map, title: str):
        title_html = f"""
        <div style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
                    background-color: white; border: 2px solid #777; border-radius: 8px;
                    padding: 8px 12px; font-size: 16px; font-weight: 600; z-index: 9999;">
            {title}
        </div>"""
        m.get_root().html.add_child(folium.Element(title_html))

    # --------- maps ---------
    def generate_popular_routes_heatmap(self, df: pd.DataFrame) -> str:
        m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        tmp = df.copy()
        tmp["lat_round"] = tmp["lat"].round(4)
        tmp["lng_round"] = tmp["lng"].round(4)
        counts = tmp.groupby(["lat_round", "lng_round"]).size().reset_index(name="count")
        maxc = max(1, int(counts["count"].max()))
        heat = [[r["lat_round"], r["lng_round"], min(r["count"]/maxc, 1.0)] for _, r in counts.iterrows()]
        plugins.HeatMap(heat, name="Popular Routes", min_opacity=0.3, max_zoom=18, radius=25, blur=20,
                        gradient={0.0:'blue',0.25:'cyan',0.5:'lime',0.75:'yellow',1.0:'red'}).add_to(m)

        # light polyline sample
        unique = tmp["randomized_id"].unique()
        sample = np.random.choice(unique, size=min(50, len(unique)), replace=False) if len(unique) else []
        for vid in sample:
            g = tmp[tmp["randomized_id"] == vid].sort_index()
            if len(g) > 1:
                folium.PolyLine(g[["lat","lng"]].values.tolist(), color='blue', weight=1, opacity=0.3).add_to(m)

        folium.LayerControl().add_to(m)
        self._add_title(m, "Popular Routes Heat Map")
        return m.get_root().render()

    def generate_endpoints_heatmap(self, df: pd.DataFrame) -> str:
        m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        pickups, dropoffs = [], []
        for vid in df["randomized_id"].unique():
            g = df[df["randomized_id"] == vid].sort_index()
            if len(g) > 1:
                pickups.append([g.iloc[0]["lat"], g.iloc[0]["lng"]])
                dropoffs.append([g.iloc[-1]["lat"], g.iloc[-1]["lng"]])
        if pickups:
            plugins.HeatMap(pickups, name="Pickups", min_opacity=0.4, max_zoom=18, radius=30, blur=25,
                            gradient={0.0:'blue',0.5:'cyan',0.75:'lightgreen',1.0:'green'}).add_to(m)
        if dropoffs:
            plugins.HeatMap(dropoffs, name="Dropoffs", min_opacity=0.4, max_zoom=18, radius=30, blur=25,
                            gradient={0.0:'yellow',0.5:'orange',0.75:'darkorange',1.0:'red'}).add_to(m)

        # simple DBSCAN markers
        def add_clusters(points, label, color):
            if len(points) < 5: return
            coords = np.array(points)
            clustering = DBSCAN(eps=0.002, min_samples=5).fit(coords)
            for cid in set(clustering.labels_):
                if cid == -1: continue
                center = coords[clustering.labels_ == cid].mean(axis=0).tolist()
                folium.Marker(center, popup=f"{label} {cid+1}", icon=folium.Icon(color=color, icon="info-sign")).add_to(m)

        add_clusters(pickups, "Pickup Cluster", "green")
        add_clusters(dropoffs, "Dropoff Cluster", "red")

        folium.LayerControl().add_to(m)
        self._add_title(m, "Trip Endpoints Heat Map (Green: Pickups, Red: Dropoffs)")
        return m.get_root().render()

    def generate_speed_heatmap(self, df: pd.DataFrame) -> str:
        m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        data = []
        if "speed_kmh" in df:
            for _, r in df.iterrows():
                norm = min(float(r["speed_kmh"]) / 100.0, 1.0) if pd.notna(r["speed_kmh"]) else 0.0
                w = 1.0 - norm
                if w > 0.3: data.append([r["lat"], r["lng"], w])
        if data:
            plugins.HeatMap(data, name="Traffic Congestion", min_opacity=0.4, max_zoom=18, radius=20, blur=15,
                            gradient={0.0:'green',0.3:'yellow',0.6:'orange',0.8:'red',1.0:'darkred'}).add_to(m)

        # sample markers
        sampled = df.sample(n=min(500, len(df))) if len(df) > 0 else df
        for _, r in sampled.iterrows():
            sp = float(r.get("speed_kmh", 0.0)) if pd.notna(r.get("speed_kmh", np.nan)) else 0.0
            color = 'red' if sp < 20 else 'orange' if sp < 40 else 'yellow' if sp < 60 else 'green'
            folium.CircleMarker(location=[r["lat"], r["lng"]], radius=3, popup=f"Speed: {sp:.1f} km/h",
                                color=color, fill=True, fill_color=color, fill_opacity=0.6).add_to(m)
        folium.LayerControl().add_to(m)
        self._add_title(m, "Speed Heat Map (Red: Congestion, Green: Free Flow)")
        return m.get_root().render()

    def generate_demand_density_heatmap(self, df: pd.DataFrame) -> str:
        m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        demand = [[r["lat"], r["lng"], 0.5] for _, r in df.iterrows()]
        # heavier weight for endpoints
        for vid in df["randomized_id"].unique():
            g = df[df["randomized_id"] == vid].sort_index()
            if len(g) > 1:
                demand.append([g.iloc[0]["lat"], g.iloc[0]["lng"], 1.0])
                demand.append([g.iloc[-1]["lat"], g.iloc[-1]["lng"], 1.0])
        plugins.HeatMap(demand, name="Demand Density", min_opacity=0.3, max_zoom=18, radius=25, blur=20,
                        gradient={0.0:'blue',0.25:'cyan',0.5:'yellow',0.75:'orange',1.0:'red'}).add_to(m)
        folium.LayerControl().add_to(m)
        self._add_title(m, "Demand Density Heat Map (Combined Activity)")
        return m.get_root().render()

    # --------- NEW: GHG emissions heatmap ---------
    def generate_ghg_emissions_heatmap(self, df: pd.DataFrame) -> str:
        """
        Weighted by per-segment emissions (kg CO2e).
        Requires columns: lat, lng, segment_kg_co2e (from DataProcessor.add_segment_distance_and_emissions).
        """
        m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        tmp = df.copy()
        tmp["lat_round"] = tmp["lat"].round(4)
        tmp["lng_round"] = tmp["lng"].round(4)
        if "segment_kg_co2e" not in tmp:
            tmp["segment_kg_co2e"] = 0.0
        weights = (tmp.groupby(["lat_round","lng_round"])["segment_kg_co2e"].sum().reset_index(name="emissions"))
        maxw = max(1e-9, float(weights["emissions"].max())) if len(weights) else 1.0
        heat = [[r["lat_round"], r["lng_round"], min(float(r["emissions"]) / maxw, 1.0)] for _, r in weights.iterrows()]
        plugins.HeatMap(heat, name="GHG Emissions", min_opacity=0.35, max_zoom=18, radius=25, blur=20,
                        gradient={0.0:'blue',0.25:'cyan',0.5:'yellow',0.75:'orange',1.0:'red'}).add_to(m)
        folium.LayerControl().add_to(m)
        self._add_title(m, "GHG Emissions Heat Map (kg CO₂e, distance-based)")
        return m.get_root().render()