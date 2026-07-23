import os
import json
import redis
import subprocess
import sys

# Yolları klasör yapına göre dinamik ayarlıyoruz
CURRENT_DIR = os.path.dirname(__file__)
JSON_PATH = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'Datasets', 'redis_seed_data.json'))
ONE_OFF_SCRIPT_PATH = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'One-off Scripts', 'DatasetFixer.py'))


def seed_redis():
    # 1. Eğer JSON yoksa, senin yazdığın veri hazırlık scriptini çalıştır
    if not os.path.exists(JSON_PATH):
        print(f"İşlenmiş JSON bulunamadı. Kendi ETL scriptimiz çalıştırılıyor: {ONE_OFF_SCRIPT_PATH}")
        # Python ile senin "One-off" scriptini tetikliyoruz
        subprocess.run([sys.executable, ONE_OFF_SCRIPT_PATH], check=True)
        print("ETL Scripti işini bitirdi. Redis'e aktarım başlıyor...")

    # 2. Hazır JSON'ı oku
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data_to_seed = json.load(f)

    # 3. Redis'e bağlan ve pipeline ile bas
    r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
    pipe = r.pipeline()

    for key, value in data_to_seed.items():
        pipe.set(key, json.dumps(value))

    pipe.execute()
    print(f"Mükemmel! {len(data_to_seed)} adet zenginleştirilmiş veri Redis'e basıldı.")


if __name__ == "__main__":
    seed_redis()