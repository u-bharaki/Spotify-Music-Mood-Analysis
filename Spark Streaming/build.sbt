name := "VibeStream"
version := "1.0"
scalaVersion := "2.12.18"

val sparkVersion = "3.5.0"

libraryDependencies ++= Seq(
  // Spark Temel Kütüphaneleri
  "org.apache.spark" %% "spark-core" % sparkVersion,
  "org.apache.spark" %% "spark-sql" % sparkVersion,

  // Kafka'dan veri okumak için
  "org.apache.spark" %% "spark-sql-kafka-0-10" % sparkVersion,

  // Redis'e bağlanıp veri zenginleştirmek için (Jedis)
  "redis.clients" % "jedis" % "4.4.3",

  // PostgreSQL'e veriyi basmak için JDBC Driver
  "org.postgresql" % "postgresql" % "42.6.0",

  "com.fasterxml.jackson.module" %% "jackson-module-scala" % "2.15.2" // JSON parse için
)
)

