/**
 * fresh-entity.ts: Create a fresh entity secret for hackathon bypass
 * 
 * Usage:
 *   node --env-file=.env --import=tsx fresh-entity.ts
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { registerEntitySecretCiphertext } from "@circle-fin/developer-controlled-wallets";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = path.join(__dirname, "output");

const apiKey = process.env.CIRCLE_API_KEY;
if (!apiKey) {
  console.error("ERROR: CIRCLE_API_KEY not set in .env");
  process.exit(1);
}

try {
  console.log("Creating fresh entity secret...");
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  
  const freshSecret = crypto.randomBytes(32).toString("hex");
  console.log("Generated new 32-byte secret");
  
  await registerEntitySecretCiphertext({
    apiKey,
    entitySecret: freshSecret,
    recoveryFileDownloadPath: OUTPUT_DIR,
  });
  
  console.log("\n✓ New entity secret registered successfully!");
  console.log("Secret:", freshSecret);
  
  // Update .env
  const envPath = path.join(__dirname, ".env");
  let envContent = fs.readFileSync(envPath, "utf-8");
  
  // Replace or add CIRCLE_ENTITY_SECRET
  if (envContent.includes("CIRCLE_ENTITY_SECRET=")) {
    envContent = envContent.replace(
      /CIRCLE_ENTITY_SECRET=.*/,
      `CIRCLE_ENTITY_SECRET=${freshSecret}`
    );
  } else {
    envContent += `\nCIRCLE_ENTITY_SECRET=${freshSecret}\n`;
  }
  
  fs.writeFileSync(envPath, envContent, "utf-8");
  console.log("✓ Updated .env with new secret");
  console.log("\nRecovery file saved to: output/");
  
} catch (err) {
  console.error("ERROR:", err instanceof Error ? err.message : String(err));
  process.exit(1);
}
