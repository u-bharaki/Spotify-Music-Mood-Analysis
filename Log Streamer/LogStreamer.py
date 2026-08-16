import os
import time
import json
from datetime import datetime
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

            # CSV'deki eski (geçmiş) tarihi kullanmıyoruz - her olay Kafka'ya
            # gönderildiği ANDAKİ gerçek zamanla damgalanıyor. Böylece
            # dashboard'daki "20 saniyelik dilim" grafikleri gerçekten
            # "şimdi" ile "az önce" arasındaki canlı akışı yansıtıyor.
            log_dict['ts'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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