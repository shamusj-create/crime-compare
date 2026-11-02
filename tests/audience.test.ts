import { fileURLToPath } from "node:url";
process.env.CWA_CLIENT_PATH = fileURLToPath(new URL("../public/audience.js", import.meta.url));
await import("./cwa-client-checks.cjs");
