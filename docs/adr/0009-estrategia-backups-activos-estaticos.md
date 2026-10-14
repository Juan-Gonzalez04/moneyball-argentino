# ADR-0009: Estrategia de Respaldo (Backup), Recuperación y Almacenamiento de Activos

* **Estado:** Aceptado
* **Fecha:** 2026-10-08
* **Autor:** Juan González

---

## 1. Contexto y Planteo del Problema
En el diseño de la plataforma MoneyBall / Argos surgen dos decisiones críticas vinculadas a la persistencia y la seguridad operativa:
1. **Almacenamiento de Activos Visuales (Escudos de Clubes):** Determinar si las imágenes deben persistirse codificadas en Base64/BYTEA dentro de PostgreSQL o como archivos estáticos en el sistema de archivos del host.
2. **Estrategia de Respaldos (Backups & Disaster Recovery):** Evaluar cómo proteger la información persistida, analizando las vulnerabilidades de los volcados en texto plano (`.sql`) frente a los estándares de la industria y la capacidad de reconstrucción del sistema.

---

## 2. Factores Decisorios (Architecture Drivers)
* **Eficiencia de Recursos (Nodo Argos - 4 GB RAM):** No saturar los buffers de memoria de PostgreSQL (`shared_buffers`) con datos binarios no relacionales.
* **Seguridad y Confidencialidad de Backups:** Evitar la exposición de información en archivos de texto plano sin compresión ni cifrado.
* **Tiempo de Recuperación (RTO - Recovery Time Objective):** Capacidad de restaurar la base de datos de manera rápida, selectiva y multihilo.
* **Reproducibilidad (Bronze Layer Replayability):** Garantizar la reconstrucción determinista de la base de datos a partir del histórico de datos crudos inmutables.

---

## 3. Alternativas Evaluadas

### A. Almacenamiento de Activos: Base64 en BD vs. Archivos Estáticos
* **Opción A1: Base64 / BYTEA en PostgreSQL:**
  * *Cons:* Añade un 33% de sobrecarga de almacenamiento por codificación ASCII; contamina el buffer cache de la base de datos en lecturas; anula el sistema de caché nativo del navegador web (`Cache-Control`, `ETag`); infla innecesariamente el tamaño de los backups.
* **Opción A2: Archivos Estáticos en Disco (`dashboard/assets/teams/{team_id}.png`) (Seleccionada):**
  * *Pros:* Delegación eficiente de I/O al sistema de archivos de Linux (ext4); memoria de PostgreSQL dedicada exclusivamente a índices B-Tree y consultas analíticas; resolución determinista por convención sobre clave primaria (`{team_id}.png`).

### B. Estrategia de Backups: Dump en Texto Plano vs. Formato Custom / Replay
* **Opción B1: Volcado en Texto Plano (`pg_dump` estándar `.sql`):**
  * *Riesgos:* No está comprimido (consume 5 a 10 veces más disco); no posee cifrado (cualquier acceso no autorizado permite leer tablas completas con un visor de texto); restauración rígida y secuencial (no permite restauraciones en paralelo ni por tabla específica).
* **Opción B2: Formato Custom Binario Comprimido (`pg_dump -Fc`) + Cifrado en Reposo (Seleccionada para la BD):**
  * *Pros:* Formato binario nativo no legible directamente; compresión integrada de bajo consumo de disco; permite restauraciones multihilo y selectivas con `pg_restore -j 4 -t <tabla>`; canalizable (*piped*) hacia herramientas de cifrado simétrico (GPG/age).
* **Opción B3: Reconstrucción desde Capa Cruda Inmutable (Lakehouse Replayability) (Eje Central de la Plataforma):**
  * *Pros:* Como el módulo `extract.py` persiste snapshots inmutables con hash SHA-256 en la capa Bronze (`/data/scouting/raw/`), la pérdida catastrófica de PostgreSQL puede mitigarse reejecutando el pipeline ETL sobre los datos crudos, reconstruyendo el 100% del estado relacional de forma determinista e idempotente.

---

## 4. Decisión Tomada
1. **Activos:** Los escudos e imágenes se almacenan exclusivamente en el sistema de archivos (`dashboard/assets/teams/`), desestimando Base64 en la base de datos.
2. **Backups de Base de Datos:** Los respaldos periódicos de PostgreSQL se realizan utilizando el **formato Custom comprimido de PostgreSQL (`pg_dump -Fc`)**, canalizado opcionalmente a cifrado con GPG para almacenamiento secundario.
3. **Resiliencia Primaria:** Se adopta el principio de **Replayability**: la capa Bronze inmutable actúa como la fuente canónica de verdad histórica para recuperación ante desastres (*Disaster Recovery*).

---

## 5. Consecuencias y Trade-offs

### Consecuencias Positivas
* Rendimiento óptimo en el hardware de Argos: Postgres solo almacena y procesa tipos de datos relacionales puros.
* Backups compactos, restaurables en paralelo y protegidos contra accesos no autorizados.
* Resiliencia total ante pérdida de la base de datos gracias a la inmutabilidad de la capa cruda.

### Limitaciones Aceptadas
* Requiere mantener el script de backup utilizando `pg_restore` en lugar de una redirección básica de shell (`psql < file.sql`).
