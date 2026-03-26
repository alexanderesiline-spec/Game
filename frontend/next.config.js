/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ["replicate.delivery", "pbxt.replicate.delivery", "localhost"],
    remotePatterns: [
      {protocol: "https", hostname: "**.replicate.delivery"},
    ],
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};

module.exports = nextConfig;
