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

### Decisiones propuestas por defecto (confírmenlas o corríjanlas)

Estas las elegí yo para no frenar; son fáciles de cambiar:

- **Repo:** monorepo (`backend/`, `frontend/`, `infra/`, `data/`, `docs/`).
- **Transporte del stream en vivo:** Server-Sent Events (SSE) sobre HTTP (más simple que WebSocket para un flujo unidireccional servidor→cliente).
- **Persistencia:** Azure Database for PostgreSQL (serverless/flexible). Supabase local solo para desarrollar rápido si hace falta.
- **IaC:** Bicep para el despliegue en Azure.
- **Modelo de Foundry:** GPT-4o (o el equivalente disponible en la suscripción); cliente intercambiable por si hay cuota/latencia.
- **Nombres sintéticos:** mantener los que ya aparecen en el README (clubes tipo *Ashford*, *Northbridge*; jugador *Hartley*) para consistencia.

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

### Entidades

- **League** — temporada, lista de clubes, calendario.
- **Club** — nombre, ciudad, formación base (p. ej. 4-3-3), *perfil de estilo* (posesión vs
  directo, altura de presión, agresividad), colores para la UI.
- **Player** — nombre, posición, *perfil de atributos* 0–100 (pace, passing, finishing,
  pressing, stamina, positioning) y *tendencias* (p. ej. "pierde el balón bajo presión en
  medio campo", "remata desde el canal izquierdo").
- **Fixture (histórico)** — partido ya jugado: marcador, stats agregadas, racha que dejó.
- **Match (en vivo)** — el partido que se simula/reproduce.
- **Event** — ver §4.
- **Possession** — cadena de eventos de un mismo equipo con inicio, fin y desenlace.

### Generador

- Determinista por **seed** → reproducible y testeable.
- **Demo seed (crítico):** además del modo procedural, el generador acepta un *guion plantado*
  que inyecta un patrón concreto en el historial y en el partido en vivo. Para el clímax
  necesitamos que *Ashford* tenga un patrón recurrente de "concede tras perder el balón en
  medio campo" en varios fixtures previos, y que en el partido en vivo ocurra otra vez y
  termine en gol de *Hartley*. Sin este gancho, la frase clímax no tiene de dónde salir.
- Media temporada previa = suficiente para head-to-head, rachas de forma y tendencias por
  jugador reales.

---

## 4. Layer 2 — Eventos y métricas deterministas

### Taxonomía de eventos

Cada evento: `match_id, minute, second, team, player, type, x, y, [end_x, end_y], outcome,
possession_id, phase`.

Tipos: `pass` (completado/fallado), `carry`, `dribble`, `shot` (on/off/goal/blocked),
`tackle`, `interception`, `clearance`, `foul`, `turnover`, `pressure`, `duel`, `save`,
`substitution`, `card`, `offside`, `corner`, `throw_in`, `kickoff`.

Las **posesiones** encadenan eventos y llevan una *fase*: `build_up → progression →
final_third → outcome`. Esto es lo que habilita leer transiciones y secuencias, no solo
eventos sueltos.

### Simulación de posesiones (para generar eventos realistas sin ML)

Máquina de estados simple por posesión: arranque → progresión (influida por el perfil de
estilo del club y atributos de jugadores) → tercio final → desenlace (tiro/pérdida/falta).
Determinista con seed. El realismo no viene de un modelo, viene de reglas afinadas + ruido
controlado.

### Catálogo de métricas (todo en código, con asserts)

- Posesión % (por tiempo y por pases), con ventana móvil.
- **Pass network** por equipo (nodos = jugadores, aristas = pases completados con peso).
- Entradas al tercio final y al área.
- Progresión por zonas (grid de valor determinista tipo "xT ligero" — **no** es un modelo).
- Eventos de presión y métrica tipo PPDA (pases por acción defensiva).
- Pérdidas y su ubicación.
- Ventanas de transición (tiempo de pérdida → remate).
- Índice de momentum/ritmo = densidad de eventos ponderada en ventana móvil.
- Peligro de remate por ubicación (peso de zona determinista).
- Rachas de forma y head-to-head (desde el historial del universo).

Cada métrica es testeable: dado un set fijo de eventos, el resultado es un número conocido.

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

### Por qué un solo agente no basta (la tesis, para README y video)

El párrafo clímax requiere tres trabajos con **evidencia distinta**: computar el evento
(métricas), reconocer el patrón de temporada (historial) y decidir que vale contarlo
(narrativa). El handoff **Historian → Narrator** es lo que hace la narración *contextual* y no
descriptiva. Cinco prompts en paralelo no lo logran: son jobs distintos con fuentes distintas.

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
- **Selector de idioma** (es/en) en vivo.
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
| 6 | 25/10 | Deploy serverless en Azure (Container Apps + Functions + Postgres + Foundry). Pulido de UX: dos modos, switch, procedencia del clímax |
| 7 | 26/10 | Grabar el partido demo. QA punta a punta desde entorno limpio. Instrucciones de prueba. README final en inglés. Guion del video |
| 8 | 27/10 | Grabar y editar video <2 min. **Entregar de día, no al filo de la 1:59 a. m.** Dejar la demo arriba (no apagar hasta el 10 de noviembre) |

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
| "UX al final" se come el tiempo | UI mínima en paralelo desde el día 2; siempre hay algo demostrable |
| Entrega al filo de la 1:59 a. m. | Cerrar el día 27 de día, con margen |
| Demo se cae durante evaluación | Serverless scale-to-zero + run grabado como respaldo del video; no apagar hasta 10/11 |

---

## 10. Decisiones aún abiertas (próxima ronda)

- Estructura fina del `pass network` y del grid de valor por zonas (parámetros).
- Esquema exacto de la base de datos (se deriva de §3–§4).
- Perfil de personalización: ¿cuántos ejes? (club favorito, jugador foco, idioma, modo) — ¿algo más?
- Guion literal del video de 2 min (orden de planos).
- Licencia del repo (pendiente en el README).
