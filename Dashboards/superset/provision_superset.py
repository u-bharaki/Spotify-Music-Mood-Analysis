"""
VibeStream - Superset otomatik provisioning script'i.

Superset ayağa kalktıktan sonra bu script:
  1. admin/admin ile login olur (Bearer token + CSRF token alır)
  2. VibeStream Postgres veritabanı bağlantısını otomatik oluşturur
  3. Dashboard'da kullanılacak 3 dataset'i otomatik oluşturur:
     - realtime_mood_metrics
     - realtime_leaderboard
     - realtime_streaming_events

Chart ve Dashboard oluşturma kasıtlı olarak buraya eklenmedi: Superset'in
chart "params" şeması (viz_type'a göre) sürümden sürüme değişebiliyor ve
API'den yanlış oluşturulmuş bir chart, UI'da sessizce bozuk görünebiliyor.
Bu yüzden veritabanı + dataset hazır geldikten sonra chart/dashboard'u
Superset UI'dan (Charts -> + Chart, birkaç dakika sürer) oluşturmanız
daha güvenilir. Adımlar DEGISIKLIKLER_ve_KURULUM.md dosyasında yazılı.
"""

import time
import sys
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
    resp = session.get(f"{SUPERSET_URL}/api/v1/database/", params={"q": f"(filters:!((col:database_name,opr:eq,value:'{DB_NAME}')))"})
    resp.raise_for_status()
    result = resp.json().get("result", [])
    return result[0]["id"] if result else None


def create_database(session):
    existing_id = get_existing_database_id(session)
    if existing_id:
        print(f"'{DB_NAME}' veritabanı bağlantısı zaten var (id={existing_id}), atlanıyor.")
        return existing_id

    payload = {
        "database_name": DB_NAME,
        "sqlalchemy_uri": SQLALCHEMY_URI,
        "expose_in_sqllab": True,
    }
    resp = session.post(f"{SUPERSET_URL}/api/v1/database/", json=payload)
    if resp.status_code >= 400:
        print("Veritabanı oluşturulamadı:", resp.status_code, resp.text)
        sys.exit(1)
    db_id = resp.json()["id"]
    print(f"'{DB_NAME}' veritabanı bağlantısı oluşturuldu (id={db_id}).")
    return db_id


def dataset_exists(session, table_name):
    resp = session.get(
        f"{SUPERSET_URL}/api/v1/dataset/",
        params={"q": f"(filters:!((col:table_name,opr:eq,value:{table_name})))"},
    )
    resp.raise_for_status()
    return len(resp.json().get("result", [])) > 0


def create_dataset(session, database_id, table_name):
    if dataset_exists(session, table_name):
        print(f"Dataset '{table_name}' zaten var, atlanıyor.")
        return

    payload = {"database": database_id, "schema": "public", "table_name": table_name}
    resp = session.post(f"{SUPERSET_URL}/api/v1/dataset/", json=payload)
    if resp.status_code >= 400:
        print(f"Dataset '{table_name}' oluşturulamadı:", resp.status_code, resp.text)
        return
    print(f"Dataset '{table_name}' oluşturuldu.")


def main():
    wait_for_superset()
    session = login()
    db_id = create_database(session)
    for table_name in DATASETS:
        create_dataset(session, db_id, table_name)

    print("\n=== HAZIR ===")
    print(f"Superset: {SUPERSET_URL} (admin / admin)")
    print("Veritabanı ve dataset'ler otomatik oluşturuldu.")
    print("Şimdi Charts -> + Chart bölümünden grafikleri oluşturabilirsiniz")
    print("(bkz. DEGISIKLIKLER_ve_KURULUM.md, Bölüm 5).")


if __name__ == "__main__":
    main()
