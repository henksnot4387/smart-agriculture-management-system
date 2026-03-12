#!/usr/bin/env node
const path = require("path");
const bcrypt = require("bcryptjs");
const { Pool } = require("pg");
const { PrismaPg } = require("@prisma/adapter-pg");
const { PrismaClient, UserRole } = require("@prisma/client");

require("dotenv").config({ path: path.resolve(__dirname, "../.env.local") });
require("dotenv").config({ path: path.resolve(__dirname, "../../.env") });

function resolveDatabaseUrl() {
  const directUrl = process.env.DATABASE_URL;
  if (directUrl && !directUrl.includes("${")) {
    return directUrl;
  }

  const user = process.env.POSTGRES_USER;
  const password = process.env.POSTGRES_PASSWORD;
  const database = process.env.POSTGRES_DB;

  if (!user || !password || !database) {
    throw new Error(
      "Missing DATABASE_URL and POSTGRES_* variables. Update frontend/.env.local or root .env.",
    );
  }

  const host = process.env.POSTGRES_HOST || "localhost";
  const port = process.env.POSTGRES_PORT || "5432";
  return `postgresql://${encodeURIComponent(user)}:${encodeURIComponent(password)}@${host}:${port}/${database}?schema=public`;
}

const databaseUrl = resolveDatabaseUrl();
if (!databaseUrl) {
  throw new Error("Missing DATABASE_URL. Set it in the root .env file.");
}

const expertPassword = process.env.SEED_EXPERT_PASSWORD || "change-me-expert-password";
const workerPassword = process.env.SEED_WORKER_PASSWORD || "change-me-worker-password";
const superAdminPassword = process.env.SEED_SUPER_ADMIN_PASSWORD || "change-me-superadmin-password";

const pool = new Pool({ connectionString: databaseUrl });
const prisma = new PrismaClient({ adapter: new PrismaPg(pool) });

async function upsertUser({ email, role, password }) {
  const passwordHash = await bcrypt.hash(password, 12);

  return prisma.user.upsert({
    where: { email },
    update: {
      role,
      isActive: true,
      passwordHash,
    },
    create: {
      email,
      role,
      isActive: true,
      passwordHash,
    },
  });
}

async function main() {
  const superAdmin = await upsertUser({
    email: "superadmin@example.local",
    role: UserRole.SUPER_ADMIN,
    password: superAdminPassword,
  });

  const expert = await upsertUser({
    email: "expert@example.local",
    role: UserRole.EXPERT,
    password: expertPassword,
  });

  const worker = await upsertUser({
    email: "worker@example.local",
    role: UserRole.WORKER,
    password: workerPassword,
  });

  console.log("[seed:auth] users ready");
  console.log(`superadmin: ${superAdmin.email} / ${superAdminPassword}`);
  console.log(`expert: ${expert.email} / ${expertPassword}`);
  console.log(`worker: ${worker.email} / ${workerPassword}`);
}

main()
  .catch((error) => {
    console.error("[seed:auth] failed:", error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
    await pool.end();
  });
