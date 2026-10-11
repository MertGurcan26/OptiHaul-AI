import sqlite3

def setup_complex_database():
    conn = sqlite3.connect('fleet_data.db')
    cursor = conn.cursor()

    # 1. ARAÇLAR TABLOSU
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT UNIQUE NOT NULL,
            tonnage REAL NOT NULL,
            height REAL NOT NULL
        )
    ''')

    # 2. ŞEHİRLER / DÜĞÜMLER TABLOSU (Harita noktaları ve dinlenme tesisi var mı?)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_name TEXT UNIQUE NOT NULL,
            lat REAL NOT NULL,  -- Harita çizimi için Enlem
            lon REAL NOT NULL,  -- Harita çizimi için Boylam
            has_rest_stop BOOLEAN NOT NULL
        )
    ''')

    # 3. ROTALAR / KENARLAR TABLOSU (Trafik, ağırlık, yükseklik kısıtlamaları)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_location_id INTEGER,
            end_location_id INTEGER,
            distance_km REAL NOT NULL,
            max_tonnage REAL NOT NULL,
            max_height REAL NOT NULL,
            traffic_multiplier REAL DEFAULT 1.0, -- 1.0 normal, 2.0 ağır trafik (süreyi 2'ye katlar)
            FOREIGN KEY(start_location_id) REFERENCES locations(id),
            FOREIGN KEY(end_location_id) REFERENCES locations(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("[SİSTEM] Gelişmiş Lojistik Veritabanı Mimarisi Başarıyla Kuruldu!")

if __name__ == "__main__":
    setup_complex_database()