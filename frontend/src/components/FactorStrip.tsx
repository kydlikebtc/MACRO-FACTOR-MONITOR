interface FactorStripProps {
  bullFactors: string[]
  neutralFactors: string[]
  bearFactors: string[]
}

function PillList({ items, cls }: { items: string[]; cls: string }) {
  if (items.length === 0) {
    return <span className="no-factors">&mdash;</span>
  }
  return (
    <>
      {items.map((item) => (
        <span key={item} className={`factor-pill ${cls}`}>
          {item}
        </span>
      ))}
    </>
  )
}

export default function FactorStrip({
  bullFactors,
  neutralFactors,
  bearFactors,
}: FactorStripProps) {
  return (
    <div className="factor-strip">
      <div className="strip-col">
        <div className="strip-col-title bull">
          BULLISH FACTORS <span className="count">{bullFactors.length}</span>
        </div>
        <PillList items={bullFactors} cls="pill-bull" />
      </div>
      <div className="strip-col">
        <div className="strip-col-title neutral">
          NEUTRAL FACTORS <span className="count">{neutralFactors.length}</span>
        </div>
        <PillList items={neutralFactors} cls="pill-neutral" />
      </div>
      <div className="strip-col">
        <div className="strip-col-title bear">
          BEARISH FACTORS <span className="count">{bearFactors.length}</span>
        </div>
        <PillList items={bearFactors} cls="pill-bear" />
      </div>
    </div>
  )
}
