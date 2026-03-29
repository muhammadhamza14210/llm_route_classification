'use client'

import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar } from 'recharts'

interface Overview { total_queries: number; total_saved: number; avg_quality: number; avg_latency: number }
interface RoutingRow { tier: string; total_queries: number; escalation_rate_pct: number; avg_quality_score: number; avg_latency_ms: number; total_escalated: number; total_bumped: number }
interface CostRow { tier: string; total_queries: number; avg_cost_usd: number; total_cost_usd: number; total_saved_usd: number; avg_quality_score: number; avg_latency_ms: number; quality_per_dollar: number }
interface QualityRow { query_date: string; queries: number; avg_quality: number }

const TIER: Record<string, { color: string; bg: string; border: string; model: string }> = {
  small:  { color: '#00c9a0', bg: '#00c9a010', border: '#00c9a025', model: 'gpt-4o-mini' },
  medium: { color: '#7c6fff', bg: '#7c6fff10', border: '#7c6fff25', model: 'o3-mini' },
  large:  { color: '#ff5f5f', bg: '#ff5f5f10', border: '#ff5f5f25', model: 'gpt-4o' },
}

function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ background: '#13131f', border: '1px solid #1f1f30', borderRadius: 12, padding: '1.1rem 1.25rem', ...style }}>
      {children}
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: '0.62rem', color: '#6b6b8a', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600, marginBottom: 14 }}>
      {children}
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#13131f', border: '1px solid #2a2a3e', borderRadius: 8, padding: '0.55rem 0.85rem', fontSize: '0.75rem' }}>
      <div style={{ color: '#6b6b8a', marginBottom: 3, fontSize: '0.68rem' }}>{label}</div>
      <div style={{ color: '#7c6fff', fontFamily: 'Courier New, monospace', fontWeight: 700 }}>
        {typeof payload[0].value === 'number' ? payload[0].value.toFixed(3) : payload[0].value}
      </div>
    </div>
  )
}

export default function AnalyticsPanel() {
  const [overview,  setOverview]  = useState<Overview | null>(null)
  const [routing,   setRouting]   = useState<RoutingRow[]>([])
  const [cost,      setCost]      = useState<CostRow[]>([])
  const [quality,   setQuality]   = useState<QualityRow[]>([])
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [ov, rt, ct, ql] = await Promise.all([
          fetch('/analytics/overview').then(r => r.json()),
          fetch('/analytics/routing').then(r => r.json()),
          fetch('/analytics/cost').then(r => r.json()),
          fetch('/analytics/quality').then(r => r.json()),
        ])
        setOverview(ov); setRouting(rt); setCost(ct)
        setQuality([...ql].reverse())
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return (
    <div style={{ color: '#6b6b8a', fontFamily: 'Courier New, monospace', fontSize: '0.83rem', padding: '4rem 0', textAlign: 'center' }}>
      Loading dashboard...
    </div>
  )

  if (error) return (
    <div style={{ color: '#ff5f5f', fontFamily: 'Courier New, monospace', fontSize: '0.83rem', padding: '1rem', background: '#ff5f5f08', border: '1px solid #ff5f5f25', borderRadius: 10 }}>
      {error} — make sure FastAPI is running on port 8000
    </div>
  )

  const totalQ = routing.reduce((s, r) => s + (r.total_queries || 0), 0)

  // Bar chart data — queries per tier
  const barData = routing.map(r => ({
    tier: r.tier.charAt(0).toUpperCase() + r.tier.slice(1),
    queries: r.total_queries,
    fill: TIER[r.tier]?.color || '#6b6b8a',
  }))

  return (
    <div>

      {/* ── Row 1: Global KPIs ─────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '0.75rem', marginBottom: '1.25rem' }}>

        {/* Total Cost Saved */}
        <Card style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: '#00c9a0' }} />
          <div style={{ fontSize: '0.62rem', color: '#6b6b8a', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600, marginBottom: 6, marginTop: 4 }}>Total Cost Saved</div>
          <div style={{ fontFamily: 'Courier New, monospace', fontSize: '1.8rem', fontWeight: 700, color: '#00c9a0', lineHeight: 1 }}>
            ${(overview?.total_saved ?? 0).toFixed(2)}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#6b6b8a', marginTop: 5 }}>vs always routing to Large</div>
        </Card>

        {/* Queries Processed */}
        <Card style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: '#7c6fff' }} />
          <div style={{ fontSize: '0.62rem', color: '#6b6b8a', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600, marginBottom: 6, marginTop: 4 }}>Queries Processed</div>
          <div style={{ fontFamily: 'Courier New, monospace', fontSize: '1.8rem', fontWeight: 700, color: '#7c6fff', lineHeight: 1 }}>
            {(overview?.total_queries ?? 0).toLocaleString()}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#6b6b8a', marginTop: 5 }}>last 30 days</div>
        </Card>

        {/* Avg Quality */}
        <Card style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: '#7c6fff' }} />
          <div style={{ fontSize: '0.62rem', color: '#6b6b8a', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600, marginBottom: 6, marginTop: 4 }}>Avg Quality Score</div>
          <div style={{ fontFamily: 'Courier New, monospace', fontSize: '1.8rem', fontWeight: 700, color: '#eeeef5', lineHeight: 1 }}>
            {(overview?.avg_quality ?? 0).toFixed(3)}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#6b6b8a', marginTop: 5 }}>relevance · completeness · accuracy</div>
        </Card>

        {/* Avg Latency */}
        <Card style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: '#3a3a55' }} />
          <div style={{ fontSize: '0.62rem', color: '#6b6b8a', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600, marginBottom: 6, marginTop: 4 }}>Avg Latency</div>
          <div style={{ fontFamily: 'Courier New, monospace', fontSize: '1.8rem', fontWeight: 700, color: '#eeeef5', lineHeight: 1 }}>
            {((overview?.avg_latency ?? 0) / 1000).toFixed(1)}s
          </div>
          <div style={{ fontSize: '0.7rem', color: '#6b6b8a', marginTop: 5 }}>weighted across all tiers</div>
        </Card>
      </div>

      {/* ── Row 2: Per-tier KPI cards ──────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '0.75rem', marginBottom: '1.25rem' }}>
        {routing.map(r => {
          const t = TIER[r.tier]
          const c = cost.find(c => c.tier === r.tier)
          const share = totalQ ? ((r.total_queries / totalQ) * 100).toFixed(1) : '0'
          return (
            <div key={r.tier} style={{
              background: t?.bg, border: `1px solid ${t?.border}`,
              borderRadius: 12, padding: '1.1rem 1.25rem', position: 'relative', overflow: 'hidden',
            }}>
              {/* Tier header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 99, background: t?.color }} />
                  <span style={{ fontWeight: 700, fontSize: '0.8rem', color: t?.color, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    {r.tier}
                  </span>
                </div>
                <span style={{ fontSize: '0.68rem', color: '#6b6b8a', fontFamily: 'Courier New, monospace' }}>
                  {t?.model}
                </span>
              </div>

              {/* Stats grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.65rem' }}>
                {[
                  ['Queries',     r.total_queries.toLocaleString()],
                  ['Share',       `${share}%`],
                  ['Avg Quality', (r.avg_quality_score || 0).toFixed(3)],
                  ['Avg Latency', `${((r.avg_latency_ms || 0) / 1000).toFixed(1)}s`],
                  ['Total Cost',  `$${(c?.total_cost_usd || 0).toFixed(2)}`],
                  ['Cost Saved',  `$${(c?.total_saved_usd || 0).toFixed(2)}`],
                  ['Escalation',  `${(r.escalation_rate_pct || 0).toFixed(1)}%`],
                  ['Bumped',      r.total_bumped?.toLocaleString() ?? '—'],
                ].map(([label, val]) => (
                  <div key={label}>
                    <div style={{ fontSize: '0.6rem', color: '#6b6b8a', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>{label}</div>
                    <div style={{
                      fontFamily: 'Courier New, monospace', fontSize: '0.88rem', fontWeight: 700,
                      color: label === 'Cost Saved' ? t?.color : label === 'Escalation' && (r.escalation_rate_pct || 0) > 10 ? '#ff5f5f' : '#eeeef5',
                    }}>
                      {val}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* ── Row 3: Charts ──────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>

        {/* Quality trend */}
        <Card>
          <SectionTitle>Quality Trend — Last 14 Days</SectionTitle>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={quality} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a28" />
              <XAxis dataKey="query_date" tick={{ fill: '#6b6b8a', fontSize: 10 }} tickFormatter={(d: string) => d?.slice(5) ?? ''} axisLine={{ stroke: '#1f1f30' }} tickLine={false} />
              <YAxis domain={[0.5, 1]} tick={{ fill: '#6b6b8a', fontSize: 10 }} axisLine={{ stroke: '#1f1f30' }} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Line type="monotone" dataKey="avg_quality" stroke="#7c6fff" strokeWidth={2} dot={{ fill: '#7c6fff', r: 3, strokeWidth: 0 }} activeDot={{ r: 5, fill: '#7c6fff' }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        {/* Query volume by tier */}
        <Card>
          <SectionTitle>Query Volume by Tier</SectionTitle>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={barData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a28" />
              <XAxis dataKey="tier" tick={{ fill: '#6b6b8a', fontSize: 11 }} axisLine={{ stroke: '#1f1f30' }} tickLine={false} />
              <YAxis tick={{ fill: '#6b6b8a', fontSize: 10 }} axisLine={{ stroke: '#1f1f30' }} tickLine={false} />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null
                  return (
                    <div style={{ background: '#13131f', border: '1px solid #2a2a3e', borderRadius: 8, padding: '0.55rem 0.85rem', fontSize: '0.75rem' }}>
                      <div style={{ color: '#6b6b8a', marginBottom: 3, fontSize: '0.68rem' }}>{label}</div>
                      <div style={{ color: '#eeeef5', fontFamily: 'Courier New, monospace', fontWeight: 700 }}>{(payload[0].value as number).toLocaleString()} queries</div>
                    </div>
                  )
                }}
              />
              <Bar dataKey="queries" radius={[4, 4, 0, 0]}>
                {barData.map((entry, i) => (
                  <rect key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* ── Row 4: Cost breakdown table ────────────────────────────────── */}
      <Card>
        <SectionTitle>Cost Breakdown — All Tiers</SectionTitle>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Tier', 'Model', 'Queries', 'Share', 'Avg Cost / Query', 'Total Cost', 'Total Saved', 'Avg Latency', 'Avg Quality', 'Quality / $'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '0.45rem 0.75rem', fontSize: '0.62rem', color: '#6b6b8a', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', borderBottom: '1px solid #1f1f30' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cost.map(c => {
              const t = TIER[c.tier]
              const share = totalQ ? ((c.total_queries / totalQ) * 100).toFixed(1) : '0'
              return (
                <tr key={c.tier} style={{ transition: 'background 0.1s' }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#0f0f18')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <td style={{ padding: '0.55rem 0.75rem', borderBottom: '1px solid #0f0f18' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                      <span style={{ width: 6, height: 6, borderRadius: 99, background: t?.color, display: 'inline-block' }} />
                      <span style={{ fontSize: '0.78rem', fontWeight: 700, color: t?.color, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{c.tier}</span>
                    </span>
                  </td>
                  <td style={{ padding: '0.55rem 0.75rem', fontSize: '0.75rem', color: '#6b6b8a', fontFamily: 'Courier New, monospace', borderBottom: '1px solid #0f0f18' }}>{t?.model}</td>
                  <td style={{ padding: '0.55rem 0.75rem', fontSize: '0.8rem', color: '#eeeef5', fontFamily: 'Courier New, monospace', borderBottom: '1px solid #0f0f18' }}>{(c.total_queries || 0).toLocaleString()}</td>
                  <td style={{ padding: '0.55rem 0.75rem', fontSize: '0.8rem', color: '#6b6b8a', borderBottom: '1px solid #0f0f18' }}>{share}%</td>
                  <td style={{ padding: '0.55rem 0.75rem', fontSize: '0.8rem', color: '#eeeef5', fontFamily: 'Courier New, monospace', borderBottom: '1px solid #0f0f18' }}>${(c.avg_cost_usd || 0).toFixed(4)}</td>
                  <td style={{ padding: '0.55rem 0.75rem', fontSize: '0.8rem', color: '#eeeef5', fontFamily: 'Courier New, monospace', borderBottom: '1px solid #0f0f18' }}>${(c.total_cost_usd || 0).toFixed(2)}</td>
                  <td style={{ padding: '0.55rem 0.75rem', fontSize: '0.8rem', color: '#00c9a0', fontFamily: 'Courier New, monospace', fontWeight: 700, borderBottom: '1px solid #0f0f18' }}>${(c.total_saved_usd || 0).toFixed(2)}</td>
                  <td style={{ padding: '0.55rem 0.75rem', fontSize: '0.8rem', color: '#6b6b8a', borderBottom: '1px solid #0f0f18' }}>{((c.avg_latency_ms || 0) / 1000).toFixed(1)}s</td>
                  <td style={{ padding: '0.55rem 0.75rem', fontSize: '0.8rem', color: '#eeeef5', borderBottom: '1px solid #0f0f18' }}>{(c.avg_quality_score || 0).toFixed(3)}</td>
                  <td style={{ padding: '0.55rem 0.75rem', fontSize: '0.8rem', color: '#00c9a0', fontFamily: 'Courier New, monospace', borderBottom: '1px solid #0f0f18' }}>{(c.quality_per_dollar || 0).toFixed(1)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>

    </div>
  )
}