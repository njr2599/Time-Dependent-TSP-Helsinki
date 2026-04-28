from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point, box


def check_required_files(paths: list[Path]) -> None:
    """Stop early with a clear message if an input data file is missing."""
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required data files:\n"
            + "\n".join(f"- {path}" for path in missing)
            + "\n\nPlace the files in the data/ folder or edit config.py."
        )


def create_output_dirs(*dirs: Path) -> None:
    """Create output folders if they do not exist."""
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)


def load_centroid_population(csv_path: Path, interest_hours: list[str]) -> pd.DataFrame:
    """Load YKR centroids and calculate the max population share in the selected hours."""
    df = pd.read_csv(csv_path)
    df["YKR_ID"] = df["YKR_ID"].astype(str)
    df["max_share_interest_window"] = df[interest_hours].max(axis=1)

    df["pop_class"] = "low"
    df.loc[df["max_share_interest_window"] >= 0.1, "pop_class"] = "medium"
    df.loc[df["max_share_interest_window"] >= 0.3, "pop_class"] = "high"
    return df


def create_subset_from_seed(centroid_population: pd.DataFrame, radius_m: float) -> gpd.GeoDataFrame:
    """Create the 3 km subset around the highest-activity YKR cell."""
    seed_row = centroid_population.loc[centroid_population["max_share_interest_window"].idxmax()]
    seed_point = Point(seed_row["lon"], seed_row["lat"])

    subset = gpd.GeoDataFrame(
        centroid_population.copy(),
        geometry=[Point(xy) for xy in zip(centroid_population["lon"], centroid_population["lat"])],
        crs="EPSG:3067",
    )
    subset["dist_to_seed_m"] = subset.geometry.distance(seed_point)
    subset = subset[subset["dist_to_seed_m"] <= radius_m].copy()
    return add_wgs_coordinates(subset)


def add_wgs_coordinates(gdf_3067: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add lon/lat columns in EPSG:4326 because OSMnx expects geographic coordinates."""
    gdf_3067 = gdf_3067.copy()
    transformer = Transformer.from_crs(3067, 4326, always_xy=True)
    lon_deg, lat_deg = transformer.transform(gdf_3067["lon"].values, gdf_3067["lat"].values)
    gdf_3067["lon_deg"] = lon_deg
    gdf_3067["lat_deg"] = lat_deg
    return gdf_3067


def load_population_zones(population_path: Path, zones_path: Path, subset_ids) -> gpd.GeoDataFrame:
    """Merge dynamic population shares with YKR grid polygons, keeping only the subset."""
    population = pd.read_csv(population_path)
    population["YKR_ID"] = population["YKR_ID"].astype(str)

    zones = gpd.read_file(zones_path)
    zones["YKR_ID"] = zones["YKR_ID"].astype(str)

    population_zones = zones.merge(population, on="YKR_ID")
    population_zones = population_zones.set_crs(epsg=3067, allow_override=True)

    subset_ids = set(str(value) for value in subset_ids)
    return population_zones[population_zones["YKR_ID"].isin(subset_ids)].copy()


def classify_subset_with_osm(
    metro_subset: gpd.GeoDataFrame,
    population_zones_sub: gpd.GeoDataFrame,
    place_name: str,
) -> gpd.GeoDataFrame:
    """Classify cells as residential, commercial, mixed, or unknown using OSM features."""
    subset_wgs = population_zones_sub.to_crs(epsg=4326)
    minx, miny, maxx, maxy = subset_wgs.total_bounds
    bbox_geom = box(minx - 0.002, miny - 0.002, maxx + 0.002, maxy + 0.002)

    tags = {"landuse": True, "building": True, "amenity": True, "shop": True, "office": True}
    try:
        pois_all = ox.features.features_from_place(place_name, tags)
    except AttributeError:
        pois_all = ox.geometries_from_place(place_name, tags)

    pois = pois_all[pois_all.intersects(bbox_geom)].copy()
    if pois.empty:
        raise ValueError("No OSM features found inside the subset bounding box.")

    pois_3067 = pois.to_crs(epsg=3067)
    subset_3067 = population_zones_sub.to_crs(epsg=3067)
    pois_joined = gpd.sjoin(
        pois_3067,
        subset_3067[["YKR_ID", "geometry"]],
        how="inner",
        predicate="intersects",
    )

    pois_joined["flag_comm"] = pois_joined.apply(_is_commercial, axis=1)
    pois_joined["flag_res"] = pois_joined.apply(_is_residential, axis=1)

    counts = pois_joined.groupby("YKR_ID")[["flag_comm", "flag_res"]].sum().reset_index()
    counts["YKR_ID"] = counts["YKR_ID"].astype(str)
    counts["area_class"] = "unknown"
    counts.loc[counts["flag_res"] > counts["flag_comm"], "area_class"] = "residential"
    counts.loc[counts["flag_comm"] > counts["flag_res"], "area_class"] = "commercial"
    counts.loc[(counts["flag_comm"] > 0) & (counts["flag_res"] > 0), "area_class"] = "mixed"

    classified = metro_subset.merge(counts[["YKR_ID", "area_class"]], on="YKR_ID", how="left")
    classified["area_class"] = classified["area_class"].fillna("unknown")
    return classified


def _is_commercial(row: pd.Series) -> bool:
    amenities = {"restaurant", "cafe", "bar", "fast_food", "bank", "clinic", "hospital", "supermarket", "pharmacy"}
    return (
        pd.notna(row.get("shop"))
        or pd.notna(row.get("office"))
        or row.get("landuse") in {"commercial", "retail"}
        or row.get("amenity") in amenities
    )


def _is_residential(row: pd.Series) -> bool:
    residential_buildings = {"apartments", "residential", "house", "detached", "terrace"}
    return row.get("landuse") == "residential" or row.get("building") in residential_buildings


def add_fallback_area_class(metro_subset: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Fallback when OSM classification is not available."""
    metro_subset = metro_subset.copy()
    metro_subset["area_class"] = "mixed"
    return metro_subset


def download_and_trim_graph(
    metro_subset: gpd.GeoDataFrame,
    population_zones_sub: gpd.GeoDataFrame,
    hours: list[int],
    radius_osm_m: float,
) -> tuple[nx.MultiDiGraph, nx.MultiDiGraph]:
    """Download OSM drive graph and trim it to the selected YKR subset."""
    center_lat = metro_subset["lat_deg"].mean()
    center_lon = metro_subset["lon_deg"].mean()

    graph_wgs = ox.graph_from_point((center_lat, center_lon), dist=radius_osm_m, network_type="drive")
    graph_3067 = ox.project_graph(graph_wgs, to_crs=3067)

    zones_work = population_zones_sub[["YKR_ID", "geometry"] + [f"H{h}" for h in hours]].copy()
    zones_work = zones_work.set_crs(epsg=3067, allow_override=True)

    try:
        subset_union = zones_work.geometry.union_all()
    except AttributeError:
        subset_union = zones_work.unary_union
    subset_union_buffer = subset_union.buffer(50)

    edges_to_remove = []
    for u, v, key, data in list(graph_3067.edges(keys=True, data=True)):
        midpoint = _edge_midpoint(graph_3067, u, v, data)
        if not subset_union_buffer.covers(midpoint):
            edges_to_remove.append((u, v, key))

    graph_3067.remove_edges_from(edges_to_remove)
    graph_3067.remove_nodes_from(list(nx.isolates(graph_3067)))

    graph_wgs_trim = graph_wgs.subgraph(graph_3067.nodes).copy()
    return graph_3067, graph_wgs_trim


def add_edge_attributes(
    graph_3067: nx.MultiDiGraph,
    population_zones_sub: gpd.GeoDataFrame,
    hours: list[int],
    speeds_kmh: dict[int, float],
    emission_kg_per_km: float,
) -> nx.MultiDiGraph:
    """Add distance, emissions, time-dependent travel time, and exposure to each edge."""
    zones_work = population_zones_sub[["YKR_ID", "geometry"] + [f"H{h}" for h in hours]].copy()
    zones_work = zones_work.set_crs(epsg=3067, allow_override=True)
    zones_sindex = zones_work.sindex
    zones_centroids = zones_work.geometry.centroid

    for u, v, key, data in graph_3067.edges(keys=True, data=True):
        dist_km = float(data.get("length", 0.0)) / 1000.0
        data["dist_km"] = dist_km
        data["E_uv"] = dist_km * emission_kg_per_km

        for h in hours:
            data[f"T_h{h}"] = (dist_km / speeds_kmh[h]) * 60.0

        midpoint = _edge_midpoint(graph_3067, u, v, data)
        row_zone = _find_zone_for_point(midpoint, zones_work, zones_sindex, zones_centroids)

        data["YKR_ID"] = str(row_zone["YKR_ID"])
        for h in hours:
            data[f"Exp_h{h}"] = float(data["E_uv"]) * float(row_zone[f"H{h}"])

    return graph_3067


def _edge_midpoint(graph: nx.MultiDiGraph, u: int, v: int, edge_data: dict) -> Point:
    geom = edge_data.get("geometry")
    if geom is not None:
        return geom.interpolate(0.5, normalized=True)

    x_u, y_u = graph.nodes[u]["x"], graph.nodes[u]["y"]
    x_v, y_v = graph.nodes[v]["x"], graph.nodes[v]["y"]
    return Point((x_u + x_v) / 2, (y_u + y_v) / 2)


def _find_zone_for_point(point: Point, zones_work: gpd.GeoDataFrame, zones_sindex, zones_centroids):
    possible = list(zones_sindex.intersection(point.bounds))
    for idx in possible:
        candidate = zones_work.iloc[idx]
        if candidate.geometry.covers(point):
            return candidate

    nearest_idx = int(zones_centroids.distance(point).idxmin())
    return zones_work.loc[nearest_idx]


def build_ykr_to_node(metro_subset: gpd.GeoDataFrame, graph_wgs_trim: nx.MultiDiGraph) -> dict[str, int]:
    """Map each YKR cell centroid to the closest OSM node."""
    ykr_to_node = {}
    for _, row in metro_subset.iterrows():
        ykr = str(row["YKR_ID"])
        node = ox.distance.nearest_nodes(graph_wgs_trim, X=row["lon_deg"], Y=row["lat_deg"])
        ykr_to_node[ykr] = int(node)
    return ykr_to_node


def compute_global_maxima(graph: nx.MultiDiGraph, hours: list[int]) -> tuple[float, float]:
    """Compute max travel time and max exposure for normalization."""
    t_max = 0.0
    exp_max = 0.0
    for _, _, _, data in graph.edges(keys=True, data=True):
        for h in hours:
            t_max = max(t_max, float(data.get(f"T_h{h}", 0.0)))
            exp_max = max(exp_max, float(data.get(f"Exp_h{h}", 0.0)))
    return t_max, exp_max


def plot_tradeoff(results_df: pd.DataFrame, save_path: Path | None = None):
    """Plot mean travel time vs. mean exposure for each alpha value."""
    trade_mean = (
        results_df.groupby("alpha", as_index=False)
        .agg(time_mean=("total_travel_min", "mean"), exp_mean=("total_exposure", "mean"))
        .sort_values("alpha")
    )

    fig, ax = plt.subplots(figsize=(7, 6), dpi=150)
    ax.plot(trade_mean["time_mean"], trade_mean["exp_mean"], marker="o", linewidth=2)

    for _, row in trade_mean.iterrows():
        ax.annotate(
            f"alpha={row['alpha']}\n({row['time_mean']:.1f}, {row['exp_mean']:.3f})",
            (row["time_mean"], row["exp_mean"]),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=9,
        )

    ax.set_xlabel("Total travel time (min) - mean across runs")
    ax.set_ylabel("Total emission exposure - mean across runs")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, bbox_inches="tight")
    return fig, ax
