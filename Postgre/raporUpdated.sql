DROP TABLE IF EXISTS realtime_streaming_events CASCADE;
DROP TABLE IF EXISTS system_metrics CASCADE;
DROP TABLE IF EXISTS realtime_leaderboard CASCADE;
DROP TABLE IF EXISTS engagement_metrics CASCADE;
DROP TABLE IF EXISTS realtime_mood_metrics CASCADE;
DROP TABLE IF EXISTS tracks CASCADE;
DROP TABLE IF EXISTS albums CASCADE;
DROP TABLE IF EXISTS artists CASCADE;
DROP TABLE IF EXISTS global_fallback_metrics CASCADE;

CREATE TABLE IF NOT EXISTS artists (
    artist_name VARCHAR(255) PRIMARY KEY, 
    avg_duration_ms BIGINT,
    avg_popularity NUMERIC(5,2),
    avg_explicit NUMERIC(5,4),          
    avg_danceability NUMERIC(5,4),
    avg_energy NUMERIC(5,4),
    avg_loudness NUMERIC(10,4),
    avg_speechiness NUMERIC(5,4),
    avg_acousticness NUMERIC(5,4),
    avg_instrumentalness NUMERIC(5,4),
    avg_liveness NUMERIC(5,4),
    avg_valence NUMERIC(5,4),
    avg_tempo NUMERIC(7,3),
    total_play_count INT DEFAULT 0,
    total_skip_count INT DEFAULT 0,
    total_listening_time_ms BIGINT DEFAULT 0,
    avg_listening_time_ms BIGINT DEFAULT 0,
    likeability_score NUMERIC(5,4)
);

CREATE TABLE IF NOT EXISTS albums (
    album_name VARCHAR(255) PRIMARY KEY,
    artist_name VARCHAR(255) REFERENCES artists(artist_name),
    year INT
);

CREATE TABLE IF NOT EXISTS tracks (
    track_uri VARCHAR(255) PRIMARY KEY,         
    track_name VARCHAR(255) NOT NULL,           
    album_name VARCHAR(255) REFERENCES albums(album_name),
    artist_name VARCHAR(255) REFERENCES artists(artist_name), 
    duration_ms BIGINT,                         
    explicit INT,                               
    popularity INT,                             
    year INT,                          
    danceability NUMERIC(5,4),                  
    energy NUMERIC(5,4),                                                                       
    loudness NUMERIC(10,4),                                                                    
    speechiness NUMERIC(5,4),                   
    acousticness NUMERIC(5,4),                  
    instrumentalness NUMERIC(5,4),              
    liveness NUMERIC(5,4),                      
    valence NUMERIC(5,4),                       
    tempo NUMERIC(7,3),
    total_play_count INT DEFAULT 0,
    total_skip_count INT DEFAULT 0,
    total_listening_time_ms BIGINT DEFAULT 0,
    avg_listening_time_ms BIGINT DEFAULT 0,
    likeability_score NUMERIC(5,4)                          
);

CREATE TABLE IF NOT EXISTS global_fallback_metrics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) DEFAULT 'Others', 
    avg_duration_ms BIGINT,
    avg_danceability NUMERIC(5,4),
    avg_energy NUMERIC(5,4),
    avg_loudness NUMERIC(10,4),
    avg_speechiness NUMERIC(5,4),
    avg_acousticness NUMERIC(5,4),
    avg_instrumentalness NUMERIC(5,4),
    avg_liveness NUMERIC(5,4),
    avg_valence NUMERIC(5,4),
    avg_tempo NUMERIC(7,3)
);

-- YENİ: VibeStreamApp.scala bu tabloya yazıyor (enrichedDF -> realtime_streaming_events)
-- ama tabloyu tanımlayan CREATE ifadesi rapordaki şemada yoktu. Eklendi.
CREATE TABLE IF NOT EXISTS realtime_streaming_events (
    id SERIAL PRIMARY KEY,
    "timestamp" TIMESTAMP NOT NULL,
    track_uri VARCHAR(255),
    artist_name VARCHAR(255),
    ms_played INT,
    energy NUMERIC(5,4),
    valence NUMERIC(5,4),
    danceability NUMERIC(5,4)
);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON realtime_streaming_events("timestamp");
CREATE INDEX IF NOT EXISTS idx_events_track ON realtime_streaming_events(track_uri);

CREATE TABLE IF NOT EXISTS realtime_mood_metrics (
    id SERIAL PRIMARY KEY,
    window_start_time TIMESTAMP NOT NULL,
    avg_valence NUMERIC(5,4),
    avg_energy NUMERIC(5,4),
    total_streams INT
);

CREATE TABLE IF NOT EXISTS engagement_metrics (
    id SERIAL PRIMARY KEY,
    window_start_time TIMESTAMP NOT NULL,
    track_uri VARCHAR(255), 
    completion_rate NUMERIC(5,4),
    skip_count INT,
    natural_end_count INT
);

CREATE TABLE IF NOT EXISTS realtime_leaderboard (
    id SERIAL PRIMARY KEY,
    window_start_time TIMESTAMP NOT NULL,
    track_uri VARCHAR(255),
    play_count INT
);

CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    events_per_second INT,
    spark_processing_delay_ms INT
);
