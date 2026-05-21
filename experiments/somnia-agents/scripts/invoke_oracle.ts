import hre from "hardhat";
import { formatUnits } from "viem";

const CONTRACT_ADDRESS = "0x94aa29bc174fd819004abdf41972b74531665aed" as `0x${string}`;

const POLL_INTERVAL = 2000;
const TIMEOUT = 120_000;

async function main() {
  console.log("=== Price Oracle — Invoking JSON API Request Agent ===\n");

  const oracle = await hre.viem.getContractAt("PriceOracle", CONTRACT_ADDRESS);
  const publicClient = await hre.viem.getPublicClient();

  const deposit = await oracle.read.getRequiredDeposit();
  // Total needed: deposit (0.03) + agent price (0.03) * 3 validators = 0.12 STT
  const totalNeeded = deposit + deposit * BigInt(3); // 0.03 + 0.03*3 = 0.12 STT
  console.log(`Required deposit: ${formatUnits(deposit, 18)} STT`);
  console.log(`Total needed:     ${formatUnits(totalNeeded, 18)} STT (deposit + 3 validators)`);

  console.log("\n📡 Requesting BTC price from CoinGecko via agent...");

  const hash = await oracle.write.requestBtcPrice({ value: totalNeeded });
  console.log(`Transaction: ${hash}`);

  const receipt = await publicClient.waitForTransactionReceipt({ hash });
  console.log(`Confirmed in block ${receipt.blockNumber}`);
  const fromBlock = receipt.blockNumber;

  console.log("\n⏳ Waiting for agent response (10-60 seconds)...\n");

  const startTime = Date.now();
  let pollBlock = fromBlock;

  while (Date.now() - startTime < TIMEOUT) {
    const blockNow = await publicClient.getBlockNumber();
    const toBlock = blockNow;

    const successEvents = await oracle.getEvents.PriceReceived(
      {},
      { fromBlock: pollBlock, toBlock }
    );
    if (successEvents.length > 0) {
      for (const event of successEvents) {
        const price = event.args.price!;
        const wholePart = price / BigInt(1e8);
        const decimalPart = price % BigInt(1e8);
        console.log(`✅ BTC/USD: $${wholePart}.${decimalPart.toString().padStart(8, "0")}`);
      }
      process.exit(0);
    }

    const failEvents = await oracle.getEvents.RequestFailed(
      {},
      { fromBlock: pollBlock, toBlock }
    );
    if (failEvents.length > 0) {
      for (const event of failEvents) {
        console.log(`❌ Request failed: ${event.args.status}`);
      }
      process.exit(1);
    }

    pollBlock = toBlock + 1n;
    await new Promise((r) => setTimeout(r, POLL_INTERVAL));
  }

  console.log("⏰ Timeout — no response after 2 minutes.");
  process.exit(1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
