/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone build → minimal server.js in .next/standalone, smaller Docker image.
  output: 'standalone',
  // Server-side proxy: browser hits Next.js on :5647, Next.js forwards
  // /api/*, /auth/*, /chat/* to FastAPI on :8000 (same container).
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/api/:path*`,
      },
      {
        source: '/auth/:path*',
        destination: `${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/auth/:path*`,
      },
      {
        source: '/chat/:path*',
        destination: `${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/chat/:path*`,
      },
    ]
  },
}

module.exports = nextConfig