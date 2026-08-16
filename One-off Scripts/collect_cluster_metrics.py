"""
VibeStream - Kubernetes Cluster Metrics Collector.

Bu script, K8s ekibinin (Kubernetes/HPA tarafı) sorumluluğundadır ve
cluster İÇİNDE çalışması gerekir. Görevi basit: `kubectl top pods` ve
`kubectl get hpa` çıktısını periyodik olarak okuyup, aynı Postgres
veritabanına (`system_metrics` tablosu) yazmak. Bu sayede Superset
tarafı (SQL-only bir BI aracı olduğu için Kubernetes API'sine hiçbir
zaman doğrudan erişemez) bu veriyi normal bir SQL sorgusu gibi
görselleştirebilir - "Cluster Kaynak Tüketimi" ve "HPA pod sayısı"
panelleri bu tabloyu okur.

NASIL ÇALIŞTIRILIR (K8s tarafı):
  1. Bu script'i vibestream-workers imajına dahil et (zaten "COPY . /app/"
     ile tüm proje kopyalandığı için otomatik dahil olur).
  2. Cluster içinde `kubectl` komutunu çalıştırabilmesi için pod'a bir
     ServiceAccount + RBAC (Role: pods/metrics okuma, hpa okuma) bağla.
     Örnek Role kuralları:
       - apiGroups: ["metrics.k8s.io"], resources: ["pods"], verbs: ["get","list"]
       - apiGroups: ["autoscaling"], resources: ["horizontalpodautoscalers"], verbs: ["get","list"]
  3. Bunu bir Deployment (sürekli döngü) veya bir CronJob (örn. her 15
     saniyede bir) olarak deploy et. En basit yol: `data-workers.yaml`
     içindeki mevcut bir pod'a sidecar container olarak eklemek, ya da
     ayrı bir "vibestream-cluster-collector" Deployment'ı açmak.
  4. Ortam değişkenleri: PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DB,
     HPA_NAME (varsayılan: vibestream-spark-hpa), NAMESPACE (varsayılan:
     vibestream), INTERVAL_SECONDS (varsayılan: 15).

Not: `kubectl` binary'sinin çalıştığı konteynerde kurulu olması gerekir
(apache/spark tabanlı worker imajında yoksa `pip install kubernetes` ile
Python Kubernetes client'ına geçmek de bir alternatif - bu script'in
sonunda o yaklaşım için de bir not var).
"""

import json
import os
import subprocess
import time
from datetime import datetime

import psycopg2

PG_HOST = os.getenv("PG_HOST", "postgres")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "vibe_admin")
PG_PASSWORD = os.getenv("PG_PASSWORD", "vibe_password")
PG_DB = os.getenv("PG_DB", "vibestream_db")

NAMESPACE = os.getenv("NAMESPACE", "vibestream")
HPA_NAME = os.getenv("HPA_NAME", "vibestream-spark-hpa")
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "15"))


def get_pg_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD, dbname=PG_DB
    )


def get_pod_metrics():
    """`kubectl top pods` çıktısını parse eder. Örnek satır:
    vibestream-spark-779584d769-2jcbz   250m   512Mi
    Döndürür: [{"pod_name": ..., "cpu_millicores": 250, "memory_mb": 512}, ...]
    """
    try:
        out = subprocess.check_output(
            ["kubectl", "top", "pods", "-n", NAMESPACE, "--no-headers"],
            stderr=subprocess.DEVNULL, timeout=10,
        ).decode()
    except Exception as e:
        print(f"[UYARI] kubectl top pods çalıştırılamadı: {e}")
        return []

    rows = []
    for line in out.strip().splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        pod_name, cpu_raw, mem_raw = parts[0], parts[1], parts[2]
        try:
            cpu_millicores = int(cpu_raw.rstrip("m")) if cpu_raw.endswith("m") else int(float(cpu_raw) * 1000)
        except ValueError:
            cpu_millicores = None
        try:
            if mem_raw.endswith("Mi"):
                memory_mb = int(mem_raw.rstrip("Mi"))
            elif mem_raw.endswith("Gi"):
                memory_mb = int(float(mem_raw.rstrip("Gi")) * 1024)
            else:
                memory_mb = None
        except ValueError:
            memory_mb = None
        rows.append({"pod_name": pod_name, "cpu_millicores": cpu_millicores, "memory_mb": memory_mb})
    return rows


def get_hpa_status():
    """`kubectl get hpa <name> -o json` üzerinden current/desired replica
    sayısını ve hedef CPU yüzdesini okur."""
    try:
        out = subprocess.check_output(
            ["kubectl", "get", "hpa", HPA_NAME, "-n", NAMESPACE, "-o", "json"],
            stderr=subprocess.DEVNULL, timeout=10,
        ).decode()
        data = json.loads(out)
        status = data.get("status", {})
        spec = data.get("spec", {})
        target_cpu = None
        for m in spec.get("metrics", []):
            if m.get("resource", {}).get("name") == "cpu":
                target_cpu = m["resource"].get("target", {}).get("averageUtilization")
        return {
            "current_replicas": status.get("currentReplicas"),
            "desired_replicas": status.get("desiredReplicas"),
            "target_cpu_percent": target_cpu,
        }
    except Exception as e:
        print(f"[UYARI] kubectl get hpa çalıştırılamadı: {e}")
        return {"current_replicas": None, "desired_replicas": None, "target_cpu_percent": None}


def write_metrics(conn, pod_rows, hpa_status):
    with conn.cursor() as cur:
        if not pod_rows:
            # Pod yoksa bile HPA durumunu tek satır olarak kaydet.
            cur.execute(
                """INSERT INTO system_metrics
                   (timestamp, hpa_current_replicas, hpa_desired_replicas, hpa_target_cpu_percent)
                   VALUES (%s, %s, %s, %s)""",
                (datetime.now(), hpa_status["current_replicas"], hpa_status["desired_replicas"], hpa_status["target_cpu_percent"]),
            )
        else:
            for row in pod_rows:
                cur.execute(
                    """INSERT INTO system_metrics
                       (timestamp, pod_name, cpu_millicores, memory_mb,
                        hpa_current_replicas, hpa_desired_replicas, hpa_target_cpu_percent)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        datetime.now(), row["pod_name"], row["cpu_millicores"], row["memory_mb"],
                        hpa_status["current_replicas"], hpa_status["desired_replicas"], hpa_status["target_cpu_percent"],
                    ),
                )
    conn.commit()


def main():
    print(f"VibeStream Cluster Metrics Collector başladı (namespace={NAMESPACE}, hpa={HPA_NAME}, interval={INTERVAL_SECONDS}s)")
    conn = get_pg_connection()
    while True:
        pod_rows = get_pod_metrics()
        hpa_status = get_hpa_status()
        try:
            write_metrics(conn, pod_rows, hpa_status)
            print(
                f"{datetime.now().strftime('%H:%M:%S')} - {len(pod_rows)} pod ölçümü + "
                f"HPA {hpa_status['current_replicas']}/{hpa_status['desired_replicas']} replica yazıldı."
            )
        except Exception as e:
            print(f"[HATA] Postgres'e yazılamadı: {e}")
            conn.rollback()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

# --- ALTERNATİF: kubectl binary'siz Python Kubernetes client ---------------
# Eğer worker imajında kubectl binary'si yoksa (ve eklemek istemiyorsanız),
# `pip install kubernetes` ile resmi Python client'ı kullanıp aynı veriyi
# şu şekilde çekebilirsiniz:
#
#   from kubernetes import client, config
#   config.load_incluster_config()
#   metrics_api = client.CustomObjectsApi()
#   pods = metrics_api.list_namespaced_custom_object(
#       "metrics.k8s.io", "v1beta1", NAMESPACE, "pods")
#   autoscaling_api = client.AutoscalingV1Api()
#   hpa = autoscaling_api.read_namespaced_horizontal_pod_autoscaler(HPA_NAME, NAMESPACE)
#
# Bu, ayrı bir bağımlılık gerektirdiği için varsayılan olarak kubectl
# subprocess yaklaşımı seçildi (daha az bağımlılık, daha kolay debug).
