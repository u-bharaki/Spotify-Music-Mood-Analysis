import os
import time
import json
import argparse
from datetime import datetime, timezone, timedelta
import pandas as pd
from kafka import KafkaProducer
import redis

CURRENT_DIR = os.path.dirname(__file__)
DATASETS_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'Datasets'))

TURKEY_TZ = timezone(timedelta(hours=3))


def now_turkey():
    return datetime.now(TURKEY_TZ)


def start_streaming(senaryo_adi, limit):
    r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

    if not r.exists('system:eps'):
        r.set('system:eps', 5)

    producer = KafkaProducer(
        bootstrap_servers=['kafka:9092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    # Dosya adını senaryoya göre belirle (Örn: mutlu_senaryo -> cleaned_mutlu_senaryo.csv)
    if senaryo_adi == "orijinal":
        csv_filename = "cleaned_streaming_history.csv"
    else:
        csv_filename = f"cleaned_{senaryo_adi}.csv"

    csv_path = os.path.join(DATASETS_DIR, csv_filename)

    # AKILLI KONTROL: Eğer temizlenmiş CSV yoksa, DatasetFixer'ı otomatik tetikle!
    if not os.path.exists(csv_path):
        print(f"[UYARI] '{csv_filename}' bulunamadı! DatasetFixer tetikleniyor...")
        fixer_path = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'One-off Scripts', 'DatasetFixer.py'))
        import subprocess
        import sys
        subprocess.run([sys.executable, fixer_path], check=True)
        print("DatasetFixer işini bitirdi, akış başlatılıyor...")

    print(f"Log verisi okunuyor: {csv_path} (Limit: {limit if limit > 0 else 'Sınırsız'})")
    df = pd.read_csv(csv_path)

    if limit > 0:
        df = df.head(limit)

    print("Kafka'ya gerçek zamanlı log akışı başladı! (Durdurmak için Ctrl+C)")

    sent_count = 0
    is_finished = False

    for _, row in df.iterrows():
        log_dict = row.to_dict()
        log_dict['ts'] = now_turkey().strftime('%Y-%m-%d %H:%M:%S')

        producer.send('vibestream_logs', value=log_dict)
        sent_count += 1

        if 0 < limit <= sent_count:
            print(f"\n[BİLGİ] Belirlenen limite ({limit}) ulaşıldı. Akış durduruluyor.")
            is_finished = True
            break

        try:
            current_eps = float(r.get('system:eps'))
        except (TypeError, ValueError):
            current_eps = 5.0

        if current_eps > 0:
            time.sleep(1.0 / current_eps)

    print(f"[{sent_count} veri gönderildi] Dosya sonuna ulaşıldı...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vibestream LogStreamer Senaryo Yöneticisi")
    parser.add_argument("--senaryo", type=str, default="orijinal",
                        help="Çalıştırılacak senaryo adı (örn: mutlu_senaryo, uzgun_senaryo, orijinal)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Gönderilecek toplam maksimum veri sayısı (0 = sınırsız/sonsuz döngü)")

    args = parser.parse_args()
    start_streaming(args.senaryo, args.limit)