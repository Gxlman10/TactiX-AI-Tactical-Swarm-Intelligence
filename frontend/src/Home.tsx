import { fixture } from "./features/match/model";
import { useState, type ReactNode } from "react";
import {
  ArrowDown,
  ArrowUpRight,
  Crosshair,
  Graph,
  List,
  X,
} from "@phosphor-icons/react";
import { useStudio } from "./features/preferences/store";
import "./home.css";

const copy = {
  en: {
    explore: "Explore",
    approach: "The approach",
    studio: "Match studio",
    open: "Enter the studio",
    eyebrow: "Football. Read differently.",
    title: "The game.",
    title2: "Beyond the score.",
    intro:
      "See the patterns. Understand the moment. Follow every insight back to the pitch.",
    scroll: "Discover TactiX",
    visual: "Fictional athletes. A new perspective.",
    purpose: "More than what happened.",
    purpose2: "Understand why it mattered.",
    purposeIntro:
      "A tactical workspace that connects the action, the numbers and the story.",
    features: [
      [
        "Read the pitch",
        "Pass connections, pressure and shots. A clearer view of the game.",
      ],
      [
        "Connect the moments",
        "Explore how a midfield loss becomes a goal. Then look back across the season.",
      ],
      [
        "Follow the evidence",
        "Open any metric to inspect the recorded actions behind it.",
      ],
    ],
    method: "Different specialists. One connected story.",
    methodIntro:
      "Five roles, built to connect their findings rather than tell five separate stories.",
    roles: ["Analyst", "Historian", "Narrator", "Personalizer", "Orchestrator"],
    details: [
      "Finds tactical patterns in computed metrics.",
      "Connects the moment to season history.",
      "Turns supported findings into a match story.",
      "Adapts the view to your language and focus.",
      "Coordinates the handoffs and surfaces gaps.",
    ],
    agentNote:
      "Live agent narration requires a configured model. Recorded match evidence is available now.",
    moment: "One moment. A bigger picture.",
    momentLabel: "The Ashford scenario",
    momentBody:
      "A midfield loss. A recovery. Hartley scores. Explore the sequence that makes the historical pattern visible.",
    seconds: "seconds from loss to goal",
    appearances: "consecutive appearances with this pattern",
    evidence: "Authored scenario · event backed evidence",
    demoTitle: "Your view of the game starts here.",
    demoIntro: "Connect to the match server, or explore the local rehearsal.",
    footer: "Fictional clubs. Synthetic data. Traceable intelligence.",
    competition: "Built for Inside the Game",
    menu: "Open navigation",
    close: "Close navigation",
  },
  es: {
    explore: "Explorar",
    approach: "Cómo funciona",
    studio: "Estudio de partido",
    open: "Entrar al estudio",
    eyebrow: "El fútbol. Otra lectura.",
    title: "El juego.",
    title2: "Más allá del marcador.",
    intro:
      "Descubre patrones. Entiende el momento. Sigue cada hallazgo hasta la cancha.",
    scroll: "Descubre TactiX",
    visual: "Jugadores ficticios. Una nueva perspectiva.",
    purpose: "Más que saber qué pasó.",
    purpose2: "Entiende por qué importó.",
    purposeIntro:
      "Un espacio táctico que conecta la acción, los números y la historia.",
    features: [
      [
        "Lee la cancha",
        "Conexiones de pases, presión y tiros. Una lectura más clara del juego.",
      ],
      [
        "Conecta los momentos",
        "Explora cómo una pérdida se convierte en gol. Después, mira la temporada.",
      ],
      [
        "Sigue la evidencia",
        "Abre una métrica y consulta las acciones que la respaldan.",
      ],
    ],
    method: "Distintos especialistas. Una historia conectada.",
    methodIntro:
      "Cinco roles diseñados para conectar hallazgos, en lugar de contar cinco historias aisladas.",
    roles: [
      "Analista",
      "Historiador",
      "Narrador",
      "Personalizador",
      "Orquestador",
    ],
    details: [
      "Busca patrones tácticos en métricas calculadas.",
      "Conecta el momento con la historia de la temporada.",
      "Convierte hallazgos respaldados en una historia del partido.",
      "Adapta la vista a tu idioma y tu foco.",
      "Coordina los relevos y muestra las limitaciones.",
    ],
    agentNote:
      "La narración de agentes en vivo requiere un modelo configurado. La evidencia del partido ya se puede explorar.",
    moment: "Un momento. Una historia más grande.",
    momentLabel: "El escenario Ashford",
    momentBody:
      "Una pérdida. Una recuperación. Gol de Hartley. Explora la secuencia que revela el patrón histórico.",
    seconds: "segundos de la pérdida al gol",
    appearances: "apariciones consecutivas con este patrón",
    evidence: "Escenario autoral · evidencia en eventos",
    demoTitle: "Tu lectura del juego empieza aquí.",
    demoIntro: "Conecta con el servidor del partido o explora el ensayo local.",
    footer: "Clubes ficticios. Datos sintéticos. Inteligencia trazable.",
    competition: "Creado para Inside the Game",
    menu: "Abrir navegación",
    close: "Cerrar navegación",
  },
};

export function Home({ sessionPanel }: { sessionPanel: ReactNode }) {
  const language = useStudio((s) => s.language);
  const setLanguage = useStudio((s) => s.setLanguage);
  const c = copy[language];
  const [menu, setMenu] = useState(false);
  const [role, setRole] = useState(0);
  const icons = [Graph, Crosshair, ArrowUpRight];
  return (
    <div className="home-page">
      <a className="skip" href="#home-main">
        {language === "es" ? "Ir al contenido" : "Skip to content"}
      </a>
      <header className="home-nav">
        <a className="home-brand" href="/" aria-label="TactiX home">
          Tacti<span>X</span>
          <i>✳</i>
        </a>
        <nav aria-label={c.menu} className={menu ? "is-open" : ""}>
          <a href="#explore" onClick={() => setMenu(false)}>
            {c.explore}
          </a>
          <a href="#approach" onClick={() => setMenu(false)}>
            {c.approach}
          </a>
          <a href="#demo" onClick={() => setMenu(false)}>
            {c.studio}
            <ArrowUpRight size={14} />
          </a>
        </nav>
        <div className="home-nav-tools">
          <button
            className="home-language"
            onClick={() => setLanguage(language === "en" ? "es" : "en")}
            aria-label={
              language === "en" ? "Cambiar a español" : "Switch to English"
            }
          >
            {language.toUpperCase()}
          </button>
          <img
            className="home-competition"
            src="/images/competition-logo.png"
            alt="Premier League"
            width="32"
            height="32"
          />
          <button
            className="home-menu"
            aria-label={menu ? c.close : c.menu}
            aria-expanded={menu}
            onClick={() => setMenu(!menu)}
          >
            {menu ? <X size={24} /> : <List size={24} />}
          </button>
        </div>
      </header>
      <main id="home-main">
        <section className="home-hero" aria-labelledby="home-title">
          <div className="hero-coordinate" aria-hidden="true">
            TX / 01 — MATCH INTELLIGENCE
          </div>
          <div className="hero-photo">
            <img
              src="/images/tactix-athletes.webp"
              alt={c.visual}
              fetchPriority="high"
              width="1536"
              height="1024"
            />
          </div>
          <div className="hero-orbit" aria-hidden="true">
            <span>62:00</span>
            <Crosshair size={32} />
          </div>
          <div className="hero-copy">
            <p className="home-kicker">
              <span />
              {c.eyebrow}
            </p>
            <h1 id="home-title">
              {c.title}
              <br />
              <span>{c.title2}</span>
            </h1>
            <p className="hero-intro">{c.intro}</p>
            <a className="home-cta" href="#demo">
              {c.open}
              <ArrowUpRight size={20} />
            </a>
          </div>
          <div className="hero-bottom">
            <a href="#explore">
              <ArrowDown size={18} />
              {c.scroll}
            </a>
            <span>TACTICAL SWARM INTELLIGENCE</span>
            <span>01 / 04</span>
          </div>
        </section>
        <section
          className="home-purpose home-section"
          id="explore"
          aria-labelledby="purpose-title"
        >
          <div className="section-overline">
            <span>01 / TACTIX</span>
            <Crosshair size={18} />
          </div>
          <div className="home-section-heading">
            <h2 id="purpose-title">
              {c.purpose}
              <br />
              <span>{c.purpose2}</span>
            </h2>
            <p>{c.purposeIntro}</p>
          </div>
          <div className="home-benefits">
            {c.features.map(([title, text], index) => {
              const Icon = icons[index];
              return (
                <article key={title}>
                  <span className="feature-index">0{index + 1}</span>
                  <Icon size={32} weight="light" />
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              );
            })}
          </div>
        </section>
        <section
          className="home-method home-section"
          id="approach"
          aria-labelledby="method-title"
        >
          <div className="section-overline">
            <span>02 / THE SWARM</span>
            <span>5 SPECIALISTS → 1 WORKFLOW</span>
          </div>
          <div className="home-section-heading">
            <h2 id="method-title">{c.method}</h2>
            <p>{c.methodIntro}</p>
          </div>
          <div
            className="home-agent-track"
            role="group"
            aria-label={c.approach}
          >
            {c.roles.map((name, index) => (
              <button
                key={name}
                aria-label={`${String(index + 1).padStart(2, "0")} ${name}`}
                aria-pressed={role === index}
                onClick={() => setRole(index)}
              >
                <span>0{index + 1}</span>
                {name}
                <ArrowUpRight size={20} />
              </button>
            ))}
          </div>
          <div className="home-agent-description" aria-live="polite">
            <span>{c.roles[role]}</span>
            <p>{c.details[role]}</p>
          </div>
          <p className="home-agent-note">{c.agentNote}</p>
        </section>
        <section
          className="home-moment home-section"
          aria-labelledby="moment-title"
        >
          <div className="moment-art" aria-label={c.evidence} role="img">
            <svg viewBox="0 0 600 400" aria-hidden="true">
              <g fill="none" stroke="currentColor">
                <path d="M24 24H576V376H24ZM300 24V376M24 110H120V290H24M576 110H480V290H576" />
                <circle cx="300" cy="200" r="64" />
              </g>
              <path className="moment-route" d="M300 200L330 200L108 300" />
              <circle cx="300" cy="200" r="8" fill="#eeefe8" />
              <circle cx="330" cy="200" r="6" fill="#b8ff69" />
              <circle cx="108" cy="300" r="12" fill="#b8ff69" />
            </svg>
            <span className="moment-clock">
              62:00<span>ASHFORD / NORTHBRIDGE</span>
            </span>
            <span className="moment-caption">{c.evidence}</span>
          </div>
          <div className="moment-copy">
            <p className="home-kicker">03 / {c.momentLabel}</p>
            <h2 id="moment-title">{c.moment}</h2>
            <p>{c.momentBody}</p>
            <div className="moment-facts">
              <div>
                <strong>
                  {fixture.context.climax.elapsed_seconds}
                  <span>s</span>
                </strong>
                <span>{c.seconds}</span>
              </div>
              <div>
                <strong>
                  {String(
                    fixture.context.verified_consecutive_matches,
                  ).padStart(2, "0")}
                </strong>
                <span>{c.appearances}</span>
              </div>
            </div>
          </div>
        </section>
        <section
          className="home-demo home-section"
          id="demo"
          aria-labelledby="demo-title"
        >
          <p className="home-kicker">04 / MATCH STUDIO</p>
          <h2 id="demo-title">{c.demoTitle}</h2>
          <p>{c.demoIntro}</p>
          {sessionPanel}
        </section>
      </main>
      <footer className="home-footer">
        <a className="home-brand" href="#home-main">
          Tacti<span>X</span>
          <i>✳</i>
        </a>
        <p>{c.footer}</p>
        <div>
          <img
            src="/images/competition-logo.png"
            alt="Premier League"
            width="28"
            height="28"
          />
          <span>
            {c.competition}
            <br />
            Microsoft × Premier League
          </span>
        </div>
      </footer>
    </div>
  );
}
