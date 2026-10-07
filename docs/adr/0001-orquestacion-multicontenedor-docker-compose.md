# ADR-0001: Orquestación Multicontenedor con Docker Compose

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Autor:** Juan González

---

## 1. Contexto y Planteo del Problema
El sistema MoneyBall / Argos está compuesto por múltiples componentes desacoplados: una base de datos relacional persistente (PostgreSQL), un proceso batch de ingesta y validación (ETL) y una interfaz analítica interactiva (Streamlit).

El entorno de producción es un servidor doméstico dedicado (*Argos*) con recursos acotados de hardware (Intel Core i3-3240 @ 3.4 GHz, 4 GB DDR3, Debian Server headless). Paralelamente, el desarrollo diario ocurre en una notebook personal de trabajo.

Se requiere un mecanismo de orquestación que:
1. Garantice paridad absoluta entre el entorno de desarrollo y el servidor de producción (*"build once, run anywhere"*).
2. Tenga un consumo despreciable de recursos para no asfixiar los 4 GB de RAM del servidor físico.
3. Permita el aislamiento de redes y la persistencia de datos independiente del ciclo de vida de los procesos.

---

## 2. Factores Decisorios (Architecture Drivers)
* **Eficiencia en Hardware (KISS):** Mantener el mínimo overhead de CPU y RAM posible.
* **Reproducibilidad:** Capacidad de levantar la infraestructura completa con un único comando (`docker compose up -d`).
* **Aislamiento de Red:** Blindar la base de datos dentro de una red privada sin necesidad de exponerla a internet.
* **Portabilidad:** Soportar diferencias de puntos de montaje de disco entre la laptop (`./data`) y Argos (`/data/scouting`).

---

## 3. Alternativas Evaluadas

### Opción 1: Kubernetes / k3s / MicroK8s
* **Pros:** Estándar empresarial para orquestación de microservicios, soporte nativo de auto-scaling y despliegues declarativos avanzados.
* **Cons:** Overhead masivo de memoria RAM (el plano de control de k3s/Kubernetes requiere entre 1.5 GB y 2.5 GB solo para mantenerse en ejecución), complejidad accidental excesiva para un despliegue mononodo (single-node) y curvas de aprendizaje desproporcionadas para el alcance del proyecto.

### Opción 2: Scripts manuales de Systemd + Bash en Host Bare-Metal
* **Pros:** Cero overhead de virtualización o capas de red; rendimiento nativo al 100%.
* **Cons:** Alto acoplamiento con las versiones del sistema operativo anfitrión (`Debian`), deriva de configuración (*configuration drift*), dificultad para replicar el entorno en la laptop de desarrollo e inexistencia de aislamiento de dependencias entre proyectos.

### Opción 3: Docker Compose (Seleccionada)
* **Pros:**
  * Overhead despreciable en CPU y RAM (comparte el kernel del host sin plano de control adicional).
  * Manifiesto declarativo estándar (`docker-compose.yml`) versionable en Git.
  * Service Discovery automático por DNS interno (`postgres`, `etl`, `streamlit`).
  * Parametrización trivial mediante variables de entorno (`.env`).
* **Cons:**
  * No apto para clústeres multinodo de alta disponibilidad (limitado a un único host físico).

---

## 4. Decisión Tomada
Se elige **Docker Compose** como orquestador del sistema. Se parametriza la persistencia a través de la variable `DATA_PATH`, permitiendo usar rutas relativas locales en la máquina de desarrollo y rutas absolutas hacia el disco secundario de 2 TB en Argos.

---

## 5. Consecuencias y Trade-offs

### Consecuencias Positivas
* Se logró un arranque y teardown determinista de todo el stack en segundos.
* Se eliminó el riesgo de discrepancias entre librerías locales y el servidor.
* La base de datos queda protegida dentro de una red bridge interna sin exposición innecesaria de puertos al exterior.

### Limitaciones Aceptadas
* El escalado horizontal entre diferentes máquinas requeriría migrar a una tecnología de orquestación distribuida (ej. Nomad o Kubernetes), lo cual excede las necesidades actuales de este proyecto.
