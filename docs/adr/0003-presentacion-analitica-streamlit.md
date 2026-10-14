# ADR-0003: Capa de Presentación Analítica con Streamlit

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Autor:** Juan González

---

## 1. Contexto y Planteo del Problema
El objetivo final de MoneyBall Argentino no es solo procesar datos, sino explotarlos visualmente para responder preguntas de negocio y scouting deportivo (detección de jugadores sub-23, comparativas de rendimiento por 90 minutos y perfiles por posición).

Se necesita una interfaz de usuario interactiva y exploratoria que:
1. Permita construir visualizaciones reactivas con bajo costo de desarrollo y mantenimiento.
2. Pueda ejecutarse de forma desatendida y autónoma dentro del servidor Debian headless (*Argos*).
3. Sea completamente versionable como código de texto plano en Git.
4. No desvíe el foco técnico del proyecto hacia el desarrollo frontend tradicional.

---

## 2. Factores Decisorios (Architecture Drivers)
* **Foco en Ingeniería de Datos:** Concentrar el esfuerzo en calidad del dato, modelado SQL y métricas de scouting, evitando la sobrecarga de crear y mantener una arquitectura web completa (SPA + API REST).
* **Compatibilidad de Infraestructura:** Debe ejecutarse nativamente en Linux sin entorno gráfico.
* **Control de Versiones y Auditoría:** Toda la lógica de visualización debe ser legible en diffs de Git y admitir revisiones de código (Pull Requests).
* **Ecosistema Científico / Datos:** Integración directa con Python (`pandas`, `numpy`, bibliotecas de visualización).

---

## 3. Alternativas Evaluadas

### Opción 1: Power BI
* **Pros:** Herramienta líder en business intelligence corporativo; creación de dashboards drag-and-drop muy rápida para usuarios de negocio.
* **Cons:**
  * **Incompatible con servidor Debian headless:** El diseñador requiere Windows; la publicación desatendida requiere Power BI Service (licencia paga en la nube de Microsoft).
  * **Binarios opacos (`.pbix`):** Imposibilita el control de versiones granular en Git y el flujo de trabajo estándar de ingeniería de software.
  * **Limitación de lógica compleja:** Exige dominar DAX o lenguajes propietarios para cálculos matemáticos avanzados que en Python se expresan de manera trivial.

### Opción 2: Frontend a Medida (React + Vite + Tailwind) consumiendo FastAPI
* **Pros:** Control total del diseño visual, excelente experiencia de usuario (UX) y separación estricta cliente-servidor.
* **Cons:**
  * Desvía una cantidad desproporcionada de tiempo a maquetado web, CSS, gestión de estado frontend (`Redux`, `React Query`), routing y configuración de empaquetadores.
  * Requiere diseñar, mantener y asegurar una capa completa de API REST intermediaria.
  * Dispersa el foco evaluativo del perfil profesional (Data Engineer / Backend) hacia tareas de Frontend Developer.

### Opción 3: Streamlit (Seleccionada)
* **Pros:**
  * Framework 100% Python con reactividad automática basada en cambios de estado de widgets.
  * Despliegue nativo y ligero en contenedor Docker (`streamlit run app.py --server.address 0.0.0.0`).
  * Código de visualización versionable en Git como archivos `.py` legibles.
  * Conexión directa a PostgreSQL mediante SQLAlchemy / Psycopg2.
* **Cons:**
  * Menor flexibilidad para layouts hiper-personalizados en comparación con React nativo.
  * El modelo de ejecución de Streamlit re-ejecuta el script ante interacciones del usuario (mitigable mediante decoradores `@st.cache_data`).

---

## 4. Decisión Tomada
Se adopta **Streamlit** para la capa de presentación y exploración de scouting deportivo. La aplicación corre en su propio contenedor dentro de la red Docker Compose y consume directamente las consultas analíticas optimizadas de PostgreSQL.

---

## 5. Consecuencias y Trade-offs

### Consecuencias Positivas
* Iteración ultrarrápida: una nueva métrica o filtro se añade con pocas líneas de Python.
* Autonomía total del servidor Argos sin dependencias de servicios externos ni licencias comerciales.
* Todo el código del proyecto se mantiene unificado bajo el ecosistema Python.

### Evolución Futura / Mitigación
* Si en el futuro el sistema requiere ser expuesto a cientos de usuarios concurrentes de forma pública, la arquitectura permite desacoplar fácilmente la base de datos y montar una API en FastAPI que sirva tanto a un cliente móvil como a una web en React.
