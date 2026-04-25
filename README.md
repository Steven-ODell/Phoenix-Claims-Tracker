# 🌵 Phoenix Claims Tracker (KORE-PC)

A personal tool to track insurance claims in the Phoenix area, visualize them on an interactive map, manage follow-up alerts, and mark neighborhood zones.

A PA opens it in the morning and in 5 minutes knows:

Who to call
Where the bought jobs are clustered for routing
Who's worth a door knock vs a write-off
What's snoozed and why

---

## Prerequisites

- Python 3.9+
- Internet access (required for the Geopy geocoding service on first address save)

---

## Installation

1. **Copy** `app.py` into your project directory.

2. **Install dependencies:**

```bash
pip install streamlit pandas folium streamlit-folium geopy
```

3. **Run the app:**

```bash
streamlit run app.py
```

The app will open in your default browser at `http://localhost:8501`.

---

## Features

### 🔔 Follow-up Alert Center
- Automatically flags any active claim where the Customer DOLC **or** Insurance DOLC is 3+ days old.
- Shows both contact dates on each alert card so you know which triggered it.
- **📞 Called Customer** — stamps Customer DOLC to today and clears snooze.
- **📋 Called Insurance** — stamps Insurance DOLC to today and clears snooze.
- **✅ Log Done** — resets both dates to today.
- **💤 Snooze** — suppresses the alert for 1–7 days.

### 🗺️ Interactive Map
- Plots all geocoded claims as color-coded dots:
  - 🟣 **Purple** — Insurance bought (active or completed)
  - 🔴 **Red** — High priority
  - 🔵 **Blue** — Medium priority
  - 🟢 **Green** — Low priority
  - ⚫ **Gray** — Job done, insurance never bought
- **Filter checkboxes** let you hide/show any marker category on the fly.
- Draw rectangles or polygons directly on the map to mark zones (no-soliciting areas, renter-heavy blocks, etc.). Zones are named, color-coded, and saved automatically.
- Manage (delete) saved zones from the collapsible zone manager below the map.

### 📝 New Claim Entry (Sidebar)
- Full entry form: Nimbus#, name, address, phone, priority, condition rating, bought/done/worth-effort toggles, both DOLC dates, description, adjuster info, and supplementals.
- Address is geocoded automatically on save.

### 📋 Claims Database Table
- **Active jobs** displayed in a sortable table (click any column header).
- **Completed jobs** collapsed into a separate pinned section below — never interfere with active sorting.
- Search by name or Nimbus# filters both tables simultaneously.

### 🛠️ Edit / Delete
- Select any claim by Nimbus# to edit all fields.
- **Clear Snooze** checkbox shows the current snooze date and lets you wipe it on save.
- Delete permanently removes the claim from the database.

---

## Data Storage

All data is stored in a single local SQLite file:

```
insurance_claims_v4.db
```

The schema is created automatically on first launch. No external server or configuration required.
