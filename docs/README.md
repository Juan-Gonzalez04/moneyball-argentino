# Sistema de Documentación Técnica de Ingeniería

Este directorio contiene la documentación formal de arquitectura, decisiones técnicas y bitácora de ingeniería del proyecto **MoneyBall Argentino / Argos**.

---

## Estructura del Directorio

```text
docs/
├── README.md               # Este índice y guía de documentación
├── devlog.md               # Cuaderno de bitácora técnico (Engineering Logbook)
└── adr/                    # Registros de Decisiones de Arquitectura (ADRs)
    ├── 0000-template.md    # Plantilla estándar oficial
    ├── 0001-orquestacion-multicontenedor-docker-compose.md
    ├── 0002-persistencia-relacional-hibrida-postgresql.md
    ├── 0003-presentacion-analitica-streamlit.md
    ├── 0004-data-contracts-pydantic-cuarentena.md
    ├── 0005-cliente-http-httpx.md
    ├── 0006-pipeline-secuencial-evtl-srp.md
    └── 0007-estrategia-claves-primarias-naturales-vs-subrogadas.md
```

---

## 1. Registros de Decisiones de Arquitectura (ADRs)

Los **ADRs** (*Architecture Decision Records*) documentan formalmente las decisiones arquitectónicas significativas, el contexto en que se tomaron, las alternativas evaluadas y las consecuencias o trade-offs asumidos.

### Índice de Decisiones Registradas
* [ADR-0001: Orquestación Multicontenedor con Docker Compose](file:///home/juan/Repos/Personal/moneyball-argentino/docs/adr/0001-orquestacion-multicontenedor-docker-compose.md)
* [ADR-0002: Persistencia Relacional Híbrida con PostgreSQL y JSONB](file:///home/juan/Repos/Personal/moneyball-argentino/docs/adr/0002-persistencia-relacional-hibrida-postgresql.md)
* [ADR-0003: Capa de Presentación Analítica con Streamlit](file:///home/juan/Repos/Personal/moneyball-argentino/docs/adr/0003-presentacion-analitica-streamlit.md)
* [ADR-0004: Contratos de Datos con Pydantic v2 y Patrón de Cuarentena](file:///home/juan/Repos/Personal/moneyball-argentino/docs/adr/0004-data-contracts-pydantic-cuarentena.md)
* [ADR-0005: Cliente HTTP con HTTPX para Ingesta y Resiliencia](file:///home/juan/Repos/Personal/moneyball-argentino/docs/adr/0005-cliente-http-httpx.md)
* [ADR-0006: Microarquitectura E-V-T-L y Principio de Responsabilidad Única](file:///home/juan/Repos/Personal/moneyball-argentino/docs/adr/0006-pipeline-secuencial-evtl-srp.md)
* [ADR-0007: Estrategia de Claves Primarias: Claves Naturales de AFA vs. Claves Subrogadas](file:///home/juan/Repos/Personal/moneyball-argentino/docs/adr/0007-estrategia-claves-primarias-naturales-vs-subrogadas.md)

### Cómo crear un nuevo ADR
1. Copiar [docs/adr/0000-template.md](file:///home/juan/Repos/Personal/moneyball-argentino/docs/adr/0000-template.md) asignando el siguiente número correlativo de 4 dígitos (ej. `0004-data-contracts-pydantic.md`).
2. Completar las secciones obligatorias: Contexto, Drivers, Alternativas con Pros/Cons, Decisión y Consecuencias.
3. Incorporar el enlace al nuevo ADR en esta tabla y en el `README.md` principal.

---

## 2. Cuaderno de Bitácora Técnico (Devlog)

El [Cuaderno de Bitácora (devlog.md)](file:///home/juan/Repos/Personal/moneyball-argentino/docs/devlog.md) es un registro dinámico y cronológico del proceso de desarrollo.

Su propósito fundamental es:
1. Registrar desafíos no triviales y errores imprevistos.
2. Detallar el Análisis de Causa Raíz (*Root Cause Analysis - RCA*).
3. Documentar la solución aplicada y la lección aprendida.
4. Servir como material de preparación para preguntas situacionales en entrevistas técnicas (*"Contame una situación donde un servicio falló y cómo lo diagnosticaste"*).
