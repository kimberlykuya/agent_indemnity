/**
 * test-transaction.ts: Test sending a transaction with an existing wallet
 *
 * Required in .env:
 *   CIRCLE_API_KEY
 *   CIRCLE_ENTITY_SECRET
 *   CIRCLE_WALLET_ADDRESS
 */

import {
  initiateDeveloperControlledWalletsClient,
  type TokenBlockchain,
} from "@circle-fin/developer-controlled-wallets";

async function main() {
  const apiKey = process.env.CIRCLE_API_KEY;
  const entitySecret = process.env.CIRCLE_ENTITY_SECRET;
  const walletAddress = process.env.CIRCLE_WALLET_ADDRESS;

  if (!apiKey) throw new Error("Missing CIRCLE_API_KEY in .env");
  if (!entitySecret) throw new Error("Missing CIRCLE_ENTITY_SECRET in .env");
  if (!walletAddress) throw new Error("Missing CIRCLE_WALLET_ADDRESS in .env");

  console.log("Initializing Circle Client...");
  
  // NOTE: Ensure your entitySecret is a 32-byte hex string (64 characters).
  const client = initiateDeveloperControlledWalletsClient({
    apiKey,
    entitySecret,
  });

  const ARC_TESTNET_USDC = "0x3600000000000000000000000000000000000000";
  // We'll send 0.01 USDC to a dummy address just to test the transaction flow.
  const destinationAddress = process.env.DESTINATION_ADDRESS || "0x000000000000000000000000000000000000dEaD"; 

  console.log(`\nCreating transaction:`);
  console.log(`From: ${walletAddress}`);
  console.log(`To: ${destinationAddress}`);
  console.log(`Amount: 0.01 USDC`);
  
  const txResponse = await client.createTransaction({
    blockchain: "ARC-TESTNET" as TokenBlockchain,
    walletAddress: walletAddress,
    destinationAddress: destinationAddress,
    amount: ["0.01"],
    tokenAddress: ARC_TESTNET_USDC,
    fee: { type: "level", config: { feeLevel: "MEDIUM" } },
  });

  const txId = txResponse.data?.id;
  if (!txId) {
    console.error(txResponse);
    throw new Error("Transaction creation failed: no ID returned");
  }
  
  console.log("\nTransaction created! ID:", txId);
  console.log("Polling for completion...");

  const terminalStates = new Set(["COMPLETE", "FAILED", "CANCELLED", "DENIED"]);
  let currentState: string | undefined = txResponse.data?.state;
  
  while (!currentState || !terminalStates.has(currentState)) {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    const poll = await client.getTransaction({ id: txId });
    const tx = poll.data?.transaction;
    currentState = tx?.state;
    console.log(`Current state: ${currentState}`);
    
    if (currentState === "COMPLETE" && tx?.txHash) {
      console.log(`\n✅ Transaction Successful!`);
      console.log(`Explorer Link: https://testnet.arcscan.app/tx/${tx.txHash}`);
    } else if (terminalStates.has(currentState) && currentState !== "COMPLETE") {
      console.log(`\n❌ Transaction failed with state: ${currentState}`);
    }
  }
}

main().catch((err) => {
  console.error("Error:", err.message || err);
  process.exit(1);
});
