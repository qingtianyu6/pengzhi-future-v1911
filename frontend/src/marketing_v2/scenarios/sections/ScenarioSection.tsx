import SceneIcon from '../components/SceneIcon'

type Card = { icon: string; title: string; desc: string }
type Props = {
  no: string
  title: string
  desc: string
  image: string
  imageAlt: string
  cards: Card[]
  benefits: string[]
  note: string
}

export default function ScenarioSection({
  no,
  title,
  desc,
  image,
  imageAlt,
  cards,
  benefits,
  note,
}: Props) {
  return (
    <section className="scenario-section">
      <div className="scenario-inner">
        <div className="scenario-title">
          <div className="scenario-leaf">◒</div>
          <div>
            <h2><span>{no}</span> {title}</h2>
            <p>{desc}</p>
          </div>
          <div className="scenario-note">{note}<i /></div>
        </div>

        <div className="scenario-grid">
          <div className="scenario-photo">
            <img src={image} alt={imageAlt} />
          </div>

          {cards.map((c) => (
            <div className="scenario-card" key={c.title}>
              <span><SceneIcon name={c.icon} /></span>
              <strong>{c.title}</strong>
              <small>{c.desc}</small>
            </div>
          ))}

          <div className="benefit-card">
            <div className="benefit-head">
              <SceneIcon name="trend" />
              <strong>典型收益</strong>
            </div>
            {benefits.map((x) => <p key={x}>{x}</p>)}
          </div>
        </div>
      </div>
    </section>
  )
}
