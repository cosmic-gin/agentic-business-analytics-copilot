import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { ChartData } from '../types'

const colors = ['#3569c9', '#19a596', '#ca8131']

export default function AnalysisChart({ chart }: { chart: ChartData }) {
  const series = Object.entries(chart.series)
  const axes = <>
    <CartesianGrid vertical={false} stroke="#e6ebf4" />
    <XAxis dataKey={chart.x_key} interval={0} tick={{ fontSize: 11, fill: '#586882' }} tickMargin={9} />
    <YAxis width={45} tick={{ fontSize: 11, fill: '#586882' }}
      unit={chart.unit === 'percent' ? '%' : ''} domain={chart.unit === 'percent' ? [0, 100] : [0, 'auto']} />
    <Tooltip />
    {series.length > 1 && <Legend />}
  </>
  return <section className="card chart-card" aria-labelledby="chart-title">
    <h2 id="chart-title">{chart.title}</h2>
    <p>{chart.unit === 'percent' ? 'Share of valid deliveries' : 'Shipment count'} · Simulated data</p>
    <div className="chart-scroll"><div className="chart-frame" style={{ minWidth: chart.rows.length > 4 ? 485 : 320 }}>
      <ResponsiveContainer width="100%" height={285}>
        {chart.kind === 'line' ? <LineChart data={chart.rows} margin={{ top: 14, right: 12, bottom: 4 }}>
          {axes}{series.map(([key, name], i) => <Line key={key} dataKey={key} name={name}
            stroke={colors[i]} strokeWidth={3} dot={{ r: 3 }} isAnimationActive={false} />)}
        </LineChart> : <BarChart data={chart.rows} margin={{ top: 14, right: 12, bottom: 4 }}>
          {axes}{series.map(([key, name], i) => <Bar key={key} dataKey={key} name={name}
            fill={colors[i]} radius={[5, 5, 0, 0]} maxBarSize={42} isAnimationActive={false} />)}
        </BarChart>}
      </ResponsiveContainer>
    </div></div>
  </section>
}
