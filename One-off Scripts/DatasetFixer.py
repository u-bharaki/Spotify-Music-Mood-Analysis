import pandas as pd
import json
import ast
import os


def clean_artists(artist_str):
    """Fixes string lists"""
    try:
        artists_list = ast.literal_eval(artist_str)
        return artists_list[0] if isinstance(artists_list, list) and len(artists_list) > 0 else artist_str
    except:
        return artist_str


def prepare_redis_seed_data(file_path, output_path):
    """
    For song's properties dagtaset, removes unnecessarries, rounds,
    Calculates artist and OTHERS, and creates Redis JSON.
    """
    print("-> 1/2: Spotify Özellikleri (Redis Seed) işleniyor...")
    df = pd.read_csv(file_path)

    numeric_features = [
        'valence', 'energy', 'danceability', 'acousticness',
        'instrumentalness', 'liveness', 'loudness', 'speechiness',
        'tempo', 'popularity', 'duration_ms', 'explicit', 'year'
    ]

    df = df[['id', 'artists'] + numeric_features].dropna()
    df['artists_clean'] = df['artists'].apply(clean_artists)

    # Rounding and creating dictionary
    id_dict = df.set_index('id')[numeric_features].round(4).to_dict('index')
    artist_dict = df.groupby('artists_clean')[numeric_features].mean().round(4).to_dict('index')
    global_avg = df[numeric_features].mean().round(4).to_dict()

    final_data = {f"track:{k}": v for k, v in id_dict.items()}
    final_data.update({f"artist:{k}": v for k, v in artist_dict.items()})
    final_data["global:OTHERS"] = global_avg

    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)

    print(f"   [Başarılı] Redis verisi hazır! ({len(id_dict)} Track, {len(artist_dict)} Artist)")


def clean_streaming_history(file_path, output_path):
    """
    Kafka'dan canlı akacak olan logların null değerlerini temizler ve
    veri tiplerini (Type Casting) optimize eder.
    """
    print("-> 2/2: Streaming Logları (Kafka Producer) işleniyor...")
    df = pd.read_csv(file_path)

    ilk_satir_sayisi = len(df)

    # 1. Kritik kolonları boş (Null/NaN) olan logları çöpe at
    critical_cols = ['ts', 'spotify_track_uri', 'artist_name']
    df = df.dropna(subset=critical_cols)

    # 2. Veri Tipi Optimizasyonları
    # ms_played int olmalı (küsüratlı ms olmaz)
    df['ms_played'] = df['ms_played'].fillna(0).astype(int)

    # shuffle ve skipped kolonlarını Boolean yap
    df['shuffle'] = df['shuffle'].astype(str).str.upper() == 'TRUE'
    df['skipped'] = df['skipped'].astype(str).str.upper() == 'TRUE'

    # ts (timestamp) kolonunu Spark'ın rahat okuyacağı standart formata getir
    df['ts'] = pd.to_datetime(df['ts']).dt.strftime('%Y-%m-%d %H:%M:%S')

    # Temizlenmiş CSV olarak kaydet
    df.to_csv(output_path, index=False)

    kurtarilan_satir = len(df)
    print(f"   [Başarılı] Loglar temizlendi! (Toplam: {ilk_satir_sayisi} -> Temiz: {kurtarilan_satir})")


def main():
    print("=== VIBESTREAM DATA PREP BATCH PROCESS ===")

    # Klasör yollarını (Kendi bilgisayarına göre ayarla)
    base_dir = r"C:\Path\to\datasets"

    # Girdiler
    features_input = os.path.join(base_dir, "Spotify Dataset.csv")
    history_input = os.path.join(base_dir, "Spotify Streaming History.csv")

    # Çıktılar (Proje klasörüne/Docker volume yoluna atılabilir)
    redis_output = os.path.join(base_dir, "redis_seed_data.json")
    history_output = os.path.join(base_dir, "cleaned_streaming_history.csv")

    # Fonksiyonları Çağır
    prepare_redis_seed_data(features_input, redis_output)
    clean_streaming_history(history_input, history_output)

    print("=== TÜM İŞLEMLER TAMAMLANDI! ARTIK SİSTEMİ AYAĞA KALDIRABİLİRİZ ===")


if __name__ == "__main__":
    main()