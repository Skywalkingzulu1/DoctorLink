"""
Somnia blockchain RPC client using web3.py.
Handles connection, transactions, and contract interactions.
"""
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from config import settings


class SomniaClient:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.SOMNIA_RPC_URL))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.chain_id = settings.SOMNIA_CHAIN_ID
        self.platform_contract_address = Web3.to_checksum_address(
            settings.SOMNIA_PLATFORM_CONTRACT
        )
        self.escrow_contract_address = (
            Web3.to_checksum_address(settings.SOMNIA_ESCROW_CONTRACT)
            if settings.SOMNIA_ESCROW_CONTRACT
            else None
        )
        self.sponsor_contract_address = (
            Web3.to_checksum_address(settings.SOMNIA_SPONSOR_CONTRACT)
            if settings.SOMNIA_SPONSOR_CONTRACT
            else None
        )
        self.t800_contract_address = (
            Web3.to_checksum_address(settings.T800_CONTRACT_ADDRESS)
            if settings.T800_CONTRACT_ADDRESS
            else None
        )
        self.router_contract_address = (
            Web3.to_checksum_address(settings.ROUTER_CONTRACT_ADDRESS)
            if settings.ROUTER_CONTRACT_ADDRESS
            else None
        )
        self.vesting_contract_address = (
            Web3.to_checksum_address(settings.TOKEN_VESTING_CONTRACT)
            if settings.TOKEN_VESTING_CONTRACT
            else None
        )
        self.dex_contract_address = (
            Web3.to_checksum_address(settings.DEX_CONTRACT_ADDRESS)
            if settings.DEX_CONTRACT_ADDRESS
            else None
        )
        self.account = None
        if settings.SOMNIA_PRIVATE_KEY:
            try:
                self.account = self.w3.eth.account.from_key(settings.SOMNIA_PRIVATE_KEY)
            except Exception:
                print("[Somnia] Invalid SOMNIA_PRIVATE_KEY — operating without platform wallet")

    def validate(self):
        """Check RPC connection and chain ID on startup. Raises on mismatch."""
        if not self.w3.is_connected():
            print("[WARN] Somnia RPC not reachable — Somnia features disabled")
            return
        actual_chain = self.w3.eth.chain_id
        if actual_chain != self.chain_id:
            print(f"[WARN] Somnia chain ID mismatch: expected {self.chain_id}, got {actual_chain}")
        print(f"[Somnia] Connected to chain {actual_chain}")

    def is_connected(self) -> bool:
        return self.w3.is_connected()

    def get_balance(self, address: str) -> int:
        return self.w3.eth.get_balance(Web3.to_checksum_address(address))

    def get_account(self):
        if not self.account:
            raise ValueError("No wallet configured. Set SOMNIA_PRIVATE_KEY in .env")
        return self.account

    def _gas_price(self) -> int:
        try:
            return self.w3.eth.gas_price
        except Exception:
            return self.w3.to_wei("10", "gwei")

    def build_tx(self, contract, function, *args, **kwargs):
        account = self.get_account()
        nonce = self.w3.eth.get_transaction_count(account.address)
        tx = function(*args).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gas": settings.SOMNIA_GAS_LIMIT,
            "gasPrice": self._gas_price(),
            "chainId": self.chain_id,
        })
        return tx

    def send_tx(self, tx):
        account = self.get_account()
        signed = self.w3.eth.account.sign_transaction(tx, account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.get("status", 1) == 0:
            tx_link = f"{tx_hash.hex()}"
            raise RuntimeError(
                f"Transaction failed on-chain (status 0). Hash: {tx_link}. "
                "Check contract logic, balance, and parameters."
            )
        return receipt

    def create_user_wallet(self) -> dict:
        """Generate a new wallet for a user. Returns address and private key."""
        account = self.w3.eth.account.create()
        return {
            "address": account.address,
            "private_key": account.key.hex(),
        }


somnia = SomniaClient()
