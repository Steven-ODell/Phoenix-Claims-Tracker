import streamlit as st
import sqlite3
import pandas as pd
import json
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium

# --- SETTINGS ---
DB_NAME = "insurance_claims_v4.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                bingus_id INTEGER PRIMARY KEY,
                name TEXT, address TEXT, phone TEXT,
                priority TEXT, worth_effort INTEGER, condition INTEGER,
                customer_dolc DATE, insurance_state_dolc DATE,
                description TEXT, company_adjuster TEXT, supplementals TEXT,
                latitude REAL, longitude REAL,
                bought INTEGER DEFAULT 0,
                job_done INTEGER DEFAULT 0,
                snooze_until DATE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS restricted_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                geo_json TEXT,
                color TEXT,
                name TEXT
            )
        """)
        conn.commit()

# --- DATABASE HELPERS ---
def get_coords(address: str):
    if not address or len(address) < 5: return None, None
    try:
        geolocator = Nominatim(user_agent="phoenix_tracker_v8")
        location = geolocator.geocode(address)
        if location: return location.latitude, location.longitude
    except: pass
    return None, None

def save_claim(data: dict, mode: str = "add"):
    for key in ['customer_dolc', 'insurance_state_dolc', 'snooze_until']:
        if key in data and pd.isna(data[key]): data[key] = None
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        if mode == "add":
            lat, lon = get_coords(data['address'])
            data['latitude'], data['longitude'] = lat, lon
            query = """INSERT INTO claims (bingus_id, name, address, phone, priority, worth_effort, 
                       condition, customer_dolc, insurance_state_dolc, description, company_adjuster, 
                       supplementals, latitude, longitude, bought, job_done, snooze_until) 
                       VALUES (:bingus_id, :name, :address, :phone, :priority, :worth_effort, 
                       :condition, :customer_dolc, :insurance_state_dolc, :description, :company_adjuster, 
                       :supplementals, :latitude, :longitude, :bought, :job_done, :snooze_until)"""
        else:
            query = """UPDATE claims SET name=:name, address=:address, phone=:phone, priority=:priority, 
                       worth_effort=:worth_effort, condition=:condition, customer_dolc=:customer_dolc, 
                       insurance_state_dolc=:insurance_state_dolc, description=:description, 
                       company_adjuster=:company_adjuster, supplementals=:supplementals,
                       latitude=:latitude, longitude=:longitude, bought=:bought, job_done=:job_done,
                       snooze_until=:snooze_until WHERE bingus_id=:bingus_id"""
        cursor.execute(query, data)
        conn.commit()

def save_zone(geo_json, color, name):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO restricted_zones (geo_json, color, name) VALUES (?, ?, ?)", 
                     (json.dumps(geo_json), color, name))
        conn.commit()

def delete_zone(zone_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM restricted_zones WHERE id = ?", (zone_id,))
        conn.commit()

def get_all_claims():
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql("SELECT * FROM claims", conn)
        for col in ['customer_dolc', 'insurance_state_dolc', 'snooze_until']:
            df[col] = pd.to_datetime(df[col])
        return df

# --- MAIN APP ---
def main():
    st.set_page_config(page_title="Phoenix Claims Tracker", layout="wide")
    init_db()
    st.title("🌵 Phoenix Neighborhood Claims Tracker")
    
    df = get_all_claims()
    today = pd.Timestamp.now().normalize()

    # --- 1. NOTIFICATION CENTER ---
    st.subheader("🔔 Follow-up Alerts")
    
    overdue = df[
        ((today - df['customer_dolc']).dt.days >= 3) & 
        (df['job_done'] == 0) & 
        ((df['snooze_until'].isna()) | (df['snooze_until'] <= today))
    ]

    if not overdue.empty:
        for _, row in overdue.iterrows():
            last_date = row['customer_dolc'].strftime('%Y-%m-%d') if pd.notnull(row['customer_dolc']) else "Unknown"
            
            with st.container():
                st.error(f"🚨 **NAME:** {row['name']}   |   **NIMBUS#:** {row['bingus_id']}")
                col_info, col_act = st.columns([2, 1])
                col_info.write(f"📞 **Phone:** {row['phone']}  |  📅 **Last Contacted:** {last_date}")
                
                snooze_val = col_act.selectbox("Snooze (Days):", list(range(1, 8)), key=f"s_val_{row['bingus_id']}")
                c1, c2 = col_act.columns(2)
                if c1.button("✅ Log Done", key=f"ok_{row['bingus_id']}"):
                    with sqlite3.connect(DB_NAME) as conn:
                        conn.execute("UPDATE claims SET customer_dolc = ?, snooze_until = NULL WHERE bingus_id = ?", (today.date(), row['bingus_id']))
                    st.rerun()
                if c2.button("💤 Snooze", key=f"sz_{row['bingus_id']}"):
                    until = (today + timedelta(days=snooze_val)).date()
                    with sqlite3.connect(DB_NAME) as conn:
                        conn.execute("UPDATE claims SET snooze_until = ? WHERE bingus_id = ?", (until, row['bingus_id']))
                    st.rerun()
                st.markdown("---")
    else:
        st.success("No pending follow-ups for today!")

    # --- 2. MAP & AUTO-SAVE ZONES ---
    st.markdown("---")
    
    col_title, col_name, col_picker = st.columns([2, 1, 1])
    col_title.subheader("Neighborhood Map & Highlights")
    active_name = col_name.text_input("🏷️ Zone Name:", "No Soliciting")
    active_color = col_picker.selectbox("🖌️ Draw Color:", ["red", "purple", "blue", "black", "orange", "yellow"])
    
    map_df = df.dropna(subset=['latitude', 'longitude']).copy()
    m = folium.Map(location=[33.4484, -112.0740], zoom_start=11)
    
    # Load Zones
    saved_zones_list = []
    with sqlite3.connect(DB_NAME) as conn:
        saved_zones = pd.read_sql("SELECT * FROM restricted_zones", conn)
        for _, zone in saved_zones.iterrows():
            geo_data = json.loads(zone['geo_json'])
            saved_zones_list.append(geo_data) 
            folium.GeoJson(
                geo_data, 
                style_function=lambda x, c=zone['color']: {
                    'fillColor': c, 'color': c, 'weight': 2, 'fillOpacity': 0.4
                },
                tooltip=zone['name']
            ).add_to(m)

    # Load Claim Markers
    for _, row in map_df.iterrows():
        if row['job_done'] and not row['bought']:
            marker_color = 'gray'          # Done, never bought → grey (closed out)
        elif row['bought']:
            marker_color = 'purple'        # Bought (done or not) → purple
        elif row['priority'] == '1-High':
            marker_color = 'red'
        elif row['priority'] == '2-Medium':
            marker_color = 'blue'
        else:
            marker_color = 'green'
        
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=8, color=marker_color, fill=True, fill_opacity=0.8,
            tooltip=f"{row['name']} (Nimbus #{row['bingus_id']})"
        ).add_to(m)

    # Drawing Tools
    Draw(
        draw_options={'polyline': False, 'circle': False, 'marker': False, 'circlemarker': False},
        edit_options={'edit': False}
    ).add_to(m)

    # Render Map
    map_output = st_folium(m, width=1400, height=550)

    # Map Legend
    st.markdown("""
        **📍 Dot Legend:** &nbsp;&nbsp; 
        🟣 **Bought (Active or Done)** &nbsp; | &nbsp; 
        🔴 **High Priority** &nbsp; | &nbsp; 
        🔵 **Medium Priority** &nbsp; | &nbsp; 
        🟢 **Low Priority** &nbsp; | &nbsp; 
        ⚫ **Job Done (Not Bought)**
    """)

    # === AUTO SAVE LOGIC ===
    if map_output and map_output.get("last_active_drawing"):
        drawn_shape = map_output["last_active_drawing"]
        geom_str = json.dumps(drawn_shape["geometry"], sort_keys=True)
        
        is_new = True
        for z in saved_zones_list:
            if json.dumps(z.get("geometry"), sort_keys=True) == geom_str:
                is_new = False
                break
                
        if is_new:
            save_zone(drawn_shape, active_color, active_name)
            st.rerun()

    # Silent Delete Expander
    with st.expander("🗑️ Manage Drawn Zones"):
        with sqlite3.connect(DB_NAME) as conn:
            z_df = pd.read_sql("SELECT id, name, color FROM restricted_zones", conn)
            for _, z in z_df.iterrows():
                if st.button(f"Delete '{z['name']}' ({z['color'].title()}) - ID:{z['id']}", key=f"del_z_{z['id']}"):
                    delete_zone(z['id'])
                    st.rerun()

    # --- 3. SIDEBAR FULL ENTRY ---
    with st.sidebar.form("new_entry", clear_on_submit=True):
        st.header("📝 New Claim")
        n_id = st.number_input("Nimbus#", min_value=1, step=1)
        n_name = st.text_input("Name")
        n_addr = st.text_input("Address (Include City, State)")
        n_phone = st.text_input("Phone")
        n_prio = st.selectbox("Priority", ["1-High", "2-Medium", "3-Low"])
        n_bought = st.toggle("Insurance Bought?")
        n_done = st.toggle("Job Done?")
        n_worth = st.toggle("Worth Effort?")
        n_cond = st.slider("Condition (1-5)", 1, 5, 3)
        n_dolc = st.date_input("Customer DOLC")
        n_ins = st.date_input("Insurance DOLC")
        n_desc = st.text_area("Description")
        n_adj = st.text_area("Adjuster Info")
        n_supp = st.text_area("Supplementals")
        
        if st.form_submit_button("Save to Database"):
            save_claim({
                "bingus_id": n_id, "name": n_name, "address": n_addr, "phone": n_phone,
                "priority": n_prio, "customer_dolc": n_dolc, "insurance_state_dolc": n_ins,
                "worth_effort": int(n_worth), "condition": n_cond, "description": n_desc, 
                "company_adjuster": n_adj, "supplementals": n_supp, "bought": int(n_bought), 
                "job_done": int(n_done), "snooze_until": None
            }, mode="add")
            st.rerun()

    # --- 4. THE DATA TABLE ---
    st.markdown("---")
    st.subheader("Claims Database")
    search = st.text_input("🔍 Search Database by Name or Nimbus#", "")

    COLUMN_CONFIG = {
        "job_done": st.column_config.CheckboxColumn("Done"),
        "bought": st.column_config.CheckboxColumn("Bought"),
        "worth_effort": st.column_config.CheckboxColumn("Worth Effort?"),
        "condition": st.column_config.ProgressColumn("Cond", min_value=1, max_value=5)
    }

    view_df = df.copy()
    if search:
        view_df = view_df[view_df['name'].str.contains(search, case=False, na=False) |
                          view_df['bingus_id'].astype(str).str.contains(search)]

    for col in ['customer_dolc', 'insurance_state_dolc', 'snooze_until']:
        view_df[col] = view_df[col].dt.date

    active_df = view_df[view_df['job_done'] == 0].drop(columns=['latitude', 'longitude'])
    done_df   = view_df[view_df['job_done'] == 1].drop(columns=['latitude', 'longitude'])

    # Active jobs — fully sortable by clicking any column header
    st.dataframe(active_df, use_container_width=True, hide_index=True, column_config=COLUMN_CONFIG)

    # Completed jobs — collapsed by default, always pinned below active table
    with st.expander(f"✅ Completed Jobs ({len(done_df)})", expanded=False):
        if not done_df.empty:
            st.dataframe(done_df, use_container_width=True, hide_index=True, column_config=COLUMN_CONFIG)
        else:
            st.caption("No completed jobs yet.")

    # --- 5. EDIT/DELETE SECTION ---
    if not df.empty:
        st.markdown("---")
        with st.expander("🛠️ Manage/Edit Existing Claims"):
            selected_nimbus = st.selectbox("Select Nimbus# to Edit", df['bingus_id'].tolist())
            rec = df[df['bingus_id'] == selected_nimbus].iloc[0]
            
            with st.form("edit_form"):
                e_name = st.text_input("Name", value=rec['name'])
                e_phone = st.text_input("Phone", value=rec['phone'])
                e_addr = st.text_input("Address", value=rec['address'])
                e_prio = st.selectbox("Priority", ["1-High", "2-Medium", "3-Low"], 
                                      index=["1-High", "2-Medium", "3-Low"].index(rec['priority']))
                e_bought = st.toggle("Insurance Bought?", value=bool(rec['bought']))
                e_done = st.toggle("Job Done?", value=bool(rec['job_done']))
                e_worth = st.toggle("Worth Effort?", value=bool(rec['worth_effort']))
                e_cond = st.slider("Condition", 1, 5, int(rec['condition']))
                
                safe_cust_dolc = rec['customer_dolc'].date() if pd.notnull(rec['customer_dolc']) else datetime.now().date()
                safe_ins_dolc = rec['insurance_state_dolc'].date() if pd.notnull(rec['insurance_state_dolc']) else datetime.now().date()
                
                e_dolc = st.date_input("Customer DOLC", value=safe_cust_dolc)
                e_ins = st.date_input("Insurance DOLC", value=safe_ins_dolc)
                e_desc = st.text_area("Description", value=rec['description'] if rec['description'] else "")
                e_adj = st.text_area("Adjuster", value=rec['company_adjuster'] if rec['company_adjuster'] else "")
                e_supp = st.text_area("Supplementals", value=rec['supplementals'] if rec['supplementals'] else "")
                
                c1, c2, _ = st.columns([1, 1, 2])
                if c1.form_submit_button("Update"):
                    lat, lon = get_coords(e_addr) if e_addr != rec['address'] else (rec['latitude'], rec['longitude'])
                    
                    save_claim({
                        "bingus_id": selected_nimbus, "name": e_name, "address": e_addr, "phone": e_phone,
                        "priority": e_prio, "worth_effort": int(e_worth), "condition": e_cond,
                        "customer_dolc": e_dolc, "insurance_state_dolc": e_ins, "description": e_desc,
                        "company_adjuster": e_adj, "supplementals": e_supp, "bought": int(e_bought),
                        "job_done": int(e_done), "snooze_until": rec['snooze_until'],
                        "latitude": lat, "longitude": lon
                    }, mode="edit")
                    st.success("Claim Updated!")
                    st.rerun()
                
                if c2.form_submit_button("🗑️ Delete"):
                    with sqlite3.connect(DB_NAME) as conn:
                        conn.execute("DELETE FROM claims WHERE bingus_id = ?", (selected_nimbus,))
                    st.warning("Claim Deleted!")
                    st.rerun()

if __name__ == "__main__":
    main()
