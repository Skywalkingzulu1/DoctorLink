import hre from "hardhat";

async function main() {
  console.log("Deploying SentimentAnalyzer to Somnia Testnet...\n");

  const analyzer = await hre.viem.deployContract("SentimentAnalyzer");

  console.log(`✅ SentimentAnalyzer deployed at: ${analyzer.address}`);
  console.log(`\nNext: npm run invoke:sentiment`);
  console.log(`  (edit CONTRACT_ADDRESS in scripts/invoke_sentiment.ts first)`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
