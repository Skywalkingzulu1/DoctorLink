"""
Somnia escrow service for appointment payments.
Handles deposit, release, refund, and platform fee splitting on-chain.
"""
from web3 import Web3
from config import settings
from somnia.client import somnia

ESCROW_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "appointmentId", "type": "uint256"},
            {"internalType": "address", "name": "doctorAddress", "type": "address"},
        ],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "appointmentId", "type": "uint256"},
        ],
        "name": "release",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "appointmentId", "type": "uint256"},
        ],
        "name": "refund",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "appointmentId", "type": "uint256"},
        ],
        "name": "getEscrowStatus",
        "outputs": [
            {"internalType": "uint256", "name": "deposited", "type": "uint256"},
            {"internalType": "uint256", "name": "released", "type": "uint256"},
            {"internalType": "uint8", "name": "state", "type": "uint8"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


def _get_escrow_contract():
    if not somnia.escrow_contract_address:
        raise ValueError(
            "Escrow contract not configured. Set SOMNIA_ESCROW_CONTRACT in .env"
        )
    return somnia.w3.eth.contract(
        address=somnia.escrow_contract_address,
        abi=ESCROW_ABI,
    )


def deposit_escrow(appointment_id: int, doctor_address: str, amount: int) -> dict:
    """Deposit STT tokens into escrow for an appointment."""
    contract = _get_escrow_contract()
    account = somnia.get_account()

    tx = contract.functions.deposit(
        appointment_id,
        Web3.to_checksum_address(doctor_address),
    ).build_transaction({
        "from": account.address,
        "value": amount,
        "nonce": somnia.w3.eth.get_transaction_count(account.address),
        "gas": settings.SOMNIA_GAS_LIMIT,
        "gasPrice": somnia._gas_price(),
        "chainId": somnia.chain_id,
    })

    receipt = somnia.send_tx(tx)
    return {
        "tx_hash": receipt.transactionHash.hex(),
        "appointment_id": appointment_id,
        "amount": amount,
    }


def release_escrow(appointment_id: int) -> dict:
    """Release escrow to doctor (80%) and platform (20%)."""
    contract = _get_escrow_contract()
    account = somnia.get_account()

    tx = contract.functions.release(appointment_id).build_transaction({
        "from": account.address,
        "nonce": somnia.w3.eth.get_transaction_count(account.address),
        "gas": settings.SOMNIA_GAS_LIMIT,
        "gasPrice": somnia._gas_price(),
        "chainId": somnia.chain_id,
    })

    receipt = somnia.send_tx(tx)
    return {
        "tx_hash": receipt.transactionHash.hex(),
        "appointment_id": appointment_id,
    }


def refund_escrow(appointment_id: int) -> dict:
    """Refund full escrow amount back to patient."""
    contract = _get_escrow_contract()
    account = somnia.get_account()

    tx = contract.functions.refund(appointment_id).build_transaction({
        "from": account.address,
        "nonce": somnia.w3.eth.get_transaction_count(account.address),
        "gas": settings.SOMNIA_GAS_LIMIT,
        "gasPrice": somnia._gas_price(),
        "chainId": somnia.chain_id,
    })

    receipt = somnia.send_tx(tx)
    return {
        "tx_hash": receipt.transactionHash.hex(),
        "appointment_id": appointment_id,
    }


def get_escrow_status(appointment_id: int) -> dict:
    """Get on-chain escrow status for an appointment."""
    contract = _get_escrow_contract()
    deposited, released, state = contract.functions.getEscrowStatus(appointment_id).call()
    state_map = {0: "pending", 1: "held", 2: "released", 3: "refunded"}
    return {
        "appointment_id": appointment_id,
        "deposited": deposited,
        "released": released,
        "state": state_map.get(state, "unknown"),
    }


def forward_platform_fees_to_sponsor(amount_in_wei: int) -> dict:
    """Forward platform fees from deployer wallet to sponsor contract.

    Since the escrow contract's platform address is immutable (set to deployer EOA),
    this manually forwards accumulated STT fees to the sponsor contract treasury.
    """
    account = somnia.get_account()
    sponsor = Web3.to_checksum_address(settings.SOMNIA_SPONSOR_CONTRACT)
    tx = {
        "from": account.address,
        "to": sponsor,
        "value": amount_in_wei,
        "nonce": somnia.w3.eth.get_transaction_count(account.address),
        "gas": 21000,
        "gasPrice": somnia._gas_price(),
        "chainId": somnia.chain_id,
    }
    receipt = somnia.send_tx(tx)
    return {
        "tx_hash": receipt.transactionHash.hex(),
        "amount_wei": amount_in_wei,
        "amount_stt": float(somnia.w3.from_wei(amount_in_wei, "ether")),
    }
