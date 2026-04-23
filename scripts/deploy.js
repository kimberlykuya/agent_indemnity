const hre = require("hardhat");

async function main() {
  const usdc = process.env.USDC_CONTRACT_ADDRESS;
  const agent = process.env.AGENT_WALLET_ADDRESS;

  const Bond = await hre.ethers.getContractFactory("PerformanceBond");
  const bond = await Bond.deploy(usdc, agent);
  await bond.waitForDeployment();

  console.log("PERFORMANCE_BOND_ADDRESS=", await bond.getAddress());
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});