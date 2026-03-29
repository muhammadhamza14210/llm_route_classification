import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: '/query',              destination: 'http://localhost:8000/query' },
      { source: '/analytics/overview', destination: 'http://localhost:8000/analytics/overview' },
      { source: '/analytics/routing',  destination: 'http://localhost:8000/analytics/routing' },
      { source: '/analytics/cost',     destination: 'http://localhost:8000/analytics/cost' },
      { source: '/analytics/quality',  destination: 'http://localhost:8000/analytics/quality' },
      { source: '/health',             destination: 'http://localhost:8000/health' },
    ]
  },
}

export default nextConfig