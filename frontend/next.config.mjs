/** @type {import('next').NextConfig} */
const isVercel = Boolean(process.env.VERCEL);

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // On Vercel, /api/* is served by the Python serverless function directly —
    // no rewrite needed (Vercel's own routing handles it via vercel.json).
    // Locally, proxy to the uvicorn dev server running on port 8000.
    if (isVercel) {
      return [];
    }
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
      {
        source: '/health',
        destination: 'http://127.0.0.1:8000/health',
      },
    ];
  },
};

export default nextConfig;

