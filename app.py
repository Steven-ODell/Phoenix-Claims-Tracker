import streamlit as st
import sqlite3
import pandas as pd
import json
from datetime import datetime
from geopy.geocoders import Nominatim
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium

# --- SETTINGS ---
DB_NAME = "insurance_claims_v4.db"

def init_db():
    """Initializes the database and ensures schemas are up to date."""
    with sqlite3.connect(DB_NAME) as conn:
        # 1. Claims Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                bingus_id INTEGER PRIMARY KEY,
                name TEXT, address TEXT, phone TEXT,
                priority TEXT, worth_effort INTEGER, condition INTEGER,
                customer_dolc DATE, insurance_state_dolc DATE,
                description TEXT, company_adjuster TEXT, supplementals TEXT,
                latitude REAL, longitude REAL,
                bought INTEGER DEFAULT 0
            )
        """)
        
        # 2. Zones Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS restricted_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                geo_json TEXT,
                color TEXT,
                name TEXT
            )
        """)
        
        # Schema migration check for columns
        cursor = conn.execute("PRAGMA table_info(claims)")
        columns = [c[1] for c in cursor.fetchall()]
        if 'bought' not in columns:
            conn.execute("ALTER TABLE claims ADD COLUMN bought INTEGER DEFAULT 0")
            
        cursor = conn.execute("PRAGMA table_info(restricted_zones)")
        if 'name' not in [c[1] for c in cursor.fetchall()]:
            conn.execute("ALTER TABLE restricted_zones ADD COLUMN name TEXT")
            
        conn.commit()

def get_coords(address: str):
    """Converts address to coordinates."""
    if not address or len(address) < 5: return None, None
    try:
        geolocator = Nominatim(user_agent="phoenix_tracker_final_v5")
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
    except:
        pass
    return None, None

def save_claim(data: dict, mode: str = "add"):
    """Saves or updates a claim."""
    lat, lon = get_coords(data['address'])
    data['latitude'] = lat
    data['longitude'] = lon
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        if mode == "add":
            query = """INSERT INTO claims (bingus_id, name, address, phone, priority, worth_effort, 
                       condition, customer_dolc, insurance_state_dolc, description, company_adjuster, 
                       supplementals, latitude, longitude, bought) 
                       VALUES (:bingus_id, :name, :address, :phone, :priority, :worth_effort, 
                       :condition, :customer_dolc, :insurance_state_dolc, :description, :company_adjuster, 
                       :supplementals, :latitude, :longitude, :bought)"""
        else:
            query = """UPDATE claims SET name=:name, address=:address, phone=:phone, priority=:priority, 
                       worth_effort=:worth_effort, condition=:condition, customer_dolc=:customer_dolc, 
                       insurance_state_dolc=:insurance_state_dolc, description=:description, 
                       company_adjuster=:company_adjuster, supplementals=:supplementals,
                       latitude=:latitude, longitude=:longitude, bought=:bought 
                       WHERE bingus_id=:bingus_id"""
        cursor.execute(query, data)
        conn.commit()

def get_all_claims():
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql("SELECT * FROM claims", conn)
        # Handle Date conversions
        for col in ['customer_dolc', 'insurance_state_dolc']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col]).dt.date
        df['worth_effort'] = df['worth_effort'].astype(bool)
        df['bought'] = df['bought'].astype(bool)
        return df

# --- UI MAIN ---
def main():
    st.set_page_config(page_title="Phoenix Claims Tracker", layout="wide")
    init_db()

    st.title("🌵 Phoenix Neighborhood Claims Tracker")
    df = get_all_claims()

    # --- MAP SECTION ---
    st.subheader("Neighborhood Map & Restricted Zones")
    map_df = df.dropna(subset=['latitude', 'longitude']).copy()

    c1, c2 = st.columns([1, 3])
    with c1:
        zone_color = st.selectbox("Select color for new zones:", ["red", "orange", "yellow", "black", "gray"])
        new_zone_name = st.text_input("Name for new zone (optional):", value="")
        jump = st.selectbox("🎯 Focus Map on Claim:", ["-- Select to Zoom --"] + map_df['name'].tolist() if not map_df.empty else ["-- Select to Zoom --"])

    center_lat, center_lon = 33.4484, -112.0740
    zoom_level = 10
    if jump != "-- Select to Zoom --":
        sel = map_df[map_df['name'] == jump].iloc[0]
        center_lat, center_lon = sel['latitude'], sel['longitude']
        zoom_level = 17

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level)

    # 1. Claims
    for _, row in map_df.iterrows():
        color = 'purple' if row['bought'] else ('red' if row['priority'] == "1-High" else ('blue' if row['priority'] == "2-Medium" else 'green'))
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=7, color=color, fill=True, fill_color=color, fill_opacity=0.8,
            tooltip=f"<b>{row['name']}</b>"
        ).add_to(m)

    # 2. Drawn Zones
    with sqlite3.connect(DB_NAME) as conn:
        saved_zones = pd.read_sql("SELECT * FROM restricted_zones", conn)
        for _, zone in saved_zones.iterrows():
            geo_data = json.loads(zone['geo_json'])
            folium.GeoJson(
                geo_data,
                style_function=lambda x, c=zone['color']: {'fillColor': c, 'color': c, 'weight': 2, 'fillOpacity': 0.3},
                tooltip=zone['name']
            ).add_to(m)

    # 3. Drawing tools
    Draw(draw_options={'polyline': False, 'polygon': True, 'rectangle': True, 'circle': False, 'marker': False, 'circlemarker': False}, edit_options={'edit': False}).add_to(m)
    map_data = st_folium(m, width=1200, height=600, key="folium_map", returned_objects=["last_active_drawing"])

    # 4. Save new zones
    if map_data and map_data.get("last_active_drawing"):
        new_geom = map_data["last_active_drawing"]
        geom_str = json.dumps(new_geom)
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM restricted_zones WHERE geo_json = ?", (geom_str,))
            if not cursor.fetchone():
                z_name = new_zone_name if new_zone_name else f"Zone at {datetime.now().strftime('%H:%M:%S')}"
                cursor.execute("INSERT INTO restricted_zones (geo_json, color, name) VALUES (?, ?, ?)", 
                               (geom_str, zone_color, z_name))
                conn.commit()
                st.rerun()

    st.caption("🟣 Bought | 🔴 High | 🔵 Medium | 🟢 Low | ⬛ Restricted Zones")

    # --- MANAGEMENT SECTION ---
    with st.expander("🛠️ Manage Restricted Zones"):
        with sqlite3.connect(DB_NAME) as conn:
            zones_df = pd.read_sql("SELECT id, name, color FROM restricted_zones", conn)
        
        if not zones_df.empty:
            zone_map = {f"{row['name']} ({row['color']})": row['id'] for _, row in zones_df.iterrows()}
            selected_option = st.selectbox("Select Zone to Delete", list(zone_map.keys()))
            
            if st.button("Delete Selected Zone"):
                with sqlite3.connect(DB_NAME) as conn:
                    conn.execute("DELETE FROM restricted_zones WHERE id = ?", (zone_map[selected_option],))
                st.rerun()
        else:
            st.write("No restricted zones found.")

    # --- SIDEBAR: NEW CLAIM ---
    with st.sidebar.form("add_form", clear_on_submit=True):
        st.header("📝 New Claim Entry")
        f_bingus = st.number_input("Bingus#", min_value=1, step=1)
        f_name = st.text_input("Name")
        f_phone = st.text_input("Phone")
        f_addr = st.text_input("Address (City, State, Zip)")
        f_prio = st.selectbox("Priority", ["1-High", "2-Medium", "3-Low"])
        f_bought = st.toggle("Insurance Bought?") 
        f_worth = st.toggle("Worth Effort?")
        f_cond = st.slider("Condition (1-5)", 1, 5, 3)
        f_dolc = st.date_input("Customer DOLC")
        f_ins = st.date_input("Insurance DOLC")
        f_desc = st.text_area("Description")
        f_adj = st.text_area("Adjuster Info")
        f_supp = st.text_area("Supplementals")
        if st.form_submit_button("Save to Database"):
            save_claim({"bingus_id": f_bingus, "name": f_name, "address": f_addr, "phone": f_phone,
                        "priority": f_prio, "worth_effort": 1 if f_worth else 0, "condition": f_cond,
                        "customer_dolc": f_dolc, "insurance_state_dolc": f_ins, "description": f_desc,
                        "company_adjuster": f_adj, "supplementals": f_supp, "bought": 1 if f_bought else 0}, mode="add")
            st.rerun()

    # --- TABLE DISPLAY ---
    st.markdown("---")
    search = st.text_input("🔍 Filter list by any keyword", "")
    view_df = df.copy()
    if search:
        view_df = df[df['name'].str.contains(search, case=False, na=False) | 
                     df['address'].str.contains(search, case=False, na=False) |
                     df['description'].str.contains(search, case=False, na=False)]
    
    st.dataframe(view_df.drop(columns=['latitude', 'longitude']), use_container_width=True, hide_index=True,
                 column_config={
                     "bought": st.column_config.CheckboxColumn("Bought?"),
                     "worth_effort": st.column_config.CheckboxColumn("Worth Effort?"),
                     "condition": st.column_config.ProgressColumn("Condition", min_value=1, max_value=5)
                 })

    # --- EDIT/DELETE ---
    if not df.empty:
        st.markdown("---")
        with st.expander("🛠️ Manage/Edit Existing Claims"):
            selected_id = st.selectbox("Select Bingus#", df['bingus_id'].tolist())
            rec = df[df['bingus_id'] == selected_id].iloc[0]
            with st.form("edit_form"):
                e_name = st.text_input("Name", value=rec['name']); e_phone = st.text_input("Phone", value=rec['phone'])
                e_addr = st.text_input("Address", value=rec['address'])
                e_prio = st.selectbox("Priority", ["1-High", "2-Medium", "3-Low"], index=["1-High", "2-Medium", "3-Low"].index(rec['priority']))
                e_bought = st.toggle("Insurance Bought?", value=bool(rec['bought']))
                e_worth = st.toggle("Worth Effort?", value=bool(rec['worth_effort']))
                e_cond = st.slider("Condition", 1, 5, int(rec['condition']))
                e_dolc = st.date_input("Customer DOLC", value=rec['customer_dolc'])
                e_ins = st.date_input("Insurance DOLC", value=rec['insurance_state_dolc'])
                e_desc = st.text_area("Description", value=rec['description'])
                e_adj = st.text_area("Adjuster", value=rec['company_adjuster'])
                e_supp = st.text_area("Supplementals", value=rec['supplementals'])
                
                c1, c2, _ = st.columns([1, 1, 2])
                if c1.form_submit_button("Update"):
                    save_claim({"bingus_id": selected_id, "name": e_name, "address": e_addr, "phone": e_phone,
                                "priority": e_prio, "worth_effort": 1 if e_worth else 0, "condition": e_cond,
                                "customer_dolc": e_dolc, "insurance_state_dolc": e_ins, "description": e_desc,
                                "company_adjuster": e_adj, "supplementals": e_supp, "bought": 1 if e_bought else 0}, mode="edit")
                    st.rerun()
                if c2.form_submit_button("🗑️ Delete"):
                    with sqlite3.connect(DB_NAME) as conn: conn.execute("DELETE FROM claims WHERE bingus_id = ?", (selected_id,))
                    st.rerun()

if __name__ == "__main__":
    main()
