# Phoenix Claims Tracker

A personal tool to track insurance claims in the Phoenix area, visualize them on a map, and manage restricted zones.

## Prerequisites
- Python 3.9+
- A machine with internet access (for the Geopy geocoding service).

## Installation

1. **Clone or copy** the `app.py` file to your project directory.

2. **Install dependencies:**
   Run the following command in your terminal:
   ```bash
   pip install streamlit pandas folium streamlit-folium geopy
Running the Application
Open your terminal in the project directory.

# Launch the app using Streamlit:

## Terminal
`streamlit run app.py`
The app will open in your default web browser (usually at http://localhost:8501).

# Features
Claims Management: Add, edit, and delete property insurance claims.

Interactive Mapping: Visualize claim locations on an interactive map.

Restricted Zones: Draw polygons/rectangles on the map to mark areas (e.g., no-soliciting zones or high-renter areas), name them, and save them to the database.

Search & Filter: Easily filter your list of claims by keyword.andas folium streamlit-folium geopy

# Data Storage
The application uses a local file database named insurance_claims_v4.db.

The app automatically initializes the database schema upon first launch.

No external server or configuration is required.

