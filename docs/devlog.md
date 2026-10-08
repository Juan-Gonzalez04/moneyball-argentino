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

