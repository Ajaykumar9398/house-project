/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  output: 'standalone',  // This is CRITICAL for Docker
  images: {
    unoptimized: true,  // Optional: helps with static images
  },
}

module.exports = nextConfig