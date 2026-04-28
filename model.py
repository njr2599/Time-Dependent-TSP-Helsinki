from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd


def compute_cuvh_for_alpha(
    graph: nx.MultiDiGraph,
    hours: list[int],
    alpha: float,
    t_max: float,
    exp_max: float,
) -> nx.MultiDiGraph:
    """Compute the scalarized edge cost C_uvh for a selected alpha."""
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be between 0 and 1.")

    for _, _, _, data in graph.edges(keys=True, data=True):
        for h in hours:
            t_uvh = float(data.get(f"T_h{h}", 0.0))
            exp_uvh = float(data.get(f"Exp_h{h}", 0.0))
            t_norm = t_uvh / t_max if t_max > 0 else 0.0
            exp_norm = exp_uvh / exp_max if exp_max > 0 else 0.0
            data[f"C_h{h}"] = alpha * t_norm + (1.0 - alpha) * exp_norm
    return graph


def hour_bucket(start_hour: int, elapsed_minutes: float, valid_hours: list[int]) -> int:
    """Convert elapsed minutes into the hour bucket used by the edge weights."""
    hour = start_hour + int(elapsed_minutes // 60)
    return max(min(hour, max(valid_hours)), min(valid_hours))


def best_edge_data_for_step(graph: nx.MultiDiGraph, u: int, v: int, weight_key: str) -> dict | None:
    """Return the best parallel edge between two nodes for the chosen weight."""
    edge_dict = graph.get_edge_data(u, v)
    if edge_dict is None:
        return None
    return min(edge_dict.values(), key=lambda data: data.get(weight_key, float("inf")))


def path_metrics(
    graph: nx.MultiDiGraph,
    path_nodes: list[int],
    hour: int,
    weight_key: str,
) -> tuple[float, float, float, float] | None:
    """Sum distance, travel time, exposure, and objective cost along a path."""
    dist_km = travel_min = exposure = cost = 0.0

    for a, b in zip(path_nodes[:-1], path_nodes[1:]):
        data = best_edge_data_for_step(graph, a, b, weight_key)
        if data is None:
            return None
        dist_km += float(data.get("dist_km", 0.0))
        travel_min += float(data.get(f"T_h{hour}", 0.0))
        exposure += float(data.get(f"Exp_h{hour}", 0.0))
        cost += float(data.get(weight_key, 0.0))

    return dist_km, travel_min, exposure, cost


def nearest_neighbor_tdtsp(
    graph: nx.MultiDiGraph,
    depot_node: int,
    customer_nodes: list[int],
    hours: list[int],
    start_hour: int,
    service_time_min: float,
) -> tuple[list[int], dict[str, float], pd.DataFrame]:
    """Build a tour using a time-dependent nearest-neighbor heuristic."""
    remaining = set(customer_nodes)
    route = [depot_node]
    current = depot_node
    elapsed = 0.0

    total_dist = total_travel = total_exposure = total_cost = 0.0
    steps = []

    while remaining:
        hour = hour_bucket(start_hour, elapsed, hours)
        weight_key = f"C_h{hour}"
        lengths = nx.single_source_dijkstra_path_length(graph, current, weight=weight_key)

        next_node = min(remaining, key=lambda node: lengths.get(node, float("inf")))
        if lengths.get(next_node, float("inf")) == float("inf"):
            raise RuntimeError("No reachable customer from current node.")

        path_nodes = nx.shortest_path(graph, current, next_node, weight=weight_key)
        metrics = path_metrics(graph, path_nodes, hour, weight_key)
        if metrics is None:
            raise RuntimeError("Could not calculate metrics for a route leg.")

        dist_leg, travel_leg, exposure_leg, cost_leg = metrics
        elapsed += travel_leg + service_time_min
        total_dist += dist_leg
        total_travel += travel_leg
        total_exposure += exposure_leg
        total_cost += cost_leg

        steps.append({
            "from": current,
            "to": next_node,
            "hour_used": hour,
            "dist_km": dist_leg,
            "travel_min": travel_leg,
            "service_min": service_time_min,
            "exposure": exposure_leg,
            "cost": cost_leg,
            "elapsed_after_min": elapsed,
        })

        route.append(next_node)
        remaining.remove(next_node)
        current = next_node

    # Return to depot.
    hour = hour_bucket(start_hour, elapsed, hours)
    weight_key = f"C_h{hour}"
    path_nodes = nx.shortest_path(graph, current, depot_node, weight=weight_key)
    metrics = path_metrics(graph, path_nodes, hour, weight_key)
    if metrics is None:
        raise RuntimeError("Could not calculate metrics for the return leg.")

    dist_leg, travel_leg, exposure_leg, cost_leg = metrics
    elapsed += travel_leg
    total_dist += dist_leg
    total_travel += travel_leg
    total_exposure += exposure_leg
    total_cost += cost_leg

    steps.append({
        "from": current,
        "to": depot_node,
        "hour_used": hour,
        "dist_km": dist_leg,
        "travel_min": travel_leg,
        "service_min": 0.0,
        "exposure": exposure_leg,
        "cost": cost_leg,
        "elapsed_after_min": elapsed,
    })
    route.append(depot_node)

    steps_df = pd.DataFrame(steps)
    steps_df["cum_dist_km"] = steps_df["dist_km"].cumsum()
    steps_df["cum_travel_min"] = steps_df["travel_min"].cumsum()
    steps_df["cum_exposure"] = steps_df["exposure"].cumsum()

    summary = {
        "total_dist_km": total_dist,
        "total_travel_min": total_travel,
        "total_exposure": total_exposure,
        "total_cost": total_cost,
        "finish_hour_bucket": hour_bucket(start_hour, elapsed, hours),
        "elapsed_total_min": elapsed,
    }
    return route, summary, steps_df


def generate_customers_and_nodes(
    metro_subset: pd.DataFrame,
    ykr_to_node: dict[str, int],
    depot_ykr_id: str,
    depot_node: int,
    seed: int,
    n_customers: int,
) -> tuple[list[str], list[int]]:
    """Randomly select customer cells and map them to graph nodes."""
    rng = np.random.default_rng(seed)

    if "area_class" in metro_subset.columns:
        candidates = metro_subset[
            (metro_subset["area_class"].isin(["mixed", "residential"]))
            & (metro_subset["YKR_ID"].astype(str) != str(depot_ykr_id))
        ]["YKR_ID"].astype(str).tolist()
    else:
        candidates = metro_subset[metro_subset["YKR_ID"].astype(str) != str(depot_ykr_id)]["YKR_ID"].astype(str).tolist()

    rng.shuffle(candidates)
    customers_ykr = []
    customer_nodes = []
    used_nodes = {depot_node}

    for ykr in candidates:
        node = ykr_to_node.get(str(ykr))
        if node is None or node in used_nodes:
            continue
        customers_ykr.append(str(ykr))
        customer_nodes.append(int(node))
        used_nodes.add(int(node))
        if len(customer_nodes) == n_customers:
            break

    if len(customer_nodes) < n_customers:
        raise ValueError("Not enough unique customer nodes found.")

    return customers_ykr, customer_nodes


def run_experiments(
    graph: nx.MultiDiGraph,
    metro_subset: pd.DataFrame,
    ykr_to_node: dict[str, int],
    depot_ykr_id: str,
    depot_node: int,
    hours: list[int],
    t_max: float,
    exp_max: float,
    seeds: list[int],
    alphas: list[float],
    n_customers: int,
    service_time_min: float,
    start_hour: int,
) -> pd.DataFrame:
    """Run the model for multiple demand seeds and alpha values."""
    rows = []

    for seed in seeds:
        _, customer_nodes = generate_customers_and_nodes(
            metro_subset=metro_subset,
            ykr_to_node=ykr_to_node,
            depot_ykr_id=depot_ykr_id,
            depot_node=depot_node,
            seed=seed,
            n_customers=n_customers,
        )

        for alpha in alphas:
            compute_cuvh_for_alpha(graph, hours, alpha, t_max, exp_max)
            _, summary, _ = nearest_neighbor_tdtsp(
                graph=graph,
                depot_node=depot_node,
                customer_nodes=customer_nodes,
                hours=hours,
                start_hour=start_hour,
                service_time_min=service_time_min,
            )
            rows.append({
                "experiment_seed": seed,
                "alpha": alpha,
                "n_customers": n_customers,
                "total_dist_km": summary["total_dist_km"],
                "total_travel_min": summary["total_travel_min"],
                "total_exposure": summary["total_exposure"],
                "elapsed_total_min": summary["elapsed_total_min"],
                "finish_hour_bucket": summary["finish_hour_bucket"],
                "total_cost": summary["total_cost"],
            })

    return pd.DataFrame(rows).sort_values(["experiment_seed", "alpha"]).reset_index(drop=True)


def summarize_results(results_df: pd.DataFrame, baseline_alpha: float = 1.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create summary tables for the GitHub results folder."""
    summary_stats = results_df.groupby("alpha")[["total_travel_min", "total_exposure", "total_dist_km"]].agg(
        ["mean", "std"]
    )

    baseline = results_df[results_df["alpha"] == baseline_alpha][
        ["experiment_seed", "total_travel_min", "total_exposure"]
    ].rename(columns={"total_travel_min": "travel_baseline", "total_exposure": "exposure_baseline"})

    tmp = results_df.merge(baseline, on="experiment_seed", how="left")
    tmp["delta_time_vs_baseline"] = tmp["total_travel_min"] - tmp["travel_baseline"]
    tmp["exposure_reduction_vs_baseline"] = tmp["exposure_baseline"] - tmp["total_exposure"]
    tmp["exposure_reduction_pct_vs_baseline"] = np.where(
        tmp["exposure_baseline"] > 0,
        100.0 * tmp["exposure_reduction_vs_baseline"] / tmp["exposure_baseline"],
        0.0,
    )

    tradeoff_stats = tmp.groupby("alpha")[[
        "delta_time_vs_baseline",
        "exposure_reduction_vs_baseline",
        "exposure_reduction_pct_vs_baseline",
    ]].agg(["mean", "std"])

    return summary_stats, tradeoff_stats
