import hre from "hardhat";

async function main() {
  console.log("Deploying HealthTips to Somnia Testnet...\n");

  const health = await hre.viem.deployContract("HealthTips");

  console.log(`✅ HealthTips deployed at: ${health.address}`);
  console.log(`\nNext: npm run invoke:healthtips`);
  console.log(`  (edit CONTRACT_ADDRESS in scripts/invoke_healthtips.ts first)`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
