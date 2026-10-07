# ADR-0002: Persistencia Relacional Híbrida con PostgreSQL y JSONB

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Autor:** Juan González

---

## 1. Contexto y Planteo del Problema
El sistema procesa información de jugadores, clubes, contratos y métricas de rendimiento deportivo. 
Las fuentes de datos externas (APIs de AFA) entregan estructuras JSON jerárquicas y propensas a cambios inesperados de esquema con el paso del tiempo.

Paralelamente, el hardware de producción (*Argos*) cuenta con 4 GB de memoria RAM compartida entre el sistema operativo y todos los servicios. Traer conjuntos masivos de datos a la memoria de Python (Pandas) para realizar transformaciones analíticas complejas (percentiles por posición, rankings, medias ponderadas) generaría picos de consumo de memoria y riesgo de fallos por OOM (*Out Of Memory*).

---

## 2. Factores Decisorios (Architecture Drivers)
* **Integridad Referencial Estricta:** El modelo de dominio de fútbol requiere relaciones consistentes (jugadores vinculados a equipos válidos, goles asociados a partidos reales).
* **Resiliencia ante Cambios de Esquema:** Capacidad de almacenar los datos crudos originales sin perder trazabilidad histórica ante eventuales cambios en las APIs de origen.
* **Pushdown de Cómputo Analítico:** Delegar agregaciones complejas y cálculos estadísticos directamente al motor de base de datos para preservar la RAM del host.
* **Idempotencia:** Posibilidad de ejecutar reintentos masivos sin duplicar filas ni requerir lecturas previas complejas.

---

## 3. Alternativas Evaluadas

### Opción 1: MongoDB (NoSQL Document Store)
* **Pros:** Excelente flexibilidad para almacenar JSON crudos sin definición previa de esquema.
* **Cons:** Pobre manejo de integridad referencial relacional estricta, mayor consumo de memoria RAM por diseño del motor WiredTiger y dificultad para ejecutar consultas analíticas avanzadas de series temporales y percentiles deportivos sin pipelines de agregación excesivamente verbosos.

### Opción 2: SQLite
* **Pros:** Embebida, sin necesidad de proceso servidor, huella de memoria minúscula.
* **Cons:** Concurrencia limitada (bloqueo a nivel de archivo en escrituras concurrentes), soporte limitado para operaciones analíticas complejas y menor optimización para volúmenes medianos/grandes con múltiples clientes simultáneos.

### Opción 3: PostgreSQL 15 (Seleccionada)
* **Pros:**
  * **Soporte Híbrido Relacional + Documental:** Permite estructurar tablas normalizadas fuertemente tipadas con índices B-Tree, mientras preserva el payload original de la API en columnas de tipo `JSONB`.
  * **Capacidades Analíticas Avanzadas:** Funciones de ventana (*Window Functions*: `PERCENT_RANK()`, `NTILE()`, `ROW_NUMBER()`), expresiones de tabla comunes (CTEs) e índices GIN sobre JSONB.
  * **Operaciones de Upsert Nativas:** Soporte directo de `ON CONFLICT (...) DO UPDATE` para garantizar cargas idempotentes.
  * **Eficiencia de Recursos:** Optimizado en C; maneja buffers compartidos de memoria de forma predecible y configurable (`shared_buffers = 128MB`).
* **Cons:** Requiere mantenimiento de esquema y diseño de migraciones formales.

---

## 4. Decisión Tomada
Se adopta **PostgreSQL 15 (Alpine)** como motor central de almacenamiento y computación analítica. Se implementa una estrategia de persistencia híbrida:
1. Columnas relacionales estructuradas para filtros frecuentes y claves de relación (`player_id`, `team_id`, `age`, `height`).
2. Columna `raw_payload JSONB` en cada tabla para auditar el objeto JSON original y permitir futuras explotaciones sin necesidad de re-extraer datos históricos.

---

## 5. Consecuencias y Trade-offs

### Consecuencias Positivas
* El ETL puede reejecutarse indefinidamente de forma segura e idempotente.
* Los cálculos de percentiles y scouting se procesan en milisegundos en la base de datos sin saturar la RAM de Python.
* Auditoría completa y reproducción histórica asegurada.

### Limitaciones Aceptadas
* Exige definir y mantener DDLs formales (`sql/schema.sql`).
* Requiere contemplar configuraciones específicas en puntos de montaje Docker (ej. definir subdirectorio `PGDATA` para evitar colisiones con archivos del sistema de archivos como `.gitkeep` o `lost+found`).
