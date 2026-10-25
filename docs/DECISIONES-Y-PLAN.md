# TactiX — Decisiones de diseño y plan de ejecución

> **Documento interno del equipo (español).** Nació como acta de la reunión de refinamiento del
> 20 de octubre de 2026; hoy es la **especificación técnica viva del producto**. El marco de
> producto (qué construimos y por qué) está en `PRODUCTO.md`; las instrucciones operativas en
> `CLAUDE.md`. Lo que mira el usuario del producto va en inglés; esto no.
>
> Si algo de aquí contradice lo que construimos, gana este documento o lo actualizamos. No es
> sagrado: es la referencia viva. Las secciones §2–§6 (arquitectura y contratos) son el núcleo
> durable; §7–§9 son el plan de producto y cambian con cada ronda.

---

## 0. Estado

- **Etapa:** producto. El proyecto ya no participa en el hackathon (la etapa hackathon vive en
  `docs/archive/`).
- **Qué existe:** las cuatro capas construidas y testeadas offline (universo, métricas, enjambre,
  frontend). Los agentes en vivo están implementados pero aún **no corren** por falta de un
  proveedor de modelo configurado con cuota.
- **Regla de oro (de `CLAUDE.md`):** ante la duda, flujo de punta a punta antes que más módulos.

---

## 1. Decisiones fijadas

### Ronda 1 — postura general

| Tema | Decisión | Nota |
|---|---|---|
| Equipo | Generalistas, flexibles, fuerte apoyo en IA/herramientas | Trabajo organizado en capas paralelizables |
| Alcance | **Backend profundo primero, UX en paralelo** | El frontend pesa igual que el backend; no es relleno |
| Stream de eventos | Simulación determinista **+** run grabado reproducible | Motor determinista; el demo reproduce un partido grabado |
| Infra | **Agnóstica de cloud**: imagen de contenedor en cualquier host | Recomendado: Vercel (front) + Render/Railway (back + Postgres); VPS con `compose.yaml` como alternativa. Nada asume Azure |

### Ronda 2 — capa fundacional

| Tema | Decisión |
|---|---|
| Universo sintético | **8–10 clubes**, cada uno con **~10–14 partidos ya jugados** (media temporada previa) |
| Granularidad de eventos | **Coordenadas (x,y) + posesiones/fases enlazadas** |
| Framework de agentes | **Microsoft Agent Framework** (contrato de cliente neutral de proveedor) |
| Proveedor de modelo | **Intercambiable.** Foundry es un adaptador; otros (OpenAI/Anthropic/local) entran detrás del mismo contrato. Ninguno asumido por el código |
| Idiomas de salida | **Inglés + español, ambos reales**, conmutables en vivo |

### Ronda 3 — enjambre de agentes

| Tema | Decisión |
|---|---|
| Orquestación | **Fan-out / fan-in sobre estado compartido**: Analyst ∥ Historian → Narrator (fan-in) → Personalizer; Orchestrator supervisa todo |
| Discrepancia | **Desacuerdo de causa**: Analyst (lectura táctica) vs Historian (patrón histórico); el Orchestrator expone ambas con su evidencia |
| Recuperación de fallos | **Agente caído → reporte parcial etiquetado** (tumbamos al Historian; el reporte sale y dice "contexto histórico no disponible") |
| Clímax de la demo | **El párrafo que un solo agente no podría escribir**, armándose en vivo con la procedencia de cada agente |

### Stack y estructura — confirmados (propuesta del equipo del 20/10)

El equipo trajo la propuesta de implementación; la evalué y **encaja con todo lo decidido**, y
está mejor especificada que mis defaults. Se adopta tal cual.

**Stack**

| Área | Tecnología | Función |
|---|---|---|
| Backend | Python + FastAPI | API y ejecución del sistema |
| Validación | Pydantic | Contratos de eventos, métricas y respuestas de agentes |
| Simulación | Python con semillas reproducibles | Liga, historial y partidos ficticios |
| Métricas | Python determinista | Estadísticas + evidencia conservada |
| Orquestación | Microsoft Agent Framework | Estado compartido, handoffs, coordinación (contrato de cliente neutral) |
| Modelos | Adaptador de proveedor intercambiable | Interpretación táctica, narración, personalización. Foundry es el adaptador de hoy |
| Frontend | React + TypeScript + Vite | Modos analista y aficionado |
| Comunicación | REST + SSE | Control del partido + actualizaciones en vivo |
| Base de datos | PostgreSQL | Universo, eventos, métricas, ejecuciones |
| Acceso a datos | SQLAlchemy + Alembic | Consultas y migraciones |
| Empaquetado | Docker | Imagen de contenedor portable |
| Despliegue | Cualquier host de contenedores | Vercel (front) + Render/Railway (back + Postgres), o VPS. Agnóstico de cloud |

**Tooling:** uv (deps Python) · npm (frontend) · Ruff + ESLint + TypeScript (formato/estático) ·
pytest (simulación, métricas, evidencia, recuperación) · Playwright (recorrido de la demo) ·
Docker Compose (local reproducible) · GitHub Actions (CI) · GitHub Copilot.

**Estructura (monorepo)**

```
TactiX/
├── backend/src/tactix/
│   ├── domain/        # contratos y entidades (Pydantic)
│   ├── universe/      # liga, jugadores, historial
│   ├── simulation/    # eventos y reproducción del partido
│   ├── metrics/       # estadísticas y evidencia
│   ├── agents/        # especialistas: instrucciones, herramientas, contratos
│   ├── workflows/     # coordinación, estado compartido, recuperación (checkpoints)
│   ├── persistence/   # acceso a PostgreSQL (SQLAlchemy + Alembic)
│   └── api/           # REST + SSE
├── frontend/src/features/   # match · analyst · fan · preferences
├── data/scenarios/    # escenarios sintéticos reproducibles (incluye el demo seed)
├── infra/             # runbook de despliegue agnóstico de cloud (Docker, cualquier host)
├── scripts/
└── docs/              # interno, español
```

**Notas sobre la propuesta:**

1. **Despliegue agnóstico de cloud.** La app es una imagen de contenedor que corre en cualquier
   host (Vercel para el front; Render/Railway/VPS para el back + Postgres). Nada asume Azure ni
   un modelo serverless concreto.
2. **`data/scenarios/` = el *demo seed***: ahí vive el guion plantado de *Ashford*. En producto
   es una fixture de demo/onboarding, no una muestra de análisis de cliente real (ver §3).
3. **Frontend:** estado con **Zustand**, i18n con **react-i18next** (es/en).
4. **Proveedor de modelo intercambiable.** El enjambre corre contra un contrato de cliente
   neutral (MAF); el proveedor concreto (Foundry hoy; OpenAI/Anthropic/local después) se elige
   por disponibilidad/cuota/latencia y entra detrás del mismo contrato. No se entrena nada.
5. **Nombres sintéticos:** mantener los del README (*Ashford*, *Northbridge*, *Hartley*).

---

## 2. Arquitectura en cuatro capas

```
Eventos sintéticos  ─►  Motor de métricas  ─►  Enjambre de agentes  ─►  Frontend
   (Layer 1)              (Layer 2, código)       (Layer 3, MAF+proveedor) (Layer 4)
   determinista          determinista             interpreta, no cuenta    analista/afición
```

Principio inquebrantable: **las métricas se calculan en código; los agentes solo interpretan
números ya calculados.** Cada afirmación de un agente apunta a los eventos/métricas que la
producen (trazabilidad).

---

## 3. Layer 1 — Universo sintético

> El equipo pidió **más profundidad futbolística** para que las respuestas de los agentes no
> salgan básicas. Esta sección y la §4 se ampliaron con eso en mente. Regla que no cambia:
> todo es **dato sintético generado por el proyecto** y **determinista por seed**.

### Entidades

**League / Season**
- Temporada, clubes, calendario (jornadas) y **tabla de posiciones** viva: PJ, G/E/P, GF/GC,
  diferencia, puntos, forma (últimos 5: W/D/L), splits local/visitante.
- Reglas de competición (puntos, desempates) para que la tabla sea coherente.

**Club**
- Identidad: nombre, ciudad, apodo, colores (para la UI).
- **Identidad táctica:** formación(es) habitual(es) (4-3-3, 3-5-2…), estilo de construcción
  (corto / directo / mixto), **altura de línea defensiva**, **intensidad de presión**, tempo,
  amplitud, forma con/sin balón, fuerza a balón parado, filosofía del DT.
- Rachas de temporada y fortalezas/debilidades agregadas (p. ej. "vulnerable en transición").

**Player**
- Ficha: nombre, dorsal, posición(es), rol, **pie preferido** (y pie malo 1–5), altura, edad.
- **Atributos 0–100 por familia:**
  - *Físico:* pace, aceleración, resistencia, fuerza, salto.
  - *Técnico:* pase, pase largo, regate, control, centro, definición, tiro lejano, balón parado.
  - *Mental:* posicionamiento, visión, compostura, decisión, agresividad, trabajo, marcaje.
  - *Portero (si aplica):* reflejos, achique, manejo, juego aéreo, distribución.
- **Tendencias** (lo que da textura a la narrativa): zonas de calor preferidas, acciones
  favoritas ("remata desde el canal izquierdo"), debilidades explotables ("pierde el balón bajo
  presión en medio campo"), rendimiento por estado del partido.
- **Estado dinámico:** fatiga (la resistencia baja en el tramo final y afecta la ejecución),
  moral/confianza, amonestaciones acumuladas y sanciones de la temporada.

**Fixture (histórico)** — no solo el marcador: alineaciones y formaciones, goleadores con
minuto, resumen de eventos clave, totales tipo xG, posesión, tiros, y la racha/patrón que dejó.

**Head-to-head** — historial entre dos clubes: registro, tendencias del enfrentamiento, último
resultado.

**Match (en vivo)** — el partido que se simula/reproduce (ver §4).

**Possession** — cadena de eventos de un mismo equipo, con fase y desenlace (ver §4).

### Generador

- **Determinista por seed** → reproducible y testeable.
- **Demo seed (ya reflejado en `data/scenarios/`):** además del modo procedural, el
  generador acepta un *guion plantado* que inyecta un patrón concreto en el historial y en el
  partido en vivo. Para el clímax: *Ashford* arrastra un patrón de "concede tras perder el
  balón en medio campo" en varios fixtures previos, y en el vivo vuelve a pasar y termina en
  gol de *Hartley*. Sin este gancho, la frase clímax no tiene de dónde salir. En producto es la
  **fixture de demo/onboarding** (muestra las capacidades), no una muestra de análisis de un
  cliente real: cuando se despliegue como SaaS hay que encuadrarla como tal en la UI.
- Media temporada previa (~10–14 jornadas) = suficiente para tabla, forma, head-to-head y
  tendencias por jugador con sustento real.

---

## 4. Layer 2 — Eventos y métricas deterministas

Principio que no se toca: **las métricas se calculan en código, nunca por un modelo.** Los
valores "esperados" (xG/xT/xA) son **modelos deterministas de peso por zona, no ML** — se
nombran "xG-like" para no dar a entender aprendizaje automático. Cada métrica es testeable:
dado un set fijo de eventos, el resultado es un número conocido (asserts en pytest).

### Esquema de evento

Base: `match_id, minute, second, team, player_id, type, subtype, x, y, [end_x, end_y]`.

**Cualificadores** (lo que hace que las métricas no sean básicas): `outcome` (success/fail),
`body_part` (left/right/head/other), `under_pressure` (+ por quién), `play_pattern`
(open_play / from_corner / from_free_kick / from_throw_in / counter / direct_free_kick /
penalty / goal_kick / keeper), `progressive` (bool), `distance`, `angle`, `pitch_zone` (grid de
18 zonas: tercios × canales), `possession_id`, `phase`, `related_player` (receptor / defensor
superado), `expected_value` (xG/xT/xA-like).

### Taxonomía de eventos

- **En posesión:** pass (short/long/through/switch/cross/cutback/line-breaking), carry,
  progressive carry, dribble/take-on, key pass, assist, shot (open play/set piece/counter/
  penalty; on/off/blocked/goal), goal.
- **Defensivos:** tackle, interception, block, clearance, recovery, duel (ground/aéreo,
  won/lost), press/press-trigger, counter-press.
- **Portero:** save (con tipo), punch/catch, sweep (salida), distribution (throw/short/long).
- **Balón parado / parones:** corner (in/out-swing), free_kick (direct/indirect), throw_in,
  penalty (scored/missed/saved), goal_kick, kickoff.
- **Disciplina / otros:** foul (committed/won), card (yellow/red/second-yellow), offside,
  substitution (motivo: táctico/lesión/tiempo), injury.

Las **posesiones** encadenan eventos y llevan *fase*: `build_up → progression → final_third →
outcome`. Esto habilita leer secuencias y transiciones, no eventos sueltos.

### Simulación de posesiones (realismo sin ML)

Máquina de estados por posesión: arranque → progresión (influida por identidad táctica del
club, atributos de los jugadores y **fatiga**) → tercio final → desenlace (tiro / pérdida /
falta / balón parado). Determinista con seed; el realismo sale de reglas afinadas + ruido
controlado, no de un modelo.

### Catálogo de métricas (todo en código)

**Posesión y control** — posesión % (por tiempo y por pases) por tercios; **field tilt** (share
de toques en tercio final); posesión por fase de juego.

**Pase y progresión** — % de acierto global y por zona; pases progresivos; pases al tercio final
y al área; through balls; switches; line-breaking passes; longitud media; direccionalidad (pass
sonar). **Pass network** por equipo (nodos = jugadores, aristas = pases con peso) con
**centralidades** (grado, intermediación) para detectar al jugador-eje.

**Conducción** — carries progresivos, al tercio final y al área; distancia conducida.

**Finalización y creación** — tiros, tiros a puerta, **xG-like** total y por tiro, grandes
ocasiones, mapa de tiros, conversión; key passes, **xA-like**, asistencias; shot-creating y
goal-creating actions.

**Defensa y presión** — tackles, interceptions, blocks, clearances, recoveries; % de duelos y
aéreos ganados; acciones defensivas por zona; **PPDA**; recuperaciones altas; éxito de presión;
recuperaciones por counter-press; proxy de altura de línea.

**Transiciones y balón parado** — pérdidas y su ubicación; velocidad de transición
(pérdida→remate); contraataques; córners/FK/laterales ganados y convertidos; xG-like a balón
parado.

**Tempo y momentum** — índice de momentum/ritmo (densidad de eventos ponderada en ventana
móvil); periodos de control; **xG race** (línea de tiempo de xG acumulado por equipo); índice
de presión.

**Físico (sintético) y portero** — distancia recorrida, sprints, carreras de alta intensidad,
curva de fatiga por jugador; paradas, % de parada, **xG prevenido** (post-shot xG-like),
salidas, precisión de distribución.

**Por estado de partido y rating** — todas las métricas con split por marcador (ganando /
empatando / perdiendo); **rating por jugador** compuesto determinista (0–10), trazable a sus
acciones.

Todo esto es la materia prima del Analyst y del Historian: cuanto más rico el catálogo, más
específica (y menos genérica) la explicación final. Se construye **faseado**: primero el núcleo
(posesión, pase, tiro, presión), luego las avanzadas (xG race, ratings, físico).

---

## 5. Layer 3 — Enjambre de agentes (el corazón de la categoría)

### Estado compartido (blackboard) — `MatchContext`

Todos los agentes leen sus dependencias de aquí y escriben solo su parte:

```
MatchContext {
  match_meta
  metrics            # salida del motor (Layer 2)
  universe_refs      # historia de club/jugador relevante al momento
  analyst_findings[] # { claim, evidence(event_ids|metric_ref), confidence, frame="tactical", moment }
  historian_findings[] # { claim, evidence, confidence, references(fixtures), frame="historical", moment }
  conflicts[]        # { moment, analyst_finding, historian_finding, resolution }
  narration          # { play_by_play[], recap, key_moments[] }
  personalized       # { analyst_view, fan_view, lang }
  degraded[]         # nombres de agentes no disponibles
}
```

### Contratos de los cinco agentes

| Agente | Entra | Sale | Rol |
|---|---|---|---|
| **Tactical Analyst** | `metrics` | `analyst_findings` | Patrones, cambios de presión, momentum. Cada hallazgo con evidencia y confianza |
| **Historian** | `metrics` + `universe_refs` | `historian_findings` | Cruza el momento en vivo contra historial de temporada y perfiles de jugador |
| **Narrator** | `analyst_findings` + `historian_findings` + `conflicts` | `narration` | **Fan-in.** Play-by-play y recap. Aquí nace el párrafo contextual |
| **Personalizer** | `narration` + perfil (club/jugador/idioma/modo) | `personalized` | Dos experiencias distintas + idioma |
| **Orchestrator** | todo | reporte final | Secuencia el workflow, detecta y expone conflictos, maneja agentes caídos |

### Activación y costo (control de latencia)

Las **métricas se actualizan por evento**, pero los **agentes se activan por ventanas de
análisis o momentos relevantes** (un gol, un cambio de momentum, una ventana de ~5'), no en
cada evento. Esto controla latencia y costo del proveedor de modelo y concentra el LLM donde
aporta. (En producción, además, la ruta de modelo necesita límites de rate/costo por usuario:
ver §7, endurecimiento.)

El estado del workflow usa **checkpoints** (para recuperar la ejecución) y, aparte, un
**historial consultable** (contexto futbolístico para el Historian): son cosas distintas con
funciones distintas.

### Por qué un solo agente no basta (la tesis, para README y video)

El párrafo clímax requiere tres trabajos con **evidencia distinta**: computar el evento
(métricas), reconocer el patrón de temporada (historial) y decidir que vale contarlo
(narrativa). El handoff **Historian → Narrator** es lo que hace la narración *contextual* y no
descriptiva. Cinco prompts en paralelo no lo logran: son jobs distintos con fuentes distintas.

Para **probarlo**, no solo afirmarlo: enviamos un *baseline de un solo agente* (un prompt
monolítico sobre los mismos eventos) y lo comparamos lado a lado con la salida del enjambre.
Esa comparación es la evidencia de que el enjambre aporta algo que un solo agente no, y es
material directo para la demo y el pitch del producto.

### Mecánica de discrepancia (real, no teatro)

Un *momento* = ancla temporal (p. ej. gol en el 62'). Si Analyst e Historian anclan al mismo
momento con *frames* distintos (táctico vs histórico), el Orchestrator crea una entrada en
`conflicts` y le ordena al Narrator **presentar ambas lecturas**, no elegir ("los números
dicen X; la historia dice Y"). Es honesto porque las dos salen de evidencia genuinamente
distinta.

### Recuperación de fallos (demostrable en vivo)

El Orchestrator corre a cada agente con try/except + timeout. Si el Historian cae (o lo
tumbamos con un toggle en la demo): `degraded += ["historian"]`, el Narrator trabaja solo con
`analyst_findings`, y el reporte muestra una insignia "Historical context unavailable". El
recorrido no se rompe: sale parcial y lo dice.

---

## 6. Layer 4 — Frontend (pesa igual que el backend, no es relleno)

- **Modo analista:** métricas densas, línea de tiempo de patrones, pass network, mapa de
  cancha en vivo, evidencia desglosable (clic en una afirmación → eventos que la sustentan).
- **Modo afición:** narrativa, momentos clave, por qué importaron. Menos números, más historia.
- **Switch analista ↔ afición** en vivo sobre el mismo momento.
- **Personalización — 4 ejes (todos entran):** idioma es/en y modo analista/afición (núcleo),
  más **club favorito** (el Personalizer sesga tono y qué momentos destaca) y **jugador foco**
  (su mapa de calor, acciones y rating). Conmutables en vivo.
- **Mapa de cancha**: las coordenadas (x,y) de los eventos se dibujan sobre el campo — es el
  mayor golpe visual y justifica haber elegido eventos con posición.
- **Procedencia del párrafo clímax**: al pasar sobre la frase, se resalta qué agente aportó
  cada fragmento y de qué eventos sale.

---

## 7. Roadmap de producto (faseado)

Lo construido (etapa hackathon) dejó las cuatro capas sólidas y testeadas offline. El roadmap de
producto parte de ahí hacia un SaaS multiusuario desplegado. Prioridad: lo que desbloquea el
valor principal (analista) y el camino a producción, antes que más features.

### Fase A — Hecho (base técnica)

- Universo sintético determinista, motor de métricas con tests, enjambre de cinco agentes con
  blackboard/handoffs/recuperación, frontend analista+afición, recording reproducible, CI.
- Orquestación con **cliente de modelo inyectable** (ya probada contra un cliente MAF no-Foundry).
- Docs y despliegue **agnósticos de cloud** (de-Azure completo).

### Fase B — Desbloquear agentes en vivo + abstracción de proveedor

- **Contrato `ModelProvider`** explícito (context-manager de cliente + `validate()` +
  `invocation_limits()`); renombrar `agents/foundry.py` → `agents/runtime.py` dejando
  `run_specialists` neutral; mover la fábrica Foundry a `agents/providers/foundry.py`.
- `TACTIX_MODEL_PROVIDER` + settings namespaced por proveedor; eliminar el `foundry_api_key`
  muerto. **No implementar un adaptador nuevo todavía** — solo dejar el contrato listo.
- Envolver los accesos a internals de MAF (`client.client.*`, `function_invocation_configuration`)
  para que un cliente no-MAF-nativo no rompa.

### Fase C — Preparación para SaaS (la brecha grande)

- **Auth + identidad + tenancy.** Hoy no existe: toda sesión es global, legible y borrable por
  cualquiera. Añadir usuarios, propiedad de sesión y aislamiento por usuario en cada ruta.
- **Modelo de sesión del producto:** privado por analista por defecto; co-viewing como opción
  explícita (no el default actual de "los controles afectan a todos").
- **Persistencia real.** Conectar la capa de BD a la API (hoy la liga se genera en memoria y la
  BD no se usa en runtime); persistir ejecuciones de análisis para que un analista las retome.
  Sacar el estado de sesión de la memoria de un worker (Redis/BD) o comprometerse a single-worker
  con routing pegajoso y documentarlo.
- **Logging/observabilidad.** Hoy es cero. Logging estructurado + request IDs + un canal de
  error interno que preserve diagnóstico sin filtrar secretos (los errores de proveedor se
  colapsan a `provider_error` a propósito; eso deja al operador ciego sin logs).
- **Límites de costo/rate por usuario** en la ruta `/analyze`.
- **Frontend de SaaS:** router, pantalla de login, selección/listado de partidos (hoy el partido
  `ashford-demo-v1` está hardcodeado en toda la pila), desacoplar los tipos del `fixture.json`.

### Fase D — Despliegue

- Imagen de contenedor en el host elegido (recomendado: Vercel front + Render/Railway back +
  Postgres). Pipeline de CD. Gestión de secretos por entorno.

---

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Agentes en vivo bloqueados por cuota/latencia del proveedor | Contrato de proveedor intercambiable; el motor determinista da una base de valor sin LLM |
| Sin fuente de datos reales | El universo sintético **es** el producto hoy; ingerir datos reales es decisión futura con tema de licencias |
| "Coordenadas + posesiones" es lo más caro de simular | Máquina de estados simple y determinista; afinar con reglas, no con ML |
| Datos futbolísticos ricos = más simulación/métricas | Faseado: primero el catálogo núcleo, luego las avanzadas (xG race, ratings, físico) |
| El salto a SaaS (auth/tenancy/persistencia) es grande | Faseado en §7-C, priorizando el analista; el acoplamiento a proveedor es estrecho y contenido |
| Costo del modelo en producción | Activación por momentos (no por evento) + límites de rate/costo por usuario |

---

## 9. Puntos abiertos

**Decididos:**

- **Estado del frontend:** Zustand. **i18n:** react-i18next (es/en). *(§1)*
- **Personalización:** 4 ejes — idioma, modo, club favorito, jugador foco. *(§6)*
- **Modelo de sesión:** privado por defecto + co-viewing opcional.
- **Proveedor de modelo:** contrato intercambiable; sin adaptador nuevo concreto por ahora.
- **Despliegue:** agnóstico de cloud (recomendado Vercel + Render/Railway).
- **Licencia:** MIT.

**Por decidir (producto/negocio, no bloquean el código):**

- Fuente de datos reales y sus licencias (si alguna vez se persigue).
- Qué adaptador de proveedor implementar primero cuando toque correr agentes en vivo.
- Modelo de monetización del SaaS (planes, límites, billing).

**Por cerrar al codear (default documentado):**

- Parámetros de los modelos xG/xT/xA-like (pesos por zona) y umbral del `pass network`.
