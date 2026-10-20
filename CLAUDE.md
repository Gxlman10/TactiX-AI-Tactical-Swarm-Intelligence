# TactiX — instrucciones para Claude Code

Proyecto para el hackathon **Microsoft × Premier League "Inside the Game" 2026**.
Categoría objetivo: **Best Multi-Agent System**. Entrega: **28 de octubre, 1:59 a. m. (hora de Perú)**.

Antes de empezar, lee `README.md` (qué estamos construyendo) y `docs/CONTEXTO-HACKATHON.md` (reglas, fechas, criterios de evaluación y qué descalifica).

---

## Idioma

- **Inglés**: código, comentarios, nombres de variables, mensajes de commit, `README.md` y todo lo que se entrega al jurado.
- **Español**: documentos internos en `docs/` y la conversación conmigo.

---

## Reglas que no se negocian

1. **Solo datos sintéticos.** Clubes, jugadores y partidos ficticios, generados por este proyecto. Nada de datos, nombres, escudos ni material real — incluye bases licenciadas tipo FIFA/PES. Esto descalifica.
2. **Las métricas se calculan en código, nunca por un modelo.** Los agentes interpretan números ya calculados; no inventan conteos. Cada afirmación debe poder rastrearse a los eventos que la produjeron.
3. **Todo código nuevo.** No importar código de proyectos anteriores.
4. **El repo es público.** Nada de secretos, claves ni `.env` versionados.

---

## Orden de construcción

Las capas bajas primero. Si el universo sintético y las métricas se demoran, los agentes se quedan sin materia prima y no hay proyecto.

1. **Synthetic Universe** — liga ficticia: clubes, plantillas, atributos de jugadores, formaciones e historial de jornadas previas.
2. **Metrics Engine** — métricas deterministas sobre el stream de eventos. Sin modelos. Testeable con asserts.
3. **Agent Swarm** — cinco especialistas sobre Microsoft Agent Framework (ver tabla en el README), con dependencias reales entre ellos.
4. **Frontend** — modo analista y modo aficionado.
5. **Azure + video demo.**

---

## Arquitectura

La cadena de dependencias entre agentes es el argumento central del proyecto, no un detalle: el handoff **Historian → Narrator** es lo que hace que la narración sea contextual en vez de descriptiva. Cinco prompts en paralelo no sirven — hay que poder demostrar que el resultado es algo que un solo agente no lograría igual de bien.

Cuando los agentes se contradigan, el Orchestrator expone el desacuerdo en vez de ocultarlo. Cuando uno falle, el reporte sale parcial y lo dice.

---

## Stack

Python + FastAPI (backend) · React + TypeScript (frontend) · PostgreSQL · Microsoft Agent Framework · Microsoft Foundry · Azure Container Apps / Functions.

Las *hero technologies* que el jurado valora están listadas en `docs/CONTEXTO-HACKATHON.md`. Usarlas de forma significativa suma; usarlas de forma decorativa no.

---

## Criterio de alcance

Quedan pocos días. Ante la duda entre más funcionalidades o que el flujo funcione de punta a punta, **siempre lo segundo**. Un recorrido completo y demostrable en 2 minutos vale más que módulos sueltos a medio terminar.

No escribir instrucciones de instalación en el README hasta haberlas corrido desde un entorno limpio.
