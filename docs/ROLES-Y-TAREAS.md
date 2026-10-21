# TactiX — Roles y tareas del equipo

> **Documento interno (español).** Reparto de trabajo para los ~8 días. Se apoya en
> `DECISIONES-Y-PLAN.md` (arquitectura y plan por día). Pensado para hasta 4 integrantes
> (máximo del hackathon) + Claude como acelerador transversal.

---

## Principios de reparto

1. **Las capas bajas desbloquean a las altas.** Universo → Métricas → Agentes → Frontend. El que
   va abajo no puede atrasarse sin frenar a todos.
2. **Contratos primero.** Los esquemas (`domain/`: entidades, eventos, `MatchContext`) se
   congelan el día 1; a partir de ahí cada quien programa contra el contrato, no contra el
   código del otro. Esto permite trabajar en paralelo sin bloquearse.
3. **Nadie toca los archivos de otro rol** salvo acuerdo. Si dos roles necesitan el mismo
   archivo, se habla antes.
4. **Claude (yo) acelero cualquier rol:** genero código, tests, scaffolding y datos. Las
   personas son dueñas de las decisiones, de las credenciales (Foundry/Azure), de la revisión
   y del video. Las subidas al repo van bajo la cuenta del Representante.

El **Representante** (registra y entrega en Innovation Studio) coordina y es dueño del deadline.

---

## Roles

### R1 — Universo y Simulación · *Layers 1–2a*

**Dueño de la materia prima.** Si R1 se atrasa, nadie tiene con qué trabajar → arranca primero.

- Generador de liga: 8–10 clubes con identidad táctica, plantillas con atributos por familia,
  media temporada previa (tabla, forma, head-to-head).
- Máquina de estados de posesiones → stream de eventos con coordenadas y cualificadores.
- **Demo seed** (`data/scenarios/`): el guion plantado de *Ashford* del que sale el clímax.
- Reproductor del partido con reloj (la línea de tiempo que "se ve en vivo").

**Depende de:** nadie. **Desbloquea a:** R2, R3, R4.

### R2 — Métricas y Datos · *Layer 2b + persistencia*

- Motor de métricas determinista (§4 del plan), con la **evidencia** trazable por métrica.
- Tests con asserts (pytest): dado un set fijo de eventos, número conocido.
- Modelos SQLAlchemy + migraciones Alembic; acceso a PostgreSQL.
- API de datos (REST) y el canal **SSE** del stream en vivo.

**Depende de:** R1 (eventos). **Desbloquea a:** R3 (interpretan métricas) y R4 (consume API/SSE).

### R3 — Agentes y Orquestación · *Layer 3*

- Workflow **fan-out/fan-in** sobre Microsoft Agent Framework + estado compartido (blackboard).
- Los 5 agentes (Analyst, Historian, Narrator, Personalizer, Orchestrator) con sus instrucciones,
  herramientas y contratos.
- Conexión a **Foundry** (cliente de modelo intercambiable), activación por ventanas/momentos.
- **Discrepancia** de causa, **recuperación** ante fallo del Historian, y el **baseline de un
  solo agente** para la comparación.

**Depende de:** R1 + R2. **Desbloquea a:** R4 (consume el reporte) y la tesis del video.

### R4 — Frontend y UX · *Layer 4*

- React + TypeScript + Vite; estado con Zustand; i18n con react-i18next (es/en).
- Modo analista y modo afición; **switch** en vivo; selector de idioma.
- **Mapa de cancha** con las coordenadas, timeline, pass network, evidencia desglosable.
- **Procedencia del párrafo clímax** (qué agente aportó cada fragmento).

**Depende de:** R2 (API/SSE) y R3 (reporte). **Arranca en paralelo desde el día 2** con datos
mock, para no nacer el día 7.

### Transversales (se reparten, no son persona dedicada)

- **DevOps/Azure:** Compose local, CI (GitHub Actions), Dockerfile, deploy a Container Apps +
  Postgres administrado, gestión de secretos. Lo lleva R2 o R3 a tiempo parcial, o el Representante.
- **QA y Video:** recorrido principal con Playwright + guion/grabación/edición del video (§7
  del plan). Dueño sugerido: R4 o el Representante. Todos aportan al guion.

---

## Tablero por día (dueño → tarea)

| Día | R1 Universo | R2 Métricas/Datos | R3 Agentes | R4 Frontend |
|---|---|---|---|---|
| 1 | Contratos `domain/` (con Claude) | Esquema BD + Alembic | Diseño de prompts/handoffs | — (espera contratos) |
| 2 | Generador + demo seed | Métricas núcleo | — | Scaffold UI + mapa de cancha (mock) |
| 3 | Reproductor + reloj | Métricas avanzadas + SSE | — | Timeline + cancha con stream |
| 4 | Afinar realismo | Evidencia + API pulida | Analyst + Historian (MAF+Foundry) | Panel de reporte |
| 5 | — | — | Narrator + Personalizer + conflictos + fallo | Dos modos + i18n |
| 6 | — | Deploy datos | Baseline 1 agente + deploy agentes | Switch + procedencia (pulido UX) |
| 7 | QA punta a punta | QA + instrucciones de prueba | QA de agentes | QA + README inglés |
| 8 | — | — | — | Grabar/editar video · entregar de día |

> Las celdas vacías no son ociosidad: son margen para ayudar a quien vaya ajustado o adelantar
> QA. La regla de oro sigue siendo flujo de punta a punta antes que más features.

---

## Cómo encaja Claude

- Genero el scaffolding, los contratos, el código base de cada capa, los tests y los datos
  sintéticos; las personas revisan, deciden y conectan lo que necesita credenciales.
- Puedo tomar el trabajo pesado de cualquier rol en paralelo; díganme en qué capa concentrarme.
- No subo al repo por mi cuenta: dejo los cambios listos y el Representante commitea/sube.

---

## Pendiente de confirmar

- **¿Cuántos son realmente?** Este reparto asume 4. Si son menos, se fusionan roles (lo típico:
  R1+R2 en una persona "backend de datos", R3 solo, R4 solo; o R3+DevOps juntos). Díganme el
  número y lo ajusto.
