# TactiX — instrucciones para Claude Code

**TactiX es un SaaS de análisis táctico de fútbol.** Toma un stream de eventos de un partido y lo
convierte en inteligencia táctica explicable y con evidencia, más narración contextual, para
analistas (producto principal) y aficionados. El valor del producto está en el **backend + el
enjambre de agentes en vivo**: métricas deterministas que un modelo no inventa, y una narración
que un solo agente no lograría igual de bien.

> **Nota de contexto.** Este proyecto nació para el hackathon Microsoft × Premier League "Inside
> the Game" 2026. El equipo ya **no participa en el hackathon**: ahora se construye como producto.
> Los documentos de esa etapa viven en `docs/archive/` como referencia histórica, no como reglas
> vigentes. Si algo de este archivo choca con un doc archivado, manda este archivo.

Antes de empezar, lee `README.md` (qué es el producto de cara al usuario) y
`docs/PRODUCTO.md` (visión, alcance y no-negociables internos). El acta de diseño y la
especificación técnica viva están en `docs/DECISIONES-Y-PLAN.md`.

---

## Idioma

- **Inglés**: código, comentarios, nombres de variables, mensajes de commit, `README.md` y todo
  lo que mira el usuario del producto.
- **Español**: documentos internos en `docs/` y la conversación conmigo.
- **Salida del producto**: multi-idioma (es/en), conmutable en vivo. Es una feature, no una
  convención de repo.

---

## Reglas que no se negocian

1. **Solo datos sintéticos.** Clubes, jugadores y partidos ficticios, generados por este
   proyecto, deterministas por seed. Hoy **no tenemos fuente ni acceso a datos reales de
   partidos**, así que el universo sintético **es** el modelo de datos del producto, no un
   recurso temporal. Nada de nombres, escudos ni material real (incluye bases licenciadas tipo
   FIFA/PES). Ingerir datos reales algún día sería una decisión de producto con implicaciones de
   licencia que habría que resolver antes de tocar código; hasta entonces, todo es sintético.
2. **Las métricas se calculan en código, nunca por un modelo.** Los agentes interpretan números
   ya calculados; no inventan conteos. Cada afirmación debe poder rastrearse a los eventos que la
   produjeron. Esta es la promesa de credibilidad del producto y pesa más con un cliente de pago
   que con cualquier jurado.
3. **Proveedor de modelo intercambiable.** El enjambre corre contra un contrato de cliente
   neutral (Microsoft Agent Framework). Microsoft Foundry es **un** adaptador, no el único, y
   **ningún camino de código asume Azure**. Cualquier proveedor (Foundry, OpenAI, Anthropic,
   local) debe poder entrar detrás del mismo contrato.
4. **El repo es público. Nada de secretos.** Ni claves, ni `.env` versionados. Al manejar API
   keys de proveedores reales, la gestión de secretos va por configuración del entorno, nunca en
   el repo.

---

## Arquitectura

La cadena de dependencias entre agentes es el argumento central del producto, no un detalle: el
handoff **Historian → Narrator** es lo que hace que la narración sea contextual en vez de
descriptiva. Cinco prompts en paralelo no sirven — hay que poder demostrar que el resultado es
algo que un solo agente no lograría igual de bien.

Cuando los agentes se contradigan, el Orchestrator expone el desacuerdo en vez de ocultarlo.
Cuando uno falle, el reporte sale parcial y lo dice.

**Modelo de sesión:** privado por analista por defecto (cada usuario tiene su sesión e
independiente scrubbing), con **colaboración (co-viewing) opcional** para compartir una sesión
en vivo. El reloj compartido de hoy es la base del co-viewing, pero el default del producto es
privado.

Detalle de capas, contratos de los cinco agentes y blackboard `MatchContext` en
`docs/DECISIONES-Y-PLAN.md` §2–§6.

---

## Orden de construcción

Las capas bajas primero: si los datos y las métricas se atrasan, los agentes se quedan sin
materia prima.

1. **Data layer (universo sintético)** — liga ficticia: clubes, plantillas, atributos de
   jugadores, formaciones e historial de jornadas previas. Determinista por seed.
2. **Metrics Engine** — métricas deterministas sobre el stream de eventos. Sin modelos.
   Testeable con asserts.
3. **Agent Swarm** — cinco especialistas sobre Microsoft Agent Framework, con dependencias
   reales entre ellos y proveedor de modelo intercambiable.
4. **Frontend** — modo analista (producto principal) y modo aficionado.
5. **Producción** — despliegue en cualquier host de contenedores + endurecimiento: auth y
   tenancy por usuario, persistencia real, logging/observabilidad, límites de costo/rate por
   usuario en la ruta de modelo.

---

## Stack

Python + FastAPI (backend) · React + TypeScript (frontend) · PostgreSQL · Microsoft Agent
Framework (contrato de agentes, neutral de proveedor) · un adaptador de proveedor de modelo
(Foundry hoy; otros detrás del mismo contrato).

**Despliegue:** la app se empaqueta como imagen de contenedor y corre en cualquier host. Hoy no
hay cloud fija ni dependencia de Azure. Recomendación vigente: frontend estático en Vercel,
backend + PostgreSQL administrado en Render o Railway; un VPS con `compose.yaml` si se prefiere
costo fijo.

La tecnología se justifica por encaje con el producto, no por sumar puntos a nadie.

---

## Criterio de alcance

Ante la duda entre más funcionalidades o que el flujo funcione de punta a punta, **siempre lo
segundo**. Un recorrido completo, desplegable y demostrable vale más que módulos sueltos a medio
terminar. El driver ahora es el valor para el cliente y la preparación para producción.

Antes de agregar una funcionalidad nueva, preguntar a qué aporta: si no aporta al producto
principal (el analista) ni a su camino a producción, no entra todavía.

No escribir instrucciones de instalación en el README hasta haberlas corrido desde un entorno
limpio.

---

## Calidad (principios que seguimos evaluando)

Estos eran criterios del jurado; siguen siendo buenas varas para el producto:

- **Preparación para producción** se evalúa de verdad: manejo de errores, configuración, logs y
  un despliegue real suman, no son adorno.
- **Balance frontend/backend.** Un backend brillante con un frontend descuidado es un producto a
  medias. El reparto de esfuerzo tiene que ser equilibrado.
- **El código se lee.** Estructura, nombres y documentación cuentan por sí mismos.
