const { ethers } = require("ethers");
require("dotenv").config();

async function main() {
  const provider = new ethers.JsonRpcProvider(process.env.ARC_RPC_URL);
  const wallet = new ethers.Wallet(process.env.DEPLOYER_PRIVATE_KEY, provider);

  const usdcAbi = [
    "function approve(address spender, uint256 amount) public returns (bool)"
  ];

  const usdc = new ethers.Contract(
    process.env.USDC_CONTRACT_ADDRESS,
    usdcAbi,
    wallet
  );

  const amount = ethers.parseUnits("10", 6); // 10 USDC

  const tx = await usdc.approve(process.env.PERFORMANCE_BOND_ADDRESS, amount);
  await tx.wait();

  console.log("Approved:", tx.hash);
}

main();