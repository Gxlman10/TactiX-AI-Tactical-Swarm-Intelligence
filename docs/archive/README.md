# Archivo histórico — etapa hackathon

Estos documentos pertenecen a la etapa en que TactiX se construyó para el hackathon
**Microsoft × Premier League "Inside the Game" 2026**. El equipo ya **no participa en el
hackathon** y el proyecto continúa como producto (un SaaS de análisis táctico).

Se conservan como **referencia histórica y provenance**, no como reglas vigentes. Nada de aquí
manda sobre `CLAUDE.md`, `docs/PRODUCTO.md` ni `docs/DECISIONES-Y-PLAN.md`.

| Archivo | Qué es | Qué se rescató al producto |
|---|---|---|
| `CONTEXTO-HACKATHON.md` | Reglamento del hackathon: fechas, categorías, premios, qué descalifica. | El pipeline de 5 etapas (Ingest → Interpret → Explain → Render → Personalize) y la vara de calidad multi-agente (roles distintos, coordinación por estado compartido + handoffs, recuperación de fallos, resultado que un solo agente no lograría) viven ahora en `docs/PRODUCTO.md`. |
| `JUDGING-RUBRIC.md` | Rúbrica oficial de evaluación (5 criterios × 20%). | Los principios de calidad (preparación para producción, balance front/back, código legible) quedaron en `CLAUDE.md` → "Calidad". |
| `ROLES-Y-TAREAS.md` | Reparto de trabajo del equipo para los ~8 días del hackathon. | El principio de dependencia por capas (Datos → Métricas → Agentes → Frontend) quedó en `CLAUDE.md` → "Orden de construcción". |

El reporte de QA `docs/QA-2026-10-24.md` **no** se archivó: es un registro con fecha y se
conserva como artefacto histórico. Los QA futuros van en registros nuevos con su propia fecha.
