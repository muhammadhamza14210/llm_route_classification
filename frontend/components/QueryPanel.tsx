'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'

interface QueryResult {
  query_id: string
  final_tier: 'small' | 'medium' | 'large'
  tier: string
  weighted_score: number
  was_bumped: boolean
  bump_reason: string | null
  content: string
  latency_ms: number
  input_tokens: number
  output_tokens: number
  cost_usd: number
  cost_saved: number
  quality_score: number
  quality_relevance: number
  quality_completeness: number
  quality_accuracy: number
  quality_rationale: string | null
  was_escalated: boolean
  rule_features: {
    has_code_block: boolean
    asks_high_precision: boolean
    asks_compare: boolean
    asks_reasoning: boolean
    has_json_like_text: boolean
    input_token_count: number
    num_distinct_requests: number
  }
  llm_scores: {
    ambiguity: number
    domain_specificity: number
    multi_step: number
    router_confidence: number
    rationale: string | null
  }
}

const TIER = {
  small:  { color: '#00c9a0', bg: '#00c9a012', label: 'Small',  model: 'gpt-4o-mini' },
  medium: { color: '#7c6fff', bg: '#7c6fff12', label: 'Medium', model: 'o3-mini' },
  large:  { color: '#ff5f5f', bg: '#ff5f5f12', label: 'Large',  model: 'gpt-4o' },
}

function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      background: '#13131f', border: '1px solid #1f1f30',
      borderRadius: 12, padding: '1rem 1.25rem', ...style,
    }}>
      {children}
    </div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: '0.65rem', color: '#6b6b8a', textTransform: 'uppercase',
      letterSpacing: '0.1em', fontWeight: 600, marginBottom: 6,
    }}>
      {children}
    </div>
  )
}

function KpiCard({ label, value, color = '#eeeef5', sub }: {
  label: string; value: string; color?: string; sub?: string
}) {
  return (
    <Card style={{ position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: color, opacity: 0.8 }} />
      <div style={{ fontSize: '0.62rem', color: '#6b6b8a', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600, marginBottom: 6, marginTop: 4 }}>
        {label}
      </div>
      <div style={{ fontFamily: 'Courier New, monospace', fontSize: '1.25rem', fontWeight: 700, color, lineHeight: 1.1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: '0.7rem', color: '#6b6b8a', marginTop: 4 }}>{sub}</div>}
    </Card>
  )
}

function Bar({ label, value, color = '#7c6fff' }: { label: string; value: number; color?: string }) {
  return (
    <div style={{ marginBottom: '0.65rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: 5 }}>
        <span style={{ color: '#9999b8' }}>{label}</span>
        <span style={{ color: '#eeeef5', fontFamily: 'Courier New, monospace', fontSize: '0.72rem' }}>{value.toFixed(2)}</span>
      </div>
      <div style={{ background: '#1f1f30', borderRadius: 99, height: 4, overflow: 'hidden' }}>
        <div style={{ width: `${Math.min(value * 100, 100)}%`, height: '100%', background: color, borderRadius: 99, transition: 'width 0.6s cubic-bezier(0.4,0,0.2,1)' }} />
      </div>
    </div>
  )
}

function Flag({ label, value }: { label: string; value: boolean | number | string }) {
  const isBool = typeof value === 'boolean'
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.42rem 0', borderBottom: '1px solid #1a1a28' }}>
      <span style={{ fontSize: '0.75rem', color: '#6b6b8a', fontFamily: 'Courier New, monospace' }}>{label}</span>
      {isBool
        ? <span style={{ fontSize: '0.72rem', fontWeight: 600, color: value ? '#00c9a0' : '#3a3a55' }}>{value ? 'YES' : 'NO'}</span>
        : <span style={{ fontSize: '0.75rem', color: '#eeeef5', fontFamily: 'Courier New, monospace' }}>{value}</span>
      }
    </div>
  )
}

export default function QueryPanel() {
  const [query, setQuery]     = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult]   = useState<QueryResult | null>(null)
  const [error, setError]     = useState<string | null>(null)

  async function handleRun() {
    if (!query.trim() || loading) return
    setLoading(true); setError(null); setResult(null)
    try {
      const res = await fetch('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim() }),
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed') }
      setResult(await res.json())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const t = result ? TIER[result.final_tier] : null

  return (
    <div>
      {/* Input area */}
      <div style={{ position: 'relative', marginBottom: '1.5rem' }}>
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleRun() }}
          placeholder="Ask anything — the router decides which model handles it..."
          rows={4}
          style={{
            width: '100%', background: '#0f0f18', border: '1px solid #1f1f30',
            borderRadius: 12, color: '#eeeef5', fontSize: '0.9rem',
            padding: '1rem 1.25rem 3rem', resize: 'none', outline: 'none',
            transition: 'border-color 0.2s', lineHeight: 1.6,
          }}
          onFocus={e => e.target.style.borderColor = '#7c6fff'}
          onBlur={e => e.target.style.borderColor = '#1f1f30'}
        />
        <div style={{ position: 'absolute', bottom: 12, right: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '0.68rem', color: '#3a3a55' }}>⌘↵</span>
          <button
            onClick={handleRun}
            disabled={loading || !query.trim()}
            style={{
              background: loading ? '#2a2a3e' : '#7c6fff',
              color: loading ? '#6b6b8a' : '#fff',
              border: 'none', borderRadius: 8,
              padding: '0.45rem 1.2rem', fontSize: '0.78rem',
              fontWeight: 600, letterSpacing: '0.02em',
              transition: 'all 0.15s', opacity: !query.trim() ? 0.4 : 1,
            }}
          >
            {loading ? 'Routing...' : 'Run →'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ color: '#ff5f5f', fontSize: '0.83rem', fontFamily: 'Courier New, monospace', marginBottom: '1rem', padding: '0.75rem 1rem', background: '#ff5f5f10', border: '1px solid #ff5f5f30', borderRadius: 8 }}>
          {error}
        </div>
      )}

      {result && t && (
        <>
          {/* Tier banner */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: '1.25rem', padding: '0.75rem 1rem', background: t.bg, border: `1px solid ${t.color}30`, borderRadius: 10 }}>
            <div style={{ width: 8, height: 8, borderRadius: 99, background: t.color }} />
            <span style={{ fontSize: '0.78rem', fontWeight: 600, color: t.color, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              {t.label} · {t.model}
            </span>
            <span style={{ fontSize: '0.72rem', color: '#6b6b8a', marginLeft: 'auto', fontFamily: 'Courier New, monospace' }}>
              score {result.weighted_score.toFixed(4)}
            </span>
            {result.was_bumped && (
              <span style={{ fontSize: '0.7rem', color: '#7c6fff', background: '#7c6fff15', border: '1px solid #7c6fff30', borderRadius: 6, padding: '0.15rem 0.5rem' }}>
                ↑ bumped
              </span>
            )}
            {result.was_escalated && (
              <span style={{ fontSize: '0.7rem', color: '#f5a623', background: '#f5a62315', border: '1px solid #f5a62330', borderRadius: 6, padding: '0.15rem 0.5rem' }}>
                ⚡ escalated
              </span>
            )}
          </div>

          {/* KPI row 1 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '0.75rem', marginBottom: '0.75rem' }}>
            <KpiCard label="Quality"     value={result.quality_score.toFixed(2)}    color="#00c9a0" />
            <KpiCard label="Latency"     value={`${result.latency_ms.toFixed(0)}ms`} />
            <KpiCard label="Cost Saved"  value={`$${result.cost_saved.toFixed(6)}`}  color="#00c9a0" />
            <KpiCard label="Actual Cost" value={`$${result.cost_usd.toFixed(6)}`}    color="#6b6b8a" />
          </div>

          {/* KPI row 2 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <KpiCard label="Tokens In"   value={result.input_tokens.toString()} />
            <KpiCard label="Tokens Out"  value={result.output_tokens.toString()} />
            <KpiCard label="Rule Score"  value={result.weighted_score.toFixed(4)} />
            <KpiCard label="Confidence"  value={result.llm_scores.router_confidence.toFixed(2)} color="#7c6fff" />
          </div>

          {/* Main two-col layout */}
          <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1rem' }}>

            {/* Left panel */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>

              <Card>
                <Label>Complexity Signals</Label>
                <Bar label="Ambiguity"          value={result.llm_scores.ambiguity} />
                <Bar label="Domain Specificity" value={result.llm_scores.domain_specificity} color="#7c6fff" />
                <Bar label="Multi-Step"         value={result.llm_scores.multi_step} color="#f5a623" />
                <Bar label="Router Confidence"  value={result.llm_scores.router_confidence} color="#00c9a0" />
                {result.llm_scores.rationale && (
                  <div style={{ marginTop: 10, fontSize: '0.72rem', color: '#6b6b8a', lineHeight: 1.5, borderTop: '1px solid #1a1a28', paddingTop: 10 }}>
                    {result.llm_scores.rationale}
                  </div>
                )}
              </Card>

              <Card>
                <Label>Quality Scores</Label>
                <Bar label="Relevance"    value={result.quality_relevance}    color="#00c9a0" />
                <Bar label="Completeness" value={result.quality_completeness} color="#00c9a0" />
                <Bar label="Accuracy"     value={result.quality_accuracy}     color="#00c9a0" />
                {result.quality_rationale && (
                  <div style={{ marginTop: 10, fontSize: '0.72rem', color: '#6b6b8a', lineHeight: 1.5, borderTop: '1px solid #1a1a28', paddingTop: 10 }}>
                    {result.quality_rationale}
                  </div>
                )}
              </Card>

              <Card>
                <Label>Rule Features</Label>
                <Flag label="code_block"      value={result.rule_features.has_code_block} />
                <Flag label="high_precision"  value={result.rule_features.asks_high_precision} />
                <Flag label="comparison"      value={result.rule_features.asks_compare} />
                <Flag label="reasoning"       value={result.rule_features.asks_reasoning} />
                <Flag label="json_content"    value={result.rule_features.has_json_like_text} />
                <Flag label="token_count"     value={result.rule_features.input_token_count} />
                <Flag label="distinct_reqs"   value={result.rule_features.num_distinct_requests} />
              </Card>
            </div>

            {/* Answer */}
            <Card style={{ padding: '1.25rem 1.5rem', maxHeight: 720, overflowY: 'auto' }}>
              <Label>Answer</Label>
              <div className="answer-content" style={{ marginTop: 8 }}>
                <ReactMarkdown>{result.content}</ReactMarkdown>
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}