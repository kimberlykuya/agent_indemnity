/**
 * encrypt-secret.ts: Encrypt an existing entity secret to ciphertext
 * 
 * Usage:
 *   node --env-file=.env --import=tsx encrypt-secret.ts
 */

import { registerEntitySecretCiphertext } from "@circle-fin/developer-controlled-wallets";

const apiKey = process.env.CIRCLE_API_KEY;
const rawSecret = "ab613ebfc2c297d9fd263d7d69011508be398af133994a2e1eb821675fbfcae7";

if (!apiKey) {
  console.error("ERROR: CIRCLE_API_KEY not set in .env");
  process.exit(1);
}

try {
  console.log("Encrypting entity secret...");
  const result = await registerEntitySecretCiphertext({
    apiKey,
    entitySecret: rawSecret,
    recoveryFileDownloadPath: "./output"
  });
  console.log("\n✓ Entity Secret Ciphertext:");
  console.log(result.ciphertext);
  console.log("\n✓ Recovery file saved to: ./output/recovery.json");
} catch (err) {
  console.error("ERROR:", err instanceof Error ? err.message : String(err));
  process.exit(1);
}
