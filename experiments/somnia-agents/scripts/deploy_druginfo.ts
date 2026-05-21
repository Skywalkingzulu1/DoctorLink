import hre from "hardhat";

async function main() {
  console.log("Deploying DrugInfo to Somnia Testnet...\n");

  const drug = await hre.viem.deployContract("DrugInfo");

  console.log(`✅ DrugInfo deployed at: ${drug.address}`);
  console.log(`\nNext: deploy scripts/invoke_druginfo.ts`);
  console.log(`  (edit CONTRACT_ADDRESS first)`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
