# TactiX — brief de producto

> **Documento interno del equipo (español).** Reemplaza a los antiguos `CONTEXTO-HACKATHON.md` y
> `JUDGING-RUBRIC.md` (ahora en `docs/archive/`) como la referencia de "qué estamos construyendo
> y por qué". La especificación técnica viva está en `DECISIONES-Y-PLAN.md`.

---

## Qué es TactiX

Un **SaaS de análisis táctico de fútbol**. Toma un stream de eventos de un partido y lo
convierte en:

- **inteligencia táctica explicable y con evidencia** (métricas deterministas, patrones,
  pass networks, mapas de tiro, contexto histórico), y
- **narración contextual** que explica *por qué* un momento importa, no solo que ocurrió.

El público principal es el **analista** (clubes, scouts, medios, formación). Hay un segundo
público aficionado (modo afición, narrativa más ligera) que puede crecer después, pero el
producto de pago se centra en el analista.

El valor está en el **backend + el enjambre de agentes en vivo**: lo que diferencia a TactiX de
un dashboard de estadísticas es la explicación multi-agente con procedencia, no las cifras.

---

## No-negociables

Los mismos de `CLAUDE.md`, resumidos aquí por contexto:

1. **Solo datos sintéticos.** No tenemos fuente ni acceso a datos reales; el universo sintético
   generado por el proyecto **es** el modelo de datos del producto. Ingerir datos reales sería
   una decisión futura con tema de licencias por resolver.
2. **Métricas en código, nunca por un modelo.** Toda afirmación trazable a sus eventos.
3. **Proveedor de modelo intercambiable.** Contrato neutral; Foundry es un adaptador; nada asume
   Azure.
4. **Repo público, cero secretos.**

---

## Pipeline (de la etapa hackathon, sigue siendo buen marco)

Las cinco etapas que ordenan el producto de punta a punta:

1. **Ingest** — recibir eventos del partido según ocurren (pases, tiros, entradas, cambios de
   posesión, presión, metadata). Hoy: stream sintético reproducible.
2. **Interpret** — convertirlos en estadísticas, patrones y contexto (motor determinista).
3. **Explain** — explicar *por qué* un momento importa (enjambre de agentes).
4. **Render** — llevar ese insight a pantalla junto al partido (frontend, mapa de cancha).
5. **Personalize** — que la misma inteligencia llegue a un analista y a un aficionado como dos
   experiencias distintas, en es/en.

Un producto que solo genera métricas no tiene audiencia; uno que solo personaliza no tiene nada
que personalizar. Hay que cubrir ambos lados.

---

## La tesis multi-agente (nuestra vara de calidad)

El corazón del producto es que los agentes especializados:

- tienen **roles distintos**,
- **coordinan mediante estado compartido (`MatchContext`) y handoffs efectivos**,
- **se recuperan de fallos** (un agente caído → reporte parcial etiquetado, no un error),
- y entregan un resultado de punta a punta **que un solo agente no lograría igual de bien**.

El handoff **Historian → Narrator** es lo que hace la narración contextual en vez de
descriptiva. Para *probarlo* y no solo afirmarlo, existe un baseline de un solo agente contra el
que comparar el enjambre.

---

## Modelo de sesión del producto

- **Privado por analista, por defecto.** Cada usuario tiene su sesión, con scrubbing
  independiente. Es lo que espera un SaaS de analista.
- **Colaboración (co-viewing) opcional.** Compartir una sesión en vivo para que varios vean el
  mismo momento. El reloj compartido actual es la base de esto, pero deja de ser el default.

Esto implica trabajo pendiente de producto (auth, propiedad de sesión por usuario), listado en
el roadmap de `DECISIONES-Y-PLAN.md`.

---

## Principios de calidad (heredados de la rúbrica, siguen vigentes)

- **Preparación para producción**: manejo de errores, configuración, logs y un despliegue real
  cuentan de verdad.
- **Balance frontend/backend**: un backend brillante con un frontend descuidado es medio
  producto.
- **Código legible**: estructura, nombres y documentación son criterio propio.
- **Alcance disciplinado**: punta a punta antes que más módulos; cada feature justifica a qué
  aporta.
