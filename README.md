# 🌍 AP - Accessibility Project

This project provides a robust, containerized environment designed to calculate and analyze urban routing accessibility in the city of Milan. It leverages the power of **OpenTripPlanner (OTP)** for public transit analysis and **OpenRouteService (ORS)** for detailed pedestrian accessibility.

By using `Docker`, the entire simulation environment is isolated, ensuring that you can run everything out of the box.

## 🏗 Repository Structure

The project is structured to maintain a clean separation between application logic, raw geographic data, and generated outputs.

### 📂 `app/` (The Application Logic)
This directory contains the `Python`-based intelligence of the project.
* `main.py`: Creates the server that clients use for making requests. It uses route.py whenever it needs to calculate the best route.
* `route.py`: Computes the best route between two points using OTP and ORS acting as an orchestrator. It returns the map putput along with the segment details.
* `OTP_routing.py`: Interacts with the `OpenTripPlanner` local API to fetch multi-modal itineraries (Foot, Bus, Tram, Metro).
* `ORS_routing.py`: Interacts with the `OpenRouteService` remote API to analyze micro-accessibility (sidewalks, slopes, and foot-path details).

Other scripts include:
* `extractScraperData.py`: extracts data from github where the scraper has already done its work. This will be used by the following two documets...
* `dailyGTFSzipUpdater.py`: daily update of the GTFS file (and creation of the base line accessibility file to be compared by ...)
* `hourlyMonitor.py`: monitors the baseline with the current scraper extraction
* `maps.py`: holds many functions used to simplify map creation with folium
* `ORS_utility.py`: utility functions for ORS

### 📂 `data/` (The Data Warehouse)
This folder is mapped as a volume to the containers so they can access large datasets.
* **`OTP_data/`**: 
    * `MyMilan.osm.pbf`: The `OpenStreetMap` data for the Milan area.
    * `Milano-gtfs.zip`: The General Transit Feed Specification file containing public transport schedules.
    * `graph.obj`: The binary representation of the network. If missing, `OTP` builds it from the `.pbf` and `.zip` files.
    * `users.txt`: A configuration file where you define the start and end coordinates for your tests.
* **`ORS_data/`**: Contains supplemental `.json` extracts and datasets produced either by `extractor.py` or potential user additions.

### 📂 Configuration & Docker Files
* `docker-compose.yml`: The orchestration file that defines how the `otp-server` and `python-client` containers communicate.
* `Dockerfile`: The blueprint for the `Python` environment.
* `.env` (in gitnore): A local environment file used to securely store your `ORS_API_KEY`.
* `.env`: in gitnore since it holds personal ORS API key
* `main.sh`: bash script to run the server, takes care of everything (build + run + rebuild etc...)

## 🚀 Getting Started

Follow these steps to deploy the environment.

### 1. Prerequisites
* `Docker` and `Docker Compose` must be installed.
* An active **OpenRouteService API Key** (you can get one [here](https://account.heigit.org/)).

### 2. Initial Configuration
Create a file named `.env` in the root directory and paste your key:
```text
ORS_API_KEY=your_secret_api_key_here
```

### 3. Build and Deployment

Simply make `main.sh` executable and run it.
Otherwise, for debugging purposes, one can run the following `docker compose` command:
```bash
$ docker compose up --build
```
once the build finishes (takes several minutes and uses a fair amount of RAM) a new output file `graph.obj` will be created. 
After the build the execution of the docker immages will start automatically.
At this point there is no need to rebuild again since that is the file OTP needs for its computation. So to just execute the program again you can use:
```bash
$ docker compose up
```

#### What happens during the execution?
1. Docker builds the Python image and installs all requirements from `requirements.txt`.
2. The otp-server starts. If `graph.obj` is not present, it scans the OSM and GTFS files to "bake" the routing graph.
3. The python-client starts and waits for the OTP server to be ready to receive requests.
4. Once ready, the flask server can start receiving and fullfilling requests.

## 🛠 Useful Commands

| Action | Command |
| :--- | :--- |
| Build and Start Environment| `docker compose up --build` |
| Start Environment | `docker compose up` |
| Stop and Remove Containers | `docker compose down` |
| View Real-time Logs | `docker compose logs -f` |
| Force Rebuild of Routing Graph | `rm data/OTP_data/graph.obj && docker compose up` |
| Rebuild Python Client | `docker compose build python-app` |
