/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Required for Mapbox GL JS + webpack — without this the bundle often fails silently and the map stays blank.
  transpilePackages: ["mapbox-gl"],

  // Keep default webpack filesystem cache. Turning it off can leave the browser requesting stale
  // `/_next/static/...` chunk URLs after HMR (404/500 for layout.css, main-app.js, etc.).
};

module.exports = nextConfig;
