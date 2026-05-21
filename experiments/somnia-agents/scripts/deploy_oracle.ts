import hre from "hardhat";

async function main() {
  console.log("Deploying PriceOracle to Somnia Testnet...\n");

  const oracle = await hre.viem.deployContract("PriceOracle");

  console.log(`✅ PriceOracle deployed at: ${oracle.address}`);
  console.log(`\nNext: npm run invoke:oracle`);
  console.log(`  (edit CONTRACT_ADDRESS in scripts/invoke_oracle.ts first)`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
