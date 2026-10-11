import streamlit as st
import folium
from streamlit_folium import st_folium
import sqlite3
from geopy.geocoders import Nominatim
import requests
from datetime import datetime, timedelta
import pandas as pd
import math
import time

st.set_page_config(page_title="OptiHaul AI - Logistics", layout="wide")

# --- DİL SÖZLÜĞÜ (TRANSLATIONS) ---
texts = {
    "TR": {
        "title": "🚛 OptiHaul AI",
        "subtitle": "Kurumsal Lojistik ve Rota Optimizasyon Paneli",
        "login_tab": "🔐 Sisteme Giriş Yap",
        "reg_tab": "📝 Yeni Şirket Kaydı",
        "email": "Kurumsal E-Posta:",
        "pass": "Şifre:",
        "login_btn": "Giriş Yap",
        "err_login": "E-posta veya şifre hatalı!",
        "req_fields": "Lütfen tüm alanları doldurun.",
        "reg_info": "Sistemi kullanmak için firmanızı kaydedin.",
        "company": "Şirket / Firma Adı:",
        "phone": "İletişim Numarası:",
        "reg_btn": "Kayıt Ol",
        "reg_success": "✅ Kayıt başarılı! Giriş yapabilirsiniz.",
        "reg_err": "❌ Bu e-posta adresi sistemde zaten kayıtlı!",
        "sidebar_title": "👨‍💼 Yönetici Paneli",
        "active_comp": "Aktif Şirket:\n**{}**",
        "logout": "🚪 Çıkış Yap",
        "tab1": "🚚 Araç Kayıt Paneli",
        "tab2": "🗺️ Operasyon Merkezi",
        "tab3": "📊 Veritabanı ve Log İzleme",
        "tab4": "⚠️ GİZLİ SİSTEM YÖNETİCİSİ",
        "plate": "Araç Plakası:",
        "tonnage": "Tonaj Kapasitesi (Ton):",
        "height": "Araç Yüksekliği (Metre):",
        "save_btn": "Sisteme Kaydet",
        "start_city": "Kalkış Şehri:",
        "end_city": "Varış Şehri:",
        "calc_btn": "Canlı Verileri Çek ve Analiz Et 🚀",
        "fuel_price": "Mazot Fiyatı (Birim/Litre):",
        "no_vehicle": "Lütfen 'Araç Kayıt' sekmesinden araç ekleyin.",
        "route_ok": "✅ OPERASYON ONAYLANDI",
        "route_err": "🚨 OPERASYON REDDEDİLDİ!"
    },
    "EN": {
        "title": "🚛 OptiHaul AI",
        "subtitle": "Corporate Logistics & Route Optimization Panel",
        "login_tab": "🔐 Login to System",
        "reg_tab": "📝 New Company Registration",
        "email": "Corporate E-Mail:",
        "pass": "Password:",
        "login_btn": "Login",
        "err_login": "Invalid email or password!",
        "req_fields": "Please fill in all fields.",
        "reg_info": "Register your company to use the system.",
        "company": "Company Name:",
        "phone": "Contact Number:",
        "reg_btn": "Register",
        "reg_success": "✅ Registration successful! You can now login.",
        "reg_err": "❌ This email is already registered!",
        "sidebar_title": "👨‍💼 Admin Panel",
        "active_comp": "Active Company:\n**{}**",
        "logout": "🚪 Logout",
        "tab1": "🚚 Vehicle Registration",
        "tab2": "🗺️ Operations Center",
        "tab3": "📊 Database & Logs",
        "tab4": "⚠️ SECRET SYSTEM ADMIN",
        "plate": "License Plate:",
        "tonnage": "Tonnage Capacity (Tons):",
        "height": "Vehicle Height (Meters):",
        "save_btn": "Save to System",
        "start_city": "Departure City:",
        "end_city": "Arrival City:",
        "calc_btn": "Fetch Live Data & Analyze 🚀",
        "fuel_price": "Fuel Price (Unit/Liter):",
        "no_vehicle": "Please add a vehicle from the 'Vehicle Registration' tab.",
        "route_ok": "✅ OPERATION APPROVED",
        "route_err": "🚨 OPERATION DENIED!"
    }
}

# --- 1. GÜVENLİK VE HAFIZA ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "current_user" not in st.session_state: st.session_state.current_user = ""
if "current_email" not in st.session_state: st.session_state.current_email = ""
if "route_map" not in st.session_state: st.session_state.route_map = None
if "route_info" not in st.session_state: st.session_state.route_info = ""
if "lang" not in st.session_state: st.session_state.lang = "TR"

def logout():
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.current_email = ""
    st.session_state.route_map = None
    st.session_state.route_info = ""

def change_lang():
    if st.session_state.lang == "TR": st.session_state.lang = "EN"
    else: st.session_state.lang = "TR"

t = texts[st.session_state.lang]

# --- 2. VERİTABANI İŞLEMLERİ ---
def init_db():
    conn = sqlite3.connect('fleet_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, phone TEXT NOT NULL, company_name TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS vehicles (id INTEGER PRIMARY KEY AUTOINCREMENT, plate_number TEXT UNIQUE NOT NULL, tonnage REAL NOT NULL, height REAL NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS trips (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, plate_number TEXT, start_point TEXT, end_point TEXT, distance_km REAL, cost_euro REAL, status TEXT)''')
    try:
        cursor.execute("INSERT INTO users (email, password, phone, company_name) VALUES (?, ?, ?, ?)", ("mert@admin.com", "Mert1234", "05550000000", "SİSTEM YÖNETİCİSİ (MERT)"))
    except sqlite3.IntegrityError: pass
    conn.commit()
    conn.close()

def register_user(email, password, phone, company):
    try:
        conn = sqlite3.connect('fleet_data.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (email, password, phone, company_name) VALUES (?, ?, ?, ?)", (email, password, phone, company))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError: return False 

def verify_user(email, password):
    conn = sqlite3.connect('fleet_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT company_name FROM users WHERE email=? AND password=?", (email, password))
    user = cursor.fetchone()
    conn.close()
    return user[0] if user else None

def add_vehicle(plate, tonnage, height):
    try:
        conn = sqlite3.connect('fleet_data.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO vehicles (plate_number, tonnage, height) VALUES (?, ?, ?)", (plate, tonnage, height))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError: return False

def get_vehicles_data():
    vehicles = {}
    try:
        conn = sqlite3.connect('fleet_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT plate_number, tonnage, height FROM vehicles")
        for row in cursor.fetchall(): vehicles[row[0]] = {"tonnage": row[1], "height": row[2]}
        conn.close()
    except: pass
    return vehicles

def save_trip(plate, start, end, dist, cost, status):
    conn = sqlite3.connect('fleet_data.db')
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO trips (date, plate_number, start_point, end_point, distance_km, cost_euro, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (now, plate, start, end, dist, cost, status))
    conn.commit()
    conn.close()

def get_trip_logs():
    conn = sqlite3.connect('fleet_data.db')
    df = pd.read_sql_query("SELECT date, plate_number, start_point, end_point, distance_km, cost_euro, status FROM trips ORDER BY date DESC", conn)
    conn.close()
    return df

def get_all_users_for_admin():
    conn = sqlite3.connect('fleet_data.db')
    df = pd.read_sql_query("SELECT company_name, email, phone, password FROM users", conn)
    conn.close()
    return df

# --- 3. HARİTA VE OTOMATİK VERİ ÇEKME MOTORU ---
def get_coordinates(city_name):
    geolocator = Nominatim(user_agent="optihaul_ai_v5")
    try:
        location = geolocator.geocode(city_name)
        if location and hasattr(location, 'latitude') and hasattr(location, 'longitude'):
            return [location.latitude, location.longitude]
    except: pass
    return None

def get_osrm_route(start_coords, end_coords):
    url = f"http://router.project-osrm.org/route/v1/driving/{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}?overview=full&geometries=geojson"
    try:
        response = requests.get(url)
        if response.status_code == 200 and response.json()["code"] == "Ok":
            data = response.json()
            route_coords = [[coord[1], coord[0]] for coord in data["routes"][0]["geometry"]["coordinates"]]
            return route_coords, data["routes"][0]["distance"] / 1000, data["routes"][0]["duration"] / 3600
    except: pass
    return None, 0, 0

def fetch_highway_constraints(start_city, end_city):
    risky_cities = ["artvin", "bayburt", "hakkari", "şırnak", "tunceli", "rize", "kastamonu", "gümüşhane", "bitlis"]
    start_lower = start_city.lower()
    end_lower = end_city.lower()
    is_risky = any(city in start_lower or city in end_lower for city in risky_cities)
    
    if is_risky:
        return {"max_tonnage": 25.0, "max_height": 3.8, "status": "Kısıtlı Bölge / Restricted Area"}
    else:
        return {"max_tonnage": 42.0, "max_height": 4.5, "status": "Standart Otoyol / Standard Highway"}

init_db()

# ==========================================
# ANA UYGULAMA AKIŞI
# ==========================================
col_lang1, col_lang2 = st.columns([9, 1])
with col_lang2:
    st.button("🇹🇷 TR / 🇬🇧 EN", on_click=change_lang)

if not st.session_state.logged_in:
    st.markdown(f"<h1 style='text-align: center; color: #1e3a8a;'>{t['title']}</h1>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='text-align: center; color: gray;'>{t['subtitle']}</h4>", unsafe_allow_html=True)
    st.write("")
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        tab_login, tab_register = st.tabs([t['login_tab'], t['reg_tab']])
        
        with tab_login:
            with st.form("login_form"):
                login_email = st.text_input(t['email'])
                login_password = st.text_input(t['pass'], type="password")
                submit_login = st.form_submit_button(t['login_btn'], use_container_width=True, type="primary")
                if submit_login:
                    if login_email and login_password:
                        company = verify_user(login_email, login_password)
                        if company:
                            st.session_state.logged_in = True
                            st.session_state.current_user = company
                            st.session_state.current_email = login_email 
                            st.rerun()
                        else: st.error(t['err_login'])
                    else: st.warning(t['req_fields'])
                        
        with tab_register:
            with st.form("register_form"):
                st.info(t['reg_info'])
                reg_company = st.text_input(t['company'])
                reg_phone = st.text_input(t['phone'])
                reg_email = st.text_input(t['email'])
                reg_password = st.text_input(t['pass'], type="password")
                submit_register = st.form_submit_button(t['reg_btn'], use_container_width=True)
                
                if submit_register:
                    if reg_company and reg_phone and reg_email and reg_password:
                        if "@" not in reg_email: st.error("Geçersiz e-posta / Invalid email")
                        else:
                            if register_user(reg_email, reg_password, reg_phone, reg_company):
                                st.success(t['reg_success'])
                            else: st.error(t['reg_err'])
                    else: st.warning(t['req_fields'])

else:
    with st.sidebar:
        st.title(t['sidebar_title'])
        st.success(t['active_comp'].format(st.session_state.current_user))
        st.button(t['logout'], on_click=logout, use_container_width=True)
        st.markdown("---")
        st.info("OptiHaul AI v5.0\nMulti-Language & Custom UI")

    st.title(t['title'])
    
    if st.session_state.current_email == "mert@admin.com":
        tab1, tab2, tab3, tab4 = st.tabs([t['tab1'], t['tab2'], t['tab3'], t['tab4']])
    else:
        tab1, tab2, tab3 = st.tabs([t['tab1'], t['tab2'], t['tab3']])

    with tab1:
        st.subheader(t['tab1'])
        with st.form("add_vehicle_form"):
            new_plate = st.text_input(t['plate'])
            col_a, col_b = st.columns(2)
            with col_a: new_tonnage = st.number_input(t['tonnage'], min_value=10.0, max_value=80.0, value=40.0)
            with col_b: new_height = st.number_input(t['height'], min_value=2.0, max_value=6.0, value=4.2)
            submit_vehicle = st.form_submit_button(t['save_btn'], type="primary")
            if submit_vehicle:
                if new_plate:
                    if add_vehicle(new_plate.upper(), new_tonnage, new_height): st.success(f"✅ {new_plate.upper()} eklendi/added!")
                    else: st.error("Plaka mevcut / Plate exists!")
                else: st.warning("Plaka giriniz / Enter plate.")

    with tab2:
        vehicles_dict = get_vehicles_data()
        col_left, col_right = st.columns([1, 2])
        
        with col_left:
            st.subheader(t['tab2'])
            with st.form("trip_form"):
                if not vehicles_dict:
                    st.error(t['no_vehicle'])
                    selected_plate = None
                else:
                    selected_plate = st.selectbox("TIR / Truck:", list(vehicles_dict.keys()))
                    
                start_city = st.text_input(t['start_city'])
                end_city = st.text_input(t['end_city'])
                
                fuel_price = st.number_input(t['fuel_price'], value=1.65, step=0.05)
                calculate_btn = st.form_submit_button(t['calc_btn'], type="primary")

        if calculate_btn and selected_plate:
            if start_city and end_city:
                with st.spinner("📡 API..."):
                    time.sleep(1) 
                    highway_data = fetch_highway_constraints(start_city, end_city)
                    route_max_tonnage = highway_data["max_tonnage"]
                    route_max_height = highway_data["max_height"]
                    route_status = highway_data["status"]
                    
                    st.info(f"📍 **INFO:** {route_status} | Max: **{route_max_tonnage} Ton**.")
                
                v_tonnage = vehicles_dict[selected_plate]["tonnage"]
                v_height = vehicles_dict[selected_plate]["height"]
                
                if v_tonnage > route_max_tonnage or v_height > route_max_height:
                    st.session_state.route_info = "error"
                    st.session_state.route_map = None 
                    save_trip(selected_plate, start_city, end_city, 0, 0, "RED/DENIED")
                    st.error(t['route_err'])
                else:
                    with st.spinner("Harita çiziliyor / Drawing map..."):
                        start_coords, end_coords = get_coordinates(start_city), get_coordinates(end_city)
                        
                        if start_coords and end_coords:
                            route_path, dist, dur_hours = get_osrm_route(start_coords, end_coords)
                            if route_path:
                                required_breaks = math.floor(dur_hours / 4.5) 
                                total_cost = (dist / 100) * (25.0 + (v_tonnage * 0.3)) * fuel_price
                                
                                # HTML KULLANARAK O ŞIK, RENKLİ VE BOŞLUKLU YAPI BURADA!
                                st.session_state.route_info = f"""
                                <div style="background-color: #f8f9fa; padding: 25px; border-radius: 10px; border-left: 6px solid #28a745;">
                                    <h3 style="color: #28a745; margin-top: 0; margin-bottom: 20px;">{t['route_ok']}</h3>
                                    
                                    <span style="color: #0056b3; font-size: 18px;"><b>🗺️ Mesafe / Dist:</b> {dist:.1f} km</span>
                                    <br><br><br>
                                    
                                    <span style="color: #fd7e14; font-size: 18px;"><b>💶 Maliyet / Cost:</b> {total_cost:.2f} €</span>
                                    <br><br><br>
                                    
                                    <span style="color: #6f42c1; font-size: 18px;"><b>⏱️ Zorunlu Mola / Breaks:</b> {required_breaks}</span>
                                </div>
                                """
                                save_trip(selected_plate, start_city, end_city, dist, round(total_cost, 2), "ONAY/APPROVED")
                                
                                m_route = folium.Map(location=[(start_coords[0]+end_coords[0])/2, (start_coords[1]+end_coords[1])/2], zoom_start=5)
                                folium.Marker(start_coords, popup=start_city, icon=folium.Icon(color="green")).add_to(m_route)
                                folium.Marker(end_coords, popup=end_city, icon=folium.Icon(color="red")).add_to(m_route)
                                folium.PolyLine(route_path, color="blue", weight=5).add_to(m_route)
                                
                                st.session_state.route_map = m_route
                            else:
                                st.session_state.route_info = "Rota bulunamadı / Route not found."
                                st.session_state.route_map = None
            else:
                st.warning(t['req_fields'])

        with col_right:
            if st.session_state.route_info and st.session_state.route_info != "error":
                if "ONAY" in st.session_state.route_info or "APPROV" in st.session_state.route_info: 
                    # HTML KODLARININ EKRANA BASILMASINA İZİN VERDİĞİMİZ YER!
                    st.markdown(st.session_state.route_info, unsafe_allow_html=True)
                else: 
                    st.error(st.session_state.route_info)
                    
            if st.session_state.route_map is not None:
                st_folium(st.session_state.route_map, width=700, height=450, key="map_route", returned_objects=[])

    with tab3:
        st.subheader(t['tab3'])
        df_trips = get_trip_logs()
        if not df_trips.empty:
            st.dataframe(df_trips, use_container_width=True, hide_index=True)
            
    if st.session_state.current_email == "mert@admin.com":
        with tab4:
            st.error("⚠️ SECRET ADMIN DATA")
            df_all_users = get_all_users_for_admin()
            st.dataframe(df_all_users, use_container_width=True, hide_index=True)
