import config as cfg
from model import run_experiments, summarize_results
from utils import (
    add_edge_attributes,
    add_fallback_area_class,
    build_ykr_to_node,
    check_required_files,
    classify_subset_with_osm,
    compute_global_maxima,
    create_output_dirs,
    create_subset_from_seed,
    download_and_trim_graph,
    load_centroid_population,
    load_population_zones,
    plot_tradeoff,
)


def main() -> None:
    create_output_dirs(cfg.RESULTS_DIR, cfg.FIGURES_DIR)
    check_required_files([
        cfg.CENTROID_POPULATION_FILE,
        cfg.DYNAMIC_POPULATION_FILE,
        cfg.ZONES_FILE,
    ])

    print("1) Loading data and creating Helsinki subset...")
    centroid_population = load_centroid_population(cfg.CENTROID_POPULATION_FILE, cfg.INTEREST_HOURS)
    metro_subset = create_subset_from_seed(centroid_population, cfg.RADIUS_M)
    population_zones_sub = load_population_zones(
        cfg.DYNAMIC_POPULATION_FILE,
        cfg.ZONES_FILE,
        metro_subset["YKR_ID"].unique(),
    )

    if cfg.USE_OSM_CLASSIFICATION:
        print("2) Classifying subset cells using OSM features...")
        try:
            metro_subset = classify_subset_with_osm(metro_subset, population_zones_sub, cfg.PLACE_NAME)
        except Exception as exc:
            print(f"   OSM classification failed: {exc}")
            print("   Continuing with fallback area_class='mixed'.")
            metro_subset = add_fallback_area_class(metro_subset)
    else:
        metro_subset = add_fallback_area_class(metro_subset)

    print("3) Downloading and preparing OSM road network...")
    graph_3067, graph_wgs_trim = download_and_trim_graph(
        metro_subset,
        population_zones_sub,
        cfg.HOURS,
        cfg.RADIUS_OSM_M,
    )

    print("4) Adding edge attributes: distance, emissions, travel time, exposure...")
    graph_3067 = add_edge_attributes(
        graph_3067,
        population_zones_sub,
        cfg.HOURS,
        cfg.SPEEDS_KMH,
        cfg.EMISSION_KG_PER_KM,
    )
    t_max, exp_max = compute_global_maxima(graph_3067, cfg.HOURS)

    print("5) Mapping YKR cells to graph nodes...")
    ykr_to_node = build_ykr_to_node(metro_subset, graph_wgs_trim)
    depot_node = ykr_to_node[cfg.DEPOT_YKR_ID]

    print("6) Running experiments...")
    results_df = run_experiments(
        graph=graph_3067,
        metro_subset=metro_subset,
        ykr_to_node=ykr_to_node,
        depot_ykr_id=cfg.DEPOT_YKR_ID,
        depot_node=depot_node,
        hours=cfg.HOURS,
        t_max=t_max,
        exp_max=exp_max,
        seeds=cfg.SEEDS,
        alphas=cfg.ALPHAS,
        n_customers=cfg.N_CUSTOMERS,
        service_time_min=cfg.SERVICE_TIME_MIN,
        start_hour=cfg.START_HOUR,
    )

    summary_stats, tradeoff_stats = summarize_results(results_df, baseline_alpha=1.0)

    print("7) Saving results...")
    results_df.to_csv(cfg.RESULTS_DIR / "experiment_results.csv", index=False)
    summary_stats.to_csv(cfg.RESULTS_DIR / "summary_stats_by_alpha.csv")
    plot_tradeoff(results_df, save_path=cfg.FIGURES_DIR / "tradeoff_time_vs_exposure.png")

    print("\nDone. Outputs saved in the results/ folder.")
    print("\nSummary by alpha:")
    print(summary_stats)


if __name__ == "__main__":
    main()
