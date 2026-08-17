"""
VibeStream - Superset otomatik provisioning script'i.

Modernize Edilmiş Versiyon (Spotify Teması: Header ve Sekme Hataları Giderildi)
"""

import json
import sys
import time

import requests

SUPERSET_URL = "http://superset:8088"
USERNAME = "admin"
PASSWORD = "admin"

DB_NAME = "VibeStream-Postgres"
SQLALCHEMY_URI = "postgresql+psycopg2://vibe_admin:vibe_password@postgres:5432/vibestream_db"

DATASETS = [
    "realtime_mood_metrics",
    "realtime_leaderboard",
    "realtime_streaming_events",
    "system_metrics",
    "partition_core_metrics",
]

DASHBOARD_SLUG = "vibestream-mood"
DASHBOARD_TITLE = "VibeStream - Mood Dashboard"

# Spotify Renk Paleti
SPOTIFY_GREEN = "#1DB954"
SPOTIFY_LIGHT_GREEN = "#1ED760"
SPOTIFY_DARK_BG = "#121212"
SPOTIFY_CARD_BG = "#181818"
GRADIENT_ACCENT = "linear-gradient(135deg, #1ED760 0%, #1DB954 100%)"

DASHBOARD_CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');

/* 1. TÜM BEYAZ ARKA PLANLARI SIFIRLA (Header, Tabs ve Grid'i şeffaflaştırıyoruz) */
body, 
#app,
.dashboard,
.dashboard-page,
.dashboard-content,
.dashboard-grid,
div[data-test="grid-content"],
.grid-container,
.grid-row,
.grid-column,
div[data-test="dashboard-component-tabs"],
.ant-tabs,
.ant-tabs-content,
.ant-tabs-nav-wrap,
.ant-tabs-nav-list,
.background--white,
.background--transparent,
.dashboard-header,
.header-with-actions,
.dashboard-v2 {{
    background-color: transparent !important;
    background: none !important;
    border: none !important;
    box-shadow: none !important;
}}

/* 2. ANA ARKA PLANI SADECE EN ALT KATMANA UYGULA */
body {{
    background-color: {SPOTIFY_DARK_BG} !important;
    background-image: radial-gradient(circle at top left, #1f402b 0%, {SPOTIFY_DARK_BG} 60%, #000000 100%) !important;
    background-attachment: fixed !important;
    background-size: cover !important;
}}

/* Üst Header Başlığı (VibeStream - Mood Dashboard) */
.editable-title input[type="button"], 
.dashboard-header .editable-title input {{
    color: #ffffff !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 800 !important;
    letter-spacing: 0.5px;
}}
/* Header sağdaki ikon ve yazılar (Published, Admin vb.) */
.dashboard-header .ant-tag, 
.dashboard-header span,
.dashboard-header button,
.dashboard-header .anticon {{
    color: #b3b3b3 !important;
}}

/* Superset'in en üstteki varsayılan Navbar'ını karanlık yap */
.navbar, .top-navbar, header {{
    background-color: #000000 !important;
    border-bottom: 1px solid #1f402b !important;
}}
.navbar * {{ color: #b3b3b3 !important; }}

/* 3. CAM EFEKTLİ KARTLAR */
.dashboard-component-chart-holder {{
    position: relative;
    background: rgba(18, 18, 18, 0.75) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 12px !important;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6) !important;
    padding: 12px !important;
    margin: 8px !important;
    overflow: hidden;
    transition: all 0.3s ease !important;
}}

.dashboard-component-chart-holder:hover {{
    border-color: rgba(29, 185, 84, 0.4) !important;
    box-shadow: 0 8px 32px rgba(29, 185, 84, 0.15) !important;
}}

/* KPI Rakamları: Spotify Neon Glow */
.dashboard-component-chart-holder .header-line,
.dashboard-component-chart-holder .text-line,
.dashboard-component-chart-holder [class*="BigNumber"],
.dashboard-component-chart-holder [class*="bignumber"] {{
    background: {GRADIENT_ACCENT} !important;
    -webkit-background-clip: text !important;
    background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    text-shadow: 0 0 25px rgba(30, 215, 96, 0.4) !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 800 !important;
    letter-spacing: -1.5px;
}}
.dashboard-component-chart-holder .subheader-line {{
    color: #ffffff !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    opacity: 0.7;
}}

/* 4. TABLO (ZEBRA ÇİZGİLERİ İPTAL) */
.dashboard-component-chart-holder table,
.dashboard-component-chart-holder .table-responsive,
.dashboard-component-chart-holder table tbody tr,
.dashboard-component-chart-holder .table-striped tbody tr:nth-of-type(odd),
.dashboard-component-chart-holder .table-striped tbody tr:nth-of-type(even) {{
    background-color: transparent !important;
    background: transparent !important;
}}
.dashboard-component-chart-holder table tbody tr:nth-child(odd) td {{
    background-color: rgba(255, 255, 255, 0.02) !important;
    color: #e5e7eb !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
}}
.dashboard-component-chart-holder table tbody tr:nth-child(even) td {{
    background-color: rgba(255, 255, 255, 0.06) !important;
    color: #ffffff !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
}}
.dashboard-component-chart-holder table th {{
    background-color: rgba(0, 0, 0, 0.4) !important;
    color: {SPOTIFY_LIGHT_GREEN} !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    border-bottom: 1px solid rgba(29, 185, 84, 0.3) !important;
    padding: 12px 10px !important;
}}
.dashboard-component-chart-holder table tr:hover td {{
    background-color: rgba(29, 185, 84, 0.15) !important;
    color: {SPOTIFY_LIGHT_GREEN} !important; 
}}

/* Eksen Çizgileri */
.dashboard-component-chart-holder svg line,
.dashboard-component-chart-holder svg path.domain {{
    stroke: rgba(255, 255, 255, 0.03) !important;
}}

/* 5. METİNLER VE SEKME MENÜSÜ DÜZELTMELERİ */
.dashboard-component-chart-holder,
.dashboard-component-chart-holder * {{
    color: #b3b3b3 !important;
}}
.dashboard-component-chart-holder svg text {{
    fill: #b3b3b3 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 11px !important;
}}
.header-title, .editable-title input, .chart-header .header-title {{
    color: #ffffff !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 700 !important;
    font-size: 16px !important;
    letter-spacing: 0.2px;
}}

/* Sekmeler (Tabs) */
.dashboard-component-tabs .ant-tabs-nav {{
    background: transparent !important;
    display: inline-flex !important;
    margin-bottom: 20px !important;
    padding-top: 10px !important; /* Başlıktan biraz ayırır */
}}

/* Pasif Sekmeler (Mat gri, hayalet efekti yok) */
.dashboard-component-tabs .ant-tabs-tab {{
    color: #8b8b8b !important; /* Kesinlikle beyaz değil, mat gri */
    background: rgba(255, 255, 255, 0.05) !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 500 !important;
    border-radius: 32px !important; 
    padding: 8px 24px !important;
    margin: 0 6px !important;
    border: none !important;
    text-shadow: none !important; /* Beyaz bulanıklığı yok et */
    transition: all 0.2s ease !important;
}}

/* Pasif Sekme Hover Durumu */
.dashboard-component-tabs .ant-tabs-tab:hover {{
    background: rgba(255, 255, 255, 0.12) !important;
    color: #ffffff !important; 
}}

/* Aktif Sekme (Neon Yeşil) */
.dashboard-component-tabs .ant-tabs-tab-active {{
    background: {SPOTIFY_LIGHT_GREEN} !important;
    box-shadow: 0 4px 15px rgba(30, 215, 96, 0.3) !important;
}}
.dashboard-component-tabs .ant-tabs-tab-active .ant-tabs-tab-btn {{
    color: #000000 !important; /* Yazısı simsiyah */
    font-weight: 700 !important;
    text-shadow: none !important;
}}
.dashboard-component-tabs .ant-tabs-ink-bar {{ display: none !important; }}
"""

TABS = {
    "Overview & KPI": [
        "Toplam Stream Sayısı",
        "Ortalama Tamamlama Oranı",
        "Skip Oranı",
        "Zaman İçinde Ortalama Mood (Valence & Energy)",
        "Dinleme Yoğunluğu Isı Haritası (Saat x Gün)",
    ],
    "Leaderboard & Engagement": [
        "En Çok Çalınan Şarkılar (Grafik)",
        "En Çok Çalınan Şarkılar",
        "Sanatçı Bazlı Beğenilirlik Skoru",
    ],
    "System Health & Trends": [
        "20 Saniyelik Dinleme Yoğunluğu",
        "Çıkış Yılına Göre Dinleme Dağılımı (Nostalji)",
        "20 Saniyelik Skip Oranı",
        "20 Saniyelik Ortalama Tamamlama Oranı",
    ],
    "Mühendislik Paneli": [
        "Anlık Veri Akış Hızı (Events/sec)",
        "Partition -> CPU Çekirdek Dağılımı",
        "Cluster CPU Kullanımı (Pod Bazlı)",
        "HPA Replica Sayısı (Zaman İçinde)",
    ],
}

DIMS = {
    "big_number_total": (4, 38), 
    "echarts_timeseries_line": (12, 62),
    "heatmap_v2": (12, 62),
    "echarts_timeseries_bar": (6, 56),
    "table": (12, 68),
}
DEFAULT_DIM = (6, 56)


def wait_for_superset():
    print("Superset'in ayağa kalkması bekleniyor...")
    for i in range(60):
        try:
            r = requests.get(f"{SUPERSET_URL}/health", timeout=5)
            if r.status_code == 200:
                print("Superset hazır.")
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(5)
    print("Superset 5 dakika içinde ayağa kalkmadı, script iptal ediliyor.")
    sys.exit(1)


def login():
    session = requests.Session()
    resp = session.post(
        f"{SUPERSET_URL}/api/v1/security/login",
        json={"username": USERNAME, "password": PASSWORD, "provider": "db", "refresh": True},
    )
    resp.raise_for_status()
    access_token = resp.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {access_token}"})

    csrf_resp = session.get(f"{SUPERSET_URL}/api/v1/security/csrf_token/")
    csrf_resp.raise_for_status()
    csrf_token = csrf_resp.json()["result"]
    session.headers.update({"X-CSRFToken": csrf_token, "Referer": SUPERSET_URL})
    return session


def get_existing_database_id(session):
    resp = session.get(
        f"{SUPERSET_URL}/api/v1/database/",
        params={"q": f"(filters:!((col:database_name,opr:eq,value:'{DB_NAME}')))"},
    )
    resp.raise_for_status()
    result = resp.json().get("result", [])
    return result[0]["id"] if result else None


def create_database(session):
    existing_id = get_existing_database_id(session)
    if existing_id:
        print(f"'{DB_NAME}' veritabanı bağlantısı zaten var (id={existing_id}), atlanıyor.")
        return existing_id

    payload = {"database_name": DB_NAME, "sqlalchemy_uri": SQLALCHEMY_URI, "expose_in_sqllab": True}
    resp = session.post(f"{SUPERSET_URL}/api/v1/database/", json=payload)
    if resp.status_code >= 400:
        print("Veritabanı oluşturulamadı:", resp.status_code, resp.text)
        sys.exit(1)
    db_id = resp.json()["id"]
    print(f"'{DB_NAME}' veritabanı bağlantısı oluşturuldu (id={db_id}).")
    return db_id


def get_dataset_id(session, table_name):
    resp = session.get(
        f"{SUPERSET_URL}/api/v1/dataset/",
        params={"q": f"(filters:!((col:table_name,opr:eq,value:{table_name})))"},
    )
    resp.raise_for_status()
    result = resp.json().get("result", [])
    return result[0]["id"] if result else None


def refresh_dataset_columns(session, ds_id):
    # Spark tarafında yeni bir fiziksel kolon eklendiğinde (örn. time_bucket_20s),
    # Superset'in bunu x_axis/metric olarak kullanabilmesi için dataset'in kolon
    # şemasını tablodan yeniden okuması gerekiyor. create_dataset zaten var olan
    # bir dataset'i atladığı için bu adım olmadan yeni kolon hiç görünmez.
    resp = session.put(f"{SUPERSET_URL}/api/v1/dataset/{ds_id}/refresh")
    if resp.status_code >= 400:
        print(f"Dataset id={ds_id} kolon yenileme başarısız:", resp.status_code, resp.text)
    else:
        print(f"Dataset id={ds_id} kolonları tablodan yenilendi.")


def create_dataset(session, database_id, table_name):
    existing_id = get_dataset_id(session, table_name)
    if existing_id:
        print(f"Dataset '{table_name}' zaten var (id={existing_id}), kolonlar yenileniyor.")
        refresh_dataset_columns(session, existing_id)
        return existing_id

    payload = {"database": database_id, "schema": "public", "table_name": table_name}
    resp = session.post(f"{SUPERSET_URL}/api/v1/dataset/", json=payload)
    if resp.status_code >= 400:
        print(f"Dataset '{table_name}' oluşturulamadı:", resp.status_code, resp.text)
        return None
    ds_id = resp.json()["id"]
    print(f"Dataset '{table_name}' oluşturuldu (id={ds_id}).")
    refresh_dataset_columns(session, ds_id)
    return ds_id


def get_chart_id(session, chart_name):
    resp = session.get(
        f"{SUPERSET_URL}/api/v1/chart/",
        params={"q": f"(filters:!((col:slice_name,opr:eq,value:'{chart_name}')))"},
    )
    resp.raise_for_status()
    result = resp.json().get("result", [])
    return result[0]["id"] if result else None


def sql_metric(expr, label):
    return {"expressionType": "SQL", "sqlExpression": expr, "label": label}


def create_chart(session, name, viz_type, datasource_id, params):
    full_params = {"datasource": f"{datasource_id}__table", "viz_type": viz_type, **params}
    payload = {
        "slice_name": name,
        "viz_type": viz_type,
        "datasource_id": datasource_id,
        "datasource_type": "table",
        "params": json.dumps(full_params),
    }

    existing_id = get_chart_id(session, name)
    try:
        if existing_id:
            resp = session.put(f"{SUPERSET_URL}/api/v1/chart/{existing_id}", json=payload)
            if resp.status_code >= 400:
                print(f"  [UYARI] Chart '{name}' güncellenemedi: {resp.status_code} {resp.text[:250]}")
                return existing_id
            print(f"  Chart '{name}' güncellendi (id={existing_id}).")
            return existing_id

        resp = session.post(f"{SUPERSET_URL}/api/v1/chart/", json=payload)
        if resp.status_code >= 400:
            print(f"  [UYARI] Chart '{name}' oluşturulamadı: {resp.status_code} {resp.text[:250]}")
            return None
        chart_id = resp.json()["id"]
        print(f"  Chart '{name}' oluşturuldu (id={chart_id}).")
        return chart_id
    except Exception as e:
        print(f"  [UYARI] Chart '{name}' işlenirken hata: {e}")
        return existing_id


def build_tabbed_position_json(tabs_with_charts):
    root_id = "ROOT_ID"
    grid_id = "GRID_ID"
    tabs_id = "TABS-vibestream"

    position = {
        "DASHBOARD_VERSION_KEY": "v2",
        root_id: {"type": "ROOT", "id": root_id, "children": [grid_id]},
        grid_id: {"type": "GRID", "id": grid_id, "children": [tabs_id], "parents": [root_id]},
        tabs_id: {"type": "TABS", "id": tabs_id, "children": [], "parents": [root_id, grid_id], "meta": {}},
    }

    for i, (title, charts) in enumerate(tabs_with_charts, start=1):
        tab_id = f"TAB-vibestream-{i}"
        position[tabs_id]["children"].append(tab_id)
        position[tab_id] = {
            "type": "TAB", "id": tab_id, "children": [],
            "parents": [root_id, grid_id, tabs_id],
            "meta": {"text": title, "defaultText": title, "placeholder": title},
        }

        rows, current_row, current_width = [], [], 0
        for chart_id, chart_name, viz_type in charts:
            width, height = DIMS.get(viz_type, DEFAULT_DIM)
            if current_row and current_width + width > 12:
                rows.append(current_row)
                current_row, current_width = [], 0
            current_row.append((chart_id, chart_name, width, height))
            current_width += width
        if current_row:
            rows.append(current_row)

        for r_idx, row_charts in enumerate(rows):
            row_id = f"ROW-vibestream-{i}-{r_idx}"
            position[tab_id]["children"].append(row_id)
            chart_node_ids = []
            for chart_id, chart_name, width, height in row_charts:
                chart_node_id = f"CHART-vibestream-{chart_id}"
                chart_node_ids.append(chart_node_id)
                position[chart_node_id] = {
                    "type": "CHART", "id": chart_node_id, "children": [],
                    "parents": [root_id, grid_id, tabs_id, tab_id, row_id],
                    "meta": {"chartId": chart_id, "sliceName": chart_name, "width": width, "height": height},
                }
            position[row_id] = {
                "type": "ROW", "id": row_id, "children": chart_node_ids,
                "parents": [root_id, grid_id, tabs_id, tab_id],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }

    return position


def get_existing_dashboard_id(session, slug):
    resp = session.get(
        f"{SUPERSET_URL}/api/v1/dashboard/",
        params={"q": f"(filters:!((col:slug,opr:eq,value:{slug})))"},
    )
    resp.raise_for_status()
    result = resp.json().get("result", [])
    return result[0]["id"] if result else None


def create_or_get_dashboard(session):
    existing_id = get_existing_dashboard_id(session, DASHBOARD_SLUG)
    if existing_id:
        print(f"Dashboard '{DASHBOARD_SLUG}' zaten var (id={existing_id}).")
        return existing_id

    payload = {"dashboard_title": DASHBOARD_TITLE, "slug": DASHBOARD_SLUG, "published": True}
    resp = session.post(f"{SUPERSET_URL}/api/v1/dashboard/", json=payload)
    if resp.status_code >= 400:
        print("Dashboard oluşturulamadı:", resp.status_code, resp.text)
        sys.exit(1)
    dash_id = resp.json()["id"]
    print(f"Dashboard '{DASHBOARD_SLUG}' oluşturuldu (id={dash_id}).")
    return dash_id


def apply_dashboard_layout(session, dashboard_id, tabs_with_charts):
    position_json = build_tabbed_position_json(tabs_with_charts)
    
    # Superset'in grafik renklerini ezip global olarak Spotify yeşiline zorluyoruz
    # VE OTOMATİK YENİLEME (Auto-Refresh) EKLIYORUZ
    json_metadata = {
        "label_colors": {
            "Play Count": SPOTIFY_GREEN,
            "Stream Count": SPOTIFY_GREEN,
            "Dinleme Sayısı": SPOTIFY_LIGHT_GREEN,
            "Skip Oranı": SPOTIFY_GREEN,
            "Ort. Tamamlama": SPOTIFY_GREEN,
            "Beğenilirlik Skoru": SPOTIFY_GREEN,
            # Not: bu sözlükte olmayan bir metrik etiketi, dashboard'un
            # "color_scheme" (supersetColors) varsayılan paletine düşer ve o
            # palet maviyle başlar - "Olay Sayısı" ve "CPU (millicore)" bu
            # yüzden chart bazında COLOR_MAIN/COLOR_SECONDARY ayarlanmış
            # olsa bile mavi görünüyordu. Dashboard seviyesindeki bu sözlük
            # chart bazlı ayarı ezdiği için her yeni metrik etiketini buraya
            # da eklemek gerekiyor.
            "Olay Sayısı": SPOTIFY_GREEN,
            "CPU (millicore)": SPOTIFY_LIGHT_GREEN,
            "Aktif Pod Sayısı": SPOTIFY_GREEN,
            "Hedef Pod Sayısı": "#ffffff",
            "Kayıt Sayısı": SPOTIFY_LIGHT_GREEN,
        },
        "color_scheme": "supersetColors",
        "refresh_frequency": 5  # <--- EKLENEN SATIR: Dashboard her 5 saniyede bir otomatik güncellenecek
    }

    payload = {
        "position_json": json.dumps(position_json), 
        "css": DASHBOARD_CSS,
        "json_metadata": json.dumps(json_metadata)
    }
    
    resp = session.put(f"{SUPERSET_URL}/api/v1/dashboard/{dashboard_id}", json=payload)
    if resp.status_code >= 400:
        print("Dashboard layout/CSS güncellenemedi:", resp.status_code, resp.text[:400])
        return False
    print("Sekmeler, chart yerleşimi, global renkler, otomatik yenileme ve koyu tema CSS'i dashboard'a uygulandı.")
    return True


def link_chart_to_dashboard(session, chart_id, dashboard_id):
    try:
        resp = session.get(f"{SUPERSET_URL}/api/v1/chart/{chart_id}")
        current_dash_ids = [d["id"] for d in resp.json().get("result", {}).get("dashboards", [])]
        if dashboard_id in current_dash_ids:
            return
        session.put(f"{SUPERSET_URL}/api/v1/chart/{chart_id}", json={"dashboards": current_dash_ids + [dashboard_id]})
    except Exception as e:
        print(f"  [UYARI] Chart id={chart_id} dashboard'a bağlanamadı: {e}")


def chart_defs(mood_ds_id, leaderboard_ds_id, events_ds_id, system_ds_id, partition_ds_id=None):
    defs = {}
    
    COLOR_MAIN = SPOTIFY_GREEN
    COLOR_SECONDARY = SPOTIFY_LIGHT_GREEN
    COLOR_CONTRAST = "#ffffff"  

    if mood_ds_id:
        defs["Zaman İçinde Ortalama Mood (Valence & Energy)"] = (
            "echarts_timeseries_line", mood_ds_id, {
                "x_axis": "window_start_time", "x_axis_sort_asc": True,
                # PT1H (saatlik) gruplama, birkaç dakikalık gerçek zamanlı veriyi
                # tek bir noktaya sıkıştırıp grafiği boş/anlamsız gösteriyordu.
                # PT5S (5 saniyelik) ile diğer canlı grafiklerle tutarlı, akan
                # bir çizgi elde ediyoruz.
                "x_axis_time_format": "%H:%M:%S", "time_grain_sqla": "PT5S",
                "metrics": [sql_metric("AVG(avg_valence)", "Avg Valence"), sql_metric("AVG(avg_energy)", "Avg Energy")],
                "groupby": [], "adhoc_filters": [], "row_limit": 1000,
                "truncate_metric": True, "show_legend": True, "rich_tooltip": True,
                "y_axis_format": "SMART_NUMBER", "time_range": "Last 20 minutes",
                "x_axis_title": "", "y_axis_title": "",
                "label_colors": {"Avg Valence": COLOR_MAIN, "Avg Energy": COLOR_CONTRAST},
                "line_style": "smooth", "show_area_chart": True, "opacity": 0.15, "markerEnabled": False,
            },
        )
        defs["Toplam Stream Sayısı"] = (
            "big_number_total", mood_ds_id, {
                "metric": sql_metric("SUM(total_streams)", "Total Streams"),
                "adhoc_filters": [], "header_font_size": 0.4, "subheader_font_size": 0.15,
                "y_axis_format": "SMART_NUMBER", "time_range": "No filter",
                "subheader": "Son pencerede toplam dinleme",
            },
        )

    if leaderboard_ds_id:
        defs["En Çok Çalınan Şarkılar"] = (
            "table", leaderboard_ds_id, {
                "query_mode": "aggregate", "groupby": ["track_name", "artist_name"],
                "metrics": [sql_metric("SUM(play_count)", "Play Count")],
                "adhoc_filters": [], "row_limit": 15,
                "column_config": {
                    "Play Count": {"showCellBars": True, "d3NumberFormat": ",d", "colorPositiveNegative": False, "alignPositiveNegative": False},
                },
                "table_timestamp_format": "smart_date", "time_range": "No filter",
            },
        )
        defs["En Çok Çalınan Şarkılar (Grafik)"] = (
            "echarts_timeseries_bar", leaderboard_ds_id, {
                "x_axis": "track_name", "metrics": [sql_metric("SUM(play_count)", "Play Count")],
                "groupby": [], "row_limit": 10, "order_desc": True,
                "series_limit": 10, "series_limit_metric": sql_metric("SUM(play_count)", "Play Count"),
                "adhoc_filters": [], "show_legend": False,
                "label_colors": {"Play Count": COLOR_MAIN},
                "x_axis_title": "", "y_axis_title": "",
                "time_range": "No filter",
            },
        )

    if events_ds_id:
        defs["Ortalama Tamamlama Oranı"] = (
            "big_number_total", events_ds_id, {
                "metric": sql_metric("AVG(completion_rate)", "Ort. Tamamlama"),
                "adhoc_filters": [], "header_font_size": 0.4, "subheader_font_size": 0.15,
                "y_axis_format": ".0%", "time_range": "No filter",
                "subheader": "Şarkının ne kadarı dinlendi",
            },
        )
        defs["Skip Oranı"] = (
            "big_number_total", events_ds_id, {
                "metric": sql_metric(
                    "SUM(CASE WHEN is_skip THEN 1 ELSE 0 END)::float / GREATEST(COUNT(*),1)", "Skip Oranı"
                ),
                "adhoc_filters": [], "header_font_size": 0.4, "subheader_font_size": 0.15,
                "y_axis_format": ".0%", "time_range": "No filter",
                "subheader": "Manuel olarak geçilen şarkı oranı",
            },
        )
        defs["Dinleme Yoğunluğu Isı Haritası (Saat x Gün)"] = (
            "heatmap_v2", events_ds_id, {
                "x_axis": "hour_of_day", "groupby": "day_of_week",
                "metric": sql_metric("COUNT(*)", "Dinleme Sayısı"),
                "linear_color_scheme": "greens", "y_axis_format": "SMART_NUMBER", 
                "adhoc_filters": [], "time_range": "No filter",
                "x_axis_title": "", "y_axis_title": "",
            },
        )
        defs["20 Saniyelik Dinleme Yoğunluğu"] = (
            "echarts_timeseries_bar", events_ds_id, {
                # hour_of_day yerine time_bucket_20s: veri artık "hour_of_day"a
                # göre değil, 20 saniyelik gerçek zaman dilimlerine göre
                # gruplanıyor -> "son 20sn, ondan önceki 20sn, ..." şeklinde
                # canlı bir akış görünümü.
                "x_axis": "time_bucket_20s", "metrics": [sql_metric("COUNT(*)", "Stream Count")],
                "groupby": [], "row_limit": 60, "adhoc_filters": [],
                "show_legend": False, "label_colors": {"Stream Count": COLOR_SECONDARY},
                "y_axis_format": "SMART_NUMBER", "time_range": "Last 20 minutes",
                # x_axis_title boş bırakılıyor: saat etiketleriyle (03:19:00 vb.)
                # üst üste biniyordu, ayrıca chart başlığı zaten bunu anlatıyor.
                "x_axis_title": "", "y_axis_title": "",
                "time_grain_sqla": None, "x_axis_time_format": "%H:%M:%S",
            },
        )
        defs["20 Saniyelik Skip Oranı"] = (
            "echarts_timeseries_bar", events_ds_id, {
                "x_axis": "time_bucket_20s",
                "metrics": [sql_metric("SUM(CASE WHEN is_skip THEN 1 ELSE 0 END)::float / GREATEST(COUNT(*),1)", "Skip Oranı")],
                "groupby": [], "row_limit": 60, "adhoc_filters": [],
                "show_legend": False, "label_colors": {"Skip Oranı": COLOR_MAIN},
                "y_axis_format": ".0%", "time_range": "Last 20 minutes",
                "x_axis_title": "", "y_axis_title": "",
                "time_grain_sqla": None, "x_axis_time_format": "%H:%M:%S",
            },
        )
        defs["20 Saniyelik Ortalama Tamamlama Oranı"] = (
            "echarts_timeseries_bar", events_ds_id, {
                "x_axis": "time_bucket_20s",
                "metrics": [sql_metric("AVG(completion_rate)", "Ort. Tamamlama")],
                "groupby": [], "row_limit": 60, "adhoc_filters": [],
                "show_legend": False, "label_colors": {"Ort. Tamamlama": COLOR_MAIN},
                "y_axis_format": ".0%", "time_range": "Last 20 minutes",
                "x_axis_title": "", "y_axis_title": "",
                "time_grain_sqla": None, "x_axis_time_format": "%H:%M:%S",
            },
        )
        defs["Çıkış Yılına Göre Dinleme Dağılımı (Nostalji)"] = (
            "echarts_timeseries_bar", events_ds_id, {
                "x_axis": "year", "metrics": [sql_metric("COUNT(*)", "Dinleme Sayısı")],
                "groupby": [], "row_limit": 80,
                "adhoc_filters": [{"clause": "WHERE", "subject": "year", "operator": ">", "comparator": "1950", "expressionType": "SIMPLE"}],
                "show_legend": False, "label_colors": {"Dinleme Sayısı": COLOR_SECONDARY},
                "x_axis_title": "", "y_axis_title": "",
                "time_range": "No filter",
            },
        )
        defs["Sanatçı Bazlı Beğenilirlik Skoru"] = (
            "echarts_timeseries_bar", events_ds_id, {
                "x_axis": "artist_name",
                "metrics": [sql_metric(
                    "AVG(completion_rate) - (SUM(CASE WHEN is_skip THEN 1 ELSE 0 END)::float / GREATEST(COUNT(*),1))",
                    "Beğenilirlik Skoru",
                )],
                "groupby": [], "row_limit": 10, "order_desc": True,
                "series_limit": 10, "series_limit_metric": sql_metric(
                    "AVG(completion_rate) - (SUM(CASE WHEN is_skip THEN 1 ELSE 0 END)::float / GREATEST(COUNT(*),1))",
                    "Beğenilirlik Skoru",
                ),
                "adhoc_filters": [], "show_legend": False,
                "label_colors": {"Beğenilirlik Skoru": COLOR_MAIN},
                "x_axis_title": "", "y_axis_title": "",
                "time_range": "No filter",
            },
        )

    # --- Mühendislik Paneli --------------------------------------------
    # "Anlık Veri Akış Hızı": Kafka'ya hiç bağlanmadan, doğrudan Postgres'e
    # yazılan olayların zaman damgasından hesaplanır - ek altyapı gerekmez.
    if events_ds_id:
        defs["Anlık Veri Akış Hızı (Events/sec)"] = (
            "echarts_timeseries_bar", events_ds_id, {
                "x_axis": "timestamp", "time_grain_sqla": "PT1M",
                "metrics": [sql_metric("COUNT(*)", "Olay Sayısı")],
                "groupby": [], "row_limit": 500, "adhoc_filters": [],
                "show_legend": False, "label_colors": {"Olay Sayısı": COLOR_MAIN},
                "x_axis_title": "Zaman (dakikalık)", "y_axis_title": "Olay/Dakika",
                "time_range": "Last day",
            },
        )

    # "Partition -> CPU Çekirdek Dağılımı": VibeStreamApp.scala her micro-batch'te
    # hangi Kafka partition'ının hangi JVM thread'inde (local[*] modunda thread =
    # çekirdek) işlendiğini partition_core_metrics tablosuna yazar. Kafka topic'i
    # artık 4 partition ile oluşturuluyor (bkz. docker-compose.yml), böylece
    # local[*] birden fazla çekirdeğe gerçekten iş dağıtabiliyor.
    if partition_ds_id:
        defs["Partition -> CPU Çekirdek Dağılımı"] = (
            "echarts_timeseries_bar", partition_ds_id, {
                # thread_name yerine thread_id kullanıyoruz: thread_name içine
                # Spark her görev için stage/TID bilgisini gömüyor (örn.
                # "...task 0.0 in stage 453.0 (TID 355)"), yani pratikte HER
                # bar için FARKLI bir metin oluyor - bu da eksende yüzlerce
                # dev, üst üste binen etiket demekti. thread_id ise JVM'in
                # thread havuzundaki sabit sayısal kimlik, çok daha az ve
                # okunabilir kategori üretiyor (gerçek "çekirdek" kimliği).
                #
                # groupby=["partition_id"] de kaldırıldı: Superset, groupby
                # varken rengi metrik etiketine göre değil, kategori
                # (partition_id) değerine göre seçiyor - bu yüzden dashboard
                # seviyesindeki "Kayıt Sayısı" rengi hiç eşleşmiyor, varsayılan
                # mavi paletin ilk rengine düşüyordu.
                "x_axis": "thread_id",
                "metrics": [sql_metric("SUM(record_count)", "Kayıt Sayısı")],
                "groupby": [], "row_limit": 32, "adhoc_filters": [],
                "show_legend": False, "label_colors": {"Kayıt Sayısı": COLOR_SECONDARY},
                "x_axis_title": "CPU Thread ID (Çekirdek)", "y_axis_title": "İşlenen Kayıt Sayısı",
                # Son 15 dakikadaki dağılımı göster - eski batch'ler ekranı kalabalıklaştırmasın.
                "time_range": "Last 15 minutes",
            },
        )

    # "Cluster CPU Kullanımı" ve "HPA Replica Sayısı": Kubernetes ekibinin
    # `collect_cluster_metrics.py` script'i ile system_metrics tablosuna
    # yazdığı veriye dayanır. O script çalışmadan bu iki chart boş görünür
    # (bu normal - K8s tarafı henüz bağlanmamış demektir).
    if system_ds_id:
        defs["Cluster CPU Kullanımı (Pod Bazlı)"] = (
            "echarts_timeseries_bar", system_ds_id, {
                "x_axis": "pod_name",
                "metrics": [sql_metric("AVG(cpu_millicores)", "CPU (millicore)")],
                "groupby": [], "row_limit": 20, "adhoc_filters": [],
                "show_legend": False, "label_colors": {"CPU (millicore)": COLOR_SECONDARY},
                "x_axis_title": "Pod", "y_axis_title": "CPU (millicore)",
                # Sadece son 15 dakikadaki ölçümleri göster (canlı anlık görüntü) -
                # Superset'in kendi zaman aralığı filtresi ile, geçersiz SQL fonksiyonu değil.
                "time_range": "Last 15 minutes",
            },
        )
        defs["HPA Replica Sayısı (Zaman İçinde)"] = (
            "echarts_timeseries_line", system_ds_id, {
                "x_axis": "timestamp", "x_axis_sort_asc": True,
                "x_axis_time_format": "smart_date", "time_grain_sqla": "PT1M",
                "metrics": [
                    sql_metric("MAX(hpa_current_replicas)", "Aktif Pod Sayısı"),
                    sql_metric("MAX(hpa_desired_replicas)", "Hedef Pod Sayısı"),
                ],
                "groupby": [], "adhoc_filters": [], "row_limit": 1000,
                "truncate_metric": True, "show_legend": True, "rich_tooltip": True,
                "y_axis_format": "SMART_NUMBER", "time_range": "No filter",
                "x_axis_title": "Zaman", "y_axis_title": "Pod Sayısı",
                "label_colors": {"Aktif Pod Sayısı": COLOR_MAIN, "Hedef Pod Sayısı": COLOR_CONTRAST},
                "line_style": "smooth", "markerEnabled": True,
            },
        )

    return defs


def main():
    wait_for_superset()
    session = login()

    db_id = create_database(session)

    dataset_ids = {}
    for table_name in DATASETS:
        dataset_ids[table_name] = create_dataset(session, db_id, table_name)

    dashboard_id = create_or_get_dashboard(session)

    defs = chart_defs(
        mood_ds_id=dataset_ids.get("realtime_mood_metrics"),
        leaderboard_ds_id=dataset_ids.get("realtime_leaderboard"),
        events_ds_id=dataset_ids.get("realtime_streaming_events"),
        system_ds_id=dataset_ids.get("system_metrics"),
        partition_ds_id=dataset_ids.get("partition_core_metrics"),
    )

    print("\n=== CHART'LAR OLUŞTURULUYOR/GÜNCELLENİYOR ===")
    chart_ids = {}
    ok, fail = 0, 0
    for chart_name, (viz_type, datasource_id, params) in defs.items():
        cid = create_chart(session, chart_name, viz_type, datasource_id, params)
        chart_ids[chart_name] = cid
        if cid:
            link_chart_to_dashboard(session, cid, dashboard_id)
            ok += 1
        else:
            fail += 1

    print("\n=== DASHBOARD LAYOUT UYGULANIYOR ===")
    tabs_with_charts = [
        (
            tab_title,
            [
                (chart_ids[name], name, defs[name][0])
                for name in chart_names
                if chart_ids.get(name) and name in defs
            ],
        )
        for tab_title, chart_names in TABS.items()
    ]
    apply_dashboard_layout(session, dashboard_id, tabs_with_charts)

    print("\n=== ÖZET ===")
    print(f"Chart'lar: {ok} başarılı, {fail} başarısız (toplam {len(defs)}).")
    print(f"\nSuperset: {SUPERSET_URL} (admin / admin)")
    print(f"'{DASHBOARD_TITLE}' -> {SUPERSET_URL}/superset/dashboard/{DASHBOARD_SLUG}/")
    print("\nBir sonraki değişiklikten sonra kontrol etmek için:")
    print("  docker compose run --rm superset-init")


if __name__ == "__main__":
    main()