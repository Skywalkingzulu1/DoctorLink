"""
Read-only endpoints for Doctors on Wheels's Somnia Agent contracts.
Data from PriceOracle, HealthTips, and SentimentAnalyzer deployed contracts.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException
from web3 import Web3
from somnia.client import somnia

RPC = "https://api.infra.testnet.somnia.network"
EXPLORER = "https://shannon-explorer.somnia.network"

DEPLOYED = {
    "PriceOracle": "0x94aa29bc174fd819004abdf41972b74531665aed",
    "HealthTips": "0x4de3358682d8652021fa608a74442a109da5cec9",
    "SentimentAnalyzer": "0xda9dda954d44b41417358b66c2760668e129e11d",
    "DrugInfoV2": "0xe8c4d8ffd5111cb6530a5ef1a1e6e213ab8b48c6",
}

PRICE_ABI = [
    {"inputs": [], "name": "latestPrice", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "lastUpdatedAt", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "getFormattedPrice", "outputs": [{"type": "uint256"}, {"type": "uint256"}], "stateMutability": "view", "type": "function"},
]

TIPS_ABI = [
    {"inputs": [], "name": "getTipCount", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "uint256"}], "name": "getTip", "outputs": [{"type": "string"}, {"type": "string"}], "stateMutability": "view", "type": "function"},
]

SENTIMENT_ABI = [
    {"inputs": [], "name": "latestClassification", "outputs": [{"type": "string"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "latestScore", "outputs": [{"type": "int256"}], "stateMutability": "view", "type": "function"},
]

DRUG_ABI = [
    {"inputs": [], "name": "getInfoCount", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "uint256"}], "name": "getInfo", "outputs": [{"type": "string"}, {"type": "string"}], "stateMutability": "view", "type": "function"},
]

w3 = Web3(Web3.HTTPProvider(RPC))
if not w3.is_connected():
    print("[WARN] Somnia testnet RPC not reachable for on-chain data endpoints")

price_oracle = w3.eth.contract(address=Web3.to_checksum_address(DEPLOYED["PriceOracle"]), abi=PRICE_ABI)
health_tips = w3.eth.contract(address=Web3.to_checksum_address(DEPLOYED["HealthTips"]), abi=TIPS_ABI)
sentiment = w3.eth.contract(address=Web3.to_checksum_address(DEPLOYED["SentimentAnalyzer"]), abi=SENTIMENT_ABI)
drug_info = w3.eth.contract(address=Web3.to_checksum_address(DEPLOYED["DrugInfoV2"]), abi=DRUG_ABI)

router = APIRouter(prefix="/api/somnia/onchain", tags=["somnia-onchain"])


@router.get("/price")
def get_btc_price():
    try:
        whole, decimal = price_oracle.functions.getFormattedPrice().call()
        updated = price_oracle.functions.lastUpdatedAt().call()
        return {
            "price": f"{whole}.{str(decimal).zfill(8)}",
            "whole": whole,
            "decimal": decimal,
            "updatedAt": updated,
            "source": "CoinGecko via JSON API Request Agent",
            "contract": DEPLOYED["PriceOracle"],
            "explorerUrl": f"{EXPLORER}/address/{DEPLOYED['PriceOracle']}",
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to read PriceOracle: {e}")


@router.get("/tips")
def get_health_tips():
    try:
        count = health_tips.functions.getTipCount().call()
        tips = []
        for i in range(count):
            topic, tip = health_tips.functions.getTip(i).call()
            tips.append({"index": i, "topic": topic, "tip": tip})
        return {
            "count": count,
            "tips": tips,
            "source": "LLM Inference Agent (Qwen3-30B) with chain-of-thought",
            "contract": DEPLOYED["HealthTips"],
            "explorerUrl": f"{EXPLORER}/address/{DEPLOYED['HealthTips']}",
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to read HealthTips: {e}")


@router.get("/sentiment")
def get_sentiment():
    try:
        classification = sentiment.functions.latestClassification().call()
        score = sentiment.functions.latestScore().call()
        return {
            "classification": classification or None,
            "score": score,
            "source": "LLM Inference Agent (Qwen3-30B)",
            "contract": DEPLOYED["SentimentAnalyzer"],
            "explorerUrl": f"{EXPLORER}/address/{DEPLOYED['SentimentAnalyzer']}",
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to read SentimentAnalyzer: {e}")


@router.get("/drug-info")
def get_drug_info():
    try:
        count = drug_info.functions.getInfoCount().call()
        drugs = []
        for i in range(count):
            drug_name, info = drug_info.functions.getInfo(i).call()
            drugs.append({"index": i, "drugName": drug_name, "info": info})
        return {
            "count": count,
            "drugs": drugs,
            "source": "LLM Inference Agent (Qwen3-30B) with chain-of-thought",
            "contract": DEPLOYED["DrugInfoV2"],
            "explorerUrl": f"{EXPLORER}/address/{DEPLOYED['DrugInfoV2']}",
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to read DrugInfoV2: {e}")

@router.get("/status")
def get_system_status():
    connected = w3.is_connected()
    try:
        chain_id = w3.eth.chain_id if connected else None
    except Exception:
        chain_id = None
    return {
        "rpc": RPC,
        "connected": connected,
        "chainId": chain_id,
        "explorer": EXPLORER,
        "platformContract": "0x037Bb9C718F3f7fe5eCBDB0b600D607b52706776",
        "contracts": DEPLOYED,
    }
