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
    For song's properties dataset, removes unnecessaries, rounds,
    Calculates artist and OTHERS, and creates Redis JSON.
    """
    print("-> 1/3: Spotify Özellikleri (Redis Seed) işleniyor...")
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
    print("-> 2/3: Streaming Logları (Kafka Producer) işleniyor...")
    df = pd.read_csv(file_path)
    ilk_satir_sayisi = len(df)

    critical_cols = ['ts', 'spotify_track_uri', 'artist_name']
    df = df.dropna(subset=critical_cols)

    df['ms_played'] = df['ms_played'].fillna(0).astype(int)
    df['shuffle'] = df['shuffle'].astype(str).str.upper() == 'TRUE'
    df['skipped'] = df['skipped'].astype(str).str.upper() == 'TRUE'
    df['ts'] = pd.to_datetime(df['ts']).dt.strftime('%Y-%m-%d %H:%M:%S')

    df.to_csv(output_path, index=False)
    print(f"   [Başarılı] Loglar temizlendi! (Toplam: {ilk_satir_sayisi} -> Temiz: {len(df)})")


def create_scenarios(clean_history_path, json_path, base_dir):
    """
    Temizlenmiş logları Redis JSON verisiyle kontrol ederek
    mutlu, üzgün ve hareketli senaryo CSV'lerini üretir.
    """
    print("-> 3/3: Senaryo CSV'leri oluşturuluyor...")

    with open(json_path, 'r', encoding='utf-8') as f:
        redis_data = json.load(f)

    df = pd.read_csv(clean_history_path)
    global_others = redis_data.get("global:OTHERS", {})

    valences, energies, danceabilities = [], [], []

    # Her log satırı için Redis'ten özellik çekiyoruz
    for _, row in df.iterrows():
        uri_key = f"track:{row['spotify_track_uri']}"
        artist_key = f"artist:{row['artist_name']}"

        if uri_key in redis_data:
            feats = redis_data[uri_key]
        elif artist_key in redis_data:
            feats = redis_data[artist_key]
        else:
            feats = global_others

        valences.append(feats.get('valence', 0.5))
        energies.append(feats.get('energy', 0.5))
        danceabilities.append(feats.get('danceability', 0.5))

    # Geçici analiz kolonları ekliyoruz
    df['temp_valence'] = valences
    df['temp_energy'] = energies
    df['temp_dance'] = danceabilities

    # Senaryo 1: Mutlu (Valence ve Enerji Yüksek)
    mutlu_df = df[(df['temp_valence'] > 0.75) & (df['temp_energy'] > 0.7)].drop(
        columns=['temp_valence', 'temp_energy', 'temp_dance'])

    # Senaryo 2: Üzgün (Valence ve Enerji Düşük)
    uzgun_df = df[(df['temp_valence'] < 0.35) & (df['temp_energy'] < 0.4)].drop(
        columns=['temp_valence', 'temp_energy', 'temp_dance'])

    # Senaryo 3: Parti/Hareketli (Danceability Yüksek)
    parti_df = df[df['temp_dance'] > 0.8].drop(columns=['temp_valence', 'temp_energy', 'temp_dance'])

    # LogStreamer'ın doğrudan okuyabilmesi için kaydediyoruz
    mutlu_df.to_csv(os.path.join(base_dir, "cleaned_mutlu_senaryo.csv"), index=False)
    uzgun_df.to_csv(os.path.join(base_dir, "cleaned_uzgun_senaryo.csv"), index=False)
    parti_df.to_csv(os.path.join(base_dir, "cleaned_parti_senaryo.csv"), index=False)

    print(f"   [Başarılı] Mutlu ({len(mutlu_df)}), Üzgün ({len(uzgun_df)}), Parti ({len(parti_df)}) senaryoları hazır!")


def main():
    print("=== VIBESTREAM DATA PREP BATCH PROCESS ===")

    base_dir = os.path.join(os.path.dirname(__file__), "..", "Datasets")
    features_input = os.path.join(base_dir, "Spotify Dataset.csv")
    history_input = os.path.join(base_dir, "Spotify Streaming History.csv")

    redis_output = os.path.join(base_dir, "redis_seed_data.json")
    history_output = os.path.join(base_dir, "cleaned_streaming_history.csv")

    # 1. Redis JSON oluştur
    prepare_redis_seed_data(features_input, redis_output)

    # 2. Ana Log dosyasını temizle
    clean_streaming_history(history_input, history_output)

    # 3. Temizlenen logdan senaryo dosyalarını üret
    create_scenarios(history_output, redis_output, base_dir)

    print("=== TÜM İŞLEMLER TAMAMLANDI! ARTIK SİSTEMİ AYAĞA KALDIRABİLİRİZ ===")


if __name__ == "__main__":
    main()