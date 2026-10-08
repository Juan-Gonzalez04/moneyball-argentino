# ADR-0004: Contratos de Datos con Pydantic v2 y Patrón de Cuarentena

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Autor:** Juan González

---

## 1. Contexto y Planteo del Problema
El pipeline consume datos desde endpoints públicos de AFA (`playersStatsFull.json`), los cuales escapan a mi control. Estas APIs no ofrecen garantías de versionado ni contratos semánticos formales: en cualquier momento un campo puede cambiar de tipo (ej. `age` entregado como string o nulo), renombrarse o eliminarse (*breaking changes*).

Si un pipeline de datos inyecta registros no validados directamente en PostgreSQL:
1. Puede abortar la transacción completa por fallas de tipo o violaciones de restricciones, perdiendo todo el lote.
2. O peor aún, puede corromper silenciosamente la calidad de los datos analíticos (*garbage in, garbage out*).

---

## 2. Factores Decisorios (Architecture Drivers)
* **Validación en Tiempo de Ejecución (Runtime Data Contracts):** Coerción y validación estricta de tipos antes de tocar la base de datos.
* **Tolerancia a Fallos Parciales (Fault Isolation):** Si 1 jugador de 790 contiene datos corruptos, los 789 restantes deben procesarse con éxito.
* **Auditabilidad y Observabilidad:** Los registros corruptos deben aislarse en cuarentena con el motivo exacto del fallo para su posterior análisis.
* **Rendimiento:** La validación de cientos de registros jerárquicos debe ejecutarse en milisegundos sin estrangular la CPU del servidor *Argos*.

---

## 3. Alternativas Evaluadas

### Opción 1: Validaciones manuales con `assert` y `if/else` en Python
* **Pros:** Sin dependencias externas.
* **Cons:** Código sumamente verboso, difícil de mantener y propenso a omitir casos borde (valores `None`, strings vacíos, formatos de fecha).

### Opción 2: JSON Schema estándar (`jsonschema`)
* **Pros:** Estándar agnóstico de lenguaje.
* **Cons:** Validación lenta en Python; no realiza coerción ni deserialización de tipos a objetos fuertemente tipados.

### Opción 3: Pydantic v2 con Política de Cuarentena (Seleccionada)
* **Pros:**
  * **Core en Rust:** Rendimiento extremo.
  * **Contratos declarativos y legibles:** Modelado con `BaseModel`, campos requeridos/opcionales y validaciones de rango numérico (`ge`, `le`).
  * **Patrón de Cuarentena (*Quarantine Pattern*):** La función `validate_afa_payload` captura excepciones `ValidationError` por entidad individual, guardando el error en un reporte de cuarentena sin interrumpir el lote global.
* **Cons:** Añade la dependencia de `pydantic>=2.6`.

---

## 4. Decisión Tomada
Se implementan **Data Contracts** mediante Pydantic v2 en `etl/src/schemas.py`. Se valida el payload completo desacoplándolo en entidades `TeamRawContract`, `PlayerRawContract` y contratos de métricas. Los registros que violen el contrato son derivados a un log de cuarentena.

---

## 5. Consecuencias y Trade-offs

### Consecuencias Positivas
* El pipeline es invulnerable a romper la base de datos por cambios menores de la API de origen.
* Proporciona trazabilidad completa de registros anómalos gracias a los logs.
* Los desarrolladores y evaluadores pueden consultar `schemas.py` como la especificación canónica del dato esperado.

### Limitaciones Aceptadas
* Exige actualizar los modelos de Pydantic si la API remota añade nuevos campos de negocio que deseemos explotar en columnas dedicadas.
