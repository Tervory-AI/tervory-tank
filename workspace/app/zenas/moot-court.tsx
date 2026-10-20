import { MOOT_LATER, MOOT_LEAD, MOOT_PARTS, MOOT_LABEL, trainingRound } from "./moot";

export function MootCourt() {
  const round = trainingRound();
  return (
    <section className="zn-moot" aria-label={MOOT_LABEL}>
      <header className="zn-head">
        <div>
          <h1>{MOOT_LABEL}</h1>
          <p>
            {MOOT_LEAD} {MOOT_LATER}
          </p>
        </div>
      </header>
      <div className="zn-moot-ground">
        {MOOT_PARTS.map((part) => (
          <article className="zn-card" key={part.id}>
            <h2>{part.title}</h2>
            <p>{round ? round[part.id] : part.empty}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
