import hre from "hardhat";
import { formatUnits } from "viem";

const CONTRACT_ADDRESS = "0x4de3358682d8652021fa608a74442a109da5cec9" as `0x${string}`;

const POLL_INTERVAL = 2000;
const TIMEOUT = 120_000;

async function main() {
  console.log("=== HealthTips — Invoking LLM Inference Agent ===\n");

  const contract = await hre.viem.getContractAt("HealthTips", CONTRACT_ADDRESS);
  const publicClient = await hre.viem.getPublicClient();

  const deposit = await contract.read.getRequiredDeposit();
  const totalNeeded = deposit + deposit * BigInt(7);
  console.log(`Required deposit: ${formatUnits(deposit, 18)} STT`);
  console.log(`Total needed:     ${formatUnits(totalNeeded, 18)} STT (deposit + 3 validators x 0.07)\n`);

  const topics = [
    "lowering blood pressure naturally",
    "benefits of strength training after 50",
    "improving sleep quality",
  ];

  let fromBlock: bigint | undefined;

  for (const topic of topics) {
    console.log(`📡 Requesting: "${topic}"`);
    const hash = await contract.write.getHealthTip([topic], { value: totalNeeded });
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

    const events = await contract.getEvents.TipReceived(
      {}, { fromBlock: pollBlock, toBlock }
    );
    pollBlock = toBlock + 1n;

    for (const e of events) {
      if (e.args.topic && !received.has(e.args.topic)) {
        received.add(e.args.topic);
        console.log(`✅ "${e.args.topic}": ${e.args.tip}`);
      }
    }

    if (received.size >= topics.length) {
      console.log("\nAll tips received!");
      process.exit(0);
    }

    await new Promise((r) => setTimeout(r, POLL_INTERVAL));
  }

  console.log("⏰ Timeout — got", received.size, "of", topics.length);
  process.exit(1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
