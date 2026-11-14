/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["@enigma-sac/contracts"]
};

export default nextConfig;
