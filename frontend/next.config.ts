import type { NextConfig } from "next";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // The turn endpoint streams graph progress as SSE. Gzip buffers its input
  // until it has a block worth emitting, which holds every node event back
  // until the response closes and kills the live pipeline animation. This is
  // a localhost prototype, so trading compression for streaming is free.
  compress: false,
  // Hide the "N" dev-tools badge in the corner - it sits on top of the
  // student UI during user testing. Compile/runtime errors still surface.
  devIndicators: false,
  // Pin the workspace root so the lockfile above this directory is ignored.
  turbopack: { root: __dirname },
  // Proxy the API so the browser only ever talks to one origin.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
};

export default nextConfig;
