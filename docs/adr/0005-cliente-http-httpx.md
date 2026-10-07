# ADR-0005: Cliente HTTP con HTTPX para Ingesta y Resiliencia

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Autor:** Juan González

---

## 1. Contexto y Planteo del Problema
El módulo de extracción (`extract.py`) del pipeline ETL es la puerta de entrada de todos los datos del sistema. Debe conectarse a los endpoints públicos de la AFA para descargar payloads periódicos de estadísticas (archivos JSON de hasta ~1 MB).

Se requiere un cliente HTTP en Python que:
1. Soporte protocolos web modernos (HTTP/1.1 y HTTP/2).
2. Tenga gestión estricta y transparente de timeouts (para no dejar procesos o contenedores colgados indefinidamente ante caídas de red).
3. Permita configurar headers personalizados (`User-Agent`, compresión `gzip/brotli`).
4. Ofrezca una interfaz limpia y testeable, con posibilidad de evolucionar a concurrencia asíncrona (`asyncio`) si en el futuro se descargan decenas de endpoints en paralelo.

---

## 2. Factores Decisorios (Architecture Drivers)
* **Robustez y Manejo de Timeouts:** Prevenir fallos silenciosos y sockets colgados en el servidor headless *Argos*.
* **Protocolos Modernos:** Soporte nativo de HTTP/2 para multiplexación de conexiones.
* **Evolución Futura:** Misma API para peticiones síncronas y asíncronas sin necesidad de migrar de biblioteca.
* **Mantenibilidad y Ergonomía:** API idiomática y moderna en Python 3.11+.

---

## 3. Alternativas Evaluadas

### Opción 1: Biblioteca Estándar (`urllib.request`)
* **Pros:** Sin dependencias externas añadidas al `requirements.txt`.
* **Cons:** API arcaica de bajo nivel, no maneja pooling de conexiones HTTP de forma transparente, soporte nulo de HTTP/2 y código verboso y engorroso para configurar headers, redirecciones y timeouts.

### Opción 2: `requests`
* **Pros:** Biblioteca histórica más utilizada y testeada de la comunidad de Python.
* **Cons:**
  * No tiene soporte para HTTP/2.
  * Por defecto no fuerza timeouts (riesgo crítico de procesos bloqueados indefinidamente).
  * Es estrictamente síncrona y bloqueante; si el pipeline escala a descargar múltiples endpoints concurrentes, obliga a reescribir todo el cliente con otra biblioteca (ej. `aiohttp`).

### Opción 3: `aiohttp`
* **Pros:** Excelente rendimiento en pipelines puramente asíncronos.
* **Cons:** Obliga a estructurar todo el módulo alrededor de un event loop de `asyncio`, añadiendo complejidad sintáctica innecesaria para un pipeline secuencial simple por lotes (violación del principio KISS).

### Opción 4: `httpx` (Seleccionada)
* **Pros:**
  * **Soporte unificado síncrono y asíncrono:** Mismo cliente y semántica (`httpx.Client` vs `httpx.AsyncClient`).
  * **Soporte HTTP/2:** Permite multiplexación y renegociación más eficiente con servidores CDN (Cloudflare).
  * **Timeouts estrictos por diseño:** Fuerza la configuración de límites de conexión, lectura y escritura, garantizando que el contenedor nunca se congele.
  * Compatibilidad total con la API familiar de `requests`.
* **Cons:** Biblioteca de terceros adicional (`httpx>=0.27.0`).

---

## 4. Decisión Tomada
Se adopta **HTTPX** como el cliente HTTP oficial para la capa de extracción del ETL (`etl/src/extract.py`). Se configura una sesión de cliente con control estricto de timeouts, redirecciones automáticas y headers de identificación del proyecto.

---

## 5. Consecuencias y Trade-offs

### Consecuencias Positivas
* El proceso de ingesta es resiliente a interrupciones de red y latencias anómalas.
* Se aprovechan optimizaciones de HTTP/2 soportadas por la infraestructura de entrega de AFA.
* Si el proyecto evoluciona hacia la ingesta paralela de partidos o actas en tiempo real, la migración a `asyncio` no requerirá cambiar la librería.

### Limitaciones Aceptadas
* Requiere mantener la dependencia en `requirements.txt`.
