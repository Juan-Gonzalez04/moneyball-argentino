# ADR-0007: Estrategia de Claves Primarias: Claves Naturales de AFA vs. Claves Subrogadas

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Autor:** Juan González

---

## 1. Contexto y Planteo del Problema
En el modelado relacional de PostgreSQL para las tablas `players` y `teams`, se debe definir la estrategia de generación y asignación de Claves Primarias (Primary Keys - PK).

Existen dos enfoques principales en la ingeniería de bases de datos:
1. **Claves Naturales (Domain/External Keys):** Utilizar los identificadores numéricos provistos directamente por el origen de datos oficial (AFA / DataFactory).
2. **Claves Subrogadas (Surrogate Keys):** Generar claves artificiales independientes del dominio, como enteros autoincrementales (`SERIAL` / `BIGSERIAL`) o identificadores únicos globales (`UUID`).

Se debe evaluar el impacto de esta decisión en la simplicidad del código de ingesta, el rendimiento de los índices B-Tree en hardware acotado (*Argos*) y la resiliencia ante eventuales cambios en el proveedor de datos.

---

## 2. Factores Decisorios (Architecture Drivers)
* **Simplicidad y Principio KISS:** Evitar capas innecesarias de mapeo y tablas intermediarias de equivalencias.
* **Eficiencia de Almacenamiento e Índices (Nodo Argos):** Minimizar el tamaño en disco y memoria RAM de los índices de claves foráneas.
* **Integridad Referencial:** Garantizar que las relaciones entre jugadores y clubes se resuelvan de forma inmediata y determinista durante la carga.

---

## 3. Alternativas Evaluadas

### Opción 1: Claves Subrogadas con UUID (`uuid_generate_v4()`)
* **Pros:** Desacople absoluto de cualquier proveedor externo. Los IDs son inmutables para siempre y permiten fusionar múltiples orígenes de datos sin colisiones.
* **Cons:**
  * Mayor consumo de memoria: un UUID ocupa 16 bytes por fila frente a los 4 bytes de un entero estándar (`INT`), aumentando el tamaño de los índices B-Tree en memoria RAM por un factor de 4.
  * Mayor complejidad en el ETL: antes de insertar un jugador, el pipeline debe consultar a la base de datos cuál es el UUID asignado a su `team_id`, requiriendo consultas adicionales de lectura previa (*lookup queries*).

### Opción 2: Claves Subrogadas con Enteros Autoincrementales (`SERIAL`)
* **Pros:** Compacto (4 bytes), desacoplado del ID externo.
* **Cons:** Requiere mantener una columna adicional `afa_id INT UNIQUE` y ejecutar lookups en cada lote de carga para resolver los IDs internos de las claves foráneas, ralentizando la ingesta batch.

### Opción 3: Claves Naturales Directas de AFA (`team_id INT`, `player_id INT`) (Seleccionada)
* **Pros:**
  * **Cero sobrecarga de lookups:** Como el JSON de AFA ya entrega `teamId: 124` en el objeto del jugador, la inserción relacional es directa e inmediata sin lecturas previas.
  * **Índices ultra compactos:** Las claves primarias y foráneas de 4 bytes (`INT`) garantizan que los índices B-Tree queden completamente cacheados en los 128 MB de `shared_buffers` de PostgreSQL en Argos.
* **Cons:** Acoplamiento con el sistema de numeración del proveedor oficial de la liga argentina.

---

## 4. Decisión Tomada
Se decide utilizar los **identificadores numéricos de AFA como Claves Primarias naturales directas** en `teams` (`team_id INT PRIMARY KEY`) y `players` (`player_id INT PRIMARY KEY`)**.

---

## 5. Consecuencias y Estrategia de Migración Futura

### Consecuencias Positivas
* Se elimina la necesidad de tablas de traducción o lookups previos durante el `load.py`.
* Máxima velocidad de carga batch y mínimo consumo de memoria en el servidor físico.
* Trazabilidad directa e intuitiva entre los JSONs crudos descargados y las filas en PostgreSQL.

### Disparador de Migración (*Migration Trigger*)
Si en fases futuras el proyecto evoluciona hacia una plataforma **multi-proveedor** (por ejemplo, ingesta simultánea de datos de *Transfermarkt*, *Wyscout* o *Sofascore*):
1. Se emitirá un nuevo ADR que reemplazará a este registro.
2. Se añadirá una columna subrogada `id BIGSERIAL` o `id UUID` como PK interna.
3. El `team_id` actual de AFA se conservará como una columna de mapeo externa (`afa_team_id INT UNIQUE`).
