import NextAuth from "next-auth";
import { authConfig } from "@/src/lib/auth/auth-config";

export const { auth: middleware } = NextAuth(authConfig);

export const config = {
  matcher: ["/dashboard/:path*", "/expert/:path*", "/worker/:path*", "/login"],
};
