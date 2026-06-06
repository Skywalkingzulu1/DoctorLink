"""
Somnia Agent service for invoking on-chain AI agents via the Sponsor contract.
Agent fees paid from sponsor contract pool. Credit deduction per invocation.
"""
import json
import time
import threading
from datetime import datetime, timezone
from typing import Optional
from web3 import Web3
from web3.exceptions import ContractCustomError
from eth_abi import encode, decode
from sqlalchemy.orm import Session
from config import settings
from somnia.client import somnia
from database import SessionLocal, User, AiResponse

AGENT_ID_LLM = 12847293847561029384
AGENT_ID_JSON = 13174292974160097713

AGENT_PRICES = {
    AGENT_ID_LLM: Web3.to_wei(0.07, "ether"),
    AGENT_ID_JSON: Web3.to_wei(0.07, "ether"),
}

# JSON API agent function selectors
FETCH_STRING_SELECTOR = Web3.keccak(text="fetchString(string,string)")[:4]
FETCH_UINT_SELECTOR = Web3.keccak(text="fetchUint(string,string,uint8)")[:4]

# Cost in credits per AI invocation
AI_CREDIT_COSTS = {
    "symptom_check": 5,
    "drug_interaction": 5,
    "health_tips": 3,
    "visit_summary": 5,
    "doctor_verification": 3,
}

REQUEST_CREATED_SIG_BYTES = Web3.keccak(
    text="RequestCreated(uint256,uint256,uint256,bytes,address[])"
)

REQUEST_FINALIZED_SIG_BYTES = Web3.keccak(
    text="RequestFinalized(uint256,uint8)"
)

AGENT_INVOKED_SIG_BYTES = Web3.keccak(
    text="AgentInvoked(uint256,uint256,uint256)"
)

AGENT_RESPONSE_SIG_BYTES = Web3.keccak(
    text="AgentResponse(uint256,uint8,bytes)"
)

INFER_STRING_SELECTOR = Web3.keccak(
    text="inferString(string,string,bool,string[])"
)[:4]

SOMNIA_SUBCOMMITTEE_SIZE = 3

REQUEST_NOT_FOUND_SELECTOR = Web3.keccak(text="RequestNotFound(uint256)")[:4]

# T-800 token integration
T800_ABI = [
    {"inputs": [{"name": "to", "type": "address"}, {"name": "value", "type": "uint256"}],
     "name": "transfer", "outputs": [{"type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "from", "type": "address"}, {"name": "to", "type": "address"}, {"name": "value", "type": "uint256"}],
     "name": "transferFrom", "outputs": [{"type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "account", "type": "address"}],
     "name": "balanceOf", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
     "name": "allowance", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "spender", "type": "address"}, {"name": "value", "type": "uint256"}],
     "name": "approve", "outputs": [{"type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "totalSupply", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
]

ROUTER_ABI = [
    {"inputs": [{"name": "agentId", "type": "uint256"}, {"name": "payload", "type": "bytes"}],
     "name": "payAndInvokeSimple", "outputs": [{"type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "agentId", "type": "uint256"}, {"name": "callbackAddress", "type": "address"},
     {"name": "callbackSelector", "type": "bytes4"}, {"name": "payload", "type": "bytes"}],
     "name": "payAndInvoke", "outputs": [{"type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "t800PerInvocation", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "getSttPoolBalance", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
]

_result_cache: dict[int, "AgentResult"] = {}
_cache_lock = threading.Lock()

PLATFORM_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "requestId", "type": "uint256"}],
        "name": "getRequest",
        "outputs": [{"components": [
            {"internalType": "uint256", "name": "id", "type": "uint256"},
            {"internalType": "address", "name": "requester", "type": "address"},
            {"internalType": "address", "name": "callbackAddress", "type": "address"},
            {"internalType": "bytes4", "name": "callbackSelector", "type": "bytes4"},
            {"internalType": "address[]", "name": "subcommittee", "type": "address[]"},
            {"components": [
                {"internalType": "address", "name": "validator", "type": "address"},
                {"internalType": "bytes", "name": "result", "type": "bytes"},
                {"internalType": "uint8", "name": "status", "type": "uint8"},
                {"internalType": "uint256", "name": "receipt", "type": "uint256"},
                {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                {"internalType": "uint256", "name": "executionCost", "type": "uint256"},
            ], "internalType": "struct Response[]", "name": "responses", "type": "tuple[]"},
            {"internalType": "uint256", "name": "responseCount", "type": "uint256"},
            {"internalType": "uint256", "name": "failureCount", "type": "uint256"},
            {"internalType": "uint256", "name": "threshold", "type": "uint256"},
            {"internalType": "uint256", "name": "createdAt", "type": "uint256"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
            {"internalType": "uint8", "name": "status", "type": "uint8"},
            {"internalType": "uint8", "name": "consensusType", "type": "uint8"},
            {"internalType": "uint256", "name": "remainingBudget", "type": "uint256"},
            {"internalType": "uint256", "name": "perAgentBudget", "type": "uint256"},
        ], "internalType": "struct Request", "name": "", "type": "tuple"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getRequestDeposit",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "agentId", "type": "uint256"},
            {"internalType": "address", "name": "callbackAddress", "type": "address"},
            {"internalType": "bytes4", "name": "callbackSelector", "type": "bytes4"},
            {"internalType": "bytes", "name": "payload", "type": "bytes"},
        ],
        "name": "createRequest",
        "outputs": [{"internalType": "uint256", "name": "requestId", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    },
]

SPONSOR_ABI = [
    {
        "inputs": [],
        "name": "sponsorBalance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

platform = somnia.w3.eth.contract(
    address=somnia.platform_contract_address, abi=PLATFORM_ABI
)

sponsor = None
if somnia.sponsor_contract_address:
    sponsor = somnia.w3.eth.contract(
        address=somnia.sponsor_contract_address, abi=SPONSOR_ABI
    )

t800_token = None
if somnia.t800_contract_address:
    t800_token = somnia.w3.eth.contract(
        address=somnia.t800_contract_address, abi=T800_ABI
    )

agent_router = None
if somnia.router_contract_address:
    agent_router = somnia.w3.eth.contract(
        address=somnia.router_contract_address, abi=ROUTER_ABI
    )


class AgentResult:
    def __init__(self, request_id: int, status: str, result: Optional[str] = None):
        self.request_id = request_id
        self.status = status
        self.result = result


def _is_request_not_found(e: Exception) -> bool:
    if isinstance(e, ContractCustomError):
        args = e.args
        if args:
            data = args[0]
            if isinstance(data, str) and data.startswith("0x"):
                return data[2:10] == REQUEST_NOT_FOUND_SELECTOR.hex()
            if isinstance(data, bytes):
                return data[:4] == REQUEST_NOT_FOUND_SELECTOR
    error_str = str(e).lower()
    return "requestnotfound" in error_str.replace(" ", "").replace("_", "")


def save_ai_response(request_id: int, user_id: Optional[int], feature: str, prompt: str, result: Optional[str], status: str = "success"):
    """Persist AI agent response to Filebase JSON database."""
    db: Session = SessionLocal()
    try:
        # Check if already exists (update if so)
        existing = db.query(AiResponse).filter(AiResponse.request_id == request_id).first()
        if existing:
            if result:
                existing.result = result
            existing.status = status
            existing.created_at = datetime.now(timezone.utc)
        else:
            resp = AiResponse(
                request_id=request_id,
                user_id=user_id,
                feature=feature,
                prompt=prompt,
                result=result,
                status=status
            )
            db.add(resp)
        db.commit()
        print(f"[Somnia] AI response for request {request_id} saved to Filebase.")
    except Exception as e:
        print(f"[Somnia] Error saving AI response to Filebase: {e}")
    finally:
        db.close()


def deduct_credits(user_id: int, feature: str) -> bool:
    """Deduct credits from user for AI invocation. Returns True if enough credits."""
    cost = AI_CREDIT_COSTS.get(feature, 5)
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        if (user.credits or 0) < cost:
            return False
        user.credits -= cost
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def _get_deposit() -> int:
    """Get total deposit needed: floor + perAgentPrice * 3."""
    floor = platform.functions.getRequestDeposit().call()
    per_agent = somnia.w3.to_wei(0.07, "ether")
    return floor + per_agent * SOMNIA_SUBCOMMITTEE_SIZE


def _send_agent_tx(agent_id: int, payload: bytes) -> int:
    """Invoke agent via platform.createRequest directly from deployer wallet.

    Uses the sponsor contract address as callback (validators need a contract
    to submit responses). The deployer wallet pays the deposit fee.
    """
    account = somnia.get_account()
    deposit = _get_deposit()

    # Use sponsor contract as callback (needs a contract address for validators)
    callback = somnia.sponsor_contract_address or account.address
    # handleResponse selector from the sponsor contract
    callback_selector = Web3.keccak(
        text="handleResponse(uint256,(address,bytes,uint8,uint256,uint256,uint256)[],uint8,(uint256,address,address,bytes4,address[],(address,bytes,uint8,uint256,uint256,uint256)[],uint256,uint256,uint256,uint256,uint256,uint256,uint8,uint8,uint256,uint256))"
    )[:4]

    # Simulate first to catch revert reasons
    try:
        platform.functions.createRequest(
            agent_id,
            callback,
            callback_selector,
            payload,
        ).call({
            "from": account.address,
            "value": deposit,
        })
    except ContractCustomError as e:
        raise RuntimeError(f"Platform createRequest reverted: {e}")
    except ValueError as e:
        msg = str(e)
        if "execution reverted" in msg.lower() or "revert" in msg.lower():
            raise RuntimeError(f"Platform createRequest reverted: {msg[:300]}")
        raise

    nonce = somnia.w3.eth.get_transaction_count(account.address)

    tx = platform.functions.createRequest(
        agent_id,
        callback,
        callback_selector,
        payload,
    ).build_transaction({
        "from": account.address,
        "value": deposit,
        "nonce": nonce,
        "gas": settings.SOMNIA_GAS_LIMIT,
        "gasPrice": somnia._gas_price(),
        "chainId": somnia.chain_id,
    })

    receipt = somnia.send_tx(tx)

    # Look for RequestCreated event
    for log in receipt.get("logs", []):
        topics = log.get("topics", [])
        if not topics:
            continue
        if topics[0] == REQUEST_CREATED_SIG_BYTES and len(topics) >= 2:
            try:
                request_id = int.from_bytes(topics[1], byteorder="big")
                _start_polling(request_id)
                
                # Pre-save pending state
                save_ai_response(request_id, None, "invoke", "on-chain", None, "pending")
                
                return request_id
            except (ValueError, IndexError):
                continue

    raise RuntimeError(
        "createRequest tx confirmed but no RequestCreated event. "
        f"Tx hash: {receipt.transactionHash.hex() if hasattr(receipt, 'transactionHash') else 'unknown'}"
    )


def _check_sponsor_balance() -> float:
    """Check sponsor contract STT balance."""
    if not sponsor:
        return 0.0
    try:
        bal = sponsor.functions.sponsorBalance().call()
        return float(somnia.w3.from_wei(bal, "ether"))
    except Exception:
        return 0.0


def invoke_via_router(agent_id: int, payload: bytes) -> int:
    """Invoke agent via AgentPaymentRouter (pays T800 instead of STT)."""
    if not agent_router:
        raise RuntimeError("AgentPaymentRouter not configured")
    tx = agent_router.functions.payAndInvokeSimple(
        agent_id, payload
    ).transact({
        "from": somnia.get_account().address,
    })
    receipt = somnia.w3.eth.wait_for_transaction_receipt(tx)
    for log in receipt.get("logs", []):
        topics = log.get("topics", [])
        if topics and len(topics) >= 2:
            if topics[0] == REQUEST_CREATED_SIG_BYTES:
                request_id = int.from_bytes(topics[1], byteorder="big")
                _start_polling(request_id)
                return request_id
    raise RuntimeError("Router invoke succeeded but no RequestCreated event")


STT_TO_T800_RATE = 30


def get_stt_invocation_cost() -> float:
    """Total STT needed per agent invocation: platform deposit + fee (10 T800 / 30)."""
    if not platform:
        return 0.0
    deposit = _get_deposit()
    fee = Web3.to_wei(10, "ether") // STT_TO_T800_RATE
    return float(somnia.w3.from_wei(deposit + fee, "ether"))


def invoke_with_stt(agent_id: int, payload: bytes) -> int:
    """Invoke agent using deployer wallet, charging STT at 1 STT = 30 T800 rate.

    The deployer wallet pays the platform deposit + fee. This is the STT-native
    payment path that bypasses both DB credits and T800 token requirements.
    """
    return _send_agent_tx(agent_id, payload)


def check_t800_balance(address: str) -> float:
    """Check T800 token balance for an address."""
    if not t800_token or not address:
        return 0.0
    try:
        bal = t800_token.functions.balanceOf(Web3.to_checksum_address(address)).call()
        return float(somnia.w3.from_wei(bal, "ether"))
    except Exception:
        return 0.0


def get_t800_fee() -> int:
    """Get current T800 fee per agent invocation."""
    if not agent_router:
        return 0
    return agent_router.functions.t800PerInvocation().call()


def transfer_t800_to_user(address: str, amount_ether: float) -> str:
    """Transfer T800 tokens from the platform/deployer to a user."""
    if not t800_token:
        print("[Somnia] T800 token not configured. Skipping transfer.")
        return ""
    try:
        amount_wei = Web3.to_wei(amount_ether, "ether")
        tx = somnia.build_tx(t800_token, t800_token.functions.transfer, Web3.to_checksum_address(address), amount_wei)
        receipt = somnia.send_tx(tx)
        print(f"[Somnia] Transferred {amount_ether} T800 to {address}. Tx: {receipt.transactionHash.hex()}")
        return receipt.transactionHash.hex()
    except Exception as e:
        print(f"[Somnia] Failed to transfer T800 to {address}: {e}")
        return ""


def get_router_stt_balance() -> float:
    """Check STT pool balance in AgentPaymentRouter."""
    if not agent_router:
        return 0.0
    try:
        bal = agent_router.functions.getSttPoolBalance().call()
        return float(somnia.w3.from_wei(bal, "ether"))
    except Exception:
        return 0.0


def invoke_llm_agent(prompt: str, system_prompt: str = "You are a helpful medical assistant.") -> int:
    """Invoke the LLM Inference agent via sponsor contract."""
    payload = INFER_STRING_SELECTOR + encode(
        ["string", "string", "bool", "string[]"],
        [prompt, system_prompt, False, []],
    )
    return _send_agent_tx(AGENT_ID_LLM, payload)


def invoke_llm_agent_for_user(user_id: int, prompt: str, feature: str, system_prompt: str = "You are a helpful medical assistant.") -> int:
    """Invoke LLM agent, deducting credits from user first and tracking in Filebase."""
    if not deduct_credits(user_id, feature):
        raise ValueError(f"Insufficient credits. Need {AI_CREDIT_COSTS.get(feature, 5)} credits for {feature}.")
    
    request_id = invoke_llm_agent(prompt, system_prompt)
    
    # Associate user and prompt metadata
    save_ai_response(request_id, user_id, feature, prompt, None, "pending")
    
    return request_id


def invoke_json_api_agent(url: str, selector_path: str = "") -> int:
    """Fetch JSON data via the JSON API Request agent (fetchString)."""
    payload = FETCH_STRING_SELECTOR + encode(
        ["string", "string"],
        [url, selector_path],
    )
    return _send_agent_tx(AGENT_ID_JSON, payload)


def invoke_website_parser_agent(url: str, prompt: str = "Extract all medical information from this page.") -> int:
    """Parse website content via Somnia LLM."""
    return invoke_llm_agent(f"Parse this URL: {url}. {prompt}", "You are a web scraping assistant.")


def _decode_request(req: tuple) -> tuple:
    """Extract (status_str, response_text) from a web3 Request tuple.
    If any validator submitted a successful response, treat as success
    even if the request-level status is still pending."""
    status_map = {0: "none", 1: "pending", 2: "success", 3: "failed", 4: "timedout"}
    status_code = req[11]
    status_str = status_map.get(status_code, "unknown")

    responses_list = req[5]
    if responses_list and len(responses_list) > 0:
        first = responses_list[0]
        result_bytes = first[1]
        resp_status = first[2]
        if resp_status > 0 and len(result_bytes) > 0:
            try:
                result_text = decode(["string"], result_bytes)[0]
                if result_text and len(result_text.strip()) > 0:
                    return "success", result_text
            except Exception:
                result_text = result_bytes.hex()
                return status_str, result_text

    return status_str, None


def _poll_for_result(request_id: int, timeout: int = 180):
    """Aggressive background poll: check getRequest on every block for responses."""
    w3 = somnia.w3
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            # Check Platform contract
            req = platform.functions.getRequest(request_id).call()
            responses = req[5]
            if responses and len(responses) > 0:
                status_str, result_text = _decode_request(req)
                result = AgentResult(request_id, status_str, result_text)
                
                with _cache_lock:
                    _result_cache[request_id] = result
                
                # Persist to Filebase on completion
                if status_str == "success":
                    save_ai_response(request_id, None, "callback", "restored", result_text, "success")
                return
            
            time.sleep(1) 
        except Exception as e:
            if _is_request_not_found(e):
                # Request finalized and cleared from Platform state
                # Check Sponsor logs
                result = _check_finalized(request_id)
                with _cache_lock:
                    _result_cache[request_id] = result
                
                if result.status == "success":
                    save_ai_response(request_id, None, "log_recovery", "restored", result.result, "success")
                return
            time.sleep(1)

    result = AgentResult(request_id, "timeout", None)
    with _cache_lock:
        _result_cache[request_id] = result
    save_ai_response(request_id, None, "timeout", "timedout", None, "timeout")


def _check_finalized(request_id: int) -> AgentResult:
    """Aggressive fallback: Scan Sponsor logs within RPC limits (1000 blocks)."""
    w3 = somnia.w3
    cb = w3.eth.block_number
    # Strict 1000 block limit for public RPCs
    fb = max(0, cb - 999)

    request_id_bytes = request_id.to_bytes(32, byteorder="big")

    # 1. Check Sponsor Contract for the actual result
    if somnia.sponsor_contract_address:
        for attempt in range(3):
            try:
                logs = w3.eth.get_logs({
                    "address": somnia.sponsor_contract_address,
                    "fromBlock": fb,
                    "toBlock": cb,
                    "topics": [AGENT_RESPONSE_SIG_BYTES, request_id_bytes],
                })
                if logs:
                    log = logs[0]
                    data = log.get("data")
                    # data is status (uint8) + result (bytes)
                    status_code, result_bytes = decode(["uint8", "bytes"], data)
                    
                    status_map = {0: "none", 1: "pending", 2: "success", 3: "failed", 4: "timedout"}
                    status_str = status_map.get(status_code, "unknown")
                    
                    result_text = None
                    if status_code == 2 and result_bytes:
                        try:
                            # Try decoding as clinical assessment string
                            result_text = decode(["string"], result_bytes)[0]
                        except Exception:
                            result_text = result_bytes.hex()
                    
                    return AgentResult(request_id, status_str, result_text)
                break # No logs found, move to fallback
            except Exception as e:
                if "block range" in str(e).lower():
                    # Shrink range even further if RPC is very strict
                    fb = max(fb, cb - 500)
                print(f"[Somnia] Log retrieval attempt {attempt+1} failed: {e}")
                time.sleep(1)

    # 2. Fallback to Platform Contract (status only)
    try:
        logs = w3.eth.get_logs({
            "address": platform.address,
            "fromBlock": fb,
            "toBlock": cb,
            "topics": [REQUEST_FINALIZED_SIG_BYTES, request_id_bytes],
        })
        if logs:
            topics = logs[0].get("topics", [])
            if len(topics) >= 3:
                status_code = int.from_bytes(topics[2], "big")
                sm = {0: "none", 1: "pending", 2: "success", 3: "failed", 4: "timedout"}
                return AgentResult(request_id, sm.get(status_code, "unknown"), None)
    except Exception:
        pass

    return AgentResult(request_id, "archived", None)


def _start_polling(request_id: int):
    thread = threading.Thread(target=_poll_for_result, args=(request_id,), daemon=True)
    thread.start()


def _try_fetch_onchain(request_id: int) -> AgentResult | None:
    """Try one fresh on-chain check for a request. Returns result or None."""
    try:
        req = platform.functions.getRequest(request_id).call()
        responses = req[5]
        if responses and len(responses) > 0:
            status_str, result_text = _decode_request(req)
            return AgentResult(request_id, status_str, result_text)
        # Has responses but all empty
        return AgentResult(request_id, "pending", None)
    except Exception as e:
        if _is_request_not_found(e):
            return _check_finalized(request_id)
        return None


def get_agent_result(request_id: int, wait: bool = True, timeout: int = 150) -> AgentResult:
    """Get agent result with persistent retries and Filebase recovery."""
    with _cache_lock:
        if request_id in _result_cache:
            return _result_cache[request_id]

    # Check Filebase first
    db: Session = SessionLocal()
    try:
        stored = db.query(AiResponse).filter(AiResponse.request_id == request_id).first()
        if stored and stored.status == "success" and stored.result:
            return AgentResult(request_id, "success", stored.result)
    except Exception:
        pass
    finally:
        db.close()

    if not wait:
        result = _try_fetch_onchain(request_id)
        if result:
            with _cache_lock:
                _result_cache[request_id] = result
            return result
        return AgentResult(request_id, "pending", None)

    deadline = time.time() + timeout
    while time.time() < deadline:
        with _cache_lock:
            if request_id in _result_cache:
                return _result_cache[request_id]

        result = _try_fetch_onchain(request_id)
        if result and result.status != "pending":
            with _cache_lock:
                _result_cache[request_id] = result
            return result

        time.sleep(3)

    return AgentResult(request_id, "timeout", None)
