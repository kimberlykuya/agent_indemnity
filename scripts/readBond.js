const { ethers } = require("ethers");
require("dotenv").config();

async function main() {
  const provider = new ethers.JsonRpcProvider(process.env.ARC_RPC_URL);

  const abi = [
    "function getBondBalance() view returns (uint256)"
  ];

  const contract = new ethers.Contract(
    process.env.PERFORMANCE_BOND_ADDRESS,
    abi,
    provider
  );

  const balance = await contract.getBondBalance();

  console.log("Bond balance:", ethers.formatUnits(balance, 6), "USDC");
}

main();
