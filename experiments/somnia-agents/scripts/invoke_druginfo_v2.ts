import hre from "hardhat";
import { formatUnits } from "viem";

const CONTRACT_ADDRESS = "0xe8c4d8ffd5111cb6530a5ef1a1e6e213ab8b48c6" as `0x${string}`;

const POLL_INTERVAL = 2000;
const TIMEOUT = 120_000;

async function main() {
  console.log("=== DrugInfoV2 — Invoking LLM Agent for Drug Info ===\n");

  const contract = await hre.viem.getContractAt("DrugInfoV2", CONTRACT_ADDRESS);
  const publicClient = await hre.viem.getPublicClient();

  const deposit = await contract.read.getRequiredDeposit();
  const totalNeeded = deposit + BigInt(7) * deposit;
  console.log(`Required deposit: ${formatUnits(deposit, 18)} STT`);
  console.log(`Total needed:     ${formatUnits(totalNeeded, 18)} STT (deposit + 3 validators x 0.07)\n`);

  const drugs = ["aspirin", "ibuprofen", "metformin"];

  let fromBlock: bigint | undefined;

  for (const drug of drugs) {
    console.log(`📡 Requesting info about: "${drug}"`);
    const hash = await contract.write.getDrugInfo([drug], { value: totalNeeded });
    const receipt = await publicClient.waitForTransactionReceipt({ hash });
    if (!fromBlock) fromBlock = receipt.blockNumber;
    console.log(`   Tx: ${hash}\n`);
  }

  console.log("⏳ Waiting for LLM responses...\n");

  const startTime = Date.now();
  let pollBlock = fromBlock!;

  while (Date.now() - startTime < TIMEOUT) {
    const blockNow = await publicClient.getBlockNumber();
    const toBlock = blockNow;

    const events = await contract.getEvents.DrugInfoReceived(
      {},
      { fromBlock: pollBlock, toBlock }
    );
    pollBlock = toBlock + 1n;

    for (const event of events) {
      const result = event.args.info!;
      console.log(`✅ "${event.args.drugName}": ${result.substring(0, 200)}...`);
    }

    if (events.length >= drugs.length) {
      console.log("\nAll drug info received!");
      process.exit(0);
    }

    await new Promise((r) => setTimeout(r, POLL_INTERVAL));
  }

  console.log("⏰ Timeout — got partial results");
  process.exit(1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
