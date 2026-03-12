import { PrismaClient } from "@prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";
import { Pool } from "pg";

function getDatabaseUrl() {
  const directUrl = process.env.DATABASE_URL;
  if (directUrl) {
    return directUrl;
  }

  const user = process.env.POSTGRES_USER;
  const password = process.env.POSTGRES_PASSWORD;
  const database = process.env.POSTGRES_DB;

  if (!user || !password || !database) {
    throw new Error(
      "Missing database configuration. Set DATABASE_URL or POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB.",
    );
  }

  const host = process.env.POSTGRES_HOST || "localhost";
  const port = process.env.POSTGRES_PORT || "5432";
  return `postgresql://${encodeURIComponent(user)}:${encodeURIComponent(password)}@${host}:${port}/${database}?schema=public`;
}

const databaseUrl = getDatabaseUrl();

type PrismaGlobals = {
  pgPool?: Pool;
  prisma?: PrismaClient;
};

const prismaGlobal = globalThis as unknown as PrismaGlobals;

const pgPool =
  prismaGlobal.pgPool ??
  new Pool({
    connectionString: databaseUrl,
  });

if (process.env.NODE_ENV !== "production") {
  prismaGlobal.pgPool = pgPool;
}

const adapter = new PrismaPg(pgPool);

export const prisma =
  prismaGlobal.prisma ??
  new PrismaClient({
    adapter,
  });

if (process.env.NODE_ENV !== "production") {
  prismaGlobal.prisma = prisma;
}
