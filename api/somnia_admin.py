import os, sys, requests as http_requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends, HTTPException
from web3 import Web3
from eth_abi import encode
from config import settings
from somnia.client import somnia
from database import Appointment, User
from auth import get_current_user

router = APIRouter(prefix="/api/somnia/admin", tags=["somnia-admin"])

DEPLOYER = Web3.to_checksum_address("0x715048055cCf1C46b225b0a4F070000a6268C7eF")


def require_deployer(current_user: User = Depends(get_current_user)):
    """Only allow access if the authenticated user's somnia_address matches the deployer."""
    if not current_user.somnia_address:
        raise HTTPException(403, "No Somnia address linked to your account")
    if Web3.to_checksum_address(current_user.somnia_address) != DEPLOYER:
        raise HTTPException(403, "Only the deployer wallet can access admin endpoints")
    return current_user

T800_ADDR = Web3.to_checksum_address("0x475385F327166423D9923024033d8deF34ea9186")
ROUTER_ADDR = Web3.to_checksum_address("0xbe6AE91380Bf23a1C1bFd613EFA794461A86337C")
DEX_ADDR = Web3.to_checksum_address("0x38e0Cd09C6eBB71e6d97653e5d083Bd1C897E7d7")
VEST_ADDR = Web3.to_checksum_address("0x7a67E8EA485223005323314249154075bd05e1B7")
PLATFORM_ADDR = Web3.to_checksum_address("0x037Bb9C718F3f7fe5eCBDB0b600D607b52706776")
SPONSOR_ADDR = Web3.to_checksum_address("0xbC26b85eaDF0e2ab1f2B5E7de048D52E80bCa3Ca")
ESCROW_ADDR = Web3.to_checksum_address("0xe68fe63F35EF5068BE57084B27753eAB6768beb1")

T800_ABI = [
    {"inputs":[],"name":"totalSupply","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"a","type":"address"}],"name":"balanceOf","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"name","outputs":[{"type":"string"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"symbol","outputs":[{"type":"string"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"decimals","outputs":[{"type":"uint8"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"owner","outputs":[{"type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"mintingFinished","outputs":[{"type":"bool"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"MAX_SUPPLY","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
]

ROUTER_ABI = [
    {"inputs":[],"name":"getSttPoolBalance","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"t800PerInvocation","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalT800Collected","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalSttPool","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"u","type":"address"}],"name":"userT800Spent","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"owner","outputs":[{"type":"address"}],"stateMutability":"view","type":"function"},
]

DEX_ABI = [
    {"inputs":[],"name":"reserveT800","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"reserveStt","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalLiquidity","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"getT800Price","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"getSttPrice","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"owner","outputs":[{"type":"address"}],"stateMutability":"view","type":"function"},
]

VEST_ABI = [
    {"inputs":[],"name":"getScheduleCount","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"","type":"uint256"}],"name":"schedules","outputs":[{"type":"address","name":"beneficiary"},{"type":"uint256","name":"totalAmount"},{"type":"uint256","name":"startTime"},{"type":"uint256","name":"cliffDuration"},{"type":"uint256","name":"duration"},{"type":"uint256","name":"released"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"token","outputs":[{"type":"address"}],"stateMutability":"view","type":"function"},
]

SPONSOR_ABI = [
    {"inputs":[],"name":"sponsorBalance","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"emergencyWithdraw","outputs":[],"stateMutability":"nonpayable","type":"function"},
]


def _get_account():
    acct = somnia.get_account()
    if not acct:
        raise HTTPException(401, "No deployer private key configured")
    return acct


def _send_tx(to_addr, data, value=0, gas=500000):
    w3 = somnia.w3
    acct = _get_account()
    nonce = w3.eth.get_transaction_count(acct.address)
    tx = {
        "from": acct.address,
        "to": Web3.to_checksum_address(to_addr),
        "data": data,
        "value": value,
        "nonce": nonce,
        "gas": gas,
        "gasPrice": w3.eth.gas_price,
        "chainId": 50312,
    }
    signed = w3.eth.account.sign_transaction(tx, acct.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.get("status", 1) == 0:
        raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
    return receipt


@router.get("/overview")
def get_admin_overview(_admin: User = Depends(require_deployer)):
    w3 = somnia.w3
    if not w3.is_connected():
        raise HTTPException(503, "Somnia RPC not connected")

    t800 = w3.eth.contract(address=T800_ADDR, abi=T800_ABI)
    router = w3.eth.contract(address=ROUTER_ADDR, abi=ROUTER_ABI)
    dex = w3.eth.contract(address=DEX_ADDR, abi=DEX_ABI)
    vest = w3.eth.contract(address=VEST_ADDR, abi=VEST_ABI)
    sponsor = w3.eth.contract(address=SPONSOR_ADDR, abi=SPONSOR_ABI)

    # T800 Token
    name = t800.functions.name().call()
    symbol = t800.functions.symbol().call()
    total_supply = t800.functions.totalSupply().call()
    deployer_t800 = t800.functions.balanceOf(DEPLOYER).call()
    router_t800_bal = t800.functions.balanceOf(ROUTER_ADDR).call()
    dex_t800_bal = t800.functions.balanceOf(DEX_ADDR).call()
    minting_finished = t800.functions.mintingFinished().call()
    try:
        max_supply = t800.functions.MAX_SUPPLY().call()
    except:
        max_supply = total_supply

    # Router
    stt_pool = router.functions.getSttPoolBalance().call()
    t800_fee = router.functions.t800PerInvocation().call()
    total_t800_collected = router.functions.totalT800Collected().call()

    # DEX
    t800_reserve = dex.functions.reserveT800().call()
    stt_reserve = dex.functions.reserveStt().call()
    total_liquidity = dex.functions.totalLiquidity().call()
    t800_price = dex.functions.getT800Price().call()
    stt_price = dex.functions.getSttPrice().call()

    # Sponsor
    try:
        sponsor_bal = sponsor.functions.sponsorBalance().call()
    except:
        sponsor_bal = 0
    try:
        emergency_withdraw_selector = Web3.keccak(text="emergencyWithdraw()")[:4].hex()
        sponsor_has_withdraw = True
    except:
        sponsor_has_withdraw = False

    # Vesting
    schedule_count = vest.functions.getScheduleCount().call()
    schedules = []
    for i in range(min(schedule_count, 20)):
        try:
            s = vest.functions.schedules(i).call()
            schedules.append({
                "id": i,
                "beneficiary": s[0],
                "total_amount": s[1],
                "start_time": s[2],
                "cliff_duration": s[3],
                "duration": s[4],
                "released": s[5],
            })
        except:
            pass

    # STT balances of all contracts
    deployer_stt = w3.eth.get_balance(DEPLOYER)
    platform_stt = w3.eth.get_balance(PLATFORM_ADDR)
    sponsor_stt = w3.eth.get_balance(SPONSOR_ADDR)
    escrow_stt = w3.eth.get_balance(ESCROW_ADDR)
    router_stt = w3.eth.get_balance(ROUTER_ADDR)
    dex_stt = w3.eth.get_balance(DEX_ADDR)

    # Compute P&L
    stt_in_dex = dex_stt  # STT in DEX (value sent + any fees)
    stt_in_router_pool = stt_pool  # STT deposited in router pool
    stt_spent_on_gas = 1589000000000000000  # ~1.589 STT (cumulative from known data)
    stt_in_platform = platform_stt  # locked in platform
    stt_in_sponsor = sponsor_stt  # in sponsor contract
    stt_faucet_received = 37000000000000000000  # 37 STT from faucet (approx)
    stt_deposited_to_platform = 13650000000000000000  # ~13.65 STT sent to platform over 170 txs
    stt_deposited_to_sponsor = 3000000000000000000  # 3 STT sent to sponsor

    # Total STT that went through deployer's wallet
    total_stt_in = stt_faucet_received
    total_stt_out = stt_in_dex + stt_in_router_pool + stt_spent_on_gas + stt_in_platform
    stt_balance_sheet = {
        "stt_in_faucet": stt_faucet_received,
        "stt_in_dex_liquidity": stt_in_dex,
        "stt_in_router_pool": stt_in_router_pool,
        "stt_locked_in_platform": stt_in_platform,
        "stt_in_sponsor": stt_in_sponsor,
        "stt_gas_spent_lifetime": stt_spent_on_gas,
        "stt_deposited_to_platform_historical": stt_deposited_to_platform,
        "stt_deposited_to_sponsor_historical": stt_deposited_to_sponsor,
        "stt_deployer_wallet": deployer_stt,
    }

    recoverable = []
    locked_permanently = []

    # Sponsor — recoverable via emergencyWithdraw
    if sponsor_stt > 0:
        recoverable.append({
            "contract": "Sponsor",
            "address": SPONSOR_ADDR,
            "amount_stt": sponsor_stt,
            "method": "emergencyWithdraw()",
            "action": "recover/sponsor",
        })

    # Router pool — recoverable via withdrawStt
    if stt_pool > 0:
        recoverable.append({
            "contract": "AgentPaymentRouter (STT pool)",
            "address": ROUTER_ADDR,
            "amount_stt": stt_pool,
            "method": "withdrawStt(deployer, balance)",
            "action": "recover/router-stt",
        })

    # DEX LP — recoverable via removeLiquidity
    if total_liquidity > 0:
        lp_t800_share = t800_reserve  # all LP is deployer's
        lp_stt_share = stt_reserve
        recoverable.append({
            "contract": "T800DEX (LP position)",
            "address": DEX_ADDR,
            "amount_stt": lp_stt_share,
            "amount_t800": lp_t800_share,
            "lp_tokens": total_liquidity,
            "method": "removeLiquidity(lp_amount)",
            "action": "recover/dex-lp",
        })

    # Platform — permanently locked
    if platform_stt > 0:
        locked_permanently.append({
            "contract": "Platform (official)",
            "address": PLATFORM_ADDR,
            "amount_stt": platform_stt,
            "reason": "No admin role, no cancelRequest, no withdraw function available",
        })

    # T800 value in STT (at DEX price) — informational only, not realizable
    t800_value_in_stt = 0
    if t800_price > 0:
        t800_value_in_stt = deployer_t800 * t800_price // 10**18

    # Off-chain platform T800 earnings
    from database import SessionLocal, User as DBUser
    _db = SessionLocal()
    platform_t800 = 0
    try:
        platform_user = _db.query(DBUser).filter(DBUser.email == "platform@doctorlink.co.za").first()
        if platform_user:
            platform_t800 = platform_user.t800_balance or 0
            # Also get total platform fee collected from appointments
            from sqlalchemy import func
            total_fee = _db.query(func.sum(Appointment.platform_fee_t800)).scalar() or 0
        else:
            total_fee = 0
    except:
        total_fee = 0
    finally:
        _db.close()

    return {
        "t800_token": {
            "name": name,
            "symbol": symbol,
            "total_supply": total_supply,
            "max_supply": max_supply,
            "minting_finished": minting_finished,
            "deployer_balance": deployer_t800,
            "router_balance": router_t800_bal,
            "dex_balance": dex_t800_bal,
            "circulating": max(0, total_supply - deployer_t800),
        },
        "router": {
            "stt_pool_balance": stt_pool,
            "stt_contract_balance": router_stt,
            "t800_per_invocation": t800_fee,
            "total_t800_collected": total_t800_collected,
        },
        "dex": {
            "t800_reserve": t800_reserve,
            "stt_reserve": stt_reserve,
            "total_liquidity_tokens": total_liquidity,
            "t800_price_stt": t800_price,
            "stt_price_t800": stt_price,
        },
        "vesting": {
            "schedule_count": schedule_count,
            "schedules": schedules,
        },
        "contract_stt_balances": {
            "deployer": deployer_stt,
            "platform": platform_stt,
            "sponsor": sponsor_stt,
            "escrow": escrow_stt,
            "router": router_stt,
            "dex": dex_stt,
        },
        "dex_price_info": {
            "t800_price_stt": t800_price,
            "t800_value_at_dex_price_stt": t800_value_in_stt,
            "note": "T800 value at DEX price is not realizable — only 50K T800 has liquidity",
        },
        "stt_balance_sheet": stt_balance_sheet,
        "recoverable_funds": recoverable,
        "locked_permanently": locked_permanently,
        "platform_t800_earnings": {
            "platform_account_balance": platform_t800,
            "total_fee_collected_from_appointments": total_fee,
        },
        "deployer": DEPLOYER,
        "chain_id": 50312,
    }


@router.post("/recover/sponsor")
def recover_sponsor(_admin: User = Depends(require_deployer)):
    """Call emergencyWithdraw() on sponsor contract to recover 3 STT."""
    w3 = somnia.w3
    data = Web3.keccak(text="emergencyWithdraw()")[:4]
    receipt = _send_tx(SPONSOR_ADDR, data, gas=100000)
    new_bal = w3.eth.get_balance(DEPLOYER)
    return {
        "success": True,
        "tx_hash": receipt.transactionHash.hex(),
        "block": receipt.blockNumber,
        "deployer_stt_before": new_bal,
        "deployer_stt_after": w3.eth.get_balance(DEPLOYER),
    }


@router.post("/recover/router-stt")
def recover_router_stt(_admin: User = Depends(require_deployer)):
    """Withdraw all STT from router pool back to deployer."""
    w3 = somnia.w3
    router = w3.eth.contract(address=ROUTER_ADDR, abi=ROUTER_ABI)
    stt_balance = router.functions.getSttPoolBalance().call()
    if stt_balance == 0:
        raise HTTPException(400, "Router STT pool is empty")
    data = Web3.keccak(text="withdrawStt(address,uint256)")[:4] + encode(
        ["address", "uint256"], [DEPLOYER, stt_balance]
    )
    receipt = _send_tx(ROUTER_ADDR, data, gas=100000)
    return {
        "success": True,
        "tx_hash": receipt.transactionHash.hex(),
        "block": receipt.blockNumber,
        "amount_stt": stt_balance,
    }


@router.post("/recover/dex-lp")
def recover_dex_lp(_admin: User = Depends(require_deployer)):
    """Remove all DEX liquidity, return T800 + STT to deployer."""
    w3 = somnia.w3
    dex = w3.eth.contract(address=DEX_ADDR, abi=DEX_ABI)
    lp_balance = dex.functions.totalLiquidity().call()
    if lp_balance == 0:
        raise HTTPException(400, "No LP tokens to remove")
    t800_before = dex.functions.reserveT800().call()
    stt_before = dex.functions.reserveStt().call()
    data = Web3.keccak(text="removeLiquidity(uint256)")[:4] + encode(
        ["uint256"], [lp_balance]
    )
    receipt = _send_tx(DEX_ADDR, data, gas=500000)
    return {
        "success": True,
        "tx_hash": receipt.transactionHash.hex(),
        "block": receipt.blockNumber,
        "lp_tokens_burned": lp_balance,
        "t800_returned_expected": t800_before,
        "stt_returned_expected": stt_before,
    }


@router.get("/schedules")
def get_vesting_schedules(_admin: User = Depends(require_deployer)):
    w3 = somnia.w3
    if not w3.is_connected():
        raise HTTPException(503, "Somnia RPC not connected")
    vest = w3.eth.contract(address=VEST_ADDR, abi=VEST_ABI)
    count = vest.functions.getScheduleCount().call()
    schedules = []
    for i in range(count):
        try:
            s = vest.functions.schedules(i).call()
            schedules.append({
                "id": i,
                "beneficiary": s[0],
                "total_amount": s[1],
                "start_time": s[2],
                "cliff_duration": s[3],
                "duration": s[4],
                "released": s[5],
            })
        except:
            pass
    return {"schedules": schedules, "count": count}
