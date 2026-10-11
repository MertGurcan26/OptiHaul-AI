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

st.set_page_config(page_title="OptiHaul AI - Kurumsal Lojistik", layout="wide")

# --- 1. GÜVENLİK VE HAFIZA ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "current_user" not in st.session_state: st.session_state.current_user = ""
if "current_email" not in st.session_state: st.session_state.current_email = "" # YENİ: Hangi maille girildiğini tutuyoruz
if "route_map" not in st.session_state: st.session_state.route_map = None
if "route_info" not in st.session_state: st.session_state.route_info = ""

def logout():
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.current_email = ""
    st.session_state.route_map = None
    st.session_state.route_info = ""

# --- 2. VERİTABANI İŞLEMLERİ ---
def init_db():
    conn = sqlite3.connect('fleet_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, phone TEXT NOT NULL, company_name TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS vehicles (id INTEGER PRIMARY KEY AUTOINCREMENT, plate_number TEXT UNIQUE NOT NULL, tonnage REAL NOT NULL, height REAL NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS trips (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, plate_number TEXT, start_point TEXT, end_point TEXT, distance_km REAL, cost_euro REAL, status TEXT)''')
    
    # YENİ: Süper Admin Hesabını Otomatik Oluştur (Eğer yoksa)
    try:
        cursor.execute("INSERT INTO users (email, password, phone, company_name) VALUES (?, ?, ?, ?)", ("mert@admin.com", "Mert1234", "05550000000", "SİSTEM YÖNETİCİSİ (MERT)"))
    except sqlite3.IntegrityError:
        pass # Zaten varsa hata verme, geç
        
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
    df = pd.read_sql_query("SELECT date as Tarih, plate_number as Plaka, start_point as Kalkış, end_point as Varış, distance_km as 'Mesafe (km)', cost_euro as 'Maliyet (€)', status as Durum FROM trips ORDER BY date DESC", conn)
    conn.close()
    return df

# SADECE ADMİNİN GÖRECEĞİ FULL LİSTE (Şifreler Dahil)
def get_all_users_for_admin():
    conn = sqlite3.connect('fleet_data.db')
    df = pd.read_sql_query("SELECT company_name as Şirket, email as 'E-Posta', phone as Telefon, password as 'Gizli Şifre' FROM users", conn)
    conn.close()
    return df

# --- 3. HARİTA VE OTOMATİK VERİ ÇEKME MOTORU ---
def get_coordinates(city_name):
    geolocator = Nominatim(user_agent="optihaul_ai_v4")
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
        return {"max_tonnage": 25.0, "max_height": 3.8, "status": "Kısıtlı Bölge (Dar Yollar / Düşük Kapasiteli Köprüler)"}
    else:
        return {"max_tonnage": 42.0, "max_height": 4.5, "status": "Standart Otoyol"}

init_db()

# ==========================================
# ANA UYGULAMA AKIŞI
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center; color: #1e3a8a;'>🚛 OptiHaul AI</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: gray;'>Kurumsal Lojistik ve Rota Optimizasyon Paneli</h4>", unsafe_allow_html=True)
    st.write("")
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        tab_login, tab_register = st.tabs(["🔐 Sisteme Giriş Yap", "📝 Yeni Şirket Kaydı"])
        
        with tab_login:
            with st.form("login_form"):
                login_email = st.text_input("Kurumsal E-Posta:")
                login_password = st.text_input("Şifre:", type="password")
                submit_login = st.form_submit_button("Giriş Yap", use_container_width=True, type="primary")
                if submit_login:
                    if login_email and login_password:
                        company = verify_user(login_email, login_password)
                        if company:
                            st.session_state.logged_in = True
                            st.session_state.current_user = company
                            st.session_state.current_email = login_email # Sisteme giren maili hafızaya al
                            st.rerun()
                        else: st.error("E-posta veya şifre hatalı!")
                    else: st.warning("Lütfen tüm alanları doldurun.")
                        
        with tab_register:
            with st.form("register_form"):
                st.info("Sistemi kullanmak için firmanızı kaydedin.")
                reg_company = st.text_input("Şirket / Firma Adı:")
                reg_phone = st.text_input("İletişim Numarası (Örn: 05551234567):")
                reg_email = st.text_input("E-Posta Adresi:")
                reg_password = st.text_input("Hesap Şifresi:", type="password")
                submit_register = st.form_submit_button("Kayıt Ol", use_container_width=True)
                
                if submit_register:
                    if reg_company and reg_phone and reg_email and reg_password:
                        if "@" not in reg_email: st.error("Lütfen geçerli bir e-posta adresi girin.")
                        elif not reg_phone.startswith("0"): st.error("Telefon numarası '0' ile başlamalıdır.")
                        elif len(reg_phone) != 11: st.error("Telefon numarası 11 hane olmalıdır.")
                        elif not reg_phone.isdigit(): st.error("Telefon numarası sadece rakamlardan oluşmalıdır.")
                        else:
                            if register_user(reg_email, reg_password, reg_phone, reg_company):
                                st.success("✅ Kayıt başarılı! Giriş sekmesinden hesabınıza girebilirsiniz.")
                            else: st.error("❌ Bu e-posta adresi sistemde zaten kayıtlı!")
                    else: st.warning("Lütfen tüm alanları doldurun.")

else:
    with st.sidebar:
        st.title("👨‍💼 Yönetici Paneli")
        st.success(f"Aktif Şirket:\n**{st.session_state.current_user}**")
        st.button("🚪 Çıkış Yap", on_click=logout, use_container_width=True)
        st.markdown("---")
        st.info("OptiHaul AI v4.0\nYapay Zeka Destekli Rota Motoru")

    st.title("🚛 OptiHaul AI - Karar Destek Merkezi")
    
    # YENİ: EĞER GİREN KİŞİ MERT İSE, 4. BİR SEKME AÇ (GİZLİ ADMİN PANELİ)
    if st.session_state.current_email == "mert@admin.com":
        tab1, tab2, tab3, tab4 = st.tabs(["🚚 Araç Kayıt Paneli", "🗺️ Operasyon ve Sefer Merkezi", "📊 Veritabanı ve Log İzleme", "⚠️ GİZLİ SİSTEM YÖNETİCİSİ PANELİ"])
    else:
        tab1, tab2, tab3 = st.tabs(["🚚 Araç Kayıt Paneli", "🗺️ Operasyon ve Sefer Merkezi", "📊 Veritabanı ve Log İzleme"])

    with tab1:
        st.subheader("Yeni Araç Ekleme Modülü")
        with st.form("add_vehicle_form"):
            new_plate = st.text_input("Araç Plakası (Örn: 34 LJS 99):")
            col_a, col_b = st.columns(2)
            with col_a: new_tonnage = st.number_input("Tonaj Kapasitesi (Ton):", min_value=10.0, max_value=80.0, value=40.0)
            with col_b: new_height = st.number_input("Araç Yüksekliği (Metre):", min_value=2.0, max_value=6.0, value=4.2)
            submit_vehicle = st.form_submit_button("Sisteme Kaydet", type="primary")
            if submit_vehicle:
                if new_plate:
                    if add_vehicle(new_plate.upper(), new_tonnage, new_height): st.success(f"✅ {new_plate.upper()} eklendi!")
                    else: st.error("Bu plaka sistemde mevcut!")
                else: st.warning("Plaka giriniz.")

    with tab2:
        vehicles_dict = get_vehicles_data()
        col_left, col_right = st.columns([1, 2])
        
        with col_left:
            st.subheader("Operasyon Kurulumu")
            with st.form("trip_form"):
                if not vehicles_dict:
                    st.error("Lütfen 'Araç Kayıt' sekmesinden tır ekleyin.")
                    selected_plate = None
                else:
                    selected_plate = st.selectbox("Aracı Seçin:", list(vehicles_dict.keys()))
                    
                start_city = st.text_input("Kalkış Şehri (Örn: Edirne):")
                end_city = st.text_input("Varış Şehri (Örn: Kars):")
                
                st.write("⏱️ **Zaman Planlaması**")
                col_date, col_time = st.columns(2)
                with col_date: departure_date = st.date_input("Kalkış Tarihi:", datetime.today())
                with col_time: departure_time = st.time_input("Kalkış Saati:", datetime.now().time())
                traffic_condition = st.selectbox("Güzergah Şartları:", ["Normal", "Kötü Hava / Kısmi Yoğunluk", "Ağır Trafik / Kar"])
                
                fuel_price = st.number_input("Mazot Fiyatı (€/Litre):", value=1.65, step=0.05)
                calculate_btn = st.form_submit_button("Canlı Verileri Çek ve Analiz Et 🚀", type="primary")

        if calculate_btn and selected_plate:
            if start_city and end_city:
                with st.spinner("📡 Karayolları API'sinden yol kısıtlamaları otomatik çekiliyor..."):
                    time.sleep(1) 
                    highway_data = fetch_highway_constraints(start_city, end_city)
                    route_max_tonnage = highway_data["max_tonnage"]
                    route_max_height = highway_data["max_height"]
                    route_status = highway_data["status"]
                    
                    st.info(f"📍 **Karayolları İstihbaratı:** Güzergah durumu **'{route_status}'** olarak belirlendi. Maksimum izin verilen ağırlık: **{route_max_tonnage} Ton**.")
                
                v_tonnage = vehicles_dict[selected_plate]["tonnage"]
                v_height = vehicles_dict[selected_plate]["height"]
                
                is_tonnage_ok = v_tonnage <= route_max_tonnage
                is_height_ok = v_height <= route_max_height
                
                if not is_tonnage_ok or not is_height_ok:
                    st.session_state.route_info = "error"
                    st.session_state.route_map = None 
                    save_trip(selected_plate, start_city, end_city, 0, 0, "REDDEDİLDİ (Karayolları İhlali)")
                    st.error("🚨 OPERASYON REDDEDİLDİ!")
                    if not is_tonnage_ok: st.warning(f"AŞIRI YÜK: Tırınız {v_tonnage} ton. Karayolları uyarısı: Bu güzergahtaki dar yollar/köprüler en fazla {route_max_tonnage} ton kaldırabilir.")
                    if not is_height_ok: st.warning(f"YÜKSEKLİK AŞIMI: Tırınız {v_height}m. Karayolları uyarısı: Bu güzergahtaki tüneller en fazla {route_max_height}m yüksekliğe izin veriyor.")
                else:
                    with st.spinner("Uydudan yol verileri çekiliyor ve Mola Noktaları hesaplanıyor..."):
                        start_coords, end_coords = get_coordinates(start_city), get_coordinates(end_city)
                        
                        if start_coords and end_coords:
                            route_path, dist, dur_hours = get_osrm_route(start_coords, end_coords)
                            if route_path:
                                if traffic_condition == "Kötü Hava / Kısmi Yoğunluk": dur_hours *= 1.20
                                elif traffic_condition == "Ağır Trafik / Kar": dur_hours *= 1.40
                                
                                required_breaks = math.floor(dur_hours / 4.5) 
                                total_break_time = required_breaks * 0.75
                                final_duration = dur_hours + total_break_time
                                
                                dep_datetime = datetime.combine(departure_date, departure_time)
                                arrival_datetime = dep_datetime + timedelta(hours=final_duration)
                                
                                fuel_per_100km = 25.0 + (v_tonnage * 0.3)
                                total_fuel = (dist / 100) * fuel_per_100km
                                total_cost = total_fuel * fuel_price
                                
                                st.session_state.route_info = f"""✅ **OPERASYON ONAYLANDI**
                                * **Toplam Mesafe:** {dist:.1f} km
                                * **Net Sürüş Süresi:** {dur_hours:.1f} saat
                                * **Zorunlu Molalar:** {required_breaks} kez (Haritada Kahve İkonu İle İşaretlendi)
                                * **Tahmini Varış (ETA):** {arrival_datetime.strftime('%d.%m.%Y - %H:%M')}
                                * **Yakıt Maliyeti:** {total_cost:.2f} €"""
                                
                                save_trip(selected_plate, start_city
