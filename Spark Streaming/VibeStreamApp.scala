import org.apache.spark.sql.{DataFrame, SparkSession, Row, SaveMode}
import org.apache.spark.sql.functions._
import org.apache.spark.sql.types._
import redis.clients.jedis.Jedis
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import java.util.Properties
import java.sql.Timestamp

object VibeStreamApp {
  def main(args: Array[String]): Unit = {

    val spark = SparkSession.builder()
      .appName("VibeStream-Analytics-Engine")
      .master("local[*]")
      .getOrCreate()

    import spark.implicits._

    // KAFKA ŞEMASI
    val logSchema = new StructType()
      .add("ts", StringType)
      .add("ms_played", IntegerType)
      .add("spotify_track_uri", StringType)
      .add("artist_name", StringType)
      .add("shuffle", BooleanType)
      .add("skipped", BooleanType)

    val rawKafkaDF = spark.readStream
      .format("kafka")
      .option("kafka.bootstrap.servers", "kafka:9092")
      .option("subscribe", "vibestream_logs")
      .option("startingOffsets", "latest")
      .load()

    val parsedLogDF = rawKafkaDF
      .selectExpr("CAST(value AS STRING)")
      .select(from_json(col("value"), logSchema).as("log"))
      .select("log.*")

    val dbUrl = "jdbc:postgresql://postgres:5432/vibestream_db"
    val dbProps = new Properties()
    dbProps.put("user", "vibe_admin")
    dbProps.put("password", "vibe_password")
    dbProps.put("driver", "org.postgresql.Driver")

    // Kaydırmalı pencere boyutu (paper'da iddia edilen 1 saatlik pencere)
    val WINDOW_DURATION = "1 hour"

    // MICRO-BATCH İŞLEME VE ANALİTİK
    val query = parsedLogDF.writeStream
      .foreachBatch { (batchDF: DataFrame, batchId: Long) =>
        if (!batchDF.isEmpty) {
          println(s"--- Micro-Batch $batchId İşleniyor ---")

          // 1. ZENGİNLEŞTİRME (Redis ile Hierarchical Fallback: Track -> Artist -> Global)
          val enrichedRDD = batchDF.rdd.mapPartitions { partition =>
            val jedis = new Jedis("redis", 6379)
            val mapper = new ObjectMapper()
            mapper.registerModule(DefaultScalaModule)

            val enrichedRows = partition.map { row =>
              val ts = row.getAs[String]("ts")
              val trackUri = row.getAs[String]("spotify_track_uri")
              val artistName = row.getAs[String]("artist_name")
              val msPlayed = row.getAs[Int]("ms_played")

              var featuresStr = jedis.get(s"track:$trackUri")
              if (featuresStr == null) featuresStr = jedis.get(s"artist:$artistName")
              if (featuresStr == null) featuresStr = jedis.get("global:OTHERS")

              var energy = 0.0
              var valence = 0.0
              var danceability = 0.0

              if (featuresStr != null) {
                try {
                  val featuresMap = mapper.readValue(featuresStr, classOf[Map[String, Any]])
                  energy = featuresMap.getOrElse("energy", 0.0).toString.toDouble
                  valence = featuresMap.getOrElse("valence", 0.0).toString.toDouble
                  danceability = featuresMap.getOrElse("danceability", 0.0).toString.toDouble
                } catch {
                  case _: Exception => // Hatalı JSON'u atla
                }
              }

              // NOT: ts formatı LogStreamer.py tarafından 'yyyy-MM-dd HH:mm:ss' olarak üretiliyor.
              Row(Timestamp.valueOf(ts), trackUri, artistName, msPlayed, energy, valence, danceability)
            }
            jedis.close()
            enrichedRows
          }

          val enrichedSchema = new StructType()
            .add("event_time", TimestampType)
            .add("track_uri", StringType)
            .add("artist_name", StringType)
            .add("ms_played", IntegerType)
            .add("energy", DoubleType)
            .add("valence", DoubleType)
            .add("danceability", DoubleType)

          val enrichedDF = spark.createDataFrame(enrichedRDD, enrichedSchema)
          enrichedDF.cache() // Üç farklı sink için tekrar tekrar kullanılıyor

          // GÖREV 1: Ham zenginleştirilmiş veriyi yaz
          // DİKKAT: bu tablo Postgre/raporUpdated.sql içinde CREATE TABLE ile tanımlı olmalı,
          // aksi halde JDBC "relation does not exist" hatası verir.
          enrichedDF
            .withColumnRenamed("event_time", "timestamp")
            .write.mode(SaveMode.Append)
            .jdbc(dbUrl, "realtime_streaming_events", dbProps)

          // GÖREV 2: Leaderboard — event-time'a göre 1 saatlik pencerelere bölünüyor
          // (Eski versiyonda current_timestamp() = processing time kullanılıyordu,
          //  bu paper'daki "sliding window" iddiasıyla çelişiyordu. Artık event_time kullanılıyor.)
          val leaderboardDF = enrichedDF
            .groupBy(window(col("event_time"), WINDOW_DURATION), col("track_uri"))
            .agg(count("*").as("play_count"))
            .select(
              col("window.start").as("window_start_time"),
              col("track_uri"),
              col("play_count")
            )

          leaderboardDF.write.mode(SaveMode.Append).jdbc(dbUrl, "realtime_leaderboard", dbProps)

          // GÖREV 3: Mood Metrics — aynı şekilde event-time pencereli
          val moodMetricsDF = enrichedDF
            .groupBy(window(col("event_time"), WINDOW_DURATION))
            .agg(
              avg("valence").as("avg_valence"),
              avg("energy").as("avg_energy"),
              count("*").as("total_streams")
            )
            .select(
              col("window.start").as("window_start_time"),
              col("avg_valence"),
              col("avg_energy"),
              col("total_streams")
            )

          moodMetricsDF.write.mode(SaveMode.Append).jdbc(dbUrl, "realtime_mood_metrics", dbProps)

          enrichedDF.unpersist()
          println(s"--- Micro-Batch $batchId Başarıyla Postgres'e Aktarıldı ---")
        }
      }
      .start()

    query.awaitTermination()
  }
}
