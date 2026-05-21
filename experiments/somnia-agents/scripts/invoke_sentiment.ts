import hre from "hardhat";
import { formatUnits } from "viem";

const CONTRACT_ADDRESS = "0xda9dda954d44b41417358b66c2760668e129e11d" as `0x${string}`;

const POLL_INTERVAL = 2000;
const TIMEOUT = 120_000;

async function main() {
  console.log("=== Sentiment Analyzer — Invoking LLM Inference Agent ===\n");

  const contract = await hre.viem.getContractAt("SentimentAnalyzer", CONTRACT_ADDRESS);
  const publicClient = await hre.viem.getPublicClient();

  const deposit = await contract.read.getRequiredDeposit();
  const totalNeeded = deposit + deposit * BigInt(7);
  console.log(`Required deposit: ${formatUnits(deposit, 18)} STT`);
  console.log(`Total needed:     ${formatUnits(totalNeeded, 18)} STT (deposit + 3 validators x 0.07)\n`);

  const texts = [
    { text: "Bitcoin just hit a new all-time high!", expected: "bullish" },
    { text: "The market is crashing, I'm panicking.", expected: "bearish" },
    { text: "Markets are trading sideways today.", expected: "neutral" },
  ];

  let fromBlock: bigint | undefined;

  for (const t of texts) {
    console.log(`📡 Classifying: "${t.text}"`);
    const hash = await contract.write.classifySentiment([t.text], { value: totalNeeded });
    const receipt = await publicClient.waitForTransactionReceipt({ hash });
    if (!fromBlock) fromBlock = receipt.blockNumber;
    console.log(`   Tx: ${hash}`);
  }

  console.log("\n⏳ Waiting for LLM responses...\n");

  const startTime = Date.now();
  let pollBlock = fromBlock!;
  const received = new Set<string>();

  while (Date.now() - startTime < TIMEOUT) {
    const blockNow = await publicClient.getBlockNumber();
    const toBlock = blockNow;

    const events = await contract.getEvents.ClassificationReceived(
      {}, { fromBlock: pollBlock, toBlock }
    );
    pollBlock = toBlock + 1n;

    for (const e of events) {
      if (e.args.classification && !received.has(e.args.classification)) {
        received.add(e.args.classification);
        console.log(`✅ "${e.args.classification}"`);
      }
    }

    if (received.size >= texts.length) {
      console.log("\nAll classifications received!");
      process.exit(0);
    }

    await new Promise((r) => setTimeout(r, POLL_INTERVAL));
  }

  console.log("⏰ Timeout — got", received.size, "of", texts.length);
  process.exit(1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
