/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // In local development or when BACKEND_URL is explicitly set, rewrite /api to the FastAPI server
    const backendUrl = process.env.BACKEND_URL || (process.env.NODE_ENV === 'development' ? 'http://127.0.0.1:8000' : '');
    if (!backendUrl) {
      return [];
    }
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/health',
        destination: `${backendUrl}/health`,
      },
    ];
  },
};

export default nextConfig;
