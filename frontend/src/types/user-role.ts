export const USER_ROLES = ["SUPER_ADMIN", "ADMIN", "EXPERT", "WORKER"] as const;

export type UserRole = (typeof USER_ROLES)[number];
