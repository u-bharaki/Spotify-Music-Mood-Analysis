import pandas as pd
import ast

def clean_artists_for_match(artist_str):
    try:
        artists_list = ast.literal_eval(artist_str)
        val = artists_list[0] if isinstance(artists_list, list) and len(artists_list) > 0 else artist_str
        return str(val).strip().lower()
    except:
        return str(artist_str).strip().lower()

print("1. Veri setleri yükleniyor...")
df_features = pd.read_csv(r"C:\Path\to\Spotify Dataset.csv")
df_history = pd.read_csv(r"C:\Path\to\Spotify Streaming History.csv")

print("2. Eşleşme kümeleri hazırlanıyor...")
valid_ids = set(df_features['id'].dropna())
valid_artists = set(df_features['artists'].dropna().apply(clean_artists_for_match))

# --- UNIQUE SONG CALCULATION ---
history_unique_ids = set(df_history['spotify_track_uri'].dropna())
unique_id_matches = history_unique_ids.intersection(valid_ids)

# --- CALCULATION BY LOG ---
total_logs = len(df_history)

# STEP 1: One to one Track ID Match
id_matches_mask = df_history['spotify_track_uri'].isin(valid_ids)
id_match_logs = id_matches_mask.sum()

# STEP 2: Artist Fallback
remaining_logs = df_history[~id_matches_mask].copy()
remaining_logs['artist_clean'] = remaining_logs['artist_name'].astype(str).str.strip().str.lower()
artist_matches_mask = remaining_logs['artist_clean'].isin(valid_artists)
artist_match_logs = artist_matches_mask.sum()

# STEP 3: OTHERS
others_logs = len(remaining_logs) - artist_match_logs

print("\n========================================================")
print("             VIBESTREAM VERİ KAPSAMA RAPORU             ")
print("========================================================")

print(f"\n🎧 BÖLÜM 1: TEKİL ŞARKI İSTATİSTİKLERİ")
print(f"Streaming History'deki Farklı Şarkı Çeşidi : {len(history_unique_ids)}")
print(f"Spotify Dataset'te Birebir Bulunan Şarkı   : {len(unique_id_matches)}")
print(f"Tekil Şarkı Eşleşme Oranı                  : %{round((len(unique_id_matches)/len(history_unique_ids))*100, 2)}")

print(f"\n📊 BÖLÜM 2: CANLI AKIŞ (LOG SATIRI) İSTATİSTİKLERİ")
print(f"Toplam Dinleme Logu (Kafka'dan Akacak) : {total_logs}")
print(f"--------------------------------------------------------")
print(f"✅ Birebir Şarkı (ID) Üzerinden Kurtarılan : {id_match_logs} Log (%{round((id_match_logs/total_logs)*100, 2)})")
print(f"⚠️ Artist Ortalamasıyla Kurtarılan         : {artist_match_logs} Log (%{round((artist_match_logs/total_logs)*100, 2)})")
print(f"❌ Hiç Eşleşmeyenler (OTHERS atanan)       : {others_logs} Log (%{round((others_logs/total_logs)*100, 2)})")
print(f"--------------------------------------------------------")
print(f"🌟 SİSTEMİN TOPLAM KAPSAMA ORANI           : %{round(((id_match_logs + artist_match_logs)/total_logs)*100, 2)}")
print("========================================================\n")