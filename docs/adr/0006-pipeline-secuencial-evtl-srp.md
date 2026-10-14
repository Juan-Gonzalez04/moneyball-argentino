# ADR-0006: Microarquitectura E-V-T-L y Principio de Responsabilidad Única

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Autor:** Juan González

---

## 1. Contexto y Planteo del Problema
En el desarrollo de software de datos tradicional, es común encontrar scripts de ETL monolíticos que ejecutan peticiones HTTP, parsean diccionarios, limpian cadenas de texto e interactúan con la base de datos dentro de un único archivo o bucle `for`.

Este enfoque genera:
1. **Acoplamiento extremo:** Un cambio en los headers HTTP o en una columna de la base de datos obliga a modificar y retestear todo el script.
2. **Imposibilidad de pruebas unitarias aisladas:** No se puede probar la lógica de transformación de fechas o métricas sin levantar una conexión activa de red o de base de datos.
3. **Manejo deficiente de errores:** Las fallas de formato de la API externa abortan las operaciones de base de datos a mitad de camino, dejando transacciones colgadas o estados inconsistentes.

---

## 2. Factores Decisorios (Architecture Drivers)
* **Principio de Responsabilidad Única (Single Responsibility Principle - SRP):** Cada módulo debe tener una única razón para cambiar.
* **Testabilidad Aislada:** Capacidad de escribir pruebas unitarias deterministas sin mocks complejos ni dependencias de infraestructura.
* **Tolerancia a Fallos y Aislamiento de Calidad:** Garantizar que los datos corruptos se filtren antes de tocar la capa de persistencia.

---

## 3. Alternativas Evaluadas

### Opción 1: Script Monolítico de Ingesta (`etl.py`)
* **Pros:** Rápido de escribir inicialmente para prototipos desechables.
* **Cons:** Mantenimiento insostenible, cero reutilización, testeabilidad nula y dificultad para trabajar en equipo.

### Opción 2: Pipeline Clásico de 3 Fases (ETL Tradicional)
* **Pros:** Separa extracción, transformación y carga.
* **Cons:** Agrupa la validación estructural de la API remota dentro de la transformación de negocio. Si la fuente cambia sus tipos de datos, los errores saltan en medio de cálculos matemáticos, dificultando el diagnóstico de causa raíz.

### Opción 3: Pipeline Secuencial E-V-T-L (Seleccionada)
* **Pros:**
  * **Fase 1: Extract (`extract.py`):** Responsabilidad exclusiva de I/O de red, manejo de sesiones HTTP, cálculo de hashes SHA-256 e inmutabilidad en disco (Bronze Layer).
  * **Fase 2: Validate (`schemas.py`):** "Aduana de datos" que aplica Data Contracts estrictos con Pydantic v2 y aísla anomalías en cuarentena sin modificar los datos.
  * **Fase 3: Transform (`transform.py`):** Normaliza y mapea entidades validadas a estructuras relacionales planas (casteo a tipos nativos SQL, manejo de defaults).
  * **Fase 4: Load (`load.py`):** Maneja transacciones, conexiones a PostgreSQL y sentencias `ON CONFLICT DO UPDATE`.
* **Cons:** Mayor cantidad de archivos y modelos intermediarios.

---

## 4. Decisión Tomada
Se adopta el patrón **E-V-T-L (Extract, Validate, Transform, Load)** como microarquitectura oficial del paquete `etl`. Cada fase se implementa en un módulo desacoplado dentro de `etl/src/`, permitiendo testear cada etapa de manera completamente independiente.

---

## 5. Consecuencias y Trade-offs

### Consecuencias Positivas
* Alta modularidad: un cambio en la API de AFA solo impacta en `extract.py` o `schemas.py`. Un cambio en las tablas de Postgres solo impacta en `transform.py` o `load.py`.
* Facilita la suite de pruebas automatizadas con `pytest`.
* Permite auditar y depurar cada fase examinando los artefactos intermedios.

### Limitaciones Aceptadas
* Requiere mantener la coordinación secuencial entre las fases a través de un orquestador liviano (`main.py`).
