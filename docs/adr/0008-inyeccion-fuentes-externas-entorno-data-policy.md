# ADR-0008: Inyección de Fuentes Externas vía Entorno y Política de Uso de Datos

* **Estado:** Aceptado
* **Fecha:** 2026-10-08
* **Autor:** Juan González

---

## 1. Contexto y Planteo del Problema
El pipeline ingiere datos desde endpoints web de estadísticas deportivas públicas. Originalmente, la URL del endpoint se encontraba declarada como un valor por defecto (*hardcoded*) dentro del código fuente (`etl/src/config.py`).

Mantener URLs de orígenes externos directamente en el código de un repositorio público presenta serios inconvenientes:
1. **Acoplamiento de Entorno y Falta de Portabilidad:** Imposibilita apuntar el pipeline hacia servidores de pruebas locales (*mock servers* o *stubs*) durante la ejecución de tests automatizados (CI/CD) sin modificar el código fuente.
2. **Higiene y Exposición Pública:** Expone rutas de infraestructura externa en repositorios públicos indexables por motores de búsqueda.
3. **Gobierno y Claridad Legal:** El proyecto carecía de una política explícita de uso ético, no comercial y educativo sobre los datos fácticos deportivos procesados.

---

## 2. Factores Decisorios (Architecture Drivers)
* **Desacople de Fuentes (Source Agnosticism):** El código debe ser agnóstico del dominio exacto del servidor proveedor.
* **Seguridad y Doce Factores (Factor III - Configuración):** Separación estricta entre código base y configuración dependiente del entorno.
* **Cumplimiento Ético y Legal:** Establecer un descargo de responsabilidad claro (*Data Disclaimer*) que enmarque el proyecto en el ámbito educativo y de investigación.

---

## 3. Alternativas Evaluadas

### Opción 1: Mantener la URL en Código (`config.py`)
* **Pros:** Cero configuración inicial requerida tras clonar el repositorio.
* **Cons:** Violación de principios de 12-Factor App; dificultad para testing con mocks; exposición de endpoints de infraestructura externa en Git.

### Opción 2: Archivo de Configuración Versionado (`config.json` o `config.yaml`)
* **Pros:** Separa la configuración del código Python.
* **Cons:** Si el archivo se comitea en Git, persiste el problema de exposición pública; si se ignora en Git, duplica el mecanismo de variables de entorno ya provisto por `.env`.

### Opción 3: Inyección Estricta por Variables de Entorno (`.env`) + Data Disclaimer (Seleccionada)
* **Pros:**
  * En `config.py`, la URL se obtiene estrictamente de `os.getenv("AFA_PLAYERS_STATS_URL")`. Si no está configurada, el pipeline falla de forma controlada indicando la variable requerida.
  * En `.env.example` se documenta la variable mediante un marcador abstracto de plantilla (`https://<data-provider-domain>/path/to/stats.json`).
  * En el `.env` local se inyecta la URL activa.
  * Se incorpora la cláusula formal de *Data Disclaimer* en la documentación pública.
* **Cons:** Requiere configurar el archivo `.env` antes de ejecutar la primera extracción.

---

## 4. Decisión Tomada
Se decide:
1. Eliminar cualquier URL externa hardcodeada en el código fuente.
2. Gestionar la fuente de datos exclusivamente a través de la variable de entorno `AFA_PLAYERS_STATS_URL`.
3. Incorporar la sección **Descargo de Responsabilidad y Términos de Uso (Data Disclaimer)** en `README.md`, aclarando la finalidad exclusivamente educativa y no comercial del proyecto.

---

## 5. Consecuencias y Trade-offs

### Consecuencias Positivas
* El código fuente es 100% limpio y portable, apto para conectarse a mocks o entornos de CI sin tocar Python.
* Higiene total en el repositorio público de GitHub.
* Protección legal y ética documentada formalmente para evaluadores y reclutadores.

### Limitaciones Aceptadas
* El desarrollador debe asegurarse de que `.env` contenga la variable definida antes de ejecutar la ingesta.
