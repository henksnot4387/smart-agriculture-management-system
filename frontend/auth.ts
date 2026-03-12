import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { PrismaAdapter } from "@auth/prisma-adapter";
import bcrypt from "bcryptjs";
import { authConfig } from "@/src/lib/auth/auth-config";
import { prisma } from "@/src/lib/prisma";
import type { UserRole } from "@/src/types/user-role";

function getCanonicalAppUrl(baseUrl?: string) {
  const explicitUrl = process.env.NEXTAUTH_URL || process.env.AUTH_URL;
  if (explicitUrl) {
    return explicitUrl.replace(/\/$/, "");
  }
  if (process.env.NODE_ENV !== "production") {
    return "http://127.0.0.1:3000";
  }
  return (baseUrl || "http://127.0.0.1:3000").replace(/\/$/, "");
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  adapter: PrismaAdapter(prisma),
  session: {
    strategy: "jwt",
  },
  providers: [
    Credentials({
      name: "Email / Password",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const email = String(credentials?.email ?? "").trim().toLowerCase();
        const password = String(credentials?.password ?? "");

        if (!email || !password) {
          return null;
        }

        const user = await prisma.user.findUnique({
          where: { email },
        });

        if (!user || !user.isActive || !user.passwordHash) {
          return null;
        }

        const isValidPassword = await bcrypt.compare(password, user.passwordHash);
        if (!isValidPassword) {
          return null;
        }

        return {
          id: user.id,
          email: user.email,
          name: user.name,
          role: user.role,
        };
      },
    }),
  ],
  callbacks: {
    ...authConfig.callbacks,
    jwt({ token, user }) {
      if (user) {
        token.role = (user as { role?: UserRole }).role;
      }
      return token;
    },
    redirect({ url, baseUrl }) {
      const canonicalBaseUrl = getCanonicalAppUrl(baseUrl);

      if (url.startsWith("/")) {
        return `${canonicalBaseUrl}${url}`;
      }

      try {
        const targetUrl = new URL(url);
        const canonicalUrl = new URL(canonicalBaseUrl);

        if (
          ["localhost", "127.0.0.1"].includes(targetUrl.hostname) &&
          ["localhost", "127.0.0.1"].includes(canonicalUrl.hostname)
        ) {
          return `${canonicalBaseUrl}${targetUrl.pathname}${targetUrl.search}${targetUrl.hash}`;
        }

        if (targetUrl.origin === canonicalUrl.origin) {
          return url;
        }
      } catch {
        return canonicalBaseUrl;
      }

      return canonicalBaseUrl;
    },
    session({ session, token }) {
      if (session.user) {
        session.user.id = token.sub ?? "";
        session.user.role = (token.role as UserRole | undefined) ?? "WORKER";
      }
      return session;
    },
  },
});
