import hre from "hardhat";

async function main() {
  console.log("=== Deploying DrugInfoV2 (LLM-based) ===\n");

  const drugInfo = await hre.viem.deployContract("DrugInfoV2", []);
  console.log(`DrugInfoV2 deployed at: ${drugInfo.address}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
