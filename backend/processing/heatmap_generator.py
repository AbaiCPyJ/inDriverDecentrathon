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

    def _add_flow_overlay(self, m: folium.Map, segments: pd.DataFrame, top_k: int = 250, min_len_km: float = 0.05):
        """
        Add animated directional flow lines (AntPath) for the strongest segments.
        - Aggregates segments by rounded endpoints to denoise.
        - Ranks by total km length so 'popular directions' pop.
        """
        if segments is None or len(segments) == 0:
            return

        seg = segments.copy()
        # keep only meaningful moves
        seg = seg[seg["dist_km"].astype(float) >= float(min_len_km)].copy()
        if seg.empty:
            return

        # bucket endpoints to ~11 m cells (round 4 decimals)
        seg["a_lat"] = seg["lat1"].round(4); seg["a_lng"] = seg["lng1"].round(4)
        seg["b_lat"] = seg["lat2"].round(4); seg["b_lng"] = seg["lng2"].round(4)

        agg = (
            seg.groupby(["a_lat","a_lng","b_lat","b_lng"], as_index=False)["dist_km"]
            .sum()
            .rename(columns={"dist_km":"km"})
            .sort_values("km", ascending=False)
        )

        if agg.empty:
            return

        agg = agg.head(min(top_k, len(agg)))

        # thickness & opacity by rank
        km_vals = agg["km"].to_numpy()
        kmin, kmax = float(km_vals.min()), float(km_vals.max())
        scale = (km_vals - kmin) / max(kmax - kmin, 1e-9)  # 0..1

        for (_, row), s in zip(agg.iterrows(), scale):
            latlngs = [(float(row["a_lat"]), float(row["a_lng"])),
                    (float(row["b_lat"]), float(row["b_lng"]))]
            weight = 2 + 6 * float(s)            # 2..8 px
            opacity = 0.4 + 0.45 * float(s)      # 0.4..0.85
            plugins.AntPath(
                locations=latlngs,
                dash_array=[10, 20],
                delay=1000,                      # wave speed
                weight=weight,
                opacity=opacity,
                color="#1976d2",
                pulseColor="#FF6A00"
            ).add_to(m)

    # ---------- Maps ----------
    def generate_route_density_map(self, df: pd.DataFrame, segments: pd.DataFrame, title: str, legend: LegendSpec) -> str:
        """
        Aggregates segment length per cell (km per cell) to reveal corridors.
        Uses a single global meter frame and a numeric legend showing km per cell.
        """
        # Fallback to presence density if segments are missing
        if segments is None or len(segments) == 0:
            tmp = df.copy()
            tmp["lat_round"] = tmp["lat"].round(4)
            tmp["lng_round"] = tmp["lng"].round(4)
            counts = tmp.groupby(["lat_round", "lng_round"]).size().reset_index(name="w")
            counts.rename(columns={"lat_round": "lat", "lng_round": "lng"}, inplace=True)
            heat = counts[["lat", "lng", "w"]].values.tolist()

            m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
            plugins.HeatMap(heat, name="Presence", radius=24, blur=18, min_opacity=0.35).add_to(m)
            self._title(m, title)
            self._legend(
                m,
                LegendSpec(
                    title=legend.title,
                    unit=legend.unit,
                    notes=(legend.notes + " Presence fallback (count per ~11 m bin).").strip()
                ),
                [("#2b83ba", 0.0), ("#abdda4", 0.25), ("#ffffbf", 0.5), ("#fdae61", 0.75), ("#d7191c", 1.0)]
            )
            self._add_layerctl(m)
            return m.get_root().render()

        seg = segments.copy()
        seg["lat"] = 0.5 * (seg["lat1"] + seg["lat2"])
        seg["lng"] = 0.5 * (seg["lng1"] + seg["lng2"])
        lat0 = float(seg["lat"].mean()); lng0 = float(seg["lng"].mean())
        mx, my = self._meters_per_degree(lat0)
        seg["x_m"] = (seg["lng"] - lng0) * mx
        seg["y_m"] = (seg["lat"] - lat0) * my
        seg["w_km"] = seg["dist_km"].astype(float)

        grid = self._grid_accumulate(seg, "x_m", "y_m", "w_km", cell_m=80.0)

        w = grid["w"].values
        vmin = float(np.percentile(w, 2)) if len(w) else 0.0
        vmax = float(np.percentile(w, 98)) if len(w) else 1.0
        if vmax <= vmin:
            vmin, vmax = 0.0, max(vmax, 1.0)
        norm_w = np.clip((w - vmin) / max(vmax - vmin, 1e-9), 0, 1)
        heat = np.stack([grid["lat"].values, grid["lng"].values, norm_w], axis=1).tolist()

        gradient = {0.0:'#2b83ba', 0.25:'#abdda4', 0.5:'#ffffbf', 0.75:'#fdae61', 1.0:'#d7191c'}

        m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        plugins.HeatMap(heat, name="Route Density", min_opacity=0.35, max_zoom=18, radius=24, blur=18,
                        gradient=gradient).add_to(m)
        self._title(m, title)

        # Numeric legend (km per cell) aligned to gradient stops
        tick_vals = [vmin,
                    vmin + 0.25 * (vmax - vmin),
                    vmin + 0.50 * (vmax - vmin),
                    vmin + 0.75 * (vmax - vmin),
                    vmax]
        swatches = [("#2b83ba", 0.0), ("#abdda4", 0.25), ("#ffffbf", 0.50), ("#fdae61", 0.75), ("#d7191c", 1.0)]
        items_html = "".join(
            f"<li><span style='background:{c}'></span>{val:.2f} {legend.unit}</li>"
            for (c, _), val in zip(swatches, tick_vals)
        )
        html = f"""
        <div style="position: fixed; bottom: 20px; right: 20px; z-index: 1000;
                    background: white; padding: 10px 12px; border: 1px solid #aaa; border-radius: 10px;">
        <div style="font-weight:600;margin-bottom:6px">{legend.title}</div>
        <div style="font-size:12px;margin-bottom:6px">Units: {legend.unit}</div>
        <ul style="list-style:none; padding:0; margin:0">{items_html}</ul>
        <div style="font-size:11px;margin-top:6px; max-width:240px; color:#444">
            {legend.notes} Color scale spans {vmin:.2f}–{vmax:.2f} {legend.unit} (2nd–98th percentile).
        </div>
        </div>
        <style>
        li {{ display:flex; align-items:center; gap:8px; font-size:12px; }}
        li span {{ display:inline-block; width:24px; height:10px; border:1px solid #999; }}
        </style>"""
        m.get_root().html.add_child(folium.Element(html))

        self._add_layerctl(m)
        return m.get_root().render()

    def generate_endpoints_map(self, df: pd.DataFrame, segments: pd.DataFrame, title: str, legend: LegendSpec) -> str:
        """
        Endpoints = nodes with no predecessor (pickups) / no successor (dropoffs).
        Uses per-layer grid counts (global meter frame) with robust normalization and a
        dual-scale legend so the colors correspond to actual counts per cell.
        """
        m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")

        if segments is None or len(segments) == 0:
            self._title(m, title)
            self._legend(m, legend, [("#0a9a00",0.33),("#55e655",0.66),("#d00000",1.0)])
            self._add_layerctl(m)
            return m.get_root().render()

        # Heads/tails
        starts = segments[["lat1","lng1"]].copy(); starts.columns = ["lat","lng"]
        ends   = segments[["lat2","lng2"]].copy(); ends.columns = ["lat","lng"]

        # Global frame
        lat0 = float(pd.concat([starts["lat"], ends["lat"]]).mean())
        lng0 = float(pd.concat([starts["lng"], ends["lng"]]).mean())
        mx, my = self._meters_per_degree(lat0)

        for df_ep, name, colors in [
            (starts.copy(), "Pickups", {0.0:'#b7f7b7', 0.5:'#55e655', 1.0:'#0a9a00'}),
            (ends.copy(),   "Dropoffs", {0.0:'#ffd0c7', 0.5:'#ff866b', 1.0:'#d00000'})
        ]:
            df_ep["x_m"] = (df_ep["lng"] - lng0) * mx
            df_ep["y_m"] = (df_ep["lat"] - lat0) * my
            df_ep["w"] = 1.0  # unit weight per endpoint
            grid = self._grid_accumulate(df_ep, "x_m", "y_m", "w", cell_m=80.0)
            w = grid["w"].values
            vmin = float(np.percentile(w, 2)) if len(w) else 0.0
            vmax = float(np.percentile(w, 98)) if len(w) else 1.0
            if vmax <= vmin: vmin, vmax = 0.0, max(vmax, 1.0)
            norm = np.clip((w - vmin) / max(vmax - vmin, 1e-9), 0, 1)
            heat = np.stack([grid["lat"].values, grid["lng"].values, norm], axis=1).tolist()
            plugins.HeatMap(heat, name=name, radius=28, blur=24, gradient=colors, min_opacity=0.35).add_to(m)
            if name == "Pickups":
                pickups_span = (vmin, vmax)
            else:
                dropoffs_span = (vmin, vmax)

        self._title(m, title)
        html = f"""
        <div style="position: fixed; bottom: 20px; right: 20px; z-index: 1000;
                    background: white; padding: 10px 12px; border: 1px solid #aaa; border-radius: 10px;">
        <div style="font-weight:600;margin-bottom:6px">{legend.title}</div>
        <div style="font-size:12px;margin-bottom:6px">Units: counts per cell</div>
        <div style="font-size:12px;margin-bottom:4px"><b>Pickups</b>: {pickups_span[0]:.0f}–{pickups_span[1]:.0f}</div>
        <div style="font-size:12px;margin-bottom:6px"><b>Dropoffs</b>: {dropoffs_span[0]:.0f}–{dropoffs_span[1]:.0f}</div>
        <div style="font-size:11px; max-width:260px; color:#444">{legend.notes}</div>
        </div>"""
        m.get_root().html.add_child(folium.Element(html))
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
        Average speed (km/h) per meter-grid cell with numeric legend.
        Uses robust percentile clipping so colors represent comparable ranges across datasets.
        """
        if "speed_kmh" not in df or df["speed_kmh"].dropna().empty:
            m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")
            self._title(m, title)
            self._legend(m, legend, [("#ccc",0.0),("#333",1.0)])
            self._add_layerctl(m)
            return m.get_root().render()

        lat0 = float(df["lat"].mean()); lng0 = float(df["lng"].mean())
        mx, my = self._meters_per_degree(lat0)
        tmp = df.copy()
        tmp["x_m"] = (tmp["lng"] - lng0) * mx
        tmp["y_m"] = (tmp["lat"] - lat0) * my
        tmp = tmp[pd.notna(tmp["speed_kmh"])]

        grid = self._grid_average(tmp, "x_m", "y_m", "speed_kmh", cell_m=cell_m)

        sp = grid["avg"].values
        vmin = float(np.percentile(sp, 5))
        vmax = float(np.percentile(sp, 95))
        if vmax <= vmin: vmin, vmax = 0.0, max(vmax, 1.0)
        norm = np.clip((sp - vmin) / max(vmax - vmin, 1e-9), 0, 1)

        if red_is_fast:
            gradient = {0.0:'#2b83ba', 0.3:'#abdda4', 0.6:'#ffffbf', 0.8:'#fdae61', 1.0:'#d7191c'}
            swatches = [("#2b83ba",0.0),("#abdda4",0.3),("#ffffbf",0.6),("#fdae61",0.8),("#d7191c",1.0)]
        else:
            gradient = {0.0:'#00ff00', 0.4:'#ffff00', 0.7:'#ff8800', 1.0:'#ff0000'}
            swatches = [("#00ff00",0.0),("#ffff00",0.4),("#ff8800",0.7),("#ff0000",1.0)]

        heat = np.stack([grid["lat"].values, grid["lng"].values, norm], axis=1).tolist()
        m = folium.Map(location=self._center(grid), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        plugins.HeatMap(heat, name="Average Speed", radius=24, blur=18, min_opacity=0.35, gradient=gradient).add_to(m)

        # Numeric legend ticks
        tick_vals = [vmin,
                    vmin + 0.30*(vmax - vmin),
                    vmin + 0.60*(vmax - vmin),
                    vmin + 0.80*(vmax - vmin),
                    vmax]
        items_html = "".join(
            f"<li><span style='background:{c}'></span>{val:.0f} km/h</li>"
            for (c, _), val in zip(swatches, tick_vals)
        )
        html = f"""
        <div style="position: fixed; bottom: 20px; right: 20px; z-index: 1000;
                    background: white; padding: 10px 12px; border: 1px solid #aaa; border-radius: 10px;">
        <div style="font-weight:600;margin-bottom:6px">{title or "Average Speed"}</div>
        <div style="font-size:12px;margin-bottom:6px">Units: km/h</div>
        <ul style="list-style:none; padding:0; margin:0">{items_html}</ul>
        <div style="font-size:11px;margin-top:6px; max-width:240px; color:#444">
            Colors span {vmin:.0f}–{vmax:.0f} km/h (5th–95th percentile).
        </div>
        </div>
        <style>
        li {{ display:flex; align-items:center; gap:8px; font-size:12px; }}
        li span {{ display:inline-block; width:24px; height:10px; border:1px solid #999; }}
        </style>"""
        m.get_root().html.add_child(folium.Element(html))

        self._add_layerctl(m)
        return m.get_root().render()

    def generate_trajectory_demand_map(self, df: pd.DataFrame, segments: pd.DataFrame, title: str, legend: LegendSpec) -> str:
        """
        Blended demand density:
        - presence (points, unit weights),
        - endpoints (heads/tails, unit weights),
        - corridor support (segment km),
        plus a directional flow overlay so users see the likely driving directions.
        """
        m = folium.Map(location=self._center(df), zoom_start=self.default_zoom, tiles="OpenStreetMap")

        if df.empty:
            self._title(m, title)
            self._legend(m, legend, [("#2b83ba",0.0),("#abdda4",0.25),("#ffffbf",0.5),("#fdae61",0.75),("#d7191c",1.0)])
            self._add_layerctl(m)
            return m.get_root().render()

        # Global frame
        lat0 = float(df["lat"].mean()); lng0 = float(df["lng"].mean())
        mx, my = self._meters_per_degree(lat0)

        # Presence
        pres = df.copy()
        pres["x_m"] = (pres["lng"] - lng0) * mx
        pres["y_m"] = (pres["lat"] - lat0) * my
        pres["w"] = 1.0
        g_pres = self._grid_accumulate(pres, "x_m", "y_m", "w", cell_m=80.0).rename(columns={"w": "pres_w"})
        demand = g_pres[["lat","lng","pres_w"]].copy()

        # Endpoints
        if segments is not None and len(segments):
            starts = segments[["lat1","lng1"]].copy(); starts.columns = ["lat","lng"]
            ends   = segments[["lat2","lng2"]].copy(); ends.columns = ["lat","lng"]
            ep = pd.concat([starts, ends], ignore_index=True)
            ep["x_m"] = (ep["lng"] - lng0) * mx
            ep["y_m"] = (ep["lat"] - lat0) * my
            ep["w"] = 1.0
            g_ep = self._grid_accumulate(ep, "x_m", "y_m", "w", cell_m=80.0).rename(columns={"w":"ep_w"})
            demand = demand.merge(g_ep, on=["lat","lng"], how="outer")
        else:
            demand["ep_w"] = 0.0

        # Corridor (km)
        if segments is not None and len(segments):
            seg = segments.copy()
            seg["lat"] = 0.5 * (seg["lat1"] + seg["lat2"])
            seg["lng"] = 0.5 * (seg["lng1"] + seg["lng2"])
            seg["x_m"] = (seg["lng"] - lng0) * mx
            seg["y_m"] = (seg["lat"] - lat0) * my
            seg["w_km"] = seg["dist_km"].astype(float)
            g_km = self._grid_accumulate(seg, "x_m", "y_m", "w_km", cell_m=80.0).rename(columns={"w":"km_w"})
            demand = demand.merge(g_km, on=["lat","lng"], how="outer")
        else:
            demand["km_w"] = 0.0

        # Fill NA
        for col in ("pres_w","ep_w","km_w"):
            demand[col] = demand.get(col, 0.0).fillna(0.0).astype(float)

        # Robust normalization
        def _norm(v):
            if v.size == 0: return v, 0, 1
            lo = float(np.percentile(v, 2)); hi = float(np.percentile(v, 98))
            if hi <= lo: lo, hi = 0.0, max(hi, 1.0)
            return np.clip((v - lo) / max(hi - lo, 1e-9), 0, 1), lo, hi

        pres_n, pres_lo, pres_hi = _norm(demand["pres_w"].values)
        ep_n,   ep_lo,   ep_hi   = _norm(demand["ep_w"].values)
        km_n,   km_lo,   km_hi   = _norm(demand["km_w"].values)

        blend = 0.6*pres_n + 0.8*ep_n + 0.6*km_n
        if blend.max() > 0: blend = blend / blend.max()

        heat = np.stack([demand["lat"].values, demand["lng"].values, blend], axis=1).tolist()
        gradient = {0.0:'#2b83ba', 0.25:'#abdda4', 0.5:'#ffffbf', 0.75:'#fdae61', 1.0:'#d7191c'}
        plugins.HeatMap(heat, name="Demand Density", radius=26, blur=18, min_opacity=0.35, gradient=gradient).add_to(m)

        # FLOW OVERLAY: help users see directions on top of demand
        self._add_flow_overlay(m, segments, top_k=200, min_len_km=0.05)

        self._title(m, title)
        self._legend(
            m,
            LegendSpec(
                title=legend.title,
                unit="relative demand (0–1)",
                notes=(legend.notes +
                    f" Presence {pres_lo:.0f}–{pres_hi:.0f} pts/cell; "
                    f"Endpoints {ep_lo:.0f}–{ep_hi:.0f} pts/cell; "
                    f"Corridor {km_lo:.2f}–{km_hi:.2f} km/cell.")
            ),
            [("#2b83ba",0.0),("#abdda4",0.25),("#ffffbf",0.5),("#fdae61",0.75),("#d7191c",1.0)]
        )
        self._add_layerctl(m)
        return m.get_root().render()

    def generate_ghg_map(self, segments: pd.DataFrame, title: str, legend: LegendSpec) -> str:
        """
        GHG = sum of segment_kg_co2e per meter-grid cell. Uses an acid color palette.
        Now aggregates in a single global meter frame and provides a numeric legend with kg CO₂e per cell.
        """
        seg = segments.copy()
        # Use geographic midpoints and project into ONE global meter frame.
        seg["lat"] = 0.5 * (seg["lat1"] + seg["lat2"])
        seg["lng"] = 0.5 * (seg["lng1"] + seg["lng2"])
        lat0 = float(seg["lat"].mean())
        lng0 = float(seg["lng"].mean())
        mx, my = self._meters_per_degree(lat0)
        seg["x_m"] = (seg["lng"] - lng0) * mx
        seg["y_m"] = (seg["lat"] - lat0) * my
        grid = self._grid_accumulate(seg, "x_m", "y_m", "segment_kg_co2e", cell_m=80.0)

        w = grid["w"].values
        vmin = float(np.percentile(w, 2)) if len(w) else 0.0
        vmax = float(np.percentile(w, 98)) if len(w) else 1.0
        if vmax <= vmin:  # degenerate case
            vmin, vmax = 0.0, max(vmax, 1.0)
        norm_w = np.clip((w - vmin) / max(vmax - vmin, 1e-9), 0, 1)
        heat = np.stack([grid["lat"].values, grid["lng"].values, norm_w], axis=1).tolist()

        # Acid palette: neon green → yellow → orange → hot pink
        acid = {
            0.0: '#00FF9C',
            0.3: '#C7FF00',
            0.6: '#FFD400',
            0.8: '#FF6A00',
            1.0: '#FF007A'
        }

        m = folium.Map(location=self._center(grid), zoom_start=self.default_zoom, tiles="OpenStreetMap")
        plugins.HeatMap(
            heat,
            name="GHG Emissions",
            min_opacity=0.35,
            max_zoom=18,
            radius=26,
            blur=18,
            gradient=acid
        ).add_to(m)
        self._title(m, title)

        # Build a numeric legend so colors mean specific kg CO₂e per cell.
        tick_vals = [
            vmin,
            vmin + 0.30 * (vmax - vmin),
            vmin + 0.60 * (vmax - vmin),
            vmin + 0.80 * (vmax - vmin),
            vmax
        ]
        swatches = [
            ("#00FF9C", 0.0),
            ("#C7FF00", 0.30),
            ("#FFD400", 0.60),
            ("#FF6A00", 0.80),
            ("#FF007A", 1.0),
        ]
        items_html = "".join(
            f"<li><span style='background:{c}'></span>{val:.2f} {legend.unit}</li>"
            for (c, _), val in zip(swatches, tick_vals)
        )
        html = f"""
        <div style="position: fixed; bottom: 20px; right: 20px; z-index: 1000;
                    background: white; padding: 10px 12px; border: 1px solid #aaa; border-radius: 10px;">
        <div style="font-weight:600;margin-bottom:6px">{legend.title}</div>
        <div style="font-size:12px;margin-bottom:6px">Units: {legend.unit}</div>
        <ul style="list-style:none; padding:0; margin:0">{items_html}</ul>
        <div style="font-size:11px;margin-top:6px; max-width:240px; color:#444">
            {legend.notes} Color scale spans {vmin:.2f}–{vmax:.2f} {legend.unit} (2nd–98th percentile).
        </div>
        </div>
        <style>
        li {{ display:flex; align-items:center; gap:8px; font-size:12px; }}
        li span {{ display:inline-block; width:24px; height:10px; border:1px solid #999; }}
        </style>"""
        m.get_root().html.add_child(folium.Element(html))

        self._add_layerctl(m)
        return m.get_root().render()