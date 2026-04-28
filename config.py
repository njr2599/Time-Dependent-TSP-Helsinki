from pathlib import Path

# ---------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
RESULTS_DIR = ROOT_DIR / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
REPORT_DIR = ROOT_DIR / "report"

# ---------------------------------------------------------------------
# Input data files
# Place these files inside the data/ folder.
# ---------------------------------------------------------------------
CENTROID_POPULATION_FILE = DATA_DIR / "LatitudeLongitudeNodes_w_PopulationDistribution.csv"
DYNAMIC_POPULATION_FILE = DATA_DIR / "HMA_Dynamic_population_24H_workdays.csv"
ZONES_FILE = DATA_DIR / "target_zones_grid250m_EPSG3067.geojson"

# ---------------------------------------------------------------------
# Spatial subset settings
# ---------------------------------------------------------------------
RADIUS_M = 3000
RADIUS_OSM_M = RADIUS_M + 1000
INTEREST_HOURS = [f"H{h}" for h in range(10, 19)]
PLACE_NAME = "Helsinki, Finland"

# ---------------------------------------------------------------------
# TDTSP model settings
# ---------------------------------------------------------------------
HOURS = list(range(8, 18))
SPEEDS_LIST_KMH = [18.8, 18.8, 20.2, 20.2, 20.2, 20.2, 20.2, 18.8, 18.8, 18.8]
SPEEDS_KMH = dict(zip(HOURS, SPEEDS_LIST_KMH))

FUEL_RATE_L_PER_100KM = 6.85
GHG_COEF_KG_PER_L = 2.67
EMISSION_KG_PER_KM = FUEL_RATE_L_PER_100KM * GHG_COEF_KG_PER_L / 100.0

DEPOT_YKR_ID = "5975374"
START_HOUR = 8
SERVICE_TIME_MIN = 20
N_CUSTOMERS = 20

# Alpha controls the trade-off:
# alpha = 1.0 -> prioritize travel time
# alpha = 0.5 -> balance travel time and exposure
# alpha = 0.0 -> prioritize exposure reduction
ALPHAS = [0.0, 0.5, 1.0]
SEEDS = list(range(100, 110))

# If OSM-based area classification fails, the code can still run by using
# all non-depot cells as possible customer locations.
USE_OSM_CLASSIFICATION = True
