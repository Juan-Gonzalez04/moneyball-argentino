# Cuaderno de Bitácora Técnico (Engineering Devlog)

Este documento registra de manera cronológica los hitos, desafíos técnicos, decisiones en caliente y lecciones aprendidas durante la construcción de la plataforma **MoneyBall Argentino / Argos**.

> [!TIP]
> **Para qué sirve esta bitácora:** En un proceso de selección técnica, los evaluadores buscan entender **cómo pensé ante problemas imprevistos** y no solo ver el resultado final pulido. Este log refleja la capacidad de diagnóstico, causa raíz (*Root Cause Analysis*) y rigor de ingeniería.

---

## Estructura Estándar de una Entrada

Cada sesión o hito significativo debe documentarse con el siguiente formato:

```markdown
### [YYYY-MM-DD] - [Título del Hito o Desafío]
* **Fase / Módulo:** (ej. Fase 1 / Infraestructura o Ingesta)
* **Objetivo de la sesión:** Breve resumen de lo que se buscaba lograr.
* **Desafío / Bloqueante encontrado:** Descripción precisa del error o comportamiento inesperado.
* **Análisis de Causa Raíz (RCA):** Por qué sucedió (detalles de sistema, red, tipos, etc.).
* **Solución Aplicada:** Qué cambio técnico resolvió el problema.
* **Lección / Buena Práctica:** Qué principio técnico se consolidó.
* **Próximos Pasos:** Siguiente tarea inmediata.
```

---

## Entradas del Registro

### [2026-10-07] - Resurrección del Proyecto y Abstracción de Almacenamiento Portable
* **Fase / Módulo:** Fase 0 & 1 / Infraestructura y Entorno Local
* **Objetivo de la sesión:** Sincronizar el repositorio contra `origin/main`, crear rama de trabajo limpia para la Fase 1 (`feature/fase-1-vertical-slice`) y garantizar que el stack Docker corra de manera idéntica tanto en la máquina de desarrollo (`notebook`) como en el servidor bare-metal (`Argos`).
* **Desafío / Bloqueante encontrado:** El archivo `docker-compose.yml` original contenía rutas absolutas hardcodeadas hacia `/data/scouting/...`. En la notebook de desarrollo personal, `/data` no existe como partición montada en la raíz del sistema, lo que impedía levantar los contenedores sin privilegios de superusuario o provocaría errores de permisos.
* **Análisis de Causa Raíz (RCA):** Falta de desacople entre la configuración del host y el manifiesto declarativo de Docker. El servidor Argos posee un disco HDD secundario dedicado montado en `/data`, pero una estación de trabajo de desarrollo debe operar de manera autocontenida sin ensuciar la raíz del SO.
* **Solución Aplicada:** 
  1. Se introdujo la variable de entorno `DATA_PATH` en `.env.example` y `.env` con valor `./data` para desarrollo local y `/data/scouting` para producción.
  2. Se actualizaron los volúmenes en `docker-compose.yml` utilizando interpolación: `${DATA_PATH:-./data}/...`.
  3. Se crearon las carpetas locales con sus respectivos `.gitkeep` y se actualizaron las reglas en `.gitignore`.
* **Lección / Buena Práctica:** Seguir los principios de *The Twelve-Factor App* (Factor III: Configuración en el entorno) para que el software sea 100% portable entre cualquier entorno de ejecución.
* **Próximos Pasos:** Verificar la inicialización del motor relacional PostgreSQL.

---

### [2026-10-07] - Diagnóstico y Fix de Inicialización de PostgreSQL en Volúmenes Montados
* **Fase / Módulo:** Fase 1 / Base de Datos & Persistencia
* **Objetivo de la sesión:** Levantar el servicio `afa-postgres` y verificar la ejecución automática del script `sql/schema.sql` en el primer arranque.
* **Desafío / Bloqueante encontrado:** Al ejecutar `docker compose up -d`, el contenedor `afa-postgres` falló inmediatamente con código de salida `1` (`Exited (1)`). Los logs arrojaron el siguiente error:
  ```text
  initdb: error: directory "/var/lib/postgresql/data" exists but is not empty
  initdb: detail: It contains a dot-prefixed/invisible file, perhaps due to it being a mount point.
  initdb: hint: Using a mount point directly as the data directory is not recommended.
  ```
* **Análisis de Causa Raíz (RCA):** 
  1. La herramienta `initdb` de PostgreSQL exige por seguridad que el directorio de datos destino esté completamente vacío al inicializar un clúster por primera vez.
  2. Como habíamos colocado un archivo `.gitkeep` en `data/database/` para mantener la estructura en Git, `initdb` detectó el archivo oculto y abortó la inicialización.
  3. *Impacto colateral en producción:* En el disco formateado en ext4 de Argos, este mismo problema ocurriría de forma inevitable debido a la carpeta oculta `lost+found` que crea Linux en el punto de montaje.
* **Solución Aplicada:**
  1. Se configuró la variable de entorno `PGDATA: /var/lib/postgresql/data/pgdata` en el servicio `postgres` de `docker-compose.yml`.
  2. De esta forma, PostgreSQL crea su clúster dentro del subdirectorio aislado `pgdata/`, conviviendo pacíficamente con archivos ocultos o de sistema presentes en la raíz del volumen montado.
  3. Se reiniciaron los servicios y se constató en los logs la correcta ejecución del DDL:
     `CREATE EXTENSION`, `CREATE TABLE (teams, players, player_goals)` y la creación de los índices.
* **Lección / Buena Práctica:** Nunca montar el directorio raíz de datos de un motor de bases de datos directamente sobre un punto de montaje o directorio con metadatos del host; utilizar siempre un subdirectorio gestionado mediante variables de configuración oficiales (`PGDATA`).
* **Próximos Pasos:** Definir contratos de datos con Pydantic v2 a partir del análisis del endpoint.

---

### [2026-10-07] - Extracción Inmutable y Contratos de Datos con Patrón de Cuarentena
* **Fase / Módulo:** Fase 1 / ETL: Ingesta (Extract) y Validación (Contracts)
* **Objetivo de la sesión:** Implementar `extract.py` para capturar el snapshot inmutable con firma SHA-256 en `data/raw/`, y `schemas.py` con Pydantic v2 para validar integridad estructural sin frenar el flujo ante anomalías.
* **Desafío / Bloqueante encontrado:** 
  1. Al correr `python -m etl.src.extract` dentro del contenedor `afa-etl`, se produjo un `ModuleNotFoundError: No module named 'etl'` porque la ruta del paquete no estaba montada ni en `PYTHONPATH`.
  2. Los diccionarios de estadísticas (`goals`, `shots`, `cards`) presentan alta dispersión: solo contienen jugadores con registros no nulos. Validar estrictamente un modelo único unificado para cada jugador fallaba con `KeyError` o errores de campos faltantes.
* **Análisis de Causa Raíz (RCA):**
  1. El contenedor `afa-etl` original solo montaba `./scripts:/app/scripts`. Hacía falta montar `./etl:/app/etl` y declarar `ENV PYTHONPATH=/app` en el Dockerfile.
  2. El payload utiliza mapas desacoplados indexados por ID de jugador (`{ "261314": { ... } }`) en vez de objetos de jugador consolidados.
* **Solución Aplicada:**
  1. Actualicé `Dockerfile` y `docker-compose.yml` para incorporar el paquete modular `etl` y `PYTHONPATH`.
  2. Diseñé `extract.py` con guardado timestamped (`playersStatsFull_YYYYMMDDTHHMMSSZ.json`) y verificación de integridad SHA-256 (Bronze Layer).
  3. Diseñé `schemas.py` desacoplando contratos para `TeamRawContract`, `PlayerRawContract` y métricas, implementando la función `validate_afa_payload` que aísla registros defectuosos en cuarentena.
  4. Resultado en prueba real con API en vivo: **30/30 equipos válidos**, **790/790 jugadores válidos**, 0 registros en cuarentena y tiempo de validación de 41 milisegundos.
* **Lección / Buena Práctica:** Adoptar el *Quarantine Pattern* en pipelines batch: nunca permitir que un registro defectuoso aislado haga fracasar una ingesta completa de datos.
* **Próximos Pasos:** Implementar `transform.py` y `load.py` para realizar el Upsert idempotente en PostgreSQL.

---

### [2026-10-08] - Completitud del Vertical Slice: Transformación y Carga Idempotente (Upsert)
* **Fase / Módulo:** Fase 1 / ETL: Transformación (Transform), Carga (Load) y Orquestación (Runner)
* **Objetivo de la sesión:** Implementar `transform.py` para normalizar los datos validados a tuplas relacionales y `load.py` para ejecutar la persistencia masiva en PostgreSQL garantizando idempotencia (`ON CONFLICT DO UPDATE`). Conectar el flujo completo en `main.py` y validar la primera consulta de scouting Sub-23.
* **Desafío / Bloqueante encontrado:** Mantener la integridad referencial durante la inserción batch sin violar claves foráneas (`players.team_id -> teams.team_id`) y evitar colisiones de clave primaria al reejecutar el pipeline de forma sucesiva.
* **Análisis de Causa Raíz (RCA):** Si los jugadores se insertan antes de los equipos o si un jugador tiene un `teamId` inexistente, PostgreSQL aborta la transacción completa. Además, en un pipeline batch, múltiples ejecuciones sobre el mismo snapshot generan errores de unicidad si se usan sentencias `INSERT` estándar.
* **Solución Aplicada:**
  1. Diseñé `transform.py` con casteo seguro de fechas (`parse_date`), saneamiento de nombres y empaquetado de payloads originales a cadenas JSON para las columnas `JSONB`.
  2. Implementé `load.py` con `psycopg2.extras.execute_values` y orden estricto de carga: 1° `teams`, 2° `players`, 3° `player_goals` y `player_stats`.
  3. Apliqué sentencias `ON CONFLICT (...) DO UPDATE` en todas las tablas para garantizar **100% de idempotencia**.
  4. Resultados empíricos:
     - Pipeline ejecutado en **0.82 segundos**.
     - **30 equipos cargados**, **790 jugadores cargados**, **213 goleadores registrados**.
     - Segunda corrida de prueba: **0.63 segundos**, 0 errores y 0 duplicados.
     - Consulta SQL Sub-23 ejecutada con éxito (detectando a Máximo Palazzo, Juan Pablo Ludueña, Josué Reinatti, Luciano Vallejo y Thiago Silvero como líderes de minutos).
* **Lección / Buena Práctica:** Diseñar pipelines batch con idempotencia nativa a nivel de motor de base de datos (`ON CONFLICT`) para tolerar reintentos automáticos sin generar estados corruptos o duplicados.
* **Próximos Pasos:** Formalizar política de backups, estrategia de activos estáticos e integración con visualización en Streamlit.

---

### [2026-10-08] - Seguridad de Respaldos, Disaster Recovery y Gestión de Activos Estáticos
* **Fase / Módulo:** Arquitectura, Seguridad de Datos & Activos (ADR-0009)
* **Objetivo de la sesión:** Analizar las vulnerabilidades de los respaldos en texto plano (`.sql`) frente a estándares de la industria (cifrado, compresión, PITR) y resolver la arquitectura de almacenamiento para escudos de clubes y fotos de futbolistas sin penalizar los recursos de hardware del nodo *Argos* (4 GB RAM).
* **Desafío / Análisis Crítico:**
  1. **Inseguridad de `.sql` en texto plano:** Los dumps sin compresión ni cifrado exponen datos crudos a cualquier lectura no autorizada, consumen 5-10x más almacenamiento y requieren restauraciones secuenciales lentas.
  2. **Sobrecarga de Base64 en BD:** Almacenar imágenes en columnas `BYTEA` o Base64 dentro de PostgreSQL añade un 33% de sobrecarga por encoding, satura `shared_buffers` desplazando datos relacionales e índices analíticos, y anula la caché HTTP nativa del navegador.
* **Solución Aplicada:**
  1. Redacté y registré formalmente el **ADR-0009** (*Estrategia de Respaldo, Recuperación y Almacenamiento de Activos*).
  2. Definición del estándar de respaldo: uso del formato binario nativo comprimido de PostgreSQL (`pg_dump -Fc`), canalizable a herramientas de cifrado en reposo (GPG/age), habilitando restauraciones paralelas selectivas (`pg_restore -j 4`).
  3. Establecimiento del principio de **Lakehouse Replayability**: la capa Bronze inmutable (`/data/scouting/raw/`) con firmas SHA-256 sirve como fuente canónica de verdad para reconstruir el 100% de la base relacional de forma determinista ante desastres.
  4. Desacople de multimedia: los escudos se gestionan como archivos PNG estáticos en disco (`dashboard/assets/teams/{team_id}.png`), descargados programáticamente vía API de Wikimedia Commons.
* **Lección / Buena Práctica:** Separar con rigor el plano relacional/analítico del almacenamiento de objetos estáticos. En entornos productivos, los respaldos jamás deben persistirse en texto plano sin cifrado ni control de acceso estricto.
* **Próximos Pasos:** Implementar `scripts/fetch_team_logos.py` para poblar los activos estáticos y construir el dashboard interactivo de scouting en Streamlit (Fase 4).

---

### [2026-10-08] - Fase 4: Implementación del Scouting Dashboard en Streamlit & Cierre del Vertical Slice
* **Fase / Módulo:** Fase 4 / Presentación: Dashboard Analítico & Visualización
* **Objetivo de la sesión:** Desarrollar `dashboard/app.py` para conectar la base analítica en PostgreSQL con una interfaz interactiva de scouting deportivo, incorporando filtros Sub-23, métricas avanzadas (minutos, goles, precisión de pases, recuperaciones), escudos oficiales de los 30 clubes y optimización de memoria.
* **Desafío / Bloqueante encontrado:**
  1. Integración de escudos oficiales en el contenedor Docker sin sobrecargar la red ni violar el desacople de almacenamiento.
  2. Al graficar métricas con Vega-Lite / Altair (`st.scatter_chart`), PostgreSQL devolvía los cálculos redondeados como tipos `decimal.Decimal`, generando advertencias de serialización.
* **Solución Aplicada:**
  1. Diseñé `dashboard/app.py` con una arquitectura basada en pestañas (*Radar Sub-23*, *Explorador Analítico*, *Resumen por Clubes* y *Salud del Pipeline*).
  2. Implementé caché con TTL (`@st.cache_data(ttl=60)`) y *Compute Pushdown* en PostgreSQL para proteger la memoria RAM en el servidor *Argos*.
  3. Integré la resolución física de escudos desde `dashboard/assets/teams/{team_id}.png` con fallback elegante para clubes o avatares sin imagen.
  4. Casteé las columnas analíticas derivadas (`pass_accuracy_pct`, `avg_age`) a tipo flotante para visualizaciones vectoriales fluidas en Streamlit.
  5. Actualicé `Dockerfile` y `docker-compose.yml` montando el volumen `./dashboard:/app/dashboard` y redirigiendo el comando de arranque a `dashboard/app.py`.
  6. Verificación empírica: el servicio `afa-streamlit` responde con HTTP 200 en `http://localhost:8501`, cargando los 790 futbolistas y los 30 clubes con sus respectivos escudos.
* **Lección / Buena Práctica:** Separar la lógica pesada de agregación delegándola al motor de base de datos y utilizar almacenamiento en caché en memoria con TTL para brindar interactividad instantánea al usuario sin degradar la infraestructura.
* **Próximos Pasos:** Refinar la interfaz hacia un estilo editorial sobrio, incorporando comparativas contra medias de liga/posición y mapas de dispersión con interpretación táctica.

---

### [2026-10-08] - Refinamiento Editorial del Dashboard: Comparativas Contextuales y Gráficos Interpretados
* **Fase / Módulo:** Fase 4 / Presentación & Analítica Táctica
* **Objetivo de la sesión:** Refactorizar integralmente `dashboard/app.py` para erradicar el ruido visual (emojis, metadatos de infraestructura/hardware), establecer un estilo sobrio y profesional, e incorporar analítica contextual: comparativas de clubes frente a la media de la liga, fichas individuales frente al promedio de su posición y diagramas de dispersión con interpretación explícita de cuadrantes.
* **Desafío / Análisis Crítico:**
  1. Los datos absolutos aislados (ej. "450 pases" o "12 tiros") carecen de valor de scouting si no se contrastan contra una referencia relativa (media de la liga para clubes o media posicional para jugadores).
  2. Los gráficos estándar sin identificación de puntos impedían reconocer a los futbolistas en los extremos de la distribución.
* **Solución Aplicada:**
  1. **Higiene Visual:** Eliminé emojis, referencias a configuraciones de servidor (*Argos*, RAM) y enlaces internos, adoptando un diseño periodístico/editorial limpio con pie de página institucional.
  2. **Pestaña Institucional (Club vs. Media de Liga):** Cada club seleccionado contrasta su edad promedio, goles, tiros al arco y precisión de pase frente al promedio de los 30 clubes de Primera División mediante indicadores de diferencia (*deltas*).
  3. **Ficha de Futbolista (Jugador vs. Media Posicional):** Inspección individual de cualquier jugador con métricas comparadas lado a lado frente a todos los colegas de su misma posición, incluyendo un gráfico de barras comparativo.
  4. **Líderes de Rendimiento:** Tablas directas con los mejores goleadores, mejores pasadores (con umbral de volumen), jugadores con más minutos y recuperadores defensivos.
  5. **Dispersión Táctica en Altair:** Gráficos interactivos con tooltips que revelan nombre, club, posición y métricas exactas al pasar el cursor, complementados con líneas de corte en las medias y un desglose pedagógico de los 4 cuadrantes tácticos.
  6. **Panel de Prospectos Sub-23 & Explorador CSV:** Muestra filtrada de promesas con nota metodológica sobre la necesidad de acumulación temporal para futuras proyecciones, más exportación tabular a CSV.
* **Lección / Buena Práctica:** El valor del dato en analítica deportiva radica en su contexto relativo. Comparar contra la media del rol o de la competición y explicar claramente los cuadrantes de una distribución transforma un simple gráfico en una herramienta de toma de decisiones.
* **Próximos Pasos:** Diseñar las bases para la Fase 2: métricas colectivas avanzadas (`teamsStats.json`) y modelado de ratios Per 90 minutos para el motor de similitud de futbolistas (*Cosine Similarity*).
