import { createPublicClient, http } from "viem";
import deployed from "./deployed.json";

const RPC = "https://api.infra.testnet.somnia.network";
const EXPLORER = "https://shannon-explorer.somnia.network";

const client = createPublicClient({ transport: http(RPC) });

const priceOracleAbi = [
  { type: "function", name: "latestPrice", inputs: [], outputs: [{ type: "uint256" }], stateMutability: "view" },
  { type: "function", name: "lastUpdatedAt", inputs: [], outputs: [{ type: "uint256" }], stateMutability: "view" },
  { type: "function", name: "getFormattedPrice", inputs: [], outputs: [{ type: "uint256" }, { type: "uint256" }], stateMutability: "view" },
  { type: "function", name: "getRequiredDeposit", inputs: [], outputs: [{ type: "uint256" }], stateMutability: "view" },
] as const;

const healthTipsAbi = [
  { type: "function", name: "getTipCount", inputs: [], outputs: [{ type: "uint256" }], stateMutability: "view" },
  { type: "function", name: "getTip", inputs: [{ type: "uint256" }], outputs: [{ type: "string" }, { type: "string" }], stateMutability: "view" },
  { type: "function", name: "getRequiredDeposit", inputs: [], outputs: [{ type: "uint256" }], stateMutability: "view" },
] as const;

export async function getBtcPrice() {
  const c = deployed.contracts.PriceOracle as `0x${string}`;
  const [whole, decimal] = await client.readContract({
    address: c,
    abi: priceOracleAbi,
    functionName: "getFormattedPrice",
  });
  const updated = await client.readContract({
    address: c,
    abi: priceOracleAbi,
    functionName: "lastUpdatedAt",
  });
  return {
    price: `${whole}.${decimal.toString().padStart(8, "0")}`,
    updatedAt: Number(updated),
  };
}

export async function getHealthTips() {
  const c = deployed.contracts.HealthTips as `0x${string}`;
  const count = await client.readContract({
    address: c,
    abi: healthTipsAbi,
    functionName: "getTipCount",
  });
  const tips: { topic: string; tip: string }[] = [];
  for (let i = 0n; i < count; i++) {
    const [topic, tip] = await client.readContract({
      address: c,
      abi: healthTipsAbi,
      functionName: "getTip",
      args: [i],
    });
    tips.push({ topic, tip });
  }
  return tips;
}

export const explorerUrl = (address: string) => `${EXPLORER}/address/${address}`;

export { deployed };
