#!/usr/bin/env bash
set -e

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ENTRYPOINT] Iniciando contenedor afa-etl..."

# 1. Esperar activamente a que PostgreSQL acepte conexiones
DB_TARGET_HOST="${DB_HOST:-postgres}"
DB_TARGET_PORT="${DB_PORT:-5432}"
DB_TARGET_USER="${DB_USER:-juan}"
DB_TARGET_NAME="${DB_NAME:-afa_data}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ENTRYPOINT] Verificando conexión a PostgreSQL (${DB_TARGET_HOST}:${DB_TARGET_PORT}/${DB_TARGET_NAME})..."

until pg_isready -h "${DB_TARGET_HOST}" -p "${DB_TARGET_PORT}" -U "${DB_TARGET_USER}" -d "${DB_TARGET_NAME}" > /dev/null 2>&1; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ENTRYPOINT] Esperando disponibilidad de PostgreSQL..."
    sleep 2
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ENTRYPOINT] PostgreSQL listo. Ejecutando pipeline ETL inicial..."

# 2. Ejecutar el pipeline E-V-T-L automáticamente
if python -m etl.src.main; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ENTRYPOINT] Pipeline ETL inicial completado con éxito."
else
    EXIT_CODE=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ENTRYPOINT] ADVERTENCIA: Pipeline ETL inicial finalizó con código de error ${EXIT_CODE}."
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ENTRYPOINT] Contenedor en espera activa (daemon) para ejecuciones programadas y tareas bajo demanda."

# 3. Mantener el contenedor en ejecución
exec tail -f /dev/null
