"""
VibeStream - Superset otomatik provisioning script'i.

Superset ayağa kalktıktan sonra bu script:
  1. admin/admin ile login olur (Bearer token + CSRF token alır)
  2. VibeStream Postgres veritabanı bağlantısını otomatik oluşturur
  3. Dashboard'da kullanılacak dataset'leri otomatik oluşturur:
     - realtime_mood_metrics
     - realtime_leaderboard
     - realtime_streaming_events
  4. Bu dataset'lere dayalı 12 chart'ı otomatik oluşturur/GÜNCELLER
  5. 3 SEKMELİ (native Superset "Tabs" layout'u) bir dashboard oluşturur,
     chart'ları viz tipine göre akıllı boyutlandırarak ilgili sekmelere
     otomatik yerleştirir ve koyu-tema CSS'i uygular:
       - Mood Overview:            KPI'lar (toplam stream, tamamlama, skip)
                                    + zaman içinde mood trendi + saat/gün ısı haritası
       - Leaderboard & Engagement: en çok çalınan şarkılar (tablo + grafik),
                                    sanatçı bazlı beğenilirlik, saatlik skip oranı
       - System Health:            saatlik dinleme yoğunluğu, nostalji (yıl
                                    dağılımı), saatlik tamamlama oranı

ÖNEMLİ - İDEMPOTENT GÜNCELLEME: Script'i tekrar çalıştırdığında (örn.
`docker compose run --rm superset-init`), chart'lar ve dashboard layout'u
zaten var olsalar bile SİLİNMEZ, üzerlerine GÜNCELLENİR. Yani bu script'te
değişiklik yapıp tekrar çalıştırman, mevcut dashboard'u sıfırlamadan
sonuçları anında görmeni sağlar - `docker compose down -v` YAPMANA GEREK
YOKTUR.

Değişiklik yaptıktan sonra sonucu kontrol etmek için:
    docker compose run --rm superset-init
    (Superset'i tarayıcıda F5 ile yenile)

Not: Chart "params" şeması Superset sürümüne göre küçük farklılıklar
gösterebilir. Bu yüzden her chart kendi try/except'i içinde oluşturulur:
biri başarısız olursa script durmaz, diğerlerine devam eder ve sonunda
özet basar.
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
]

DASHBOARD_SLUG = "vibestream-mood"
DASHBOARD_TITLE = "VibeStream - Mood Dashboard"

# Spotify-koyu tema paleti.
SPOTIFY_GREEN = "#1DB954"
BG_DARK = "#121212"
CARD_DARK = "#181818"

DASHBOARD_CSS = f"""
.dashboard-content {{ background-color: {BG_DARK} !important; }}

.dashboard-component-chart-holder {{
    background-color: {CARD_DARK} !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 14px !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.35) !important;
    padding: 4px !important;
    margin: 6px !important;
    transition: border-color 0.15s ease-in-out;
}}
.dashboard-component-chart-holder:hover {{ border-color: {SPOTIFY_GREEN}44 !important; }}

.grid-row {{ margin-bottom: 8px !important; }}

/* GENEL METİN RENGİ: koyu kart üzerinde varsayılan siyah yazı görünmez
   olduğu için TÜM chart içeriğini önce açık renge zorluyoruz. Daha
   spesifik kurallar (başlık yeşili vb.) aşağıda bunun üzerine yazılır. */
.dashboard-component-chart-holder,
.dashboard-component-chart-holder * {{
    color: #e8e8e8 !important;
}}
/* ECharts/D3 SVG metinleri "color" ile değil "fill" ile boyanır - Big
   Number, çizgi/bar grafik eksen etiketleri bu satır olmadan siyah kalır. */
.dashboard-component-chart-holder svg text {{
    fill: #e8e8e8 !important;
}}
/* Big Number kartındaki büyük rakam: birkaç olası class ismini birden
   hedefliyoruz (Superset sürümüne göre değişebiliyor). */
.dashboard-component-chart-holder .header-line,
.dashboard-component-chart-holder .text-line,
.dashboard-component-chart-holder [class*="BigNumber"],
.dashboard-component-chart-holder [class*="bignumber"] {{
    color: {SPOTIFY_GREEN} !important;
    fill: {SPOTIFY_GREEN} !important;
}}

/* Chart başlıkları */
.header-title, .editable-title input, .chart-header .header-title {{
    color: #FFFFFF !important;
    font-weight: 600 !important;
}}
.header-title {{ font-size: 15px !important; }}

/* Sekme (tab) çubuğu */
.dashboard-component-tabs .ant-tabs-tab {{
    color: #b3b3b3 !important;
    font-weight: 500 !important;
}}
.dashboard-component-tabs .ant-tabs-tab-active {{
    color: {SPOTIFY_GREEN} !important;
}}
.dashboard-component-tabs .ant-tabs-ink-bar {{
    background-color: {SPOTIFY_GREEN} !important;
}}

/* Tablo (Ham Veri) satırları */
.dashboard-component-chart-holder table tr:nth-child(even) {{
    background-color: #1c1c1c !important;
}}
.dashboard-component-chart-holder table th {{
    color: #b3b3b3 !important;
    border-bottom: 1px solid #2a2a2a !important;
}}

/* Grafik eksen çizgileri / gridline'lar çok karanlıkta kaybolmasın */
.dashboard-component-chart-holder svg line,
.dashboard-component-chart-holder svg path.domain {{
    stroke: #444 !important;
}}
"""

# Sekme adı -> o sekmeye konacak chart adlarının sırası.
TABS = {
    "Mood Overview": [
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
        "Saatlik Skip Oranı",
    ],
    "System Health": [
        "Saate Göre Dinleme Yoğunluğu",
        "Çıkış Yılına Göre Dinleme Dağılımı (Nostalji)",
        "Saatlik Ortalama Tamamlama Oranı",
    ],
}

# viz_type -> (genişlik /12, yükseklik). Akıllı yerleşim için.
DIMS = {
    "big_number_total": (4, 42),
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


def create_dataset(session, database_id, table_name):
    existing_id = get_dataset_id(session, table_name)
    if existing_id:
        print(f"Dataset '{table_name}' zaten var (id={existing_id}), atlanıyor.")
        return existing_id

    payload = {"database": database_id, "schema": "public", "table_name": table_name}
    resp = session.post(f"{SUPERSET_URL}/api/v1/dataset/", json=payload)
    if resp.status_code >= 400:
        print(f"Dataset '{table_name}' oluşturulamadı:", resp.status_code, resp.text)
        return None
    ds_id = resp.json()["id"]
    print(f"Dataset '{table_name}' oluşturuldu (id={ds_id}).")
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
    """Chart zaten varsa GÜNCELLER (skip etmez) - böylece script'i tekrar
    çalıştırmak her zaman en güncel tanımı yansıtır."""
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
                print(f"  [UYARI] Chart '{name}' güncellenemedi (id={existing_id}): {resp.status_code} {resp.text[:250]}")
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
    """tabs_with_charts: [(tab_title, [(chart_id, chart_name, viz_type), ...]), ...]
    Her chart'ı viz_type'ına göre farklı genişlik/yükseklikte yerleştirir ve
    bin-packing ile satırlara otomatik diziyor (KPI kutuları yan yana,
    bar grafikler ikili, tablo/line/heatmap tam genişlik)."""
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

        # --- Bin packing: chart'ları 12 kolonluk satırlara diz ---
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
    payload = {"position_json": json.dumps(position_json), "css": DASHBOARD_CSS}
    resp = session.put(f"{SUPERSET_URL}/api/v1/dashboard/{dashboard_id}", json=payload)
    if resp.status_code >= 400:
        print("Dashboard layout/CSS güncellenemedi:", resp.status_code, resp.text[:400])
        return False
    print("Sekmeler, chart yerleşimi ve koyu tema CSS'i dashboard'a uygulandı.")
    return True


def link_chart_to_dashboard(session, chart_id, dashboard_id):
    """Chart'ın 'dashboards' ilişkisini günceller (zaten bağlıysa dokunmaz)."""
    try:
        resp = session.get(f"{SUPERSET_URL}/api/v1/chart/{chart_id}")
        current_dash_ids = [d["id"] for d in resp.json().get("result", {}).get("dashboards", [])]
        if dashboard_id in current_dash_ids:
            return
        session.put(f"{SUPERSET_URL}/api/v1/chart/{chart_id}", json={"dashboards": current_dash_ids + [dashboard_id]})
    except Exception as e:
        print(f"  [UYARI] Chart id={chart_id} dashboard'a bağlanamadı: {e}")


# --- Chart tanımları -------------------------------------------------------

def chart_defs(mood_ds_id, leaderboard_ds_id, events_ds_id):
    defs = {}

    if mood_ds_id:
        defs["Zaman İçinde Ortalama Mood (Valence & Energy)"] = (
            "echarts_timeseries_line", mood_ds_id, {
                "x_axis": "window_start_time", "x_axis_sort_asc": True,
                "x_axis_time_format": "smart_date", "time_grain_sqla": "PT1H",
                "metrics": [sql_metric("AVG(avg_valence)", "Avg Valence"), sql_metric("AVG(avg_energy)", "Avg Energy")],
                "groupby": [], "adhoc_filters": [], "row_limit": 1000,
                "truncate_metric": True, "show_legend": True, "rich_tooltip": True,
                "y_axis_format": "SMART_NUMBER", "time_range": "No filter",
            },
        )
        defs["Toplam Stream Sayısı"] = (
            "big_number_total", mood_ds_id, {
                "metric": sql_metric("SUM(total_streams)", "Total Streams"),
                "adhoc_filters": [], "header_font_size": 0.4, "subheader_font_size": 0.15,
                "y_axis_format": "SMART_NUMBER", "time_range": "No filter",
            },
        )

    if leaderboard_ds_id:
        defs["En Çok Çalınan Şarkılar"] = (
            "table", leaderboard_ds_id, {
                "query_mode": "aggregate", "groupby": ["track_name", "artist_name"],
                "metrics": [sql_metric("SUM(play_count)", "Play Count")],
                "adhoc_filters": [], "row_limit": 15,
                "column_config": {"Play Count": {"showCellBars": True, "d3NumberFormat": ",d"}},
                "table_timestamp_format": "smart_date", "time_range": "No filter",
            },
        )
        defs["En Çok Çalınan Şarkılar (Grafik)"] = (
            "echarts_timeseries_bar", leaderboard_ds_id, {
                "x_axis": "track_name", "metrics": [sql_metric("SUM(play_count)", "Play Count")],
                "groupby": [], "row_limit": 10, "order_desc": True,
                "series_limit": 10, "series_limit_metric": sql_metric("SUM(play_count)", "Play Count"),
                "adhoc_filters": [], "show_legend": False, "color_scheme": "supersetColors",
                "time_range": "No filter",
            },
        )

    if events_ds_id:
        defs["Ortalama Tamamlama Oranı"] = (
            "big_number_total", events_ds_id, {
                "metric": sql_metric("AVG(completion_rate)", "Ort. Tamamlama"),
                "adhoc_filters": [], "header_font_size": 0.4, "subheader_font_size": 0.15,
                "y_axis_format": ".0%", "time_range": "No filter",
            },
        )
        defs["Skip Oranı"] = (
            "big_number_total", events_ds_id, {
                "metric": sql_metric(
                    "SUM(CASE WHEN is_skip THEN 1 ELSE 0 END)::float / GREATEST(COUNT(*),1)", "Skip Oranı"
                ),
                "adhoc_filters": [], "header_font_size": 0.4, "subheader_font_size": 0.15,
                "y_axis_format": ".0%", "time_range": "No filter",
            },
        )
        defs["Dinleme Yoğunluğu Isı Haritası (Saat x Gün)"] = (
            "heatmap_v2", events_ds_id, {
                "x_axis": "hour_of_day", "groupby": "day_of_week",
                "metric": sql_metric("COUNT(*)", "Dinleme Sayısı"),
                "linear_color_scheme": "blue_white_yellow", "y_axis_format": "SMART_NUMBER",
                "adhoc_filters": [], "time_range": "No filter",
            },
        )
        defs["Saate Göre Dinleme Yoğunluğu"] = (
            "echarts_timeseries_bar", events_ds_id, {
                "x_axis": "hour_of_day", "metrics": [sql_metric("COUNT(*)", "Stream Count")],
                "groupby": [], "row_limit": 24, "adhoc_filters": [],
                "show_legend": False, "color_scheme": "supersetColors",
                "y_axis_format": "SMART_NUMBER", "time_range": "No filter",
            },
        )
        defs["Saatlik Skip Oranı"] = (
            "echarts_timeseries_bar", events_ds_id, {
                "x_axis": "hour_of_day",
                "metrics": [sql_metric("SUM(CASE WHEN is_skip THEN 1 ELSE 0 END)::float / GREATEST(COUNT(*),1)", "Skip Oranı")],
                "groupby": [], "row_limit": 24, "adhoc_filters": [],
                "show_legend": False, "color_scheme": "supersetColors", "time_range": "No filter",
            },
        )
        defs["Saatlik Ortalama Tamamlama Oranı"] = (
            "echarts_timeseries_bar", events_ds_id, {
                "x_axis": "hour_of_day",
                "metrics": [sql_metric("AVG(completion_rate)", "Ort. Tamamlama")],
                "groupby": [], "row_limit": 24, "adhoc_filters": [],
                "show_legend": False, "color_scheme": "supersetColors", "time_range": "No filter",
            },
        )
        defs["Çıkış Yılına Göre Dinleme Dağılımı (Nostalji)"] = (
            "echarts_timeseries_bar", events_ds_id, {
                "x_axis": "year", "metrics": [sql_metric("COUNT(*)", "Dinleme Sayısı")],
                "groupby": [], "row_limit": 80,
                "adhoc_filters": [{"clause": "WHERE", "subject": "year", "operator": ">", "comparator": "1950", "expressionType": "SIMPLE"}],
                "show_legend": False, "color_scheme": "supersetColors", "time_range": "No filter",
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
                "adhoc_filters": [], "show_legend": False, "color_scheme": "supersetColors", "time_range": "No filter",
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
    print("  (sonra tarayıcıda dashboard sayfasını F5 ile yenile)")


if __name__ == "__main__":
    main()