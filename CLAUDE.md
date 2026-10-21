# TactiX — instrucciones para Claude Code

Proyecto para el hackathon **Microsoft × Premier League "Inside the Game" 2026**.
Categoría objetivo: **Best Multi-Agent System**. Entrega: **28 de octubre, 1:59 a. m. (hora de Perú)**.

Antes de empezar, lee `README.md` (qué estamos construyendo), `docs/CONTEXTO-HACKATHON.md` (reglas, fechas y qué descalifica) y `docs/JUDGING-RUBRIC.md` (rúbrica oficial de evaluación).

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

## Cómo nos evalúan

Cinco criterios, **20% cada uno**. Ninguno pesa más que otro, y eso debe guiar dónde se invierte el tiempo:

1. **Technological Implementation** — buenas prácticas, uso efectivo de las *hero technologies*, código estructurado, documentado y mantenible.
2. **Agentic Design & Innovation** — patrones agénticos creativos, orquestación sofisticada o colaboración multiagente, implementación novedosa.
3. **Real-World Impact & Applicability** — relevancia del problema, preparación para producción, impacto potencial.
4. **User Experience & Presentation** — UX intuitiva, comunicación clara del valor en la demo, **balance entre frontend y backend**.
5. **Adherence to Hackathon Category** — cumplir la descripción de Best Multi-Agent System.

Consecuencias prácticas al tomar decisiones:

- Un backend brillante con un frontend descuidado pierde en el criterio 4, que vale lo mismo que el código. El reparto de esfuerzo tiene que ser equilibrado.
- "Production deployment readiness" se evalúa de verdad: manejo de errores, configuración, logs y un despliegue real suman, no son adorno.
- El código se lee. Estructura, nombres y documentación cuentan como criterio propio, no como consecuencia.
- Antes de agregar una funcionalidad nueva, preguntar a qué criterio aporta. Si no aporta a ninguno, no entra.

Texto oficial completo en `docs/JUDGING-RUBRIC.md`.

---

## Criterio de alcance

Quedan pocos días. Ante la duda entre más funcionalidades o que el flujo funcione de punta a punta, **siempre lo segundo**. Un recorrido completo y demostrable en 2 minutos vale más que módulos sueltos a medio terminar.

No escribir instrucciones de instalación en el README hasta haberlas corrido desde un entorno limpio.
