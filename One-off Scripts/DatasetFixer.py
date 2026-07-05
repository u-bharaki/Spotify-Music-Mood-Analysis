import pandas as pd
import json
import ast

# Changes artist lists to one main artist as a string
def clean_artists(artist_str):

    try:
        artists_list = ast.literal_eval(artist_str)
        return artists_list[0] if isinstance(artists_list, list) and len(artists_list) > 0 else artist_str
    except:
        return artist_str

print("1. Veri seti yükleniyor...")

# Path to Spotify Dataset
file_path = r"C:\Path\to\Spotify Dataset.csv"
df_features = pd.read_csv(file_path)

# Numeric Columns
numeric_features = [
    'valence', 'energy', 'danceability', 'acousticness',
    'instrumentalness', 'liveness', 'loudness', 'speechiness',
    'tempo', 'popularity', 'duration_ms', 'explicit', 'year'
]

features_to_keep = ['id', 'artists'] + numeric_features
df_features = df_features[features_to_keep]

# Clean null values
df_features = df_features.dropna()

print("2. Sanatçı isimleri temizleniyor...")
df_features['artists_clean'] = df_features['artists'].apply(clean_artists)

print("3. Hiyerarşik Sözlükler (Dictionaries) oluşturuluyor ve yuvarlanıyor...")

# Round all numeric values (4 digits after comma [.round(4)])

# STEP 1: One to one Track ID matches
id_dict = df_features.set_index('id')[numeric_features].round(4).to_dict('index')

# STEP 2: Artist Averages
artist_avg_df = df_features.groupby('artists_clean')[numeric_features].mean().round(4)
artist_dict = artist_avg_df.to_dict('index')

# STEP 3: Global Average (OTHERS Fallback)
global_avg = df_features[numeric_features].mean().round(4).to_dict()

print("4. Redis formatında tek bir JSON'da birleştiriliyor...")
final_redis_data = {}

# Add songs
for track_id, feats in id_dict.items():
    final_redis_data[f"track:{track_id}"] = feats

# Add artist averages
for artist, feats in artist_dict.items():
    final_redis_data[f"artist:{artist}"] = feats

# Add global average
final_redis_data["global:OTHERS"] = global_avg

# Save JSON file
output_filename = "redis_seed_data.json"
with open(output_filename, "w", encoding='utf-8') as f:
    json.dump(final_redis_data, f, ensure_ascii=False, indent=4)

print(f"İşlem tamam! Yuvarlanmış ve optimize edilmiş '{output_filename}' dosyası hazır.")
print(f"Toplam Track Sayısı: {len(id_dict)}")
print(f"Toplam Artist Sayısı: {len(artist_dict)}")