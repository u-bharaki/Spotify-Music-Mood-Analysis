import os
import time
import json
import pandas as pd
from kafka import KafkaProducer
import redis

CURRENT_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.abspath(
    os.path.join(CURRENT_DIR, '..', 'Datasets', 'cleaned_streaming_history.csv')
)

def start_streaming():
    r = redis.Redis(
        host='redis',
        port=6379,
        db=0,
        decode_responses=True
    )

    if not r.exists('system:eps'):
        r.set('system:eps', 5)

    producer = KafkaProducer(
        bootstrap_servers=['kafka:9092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    print(f"Log verisi okunuyor: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)

    print("Kafka'ya gerçek zamanlı log akışı başladı! (Durdurmak için Ctrl+C)")

    while True:
        for _, row in df.iterrows():

            log_dict = row.to_dict()

            if pd.isna(log_dict.get('ts')):
                print("Timestamp bulunamadı, kayıt atlanıyor.")
                continue

            log_dict['ts'] = str(log_dict['ts'])

            producer.send(
                'vibestream_logs',
                value=log_dict
            )

            try:
                current_eps = float(r.get('system:eps'))
            except (TypeError, ValueError):
                current_eps = 5.0

            if current_eps > 0:
                time.sleep(1.0 / current_eps)


if __name__ == "__main__":
    start_streaming()