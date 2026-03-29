'use client'

import { useState } from 'react'
import QueryPanel from '@/components/QueryPanel'
import AnalyticsPanel from '@/components/AnalyticsPanel'

type Tab = 'analytics' | 'query'

export default function Home() {
  const [tab, setTab] = useState<Tab>('analytics')

  return (
    <div style={{ maxWidth: 1360, margin: '0 auto', padding: '0 2rem 4rem' }}>

      {/* Top nav */}
      <nav style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '1.5rem 0', borderBottom: '1px solid #1f1f30', marginBottom: '2.5rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div style={{
            width: 28, height: 28, background: '#7c6fff',
            borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14,
          }}>⚡</div>
          <span style={{ fontWeight: 600, fontSize: '1rem', letterSpacing: '-0.01em', color: '#eeeef5' }}>
            LLM Router
          </span>
          <span style={{
            fontSize: '0.7rem', color: '#6b6b8a', background: '#13131f',
            border: '1px solid #1f1f30', borderRadius: 99, padding: '0.15rem 0.6rem',
            marginLeft: 4, letterSpacing: '0.03em',
          }}>
            Azure AI Foundry
          </span>
        </div>

        <div style={{
          display: 'flex', gap: 2, background: '#0f0f18',
          border: '1px solid #1f1f30', borderRadius: 10, padding: 3,
        }}>
          {([['analytics', 'Dashboard'], ['query', 'Live Query']] as [Tab, string][]).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              style={{
                padding: '0.4rem 1.1rem', borderRadius: 8, border: 'none',
                fontSize: '0.78rem', fontWeight: 500, letterSpacing: '0.01em',
                transition: 'all 0.15s',
                background: tab === id ? '#7c6fff' : 'transparent',
                color: tab === id ? '#fff' : '#6b6b8a',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </nav>

      {tab === 'analytics' && <AnalyticsPanel />}
      {tab === 'query'     && <QueryPanel />}
    </div>
  )
}