# Multi-Objective Time-Dependent Traveling Salesman Problem (TDTSP)

## 1. Abstract

This project investigates a multi-objective **Time-Dependent Traveling
Salesman Problem (TDTSP)**. It balances logistical efficiency
(minimizing travel time) with a social responsibility goal: minimizing
population exposure to vehicle emissions.

Using the Helsinki Metropolitan Area as a case study, the model
integrates dynamic population shifts to evaluate the social cost of a
journey at each road segment.

------------------------------------------------------------------------

## 2. Dataset Explanation

The study utilizes two primary datasets centered on the Helsinki
Metropolitan Area (HMA):

-   **Dynamic Population Data**\
    A 24-hour distribution reflecting hourly population percentages for
    weekdays, Saturdays, and Sundays.

-   **Spatial Grid Cells (YKR)**\
    The city is divided into **250 × 250 meter grid cells**, each
    identified by a unique `YKR_ID`.

-   **Subset Selection**\
    To optimize performance, a subset of **352 cells** was selected,
    representing the city's four main municipalities.

------------------------------------------------------------------------

## 3. Methods Used

The project uses a two-stage hierarchical framework to balance travel efficiency and emission exposure.

**Local Level**

At the local level, the model evaluates each road segment (u, v) instead of only considering full routes.

A cost function C_uvh is calculated for every segment, combining:

- Travel Time 
- Emission Exposure 

**Global Level**

After assigning costs to all road segments:

- Dijkstra’s Algorithm is used to find the best path between two locations based on the combined cost
- A Nearest Neighbor heuristic is then used to construct the full tour

How it works:

Start from the depot
Select the next closest customer based on the computed cost
Repeat until all customers are visited

In simple terms:

- Dijkstra → Finds the best path between two points
- Nearest Neighbor → Connects all points into a complete route

**Variable Weighting (α)**

The parameter α ∈ [0, 1] controls the trade-off between travel time and emission exposure:

α ∈ \[0, 1\]

-   α = 1 → Prioritizes travel time
-   α = 0 → Prioritizes emission exposure
------------------------------------------------------------------------

## 4. Results & Analysis

-   **Non-Linear Trade-off**
    Moving from α = 1.0 to α = 0.5 achieved a **17.3% reduction in
    emission exposure** with only a **1-minute increase in travel
    time**.

-   **Detour Paradox**\
    Prioritizing only exposure (α = 0) leads to significantly longer
    detours, which can **increase total emissions generated**.

-   **Optimal Balance**\
    α = 0.5 provides the most efficient trade-off for urban logistics.
------------------------------------------------------------------------
## How to cite

If you use this code, methodology, or results, please cite this repository:

Gök, C., Juscamaita Ramos, N., & Lagoo, M. (2026). 
Time-Dependent Emission Exposure in Helsinki. 
GitHub repository: https://github.com/njr2599/Time-Dependent-TSP-Helsinki

You can also use the "Cite this repository" button on the right side of the GitHub page.
