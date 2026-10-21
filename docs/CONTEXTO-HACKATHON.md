# Contexto del hackathon — TactiX

> **Documento interno del equipo.** No forma parte de la entrega. Los materiales que se entregan al jurado (README, pitch, video, instrucciones de prueba) van en inglés.

---

## Enlaces oficiales

| Qué | Enlace |
|---|---|
| Sitio oficial (registro + entrega del proyecto) | https://aka.ms/insidethegame |
| Reglamento oficial completo | https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md |
| Página de registro del evento | https://events.microsoft.com/flow/microsoft/plmshackathon/registration/page/landing |
| Livestreams (Microsoft Reactor) | https://developer.microsoft.com/en-us/reactor/series/s-1709/ |
| Microsoft Agent Framework — docs | https://learn.microsoft.com/en-us/agent-framework/overview/ |
| Microsoft Agent Framework — repo | https://github.com/microsoft/agent-framework |
| Microsoft Foundry — docs | https://learn.microsoft.com/en-us/azure/ai-foundry/ |

**Plataforma de entrega:** Innovation Studio. El registro ya está confirmado; el correo con el acceso para crear el perfil del equipo llega dentro de las 48 horas posteriores a la confirmación.

---

## Fechas (hora de Perú)

| Hito | Fecha |
|---|---|
| Cierre de inscripciones | 20 de octubre, 2:00 p. m. ✅ *(ya registrados)* |
| **Fecha límite de entrega** | **28 de octubre, 1:59 a. m.** |
| Evaluación del jurado | 27 de octubre – 10 de noviembre |
| Anuncio de ganadores | máximo 20 de noviembre |

La entrega equivale al 27 de octubre, 11:59 p. m. hora del Pacífico.

**La demo debe seguir funcionando y accesible hasta que termine el periodo de evaluación (10 de noviembre).** No apagar nada antes.

---

## El reto

Construir una solución con IA que transforme **eventos sintéticos de fútbol** en inteligencia de partido explicable, narrativas en tiempo real y resúmenes automáticos, aptos para escenarios de estudio, transmisión o streaming, y flexibles para que cualquier aficionado adapte su experiencia.

El pipeline que piden tiene cinco etapas:

1. **Ingest** — recibir eventos del partido según ocurren (pases, tiros, entradas, cambios de posesión, eventos de presión, metadata).
2. **Interpret** — convertirlos en estadísticas, patrones y contexto.
3. **Explain** — explicar *por qué* un momento importa, no solo reportar que ocurrió.
4. **Render** — convertir ese insight en algo que pueda ir en pantalla junto al partido.
5. **Personalize** — que la misma inteligencia llegue a un analista y a un aficionado casual como dos experiencias genuinamente distintas.

El reglamento lo dice sin rodeos: un proyecto que solo genera métricas no tiene audiencia, y uno que solo personaliza no tiene nada que personalizar. Hay que cubrir ambos lados.

Líneas temáticas que el reto menciona explícitamente: inteligencia de partido en tiempo real, generación de narrativa, explicabilidad, **innovación en datos** (crear o extender datasets sintéticos realistas) y **narrativa multi-idioma**.

---

## Categorías

Hay 2 Grandes Premios (primer y segundo lugar) y 4 premios por categoría:

- Best Use of Microsoft Foundry Project
- Best Enterprise Solution
- **Best Multi-Agent System** ← **nuestra categoría objetivo**
- Best Azure Cloud Native Integration

Un proyecto puede ganar como máximo un Gran Premio **y** un premio de categoría.

### Qué evalúan en Best Multi-Agent System

Textualmente, el jurado mira si los agentes especializados:

- tienen **roles distintos**,
- **coordinan mediante estado compartido y handoffs efectivos**,
- **se recuperan de fallos**,
- y entregan un resultado de punta a punta **que un solo agente no lograría igual de bien**.

Ese último punto es el que hay que poder demostrar explícitamente en el video y el README.

---

## Criterios de evaluación

La evaluación tiene dos etapas. La primera es un **pass/fail**: verifica que el proyecto encaje razonablemente con el tema y aplique las tecnologías del hackathon. Los que pasan se evalúan con cinco criterios **de peso igual, 20% cada uno**:

> El texto oficial literal, en inglés, está en [`JUDGING-RUBRIC.md`](JUDGING-RUBRIC.md). Lo de abajo es la traducción de trabajo.

### 1. Implementación tecnológica — 20%

- Buenas prácticas de desarrollo de software
- Uso efectivo de las *hero technologies*
- Código bien estructurado, documentado y mantenible

### 2. Diseño agéntico e innovación — 20%

- Aplicación creativa de patrones de IA agéntica
- Orquestación sofisticada de agentes o colaboración multiagente
- Implementación de IA novedosa, o mejoras significativas sobre enfoques existentes

### 3. Impacto y aplicabilidad real — 20%

- Relevancia del problema que se resuelve
- Preparación para despliegue en producción
- Impacto potencial sobre desarrolladores, empresas o usuarios finales

### 4. Experiencia de usuario y presentación — 20%

- Experiencia de usuario bien diseñada e intuitiva
- Comunicación clara del valor del proyecto en la demo
- Balance entre implementación de frontend y backend

### 5. Cumplimiento de la categoría — 20%

- Cumplir con la descripción de la categoría del hackathon correspondiente (en nuestro caso, **Best Multi-Agent System**)

**Hero technologies** que el reglamento nombra: Microsoft Foundry, Agent Framework, Azure MCP, GitHub Copilot Agent Mode, Fabric, GitHub SDK, GitHub CLI, Azure Apps and AI Services, bases de datos de Azure.

Conclusión práctica: no gana el proyecto más grande, sino el que funciona, está bien explicado y se ve bien. Presentación pesa lo mismo que el código.

---

## Qué hay que entregar

1. **Proyecto funcional**, que instale y corra de forma consistente en la plataforma para la que fue construido, y que funcione como se muestra en el video.
2. **Repositorio público de GitHub** con el código.
3. **Video demo de menos de 2 minutos**, con URL pública (YouTube, Vimeo, Facebook Video o Youku), que muestre el proyecto funcionando. Los jueces no están obligados a ver más allá de los 2 minutos. Sin música ni marcas de terceros sin permiso.
4. **Pitch / descripción**: qué construimos, qué tecnologías de Microsoft y Azure usamos, qué hace y qué problema resuelve.
5. **Acceso para evaluación**: enlace a sitio, demo funcional o build de prueba. Si es privado, incluir credenciales en las instrucciones. Gratis y sin restricciones hasta que termine la evaluación.
6. **Todo en inglés**, o con traducción al inglés del video, la descripción, las instrucciones de prueba y cualquier otro material.

---

## Reglas duras — esto descalifica

- ❌ **Reutilizar un proyecto previo.** Debe ser creado después del inicio del periodo de inscripción (29 de septiembre).
- ❌ **Usar datos, video o material real de partidos.** Solo datos sintéticos y realistas, generados por nosotros. No se redistribuye material oficial a los participantes; cada equipo es responsable de su propia data.
- ❌ **Repo privado.** Debe ser público para que la entrega se considere.
- ❌ **Demo caída** durante la evaluación.
- ❌ Jugadores, clubes, escudos o marcas reales (incluye bases licenciadas tipo FIFA/PES). Todo ficticio.
- ❌ Contenido ofensivo, o que refleje negativamente sobre Microsoft.
- ❌ Integrar SDKs, APIs o datos de terceros sin estar autorizados por sus términos.

El trabajo debe ser original y de propiedad del equipo. Se puede usar software open source siempre que se cumplan sus licencias y que lo que construimos amplíe su funcionalidad.

---

## Equipo y premios

- Máximo **4 integrantes**. El equipo designa un **Representante** que registra y entrega en nombre de todos.
- Perú es elegible. La lista de exclusión es Brasil, Quebec, Rusia, Crimea, Cuba, Irán, Corea del Norte, Sudán, Siria y países designados por OFAC.

Premios (valor aproximado, por integrante, en tarjeta electrónica de regalo):

| Premio | Monto por integrante | Extras |
|---|---|---|
| Primer lugar | ~US$4,000 | entrada digital a un partido (~US$1,000) + vale US$50 + difusión |
| Segundo lugar | ~US$2,500 | entrada digital a un partido (~US$1,000) + vale US$50 + difusión |
| Cada categoría | ~US$1,500 | vale US$50 + difusión |

Son e-Gift Cards en USD, no transferencias. Cada ganador responde por los impuestos de su jurisdicción y puede tener que firmar formularios (W-8BEN para no residentes de EE. UU.) con plazo de 10 días hábiles.

---

## Convención de idioma del proyecto

| Qué | Idioma |
|---|---|
| Documentos internos del equipo (`docs/`, este archivo) | Español |
| README, código, comentarios, commits, nombres de variables | Inglés |
| Video, pitch, instrucciones de prueba | Inglés |
| Salida del producto al usuario final | Multi-idioma (es/en) — es parte del reto |
