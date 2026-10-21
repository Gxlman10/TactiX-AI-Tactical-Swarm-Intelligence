# TactiX — Decisiones de diseño y plan de ejecución

> **Documento interno del equipo (español).** Es el acta de la reunión de refinamiento del
> 20 de octubre de 2026 y la especificación técnica maestra. Todo lo que se entrega al jurado
> (README, pitch, video, instrucciones) va en inglés; esto no.
>
> Si algo de aquí contradice lo que construimos, gana este documento o lo actualizamos. No es
> sagrado: es la referencia viva.

---

## 0. Estado y restricción dura

- **Hoy:** 20 de octubre de 2026. **Entrega:** 28 de octubre, 1:59 a. m. (Perú) → **~8 días**.
- **Punto de partida:** 0 líneas de código. Solo documentación.
- **Regla de oro (de `CLAUDE.md`):** ante la duda, flujo de punta a punta antes que más módulos.
- **La demo debe quedar arriba hasta el 10 de noviembre.** No apagar nada antes.

---

## 1. Decisiones fijadas (reunión del 20/10)

### Ronda 1 — postura general

| Tema | Decisión | Nota |
|---|---|---|
| Equipo | Generalistas recién egresados, flexibles, fuerte apoyo en IA/herramientas | Trabajo organizado en capas paralelizables |
| Alcance | **Backend profundo al 100% primero, luego UX** | Mitigación obligatoria: UI mínima en paralelo desde el día 2 (ver §7) |
| Stream de eventos | Simulación real **+** run grabado para la demo | Motor determinista; la demo reproduce un partido grabado |
| Infra | **100% serverless en Azure** | Detalles sobre la marcha; Vercel/Supabase solo como andamiaje local, nunca deploy final |

### Ronda 2 — capa fundacional

| Tema | Decisión |
|---|---|
| Universo sintético | **8–10 clubes**, cada uno con **~10–14 partidos ya jugados** (media temporada previa) |
| Granularidad de eventos | **Coordenadas (x,y) + posesiones/fases enlazadas** |
| Modelos / framework | **Microsoft Agent Framework + Microsoft Foundry** |
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
| Orquestación | Microsoft Agent Framework | Estado compartido, handoffs, coordinación |
| Modelos | Microsoft Foundry | Interpretación táctica, narración, personalización |
| Frontend | React + TypeScript + Vite | Modos analista y aficionado |
| Comunicación | REST + SSE | Control del partido + actualizaciones en vivo |
| Base de datos | PostgreSQL | Universo, eventos, métricas, ejecuciones |
| Acceso a datos | SQLAlchemy + Alembic | Consultas y migraciones |
| Despliegue | Docker + Azure Container Apps | Publicar la app (serverless, scale-to-zero) |
| Persistencia nube | Azure Database for PostgreSQL | Datos de la demo |

**Tooling:** uv (deps Python) · npm (frontend) · Ruff + ESLint + TypeScript (formato/estático) ·
pytest (simulación, métricas, evidencia, recuperación) · Playwright (recorrido de la demo) ·
Docker Compose (local reproducible) · GitHub Actions (CI + deploy) · GitHub Copilot · Azure CLI.

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
├── infra/             # Azure (Bicep + Azure CLI)
├── scripts/
└── docs/              # interno, español
```

**Notas sobre la propuesta:**

1. **Azure Functions fuera; solo Container Apps.** La propuesta consolida en Container Apps
   (scale-to-zero ya es serverless). Menos superficie que mantener arriba 3 semanas. Functions
   queda opcional si la ingesta lo pide.
2. **`data/scenarios/` = el *demo seed*** que marqué: ahí vive el guion plantado de *Ashford*.
3. **Frontend:** estado con **Zustand**, i18n con **react-i18next** (es/en).
4. **Modelo de Foundry:** se elige al verificar disponibilidad/cuota/latencia en la cuenta; no
   se entrena nada. Cliente de modelo intercambiable como respaldo.
5. **Nombres sintéticos:** mantener los del README (*Ashford*, *Northbridge*, *Hartley*).

---

## 2. Arquitectura en cuatro capas

```
Eventos sintéticos  ─►  Motor de métricas  ─►  Enjambre de agentes  ─►  Frontend
   (Layer 1)              (Layer 2, código)       (Layer 3, MAF+Foundry)   (Layer 4)
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
- **Demo seed (crítico, ya reflejado en `data/scenarios/`):** además del modo procedural, el
  generador acepta un *guion plantado* que inyecta un patrón concreto en el historial y en el
  partido en vivo. Para el clímax: *Ashford* arrastra un patrón de "concede tras perder el
  balón en medio campo" en varios fixtures previos, y en el vivo vuelve a pasar y termina en
  gol de *Hartley*. Sin este gancho, la frase clímax no tiene de dónde salir.
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
cada evento. Esto controla latencia y costo de Foundry y concentra el LLM donde aporta.

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
Esa comparación va en la evaluación (§7, día 6–7) y es munición directa para el criterio 5.

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

## 6. Layer 4 — Frontend (criterio 4 = 20%, no es relleno)

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

## 7. Plan de 8 días (paralelizable)

> Las capas bajas primero: si el universo y las métricas se atrasan, los agentes se quedan sin
> materia prima. La UI mínima arranca el día 2 para que **siempre** haya algo demostrable.

| Día | Fecha | Hito |
|---|---|---|
| 1 | 20/10 (hoy) | Congelar este doc. Scaffold monorepo + CI. Definir **en código** los contratos: entidades, taxonomía de eventos y `MatchContext`. Esto desbloquea el trabajo en paralelo |
| 2 | 21/10 | Generador de universo (clubes, jugadores, media temporada) + gancho de *demo seed*. Arranca motor de métricas (posesión, pass network, presión). Scaffold de frontend (Vite, i18n, routing, componente de cancha stub) |
| 3 | 22/10 | Motor de métricas completo + tests con asserts. Reproductor de stream con reloj + API `/stream` (SSE). Frontend: línea de tiempo + mapa de cancha consumiendo el stream |
| 4 | 23/10 | Agentes sobre MAF: Analyst + Historian con Foundry. Blackboard. Orchestrator fan-out/fan-in |
| 5 | 24/10 | Narrator + Personalizer. Conflictos (desacuerdo de causa). Fallo del Historian → parcial. Salida multi-idioma |
| 6 | 25/10 | Deploy serverless en Azure (Container Apps + Postgres + Foundry). Baseline de un solo agente para la comparación. Pulido de UX: dos modos, switch, procedencia del clímax |
| 7 | 26/10 | Grabar el partido demo. QA punta a punta desde entorno limpio. Instrucciones de prueba. README final en inglés. Guion del video |
| 8 | 27/10 | Grabar y editar video <2 min. **Entregar de día, no al filo de la 1:59 a. m.** Dejar la demo arriba (no apagar hasta el 10 de noviembre) |

### Guion del video (<2 min) — arco "construir hacia el párrafo"

| Tramo | Qué se ve |
|---|---|
| 0:00–0:20 | **El problema.** Salida típica ("Gol de Hartley, 62'") vs lo que promete TactiX. Gancho corto |
| 0:20–1:10 | **El clímax.** Partido en vivo con el mapa de cancha; el enjambre arma el párrafo contextual y se muestra la procedencia: qué aportó Analyst, Historian y Narrator, y de qué eventos sale |
| 1:10–1:40 | **Lo multi-agente.** La discrepancia honesta Analyst vs Historian con su evidencia; luego tumbamos al Historian y el reporte sale parcial y etiquetado (recuperación) |
| 1:40–2:00 | **Personalización.** Switch analista↔afición y es/en sobre el mismo momento; cierre con el baseline de un solo agente al lado para rematar la tesis |

Todo lo demostrable primero: lo que no entra en estos 2 minutos no manda sobre lo que sí.

---

## 8. Mapa a la rúbrica (5 × 20%)

| Criterio | Dónde lo ganamos |
|---|---|
| 1. Implementación tecnológica | MAF + Foundry + Azure serverless bien hechos; código estructurado, tests deterministas, README claro |
| 2. Diseño agéntico e innovación | Fan-out/fan-in sobre blackboard, discrepancia honesta con reconciliación, degradación elegante |
| 3. Impacto y aplicabilidad | Problema real (explicar *por qué* importa un momento); deploy serverless real que queda arriba |
| 4. UX y presentación | Dos modos genuinos, mapa de cancha, switch e idioma en vivo, clímax con procedencia; balance front/back |
| 5. Cumplimiento de categoría | Roles distintos, estado compartido + handoffs, recuperación de fallos, resultado que un solo agente no lograría |

---

## 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Foundry con cuota/latencia en la demo | Cliente de modelo intercambiable; el motor determinista da una base sin LLM |
| "Coordenadas + posesiones" es lo más caro de simular | Máquina de estados simple y determinista; afinar con reglas, no con ML |
| Datos futbolísticos ricos = más simulación/métricas | Fasear: primero el catálogo núcleo (posesión, pase, tiro, presión), luego las avanzadas (xG race, ratings, físico). El núcleo ya alcanza para una demo sólida |
| "UX al final" se come el tiempo | UI mínima en paralelo desde el día 2; siempre hay algo demostrable |
| Entrega al filo de la 1:59 a. m. | Cerrar el día 27 de día, con margen |
| Demo se cae durante evaluación | Serverless scale-to-zero + run grabado como respaldo del video; no apagar hasta 10/11 |

---

## 10. Puntos abiertos — resueltos (reunión del 20/10)

- **Estado del frontend:** Zustand. **i18n:** react-i18next (es/en). *(§1)*
- **Personalización:** 4 ejes — idioma, modo, club favorito, jugador foco. *(§6)*
- **Guion del video:** arco "construir hacia el párrafo". *(§7)*
- **Licencia:** MIT (archivo `LICENSE` + README).

**Me toca cerrarlos al codear (no bloquean, default documentado):**

- Parámetros de los modelos xG/xT/xA-like (pesos por zona) y umbral del `pass network`.
- Esquema exacto de la base de datos → modelos SQLAlchemy + primera migración Alembic (día 1).
