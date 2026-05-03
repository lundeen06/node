/** @type {import('next').NextConfig} */

/** Browser uses same-origin `/node-api/*`; dev server rewrites to FastAPI (avoids CORS + port drift). */
const apiUpstream =
  (process.env.NODE_API_UPSTREAM && process.env.NODE_API_UPSTREAM.replace(/\/$/, "")) ||
  "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,

  transpilePackages: ["three", "satellite.js"],

  async rewrites() {
    const direct = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
    if (direct) return [];
    return [{ source: "/node-api/:path*", destination: `${apiUpstream}/:path*` }];
  },

  // Keep default webpack filesystem cache. Turning it off can leave the browser requesting stale
  // `/_next/static/...` chunk URLs after HMR (404/500 for layout.css, main-app.js, etc.).
};

module.exports = nextConfig;
