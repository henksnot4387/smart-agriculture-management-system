import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: [
    "antd",
    "@ant-design/icons",
    "@ant-design/pro-components",
    "@ant-design/pro-layout",
    "@ant-design/pro-provider",
    "@ant-design/pro-utils",
  ],
};

export default nextConfig;
