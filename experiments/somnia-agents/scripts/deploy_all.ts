import hre from "hardhat";
import fs from "fs";
import path from "path";

const OUTPUT = path.join(__dirname, "..", "deployed.json");

async function main() {
  console.log("=== Deploying all contracts to Somnia Testnet ===\n");

  const priceOracle = await hre.viem.deployContract("PriceOracle");
  console.log(`✅ PriceOracle:     ${priceOracle.address}`);

  const sentiment = await hre.viem.deployContract("SentimentAnalyzer");
  console.log(`✅ SentimentAnalyzer: ${sentiment.address}`);

  const health = await hre.viem.deployContract("HealthTips");
  console.log(`✅ HealthTips:      ${health.address}`);

  const deployed = {
    network: "somnia-testnet",
    chainId: 50312,
    deployedAt: new Date().toISOString(),
    platform: "0x037Bb9C718F3f7fe5eCBDB0b600D607b52706776",
    contracts: {
      PriceOracle: priceOracle.address,
      SentimentAnalyzer: sentiment.address,
      HealthTips: health.address,
    },
  };

  fs.writeFileSync(OUTPUT, JSON.stringify(deployed, null, 2));
  console.log(`\n📝 Addresses saved to ${OUTPUT}`);
  console.log(`\nTo invoke:`);
  Object.entries(deployed.contracts).forEach(([name, addr]) => {
    console.log(`  npm run invoke:${name.replace(/([A-Z])/g, (_, c) => c.toLowerCase())}`);
  });
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
