# Time-Dependent Emission Exposure TSP in Helsinki

This repository contains a compact Python implementation of a multi-objective Time-Dependent Traveling Salesman Problem (TDTSP) for urban routing in Helsinki.
The project compares routes under different values of `alpha`:
`alpha = 1.0`: prioritize travel time
`alpha = 0.5`: balance travel time and emission exposure
`alpha = 0.0`: prioritize reducing population exposure to emissions
The workflow follows the original project structure:
1. Load Helsinki population and YKR grid data.
2. Create a 3 km study subset around the most active YKR cell.
3. Download and trim the OSM road network.
4. Add distance, emissions, travel time, and exposure attributes to each road segment.
5. Solve the tour using a time-dependent nearest-neighbor heuristic.
6. Compare travel time and exposure across alpha values.

## Repository structure
```text
time-dependent-emission-tsp-compact/
│
├── config.py          # All paths, parameters, alpha values, seeds, vehicle assumptions
├── utils.py           # Helper functions for data, graph preparation, and plotting
├── model.py           # Cost function, TDTSP heuristic, and experiment logic
├── main.py            # Main execution script
│
├── data/              # Input data goes here, not included in this repository
├── results/           # Generated result tables and figures
├── report/            # Optional redacted report PDF
│
├── requirements.txt
├── .gitignore
└── README.md
```
## Data files
Place the following files inside the `data/` folder:
```text
data/
├── LatitudeLongitudeNodes_w_PopulationDistribution.csv
├── HMA_Dynamic_population_24H_workdays.csv
└── target_zones_grid250m_EPSG3067.geojson
```
These data files are not included in the repository because they may be large, private, or restricted.

## Installation
Create and activate a virtual environment:
```bash
python -m venv .venv
```
On macOS/Linux:
```bash
source .venv/bin/activate
```
On Windows:
```bash
.venv\Scripts\activate
```
Install the required packages:
```bash
pip install -r requirements.txt
```

## How to run
From the project folder, run:
```bash
python main.py
```
The script will save outputs to the `results/` folder:
```text
results/
├── experiment_results.csv
├── summary_stats_by_alpha.csv
├── tradeoff_stats_vs_alpha_1.csv
└── figures/
    └── tradeoff_time_vs_exposure.png
```

### How the code is divided
1. `config.py`
Use this file when you want to change:
input file names,
radius of the subset,
working hours,
speeds,
fuel/emission parameters,
depot YKR ID,
number of customers,
seeds,
alpha values.
2. `utils.py`
Contains helper functions for:
loading data,
creating the Helsinki subset,
OSM-based classification,
downloading and trimming the road graph,
assigning edge attributes,
plotting the trade-off figure.\
3. `model.py`
Contains the optimization logic:
scalarized cost calculation `C_uvh`,
hour bucket rule,
path metric calculation,
time-dependent nearest-neighbor heuristic,
experiment loops,
summary statistics.\
4. `main.py`
Runs the full workflow from start to finish. This is the file to execute.

### Notes
- The code needs internet access the first time it downloads the OSM road network through OSMnx. If you want a fully offline version later, you can add graph caching.\
- For public GitHub upload, avoid committing private data, personal local paths, student IDs, signatures, or unredacted reports.
