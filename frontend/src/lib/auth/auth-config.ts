import type { NextAuthConfig } from "next-auth";

const protectedPrefixes = [
  "/dashboard",
  "/monitor",
  "/sensor",
  "/vision",
  "/ai-insights",
  "/copilot",
  "/tasks",
  "/expert",
  "/worker",
  "/users",
  "/settings",
  "/scheduler",
  "/observability",
];

export const authConfig: NextAuthConfig = {
  providers: [],
  trustHost: true,
  pages: {
    signIn: "/login",
  },
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = Boolean(auth?.user);
      const isLoginRoute = nextUrl.pathname.startsWith("/login");
      const isProtectedRoute = protectedPrefixes.some((prefix) =>
        nextUrl.pathname.startsWith(prefix),
      );

      if (isLoginRoute && isLoggedIn) {
        return Response.redirect(new URL("/dashboard", nextUrl));
      }

      if (isProtectedRoute) {
        return isLoggedIn;
      }

      return true;
    },
  },
};
