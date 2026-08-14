"""
VibeStream Dashboard - Canlı Müzik Ruh Hali Analiz Paneli

Bu Streamlit uygulaması doğrudan PostgreSQL'e bağlanır (Spark Streaming'in
yazdığı tablolar) ve isteğe bağlı olarak Redis (ingestion hızı kontrolü) ile
Docker (konteyner kaynak kullanımı) ile konuşur. Hiçbir tablo/veri yoksa
panel çökmez, "henüz veri yok" mesajı gösterir; bu sayede Spark/consumer
henüz ayağa kalkmadan da dashboard açılabilir.
"""

import os
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine, text

# ------------------------------------------------------------------
# Sayfa yapılandırması & Spotify temalı görsel stil
# ------------------------------------------------------------------
st.set_page_config(
    page_title="VibeStream | Live Mood Dashboard",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

SPOTIFY_GREEN = "#1DB954"
BG_DARK = "#121212"
CARD_DARK = "#181818"

st.markdown(
    f"""
    <style>
        .stApp {{ background-color: {BG_DARK}; color: #E8E8E8; }}
        section[data-testid="stSidebar"] {{ background-color: #0a0a0a; }}
        div[data-testid="stMetric"] {{
            background-color: {CARD_DARK};
            border: 1px solid #2a2a2a;
            border-radius: 12px;
            padding: 14px 16px 6px 16px;
        }}
        div[data-testid="stMetricValue"] {{ color: {SPOTIFY_GREEN}; }}
        h1, h2, h3 {{ color: #FFFFFF; }}
        .vibe-badge {{
            display:inline-block; background:{SPOTIFY_GREEN}; color:#0a0a0a;
            padding:2px 10px; border-radius:999px; font-size:12px; font-weight:600;
        }}
        div[data-testid="stTabs"] button p {{ font-size: 15px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# Bağlantılar
# ------------------------------------------------------------------
PG_HOST = os.getenv("PG_HOST", "postgres")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "vibe_admin")
PG_PASSWORD = os.getenv("PG_PASSWORD", "vibe_password")
PG_DB = os.getenv("PG_DB", "vibestream_db")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


@st.cache_resource
def get_engine():
    uri = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(uri, pool_pre_ping=True)


@st.cache_resource
def get_redis():
    try:
        import redis

        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        r.ping()
        return r
    except Exception:
        return None


def run_query(sql, params=None):
    """SQL çalıştır, hata/boş veri durumunda boş DataFrame döndür (dashboard çökmesin)."""
    try:
        with get_engine().connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})
    except Exception as e:
        st.session_state.setdefault("_errors", []).append(str(e))
        return pd.DataFrame()


def empty_state(msg="Henüz veri akmadı — simulator/spark servislerinin çalıştığından emin olun."):
    st.info(f"ℹ️ {msg}")


# ------------------------------------------------------------------
# Sidebar - kontroller
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🎧 VibeStream")
    st.markdown('<span class="vibe-badge">LIVE</span>', unsafe_allow_html=True)
    st.caption("Real-Time Contextual Music Analytics Pipeline")
    st.divider()

    refresh_sec = st.select_slider(
        "Otomatik yenileme (sn)",
        options=[0, 5, 10, 20, 30, 60],
        value=10,
        help="0 = otomatik yenileme kapalı",
    )

    lookback_min = st.slider("Zaman penceresi (son N dakika)", 1, 240, 30)

    st.divider()
    st.markdown("### ⚡ Ingestion Hız Kontrolü")
    r = get_redis()
    if r is not None:
        try:
            current_eps = float(r.get("system:eps") or 5)
        except (TypeError, ValueError):
            current_eps = 5.0
        new_eps = st.slider("Saniyedeki log sayısı (EPS)", 1, 100, int(current_eps))
        if new_eps != int(current_eps):
            r.set("system:eps", new_eps)
            st.success(f"EPS -> {new_eps} olarak güncellendi")
    else:
        st.caption("Redis'e bağlanılamadı (LogStreamer hız kontrolü devre dışı).")

    st.divider()
    if st.button("🔄 Şimdi yenile", use_container_width=True):
        st.rerun()

if refresh_sec:
    try:
        from streamlit_autorefresh import st_autorefresh

        st_autorefresh(interval=refresh_sec * 1000, key="auto_refresh")
    except ImportError:
        pass

st.title("🎧 VibeStream — Canlı Müzik Ruh Hali Paneli")
st.caption(f"Son güncelleme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

tab_overview, tab_engage, tab_mood, tab_top, tab_sys = st.tabs(
    [
        "🌈 Genel Bakış & Zaman Çizelgesi",
        "⏭️ Skip & Engagement",
        "🎯 Mood Matrix & Nostalji",
        "🏆 Top Liste",
        "⚙️ Mühendislik Paneli",
    ]
)

# ==================================================================
# TAB 1 — OVERVIEW: mood timeline (line) + hour x day heatmap
# ==================================================================
with tab_overview:
    kpi = run_query(
        """
        SELECT
            COUNT(*)                                   AS total_events,
            AVG(valence)                                AS avg_valence,
            AVG(energy)                                 AS avg_energy,
            AVG(completion_rate)                         AS avg_completion,
            SUM(CASE WHEN is_skip THEN 1 ELSE 0 END)::float
                / GREATEST(COUNT(*), 1)                  AS skip_rate
        FROM realtime_streaming_events
        WHERE timestamp >= NOW() - INTERVAL ':m minutes'
        """.replace(":m", str(lookback_min))
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    if not kpi.empty and kpi.iloc[0]["total_events"]:
        row = kpi.iloc[0]
        c1.metric("Toplam Stream (pencere)", f"{int(row['total_events']):,}")
        c2.metric("Ort. Valence", f"{row['avg_valence']:.2f}" if row['avg_valence'] is not None else "—")
        c3.metric("Ort. Energy", f"{row['avg_energy']:.2f}" if row['avg_energy'] is not None else "—")
        c4.metric("Ort. Tamamlama", f"{row['avg_completion']*100:.1f}%" if row['avg_completion'] is not None else "—")
        c5.metric("Skip Oranı", f"{row['skip_rate']*100:.1f}%" if row['skip_rate'] is not None else "—")
    else:
        c1.metric("Toplam Stream (pencere)", "0")
        c2.metric("Ort. Valence", "—")
        c3.metric("Ort. Energy", "—")
        c4.metric("Ort. Tamamlama", "—")
        c5.metric("Skip Oranı", "—")

    st.markdown("### 📈 Zaman Çizelgesinde Duygu Durumu (Valence & Energy)")
    mood_df = run_query(
        """
        SELECT window_start_time, avg_valence, avg_energy, total_streams
        FROM realtime_mood_metrics
        WHERE window_start_time >= NOW() - INTERVAL ':m minutes'
        ORDER BY window_start_time
        """.replace(":m", str(lookback_min))
    )
    if mood_df.empty:
        empty_state()
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=mood_df["window_start_time"], y=mood_df["avg_valence"],
                                  name="Valence (Pozitiflik)", line=dict(color=SPOTIFY_GREEN, width=3)))
        fig.add_trace(go.Scatter(x=mood_df["window_start_time"], y=mood_df["avg_energy"],
                                  name="Energy", line=dict(color="#F5B700", width=3)))
        fig.update_layout(template="plotly_dark", plot_bgcolor=CARD_DARK, paper_bgcolor=CARD_DARK,
                           height=380, legend=dict(orientation="h", y=1.1), margin=dict(t=30))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🔥 Dinleme Yoğunluğu Isı Haritası (Saat x Gün)")
    heat_df = run_query(
        """
        SELECT day_of_week, hour_of_day, COUNT(*) AS plays
        FROM realtime_streaming_events
        WHERE timestamp >= NOW() - INTERVAL ':m minutes'
        GROUP BY day_of_week, hour_of_day
        """.replace(":m", str(lookback_min))
    )
    if heat_df.empty:
        empty_state()
    else:
        day_labels = {1: "Pzt", 2: "Sal", 3: "Çar", 4: "Per", 5: "Cum", 6: "Cmt", 7: "Paz"}
        pivot = heat_df.pivot(index="day_of_week", columns="hour_of_day", values="plays").fillna(0)
        pivot = pivot.reindex(range(1, 8)).reindex(columns=range(0, 24), fill_value=0)
        pivot.index = [day_labels.get(i, i) for i in pivot.index]
        fig = px.imshow(
            pivot, labels=dict(x="Saat", y="Gün", color="Dinleme Sayısı"),
            color_continuous_scale=[[0, CARD_DARK], [1, SPOTIFY_GREEN]], aspect="auto",
        )
        fig.update_layout(template="plotly_dark", height=320, margin=dict(t=20))
        st.plotly_chart(fig, use_container_width=True)

# ==================================================================
# TAB 2 — Skip behaviour, completion rate, likeability
# ==================================================================
with tab_engage:
    st.markdown("### ⏭️ Skip Davranışı vs. Müzik Karakteristiği (Saatlik)")
    skip_df = run_query(
        """
        SELECT hour_of_day,
               AVG(CASE WHEN is_skip THEN danceability END)     AS skip_danceability,
               AVG(CASE WHEN NOT is_skip THEN danceability END) AS keep_danceability,
               AVG(CASE WHEN is_skip THEN acousticness END)     AS skip_acousticness,
               AVG(CASE WHEN NOT is_skip THEN acousticness END) AS keep_acousticness,
               SUM(CASE WHEN is_skip THEN 1 ELSE 0 END)::float / GREATEST(COUNT(*),1) AS skip_rate
        FROM realtime_streaming_events
        WHERE timestamp >= NOW() - INTERVAL ':m minutes'
        GROUP BY hour_of_day ORDER BY hour_of_day
        """.replace(":m", str(lookback_min))
    )
    if skip_df.empty:
        empty_state()
    else:
        col_a, col_b = st.columns([2, 1])
        with col_a:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=skip_df["hour_of_day"], y=skip_df["skip_danceability"],
                                  name="Geçilen şarkı - danceability", marker_color="#E74C3C"))
            fig.add_trace(go.Bar(x=skip_df["hour_of_day"], y=skip_df["keep_danceability"],
                                  name="Dinlenen şarkı - danceability", marker_color=SPOTIFY_GREEN))
            fig.update_layout(template="plotly_dark", barmode="group", height=360,
                               plot_bgcolor=CARD_DARK, paper_bgcolor=CARD_DARK,
                               xaxis_title="Saat", legend=dict(orientation="h", y=1.15))
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            fig2 = px.bar(skip_df, x="hour_of_day", y="skip_rate",
                           color_discrete_sequence=["#E74C3C"])
            fig2.update_layout(template="plotly_dark", height=360, title="Saatlik Skip Oranı",
                                plot_bgcolor=CARD_DARK, paper_bgcolor=CARD_DARK, xaxis_title="Saat", yaxis_tickformat=".0%")
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### ✅ Şarkı Tamamlama Oranı (Engagement)")
    comp_df = run_query(
        """
        SELECT hour_of_day, AVG(completion_rate) AS avg_completion, COUNT(*) AS n
        FROM realtime_streaming_events
        WHERE timestamp >= NOW() - INTERVAL ':m minutes'
        GROUP BY hour_of_day ORDER BY hour_of_day
        """.replace(":m", str(lookback_min))
    )
    if comp_df.empty:
        empty_state()
    else:
        fig = px.area(comp_df, x="hour_of_day", y="avg_completion",
                       color_discrete_sequence=[SPOTIFY_GREEN])
        fig.update_layout(template="plotly_dark", height=320, plot_bgcolor=CARD_DARK,
                           paper_bgcolor=CARD_DARK, yaxis_tickformat=".0%", xaxis_title="Saat",
                           yaxis_title="Ort. Tamamlama Oranı")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### ❤️ Canlı Beğenilirlik (Likeability) Skoru — Sanatçı Bazlı")
    st.caption("likeability_score ≈ ortalama tamamlama oranı − skip oranı (canlı pencereden hesaplanır)")
    like_df = run_query(
        """
        SELECT artist_name,
               AVG(completion_rate) AS avg_completion,
               SUM(CASE WHEN is_skip THEN 1 ELSE 0 END)::float / GREATEST(COUNT(*),1) AS skip_rate,
               COUNT(*) AS plays
        FROM realtime_streaming_events
        WHERE timestamp >= NOW() - INTERVAL ':m minutes' AND artist_name IS NOT NULL
        GROUP BY artist_name
        HAVING COUNT(*) >= 1
        """.replace(":m", str(lookback_min))
    )
    if like_df.empty:
        empty_state()
    else:
        like_df["likeability"] = (like_df["avg_completion"] - like_df["skip_rate"]).clip(-1, 1)
        top_like = like_df.sort_values("likeability", ascending=False).head(10)
        fig = px.bar(top_like.sort_values("likeability"), x="likeability", y="artist_name",
                     orientation="h", color="likeability",
                     color_continuous_scale=[[0, "#E74C3C"], [0.5, "#F5B700"], [1, SPOTIFY_GREEN]])
        fig.update_layout(template="plotly_dark", height=420, plot_bgcolor=CARD_DARK,
                           paper_bgcolor=CARD_DARK, xaxis_title="Beğenilirlik Skoru", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

# ==================================================================
# TAB 3 — Mood matrix scatter + nostalgia index
# ==================================================================
with tab_mood:
    st.markdown("### 🎯 Mood Matrix (Valence x Energy)")
    scatter_df = run_query(
        """
        SELECT timestamp, artist_name, valence, energy
        FROM mood_matrix_samples
        WHERE timestamp >= NOW() - INTERVAL ':m minutes'
        ORDER BY timestamp DESC LIMIT 3000
        """.replace(":m", str(lookback_min))
    )
    if scatter_df.empty:
        empty_state()
    else:
        fig = px.scatter(
            scatter_df, x="valence", y="energy", opacity=0.55,
            hover_data=["artist_name"], color_discrete_sequence=[SPOTIFY_GREEN],
        )
        fig.add_hline(y=0.5, line_dash="dot", line_color="#555")
        fig.add_vline(x=0.5, line_dash="dot", line_color="#555")
        fig.add_annotation(x=0.85, y=0.9, text="Enerjik & Mutlu", showarrow=False, font=dict(color="#aaa"))
        fig.add_annotation(x=0.15, y=0.9, text="Agresif / Gergin", showarrow=False, font=dict(color="#aaa"))
        fig.add_annotation(x=0.85, y=0.1, text="Sakin & Mutlu", showarrow=False, font=dict(color="#aaa"))
        fig.add_annotation(x=0.15, y=0.1, text="Hüzünlü / Durgun", showarrow=False, font=dict(color="#aaa"))
        fig.update_layout(template="plotly_dark", height=480, plot_bgcolor=CARD_DARK,
                           paper_bgcolor=CARD_DARK, xaxis_range=[0, 1], yaxis_range=[0, 1])
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🕰️ Nostalji İndeksi (Çıkış Yılına Göre Dağılım)")
    year_df = run_query(
        """
        SELECT year, COUNT(*) AS plays
        FROM realtime_streaming_events
        WHERE timestamp >= NOW() - INTERVAL ':m minutes' AND year > 1950
        GROUP BY year ORDER BY year
        """.replace(":m", str(lookback_min))
    )
    if year_df.empty:
        empty_state()
    else:
        fig = px.bar(year_df, x="year", y="plays", color_discrete_sequence=[SPOTIFY_GREEN])
        fig.update_layout(template="plotly_dark", height=340, plot_bgcolor=CARD_DARK,
                           paper_bgcolor=CARD_DARK, xaxis_title="Çıkış Yılı", yaxis_title="Dinlenme Sayısı")
        st.plotly_chart(fig, use_container_width=True)

# ==================================================================
# TAB 4 — Leaderboard
# ==================================================================
with tab_top:
    st.markdown("### 🏆 Canlı Top N Liderlik Tablosu")
    top_n = st.slider("Kaç sanatçı/şarkı gösterilsin?", 5, 25, 10)
    lb_df = run_query(
        """
        SELECT track_name, artist_name, SUM(play_count) AS plays
        FROM realtime_leaderboard
        WHERE window_start_time >= NOW() - INTERVAL ':m minutes'
        GROUP BY track_name, artist_name
        ORDER BY plays DESC
        LIMIT :n
        """.replace(":m", str(lookback_min)),
        params={"n": top_n},
    )
    if lb_df.empty:
        empty_state()
    else:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.dataframe(
                lb_df.rename(columns={"track_name": "Şarkı", "artist_name": "Sanatçı", "plays": "Çalınma"}),
                use_container_width=True, hide_index=True,
            )
        with col2:
            fig = px.bar(lb_df.sort_values("plays"), x="plays", y="track_name", orientation="h",
                         color="plays", color_continuous_scale=[[0, "#0a0a0a"], [1, SPOTIFY_GREEN]],
                         hover_data=["artist_name"])
            fig.update_layout(template="plotly_dark", height=420, plot_bgcolor=CARD_DARK,
                               paper_bgcolor=CARD_DARK, yaxis_title="", xaxis_title="Toplam Çalınma")
            st.plotly_chart(fig, use_container_width=True)

# ==================================================================
# TAB 5 — Engineering panel: ingestion rate + container resources
# ==================================================================
with tab_sys:
    st.markdown("### 🚀 Anlık Veri Akış Hızı (Events / Second)")
    eps_df = run_query(
        """
        SELECT date_trunc('second', timestamp) AS sec, COUNT(*) AS events
        FROM realtime_streaming_events
        WHERE timestamp >= NOW() - INTERVAL '2 minutes'
        GROUP BY sec ORDER BY sec
        """
    )
    c1, c2 = st.columns([1, 3])
    with c1:
        current_rate = eps_df["events"].tail(5).mean() if not eps_df.empty else 0
        st.metric("Ort. EPS (son 5 sn)", f"{current_rate:.1f}")
        rr = get_redis()
        if rr is not None:
            try:
                st.metric("Hedef EPS (Redis dial)", f"{float(rr.get('system:eps') or 0):.0f}")
            except Exception:
                pass
    with c2:
        if eps_df.empty:
            empty_state("Ingestion henüz başlamadı.")
        else:
            fig = px.line(eps_df, x="sec", y="events", markers=True,
                          color_discrete_sequence=[SPOTIFY_GREEN])
            fig.update_layout(template="plotly_dark", height=280, plot_bgcolor=CARD_DARK,
                               paper_bgcolor=CARD_DARK, xaxis_title="", yaxis_title="log/sn")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🖥️ Cluster Kaynak Tüketimi (Docker Konteynerleri)")
    st.caption(
        "MVP fazında (Docker Compose) gerçek konteyner CPU/RAM kullanımı gösterilir. "
        "Kubernetes'e taşındığında bu panel HPA'nın devreye girdiği anlardaki pod "
        "sayısı artışını da gösterecek şekilde genişletilecektir."
    )
    try:
        import docker

        client = docker.DockerClient(base_url="unix://var/run/docker.sock")
        rows = []
        for c in client.containers.list():
            if not c.name.startswith("vibestream"):
                continue
            try:
                stats = c.stats(stream=False)
                cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
                sys_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
                n_cpus = stats["cpu_stats"].get("online_cpus", 1) or 1
                cpu_pct = (cpu_delta / sys_delta) * n_cpus * 100 if sys_delta > 0 else 0.0
                mem_usage = stats["memory_stats"].get("usage", 0)
                mem_limit = stats["memory_stats"].get("limit", 1)
                rows.append({
                    "Servis": c.name.replace("vibestream-", ""),
                    "CPU %": round(cpu_pct, 2),
                    "RAM (MB)": round(mem_usage / (1024 * 1024), 1),
                    "RAM %": round(mem_usage / mem_limit * 100, 2) if mem_limit else 0,
                })
            except Exception:
                continue
        if rows:
            res_df = pd.DataFrame(rows)
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(res_df, x="Servis", y="CPU %", color_discrete_sequence=[SPOTIFY_GREEN])
                fig.update_layout(template="plotly_dark", height=320, plot_bgcolor=CARD_DARK, paper_bgcolor=CARD_DARK)
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.bar(res_df, x="Servis", y="RAM (MB)", color_discrete_sequence=["#F5B700"])
                fig.update_layout(template="plotly_dark", height=320, plot_bgcolor=CARD_DARK, paper_bgcolor=CARD_DARK)
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(res_df, use_container_width=True, hide_index=True)
        else:
            empty_state("vibestream-* konteynerleri bulunamadı.")
    except Exception:
        empty_state(
            "Docker socket'e erişilemedi. docker-compose.yml içinde dashboard servisine "
            "'/var/run/docker.sock:/var/run/docker.sock:ro' volume'ünün eklendiğinden emin olun."
        )

    st.markdown("### 🧩 CPU Çekirdek Dağılımı & Kafka Partition Paralelliği")
    st.caption(
        "Her servise docker-compose.yml içinde 'deploy.resources.limits.cpus' ile açıkça "
        "kaç çekirdek ayrıldığını, ve Kafka topic'inin kaç partition'a bölündüğünü (gerçek "
        "paralellik tavanı) gösterir."
    )
    host_cores = os.cpu_count() or 0
    col1, col2 = st.columns([3, 2])

    with col1:
        try:
            import docker as docker_sdk

            client2 = docker_sdk.DockerClient(base_url="unix://var/run/docker.sock")
            limit_rows = []
            for c in client2.containers.list(all=True):
                if not c.name.startswith("vibestream"):
                    continue
                nano = c.attrs.get("HostConfig", {}).get("NanoCpus", 0)
                cores = round(nano / 1e9, 2) if nano else None
                limit_rows.append({
                    "Servis": c.name.replace("vibestream-", ""),
                    "Ayrılan Çekirdek": cores if cores else host_cores,
                    "Sınırlı mı?": "Evet" if cores else "Hayır (host limiti)",
                })
            if limit_rows:
                lim_df = pd.DataFrame(limit_rows).sort_values("Ayrılan Çekirdek", ascending=False)
                fig = px.bar(lim_df, x="Servis", y="Ayrılan Çekirdek", color="Sınırlı mı?",
                             color_discrete_map={"Evet": SPOTIFY_GREEN, "Hayır (host limiti)": "#555"})
                fig.update_layout(template="plotly_dark", height=340, plot_bgcolor=CARD_DARK,
                                   paper_bgcolor=CARD_DARK, yaxis_title="Çekirdek")
                st.plotly_chart(fig, use_container_width=True)
            else:
                empty_state("Konteyner listesi alınamadı.")
        except Exception:
            empty_state("Docker socket üzerinden çekirdek limitleri okunamadı.")

    with col2:
        st.metric("Bu makinenin gördüğü toplam çekirdek", host_cores)
        try:
            from kafka.admin import KafkaAdminClient

            admin = KafkaAdminClient(bootstrap_servers="kafka:9092", request_timeout_ms=3000)
            desc = admin.describe_topics(["vibestream_logs"])
            n_partitions = len(desc[0]["partitions"]) if desc else None
            admin.close()
        except Exception:
            n_partitions = None

        if n_partitions is not None:
            st.metric("Kafka 'vibestream_logs' partition sayısı", n_partitions)
            spark_cores = 2  # docker-compose.yml -> spark servisi deploy.resources.limits.cpus
            if n_partitions < spark_cores:
                st.warning(
                    f"⚠️ Darboğaz: Spark'a {spark_cores} çekirdek ayrılmış olsa da, "
                    f"Kafka topic'i sadece {n_partitions} partition'a sahip. Structured "
                    f"Streaming bir partition'ı aynı anda tek bir görevle okuyabildiğinden, "
                    f"gerçek okuma paralelliği {n_partitions} ile sınırlı — fazladan çekirdek "
                    f"bu aşamada boşta kalır. Paralelliği artırmak için topic'i daha fazla "
                    f"partition ile oluşturmak gerekir."
                )
            else:
                st.success("✅ Partition sayısı, Spark'a ayrılan çekirdek sayısını karşılıyor.")
        else:
            empty_state("Kafka admin bağlantısı kurulamadı (broker henüz hazır olmayabilir).")

st.divider()
st.caption("VibeStream · Kafka → Spark Structured Streaming → Redis (enrichment) → PostgreSQL → Streamlit")