# processing/heatmap_generator.py
from __future__ import annotations
import folium
from folium import plugins
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ---------------- Legend spec ----------------
@dataclass
class LegendSpec:
    title: str
    unit: str
    notes: str = ""

# ---------------- Generator ------------------
class HeatmapGenerator:
    """Folium-based map generator with legends and meter-based aggregation."""

    def __init__(self, default_zoom: int = 13):
        self.default_zoom = default_zoom

    # ---------- UI helpers ----------
    def _center(self, df_like) -> List[float]:
        if isinstance(df_like, pd.DataFrame):
            return [float(df_like["lat"].mean()), float(df_like["lng"].mean())]
        return [51.0954, 71.4275]

    def _title(self, m: folium.Map, title: str):
        html = f"""
        <div style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
                    background: white; border: 2px solid #444; border-radius: 10px;
                    padding: 8px 14px; font-size: 16px; font-weight: 700; z-index: 1000;">
            {title}
        </div>"""
        m.get_root().html.add_child(folium.Element(html))

    def _legend(self, m: folium.Map, spec: LegendSpec, gradient: List[Tuple[str, float]]):
        """
        gradient: list of (hex, stop 0..1) sorted by stop asc.
        """
        stops = "".join([f"<li><span style='background:{c}'></span>{int(s*100)}%</li>" for c, s in gradient])
        html = f"""
        <div style="position: fixed; bottom: 20px; right: 20px; z-index: 1000;
                    background: white; padding: 10px 12px; border: 1px solid #aaa; border-radius: 10px;">
          <div style="font-weight:600;margin-bottom:6px">{spec.title}</div>
          <div style="font-size:12px;margin-bottom:6px">Units: {spec.unit}</div>
          <ul style="list-style:none; padding:0; margin:0">
            {stops}
          </ul>
          <div style="font-size:11px;margin-top:6px; max-width:240px; color:#444">{spec.notes}</div>
        </div>
        <style>
        li {{ display:flex; align-items:center; gap:8px; font-size:12px; }}
        li span {{ display:inline-block; width:24px; height:10px; border:1px solid #999; }}
        </style>"""
        m.get_root().html.add_child(folium.Element(html))

    def _add_layerctl(self, m: folium.Map):
        folium.LayerControl(collapsed=False).add_to(m)

    # ---------- Aggregation helpers ----------
    def _meters_per_degree(self, lat_deg: float) -> Tuple[float, float]:
        lat = np.radians(lat_deg)
        m_per_deg_lat = 111_132.92 - 559.82*np.cos(2*lat) + 1.175*np.cos(4*lat)
        m_per_deg_lon = 111_412.84*np.cos(lat) - 93.5*np.cos(3*lat)
        return float(m_per_deg_lon), float(m_per_deg_lat)

    def _grid_accumulate(self, df_centered: pd.DataFrame, xcol: str, ycol: str, wcol: str, cell_m: float = 75.0):
        """
        df_centered must have xcol,ycol in meters around local origin.
        Returns lat,lng,weight per cell using cell center back-projected to lat/lng.
        """
        lat0 = float(df_centered["lat"].mean())
        lng0 = float(df_centered["lng"].mean())
        mx, my = self._meters_per_degree(lat0)
        # integer grid indices
        ix = np.floor(df_centered[xcol].values / cell_m).astype(int)
        iy = np.floor(df_centered[ycol].values / cell_m).astype(int)
        weights = df_centered[wcol].values
        # aggregate
        keys = np.stack([ix, iy], axis=1)
        uniq, inv = np.unique(keys, axis=0, return_inverse=True)
        sums = np.bincount(inv, weights, minlength=len(uniq)).astype(float)
        # centers to lat/lng
        cx = (uniq[:,0].astype(float) + 0.5) * cell_m
        cy = (uniq[:,1].astype(float) + 0.5) * cell_m
        lng = lng0 + cx / mx
        lat = lat0 + cy / my
        return pd.DataFrame({"lat": lat, "lng": lng, "w": sums})

    def _grid_average(self, df_centered: pd.DataFrame, xcol: str, ycol: str, vcol: str, cell_m: float = 80.0):
        """
        Average a value per meter-grid cell. Returns lat,lng,avg columns.
        """
        lat0 = float(df_centered["lat"].mean())
        lng0 = float(df_centered["lng"].mean())
        mx, my = self._meters_per_degree(lat0)

        ix = np.floor(df_centered[xcol].values / cell_m).astype(int)
        iy = np.floor(df_centered[ycol].values / cell_m).astype(int)
        vals = df_centered[vcol].values.astype(float)

        keys = np.stack([ix, iy], axis=1)
        uniq, inv = np.unique(keys, axis=0, return_inverse=True)
        sums = np.bincount(inv, vals, minlength=len(uniq)).astype(float)
        cnts = np.bincount(inv, np.ones_like(vals), minlength=len(uniq)).astype(float)
        avgs = np.divide(sums, np.maximum(cnts, 1e-9))

        cx = (uniq[:,0].astype(float) + 0.5) * cell_m
        cy = (uniq[:,1].astype(float) + 0.5) * cell_m
        lng = lng0 + cx / mx
        lat = lat0 + cy / my

        return pd.DataFrame({"lat": lat, "lng": lng, "avg": avgs, "count": cnts})

    # ---------- Maps ----------
    def generate_route_density_map(self, df: pd.DataFrame, segments: pd.DataFrame, title: str, legend: LegendSpec) -> str:
        """
        Aggregates segment length per cell (km per cell) to reveal corridors.
        """
        if segments is None or len(segments) == 0:
            # fallback to presence density
            tmp = df.copy()
            tmp["lat_round"] = tmp["lat"].round(4); tmp["lng_round"] = tmp["lng"].round(4)
            counts = tmp.groupby(["lat_round","lng_round"]).size().reset_index(name="w")
            counts.rename(columns={"lat_round":"lat","lng_round":"lng"}, inplace=True)
            heat = counts[["lat","lng","w"]].values.tolist()
            m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
            plugins.HeatMap(heat, name="Presence", radius=24, blur=18, min_opacity=0.35).add_to(m)
            self._title(m, title); self._legend(m, legend, [("#00f",0.0),("#0ff",0.5),("#ff0",0.8),("#f00",1.0)]); self._add_layerctl(m)
            return m.get_root().render()

        # Use segment midpoints to deposit length
        seg = segments.copy()
        seg["mx"] = 0.5*(seg["x1"] + seg["x2"])
        seg["my"] = 0.5*(seg["y1"] + seg["y2"])
        seg["lat"] = 0.5*(seg["lat1"] + seg["lat2"])  # midpoint lat
        seg["lng"] = 0.5*(seg["lng1"] + seg["lng2"])  # midpoint lng
        seg["w_km"] = seg["dist_km"].astype(float)
        grid = self._grid_accumulate(seg.rename(columns={"mx":"x_m","my":"y_m"}), "x_m", "y_m", "w_km", cell_m=80.0)

        # Normalize with percentile clipping
        w = grid["w"].values
        vmax = np.percentile(w, 98) if len(w) else 1.0
        norm_w = np.clip(w / max(vmax, 1e-9), 0, 1)
        heat = np.stack([grid["lat"].values, grid["lng"].values, norm_w], axis=1).tolist()

        m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        plugins.HeatMap(heat, name="Route Density", min_opacity=0.35, max_zoom=18, radius=24, blur=18,
                        gradient={0.0:'#2b83ba',0.25:'#abdda4',0.5:'#ffffbf',0.75:'#fdae61',1.0:'#d7191c'}).add_to(m)
        self._title(m, title)
        self._legend(m, legend, [("#2b83ba",0.0),("#abdda4",0.25),("#ffffbf",0.5),("#fdae61",0.75),("#d7191c",1.0)])
        self._add_layerctl(m)
        return m.get_root().render()

    def generate_endpoints_map(self, df: pd.DataFrame, segments: pd.DataFrame, title: str, legend: LegendSpec) -> str:
        """
        Endpoints = nodes with no predecessor (pickups) / no successor (dropoffs).
        Derive from segments.
        """
        if segments is None or len(segments) == 0:
            m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
            self._title(m, title); self._legend(m, legend, [("#0f0",0.0),("#f00",1.0)]); self._add_layerctl(m)
            return m.get_root().render()

        # Reconstruct predecessor/successor sets from segments
        starts = segments[["lat1","lng1"]].copy(); starts.columns = ["lat","lng"]
        ends   = segments[["lat2","lng2"]].copy(); ends.columns = ["lat","lng"]

        # heads = lat1,lng1 that never appear as lat2,lng2; tails vice versa
        starts_key = list(zip(starts["lat"].round(6), starts["lng"].round(6)))
        ends_key = list(zip(ends["lat"].round(6), ends["lng"].round(6)))
        head_mask = ~pd.Series(starts_key).isin(set(ends_key)).values
        tail_mask = ~pd.Series(ends_key).isin(set(starts_key)).values
        pickups = starts[head_mask]; dropoffs = ends[tail_mask]

        m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        if len(pickups):
            plugins.HeatMap(pickups[["lat","lng"]].values.tolist(), name="Pickups", radius=28, blur=24,
                            gradient={0.0:'#b7f7b7',0.5:'#55e655',1.0:'#0a9a00'}).add_to(m)
        if len(dropoffs):
            plugins.HeatMap(dropoffs[["lat","lng"]].values.tolist(), name="Dropoffs", radius=28, blur=24,
                            gradient={0.0:'#ffd0c7',0.5:'#ff866b',1.0:'#d00000'}).add_to(m)
        self._title(m, title)
        self._legend(m, legend, [("#0a9a00",0.33),("#55e655",0.66),("#d00000",1.0)])
        self._add_layerctl(m)
        return m.get_root().render()

    def generate_speed_map(self, df: pd.DataFrame, title: str, legend: LegendSpec) -> str:
        s = df["speed_kmh"].dropna()
        if len(s) == 0:
            m = folium.Map(location=self._center(df), zoom_start=self.default_zoom)
            self._title(m, title); self._legend(m, legend, [("#f00",0.0),("#ff0",0.5),("#0f0",1.0)]); self._add_layerctl(m)
            return m.get_root().render()
        p25, p75 = float(s.quantile(0.25)), float(s.quantile(0.75))
        t_low = min(25.0, p25)  # congestion threshold
        w = np.clip((t_low - df["speed_kmh"].fillna(999)) / max(t_low, 1e-6), 0, 1).values
        data = np.stack([df["lat"].values, df["lng"].values, w], axis=1).tolist()

        m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        plugins.HeatMap(data, name="Low Speed Intensity", radius=22, blur=18, min_opacity=0.35,
                        gradient={0.0:'#00ff00',0.4:'#ffff00',0.7:'#ff8800',1.0:'#ff0000'}).add_to(m)
        self._title(m, title)
        self._legend(m, legend, [("#ff0000",1.0),("#ff8800",0.7),("#ffff00",0.4),("#00ff00",0.0)])
        self._add_layerctl(m)
        return m.get_root().render()

    def generate_avg_speed_map(self, df: pd.DataFrame, title: str, legend: LegendSpec,
                           cell_m: float = 80.0, red_is_fast: bool = True) -> str:
        """
        Average speed (km/h) per meter-grid cell with a clear legend.
        red_is_fast=True -> highways glow red; False -> congestion red.
        """
        if "speed_kmh" not in df or df["speed_kmh"].dropna().empty:
            m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
            self._title(m, title); self._legend(m, legend, [("#ccc",0.0),("#333",1.0)]); self._add_layerctl(m)
            return m.get_root().render()

        # local meters (reuse the same approximation as elsewhere)
        lat0 = float(df["lat"].mean()); lng0 = float(df["lng"].mean())
        mx, my = self._meters_per_degree(lat0)
        x_m = (df["lng"].values - lng0) * mx
        y_m = (df["lat"].values - lat0) * my
        tmp = df.copy()
        tmp["x_m"] = x_m; tmp["y_m"] = y_m
        tmp = tmp[pd.notna(tmp["speed_kmh"])]

        grid = self._grid_average(tmp, "x_m", "y_m", "speed_kmh", cell_m=cell_m)

        # Robust scaling: use percentiles to keep mid-structure visible
        sp = grid["avg"].values
        lo, hi = np.percentile(sp, 5), np.percentile(sp, 95)
        lo = float(lo); hi = float(max(hi, lo + 1e-6))
        norm = np.clip((sp - lo) / (hi - lo), 0, 1)

        # Palette: either red=fast or red=slow
        if red_is_fast:
            # low -> high : blue -> cyan -> yellow -> red
            gradient = {0.0:'#2b83ba', 0.3:'#abdda4', 0.6:'#ffffbf', 0.8:'#fdae61', 1.0:'#d7191c'}
            legend_swatches = [("#2b83ba",0.0),("#abdda4",0.3),("#ffffbf",0.6),("#fdae61",0.8),("#d7191c",1.0)]
        else:
            # low -> high : green -> yellow -> orange -> red (red = slow)
            gradient = {0.0:'#00ff00', 0.4:'#ffff00', 0.7:'#ff8800', 1.0:'#ff0000'}
            legend_swatches = [("#00ff00",0.0),("#ffff00",0.4),("#ff8800",0.7),("#ff0000",1.0)]

        # Heat payload: (lat, lng, weight)
        heat = np.stack([grid["lat"].values, grid["lng"].values, norm], axis=1).tolist()

        m = folium.Map(location=self._center(grid), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        plugins.HeatMap(heat, name="Average Speed", radius=24, blur=18, min_opacity=0.35, gradient=gradient).add_to(m)

        # Legend with numeric bands
        title_text = f"{legend.title} (clipped {lo:.0f}–{hi:.0f} km/h)"
        self._title(m, title or "Average Speed Heat Map")
        self._legend(m, LegendSpec(title=title_text, unit="km/h", notes=legend.notes),
                     legend_swatches)
        self._add_layerctl(m)
        return m.get_root().render()

    def generate_trajectory_demand_map(self, df: pd.DataFrame, segments: pd.DataFrame, title: str, legend: LegendSpec) -> str:
        """
        Demand = presence (all points, equal weight) + endpoint boosting.
        """
        m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        demand = [[r["lat"], r["lng"], 0.5] for _, r in df.iterrows()]

        if segments is not None and len(segments):
            starts = segments[["lat1","lng1"]].values.tolist()
            ends = segments[["lat2","lng2"]].values.tolist()
            demand += [[a, b, 1.0] for (a,b) in starts]
            demand += [[a, b, 1.0] for (a,b) in ends]

        plugins.HeatMap(demand, name="Demand Density", radius=26, blur=18, min_opacity=0.35,
                        gradient={0.0:'#2b83ba',0.25:'#abdda4',0.5:'#ffffbf',0.75:'#fdae61',1.0:'#d7191c'}).add_to(m)
        self._title(m, title)
        self._legend(m, legend, [("#2b83ba",0.0),("#abdda4",0.25),("#ffffbf",0.5),("#fdae61",0.75),("#d7191c",1.0)])
        self._add_layerctl(m)
        return m.get_root().render()

    def generate_ghg_map(self, segments: pd.DataFrame, title: str, legend: LegendSpec) -> str:
        """
        GHG = sum of segment_kg_co2e per meter-grid cell. Uses an acid color palette.
        """
        seg = segments.copy()
        seg["mx"] = 0.5*(seg["x1"] + seg["x2"])
        seg["my"] = 0.5*(seg["y1"] + seg["y2"])
        seg["lat"] = 0.5*(seg["lat1"] + seg["lat2"])  # midpoint lat
        seg["lng"] = 0.5*(seg["lng1"] + seg["lng2"])  # midpoint lng
        grid = self._grid_accumulate(seg.rename(columns={"mx":"x_m","my":"y_m"}), "x_m", "y_m", "segment_kg_co2e", cell_m=80.0)

        w = grid["w"].values
        vmax = np.percentile(w, 98) if len(w) else 1.0
        norm_w = np.clip(w / max(vmax, 1e-9), 0, 1)
        heat = np.stack([grid["lat"].values, grid["lng"].values, norm_w], axis=1).tolist()

        # Acid palette: neon green → yellow → orange → hot pink
        acid = {0.0:'#00FF9C', 0.3:'#C7FF00', 0.6:'#FFD400', 0.8:'#FF6A00', 1.0:'#FF007A'}

        m = folium.Map(location=self._center(grid), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        plugins.HeatMap(heat, name="GHG Emissions", min_opacity=0.35, max_zoom=18, radius=26, blur=18,
                        gradient=acid).add_to(m)
        self._title(m, title)
        self._legend(m, legend, [("#00FF9C",0.0),("#C7FF00",0.3),("#FFD400",0.6),("#FF6A00",0.8),("#FF007A",1.0)])
        self._add_layerctl(m)
        return m.get_root().render()