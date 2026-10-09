# ADR-0010: Estrategia de Granularidad Temporal, Acumulación Anual y Desacople de Torneos

* **Estado:** Aceptado
* **Fecha:** 2026-10-08
* **Autor:** Juan González

---

## 1. Contexto y Planteo del Problema
En el fútbol argentino, la Primera División divide el calendario competitivo anual en certámenes semestrales (históricamente Apertura/Clausura o Copa de la Liga / Liga Profesional), con libros de pases intermedios (verano e invierno) y formatos de competencia altamente cambiantes determinados por la AFA.

Durante la Fase 1 del proyecto, se identificaron dos desafíos críticos en el modelado de datos:

1. **Riesgo de Sobreescritura Destructiva entre Torneos:**  
   Las tablas relacionales `player_stats` y `player_goals` fueron diseñadas inicialmente con la clave primaria `(player_id, season_year)` fijada en el año calendario (`2026`). Si el pipeline ETL ingesta el segundo semestre tras haber procesado el primero, la propiedad de **idempotencia** (`ON CONFLICT (player_id, season_year) DO UPDATE`) provocaría que los datos del segundo torneo pisen y eliminen los registros del primer torneo.
2. **Discrepancias por Dimensiones Cambiantes (El caso Tiziano Perrotta):**  
   El endpoint de estadísticas individuales (`playersStatsFull.json`) asocia a cada futbolista con su club de pertenencia actual (`currentTeam`), pero mantiene su acumulador estadístico individual a lo largo del certamen.  
   * *Caso detectado:* Tiziano Perrotta (`player_id: 329540`) convirtió un doblete (2 goles) en la Fecha 2 jugando para Banfield. En agosto de 2026 fue transferido al Elche y cedido a Defensa y Justicia. La API actualizó su club a Defensa y Justicia manteniendo sus 2 goles anotados. Al realizar una agregación ingenua de goles por club sumando el plantel actual (`df_players.groupby('team_id')['goals'].sum()`), Defensa y Justicia registraba 18 goles en lugar de sus 16 goles oficiales, mientras que Banfield registraba 6 en lugar de sus 8 oficiales.

---

## 2. Factores Decisorios (Architecture Drivers)
* **Preservación Histórica:** Capacidad de consultar tanto el rendimiento específico de un torneo semestral como el acumulado anual de un futbolista.
* **Idempotencia Estricta:** Reejecutar el pipeline ETL sobre cualquier snapshot nunca debe alterar ni duplicar valores numéricos acumulados.
* **Independencia del Grano de Datos:** Separar conceptual y técnicamente el grano de *Estadísticas de Futbolistas* del grano de *Estadísticas de Clubes*.
* **Resiliencia ante Cambios de Formato de AFA:** El esquema relacional debe tolerar que la AFA modifique calendarios, organice torneos cortos, copas zonales o ligas unificadas sin quebrar el modelo analítico.

---

## 3. Alternativas Evaluadas

### Opción 1: Acumulación Destructiva en Upsert (Sumar deltas en BD)
* *Mecanismo:* Modificar la sentencia de carga para sumar:  
  `ON CONFLICT (player_id, season_year) DO UPDATE SET total_goals = player_goals.total_goals + EXCLUDED.total_goals`
* *Descarte:* **Viola la idempotencia**. Si el pipeline se reejecuta por mantenimiento, reprocesamiento o reintento automático, sumaría dos veces las mismas estadísticas, corrompiendo irreversiblemente el almacén analítico.

### Opción 2: Sobreescritura Semestral Simple
* *Mecanismo:* Permitir que el torneo en curso pise al anterior, manteniendo solo la foto del último certamen.
* *Descarte:* Pérdida inaceptable de trazabilidad histórica; anula la posibilidad de análisis comparativos longitudinales.

### Opción 3: Clave Compuesta por Torneo + Vista Analítica Anual + Desacople de Grano (Seleccionada)
* *Mecanismo:*
  1. **Clave Primaria Compuesta:** Incorporar el identificador del torneo en las tablas de hechos:  
     `PRIMARY KEY (player_id, season_year, tournament_id)` (ej. `'2026_apertura'`, `'2026_clausura'`).
  2. **Vista Analítica Anual Consolidada:** Crear vistas en PostgreSQL (`v_player_stats_annual`, `v_player_goals_annual`) que agreguen métricas mediante `SUM(...) GROUP BY player_id, season_year`.
  3. **Desacople de Fuentes Institucionales:** Desestimar la suma de futbolistas para calcular estadísticas de clubes. La fuente canónica para métricas oficiales de equipos (goles del club, posesión, tiros concedidos) es el endpoint dedicado de clubes (`teamsStats.json`).

---

## 4. Decisión Tomada
1. Se adopta la **persistencia semestral aislada** en la capa relacional mediante la clave compuesta `(player_id, season_year, tournament_id)`.
2. La exposición analítica para scouting se realiza a nivel **ANUAL** a través de vistas SQL consolidadas, brindando una referencia anual homogénea inmune a los vaivenes reglamentarios de AFA.
3. Se establece formalmente la regla de negocio: **Las estadísticas colectivas de un club no equivalen a la suma de su plantel actual**. Las métricas de clubes se delegan a la ingesta de `teamsStats.json` planificada para la Fase 2.

---

## 5. Consecuencias

### Positivas:
* **Trazabilidad Completa:** Permite auditar el desempeño de un jugador en cada torneo semestral por separado o de forma agregada anual.
* **100% Idempotente:** Cada snapshot de torneo puede reejecutarse infinitas veces sin riesgo de duplicar datos.
* **Resolución del problema de traspasos:** Movimientos como el de Tiziano Perrotta o Jeremías Lucco quedan auditados con precisión en el torneo correspondiente sin distorsionar los totales anuales ni institucionales.

### Desafíos Mitigados:
* Para consultar estadísticas anuales, la capa de presentación lee de vistas agregadas en PostgreSQL, aprovechando el *Compute Pushdown* sin sobrecargar la memoria de la aplicación.
