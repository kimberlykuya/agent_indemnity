const { ethers } = require("ethers");
require("dotenv").config();

async function main() {
  const provider = new ethers.JsonRpcProvider(process.env.ARC_RPC_URL);
  const wallet = new ethers.Wallet(process.env.DEPLOYER_PRIVATE_KEY, provider);

  const abi = [
    "function stakeBond(uint256 amount) external",
  ];

  const contract = new ethers.Contract(
    process.env.PERFORMANCE_BOND_ADDRESS,
    abi,
    wallet
  );

  const amount = ethers.parseUnits("5", 6); // 5 USDC

  const tx = await contract.stakeBond(amount);
  await tx.wait();

  console.log("Bond staked:", tx.hash);
}

main();