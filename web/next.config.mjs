/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Preview pages are personalized per lead — never index them.
  async headers() {
    return [
      {
        source: "/preview/:slug*",
        headers: [
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
        ],
      },
    ];
  },
};

export default nextConfig;
