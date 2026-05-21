import hre from "hardhat";
import { formatUnits } from "viem";

const CONTRACT_ADDRESS = "0x98f7e3d6576289a1b9e2f159ecca55f863e8ef23" as `0x${string}`;

const POLL_INTERVAL = 2000;
const TIMEOUT = 150_000;

async function main() {
  console.log("=== DrugInfo — Invoking Web Data Extraction Agent ===\n");

  const contract = await hre.viem.getContractAt("DrugInfo", CONTRACT_ADDRESS);
  const publicClient = await hre.viem.getPublicClient();

  const deposit = await contract.read.getRequiredDeposit();
  const totalNeeded = deposit + deposit * BigInt(10); // 0.03 + 0.10*3 = 0.33 STT
  console.log(`Required deposit: ${formatUnits(deposit, 18)} STT`);
  console.log(`Total needed:     ${formatUnits(totalNeeded, 18)} STT (deposit + 3 validators x 0.10)\n`);

  const drugs = ["aspirin", "ibuprofen", "metformin"];

  let fromBlock: bigint | undefined;

  for (const drug of drugs) {
    console.log(`📡 Requesting: "${drug}"`);
    const hash = await contract.write.getDrugInfo([drug], { value: totalNeeded });
    const receipt = await publicClient.waitForTransactionReceipt({ hash });
    if (!fromBlock) fromBlock = receipt.blockNumber;
    console.log(`   Tx: ${hash}\n`);
  }

  console.log("⏳ Waiting for web extraction responses...\n");

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
      const result = event.args.result!;
      console.log(`✅ "${event.args.drugName}": ${result.substring(0, 250)}...`);
    }

    if (events.length >= drugs.length) {
      console.log("\nAll drug info retrieved!");
      process.exit(0);
    }

    await new Promise((r) => setTimeout(r, POLL_INTERVAL));
  }

  console.log("⏰ Timeout");
  process.exit(1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
