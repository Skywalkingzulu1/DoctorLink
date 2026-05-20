import os
import json
from web3 import Web3
from dotenv import load_dotenv

def deploy():
    load_dotenv()
    
    RPC_URL = os.getenv("SOMNIA_RPC_URL", "https://api.infra.testnet.somnia.network")
    CHAIN_ID = int(os.getenv("SOMNIA_CHAIN_ID", "50312"))
    PRIVATE_KEY = os.getenv("SOMNIA_PRIVATE_KEY")
    PLATFORM_ADDRESS = os.getenv("SOMNIA_PLATFORM_CONTRACT", "0x037Bb9C718F3f7fe5eCBDB0b600D607b52706776")
    
    if not PRIVATE_KEY or PRIVATE_KEY == "your_testnet_wallet_private_key":
        print("Error: Invalid SOMNIA_PRIVATE_KEY in .env")
        return

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("Error: Failed to connect to Somnia Testnet")
        return

    # Add middle-ware for POA chain
    from web3.middleware import ExtraDataToPOAMiddleware
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    account = w3.eth.account.from_key(PRIVATE_KEY)
    print(f"Deploying from account: {account.address}")
    
    balance = w3.eth.get_balance(account.address)
    print(f"Account Balance: {w3.from_wei(balance, 'ether')} STT")
    if balance == 0:
        print("Error: Insufficient STT balance to deploy. Please get some testnet STT.")
        return

    # Load compiled contracts
    with open("somnia/compiled_contracts.json", "r") as f:
        compiled = json.load(f)

    # 1. Deploy Escrow
    print("Deploying DoctorLinkEscrow...")
    escrow_data = compiled["escrow.sol"]
    EscrowContract = w3.eth.contract(abi=escrow_data["abi"], bytecode=escrow_data["bytecode"])
    
    # Estimate gas
    try:
        gas_estimate = EscrowContract.constructor(PLATFORM_ADDRESS).estimate_gas({
            'from': account.address
        })
        print(f"Estimated Gas: {gas_estimate}")
    except Exception as e:
        print(f"Gas estimation failed: {e}")
        # Fallback to a high number if estimation fails, but stay within balance
        gas_estimate = 5000000 

    gas_price = w3.eth.gas_price
    max_gas_by_balance = int(balance / gas_price)
    print(f"Max gas affordable with current balance: {max_gas_by_balance}")

    # Use 95% of balance to be safe or the estimate + 20% buffer
    gas_to_use = min(max_gas_by_balance - 100000, int(gas_estimate * 1.2))
    print(f"Gas limit to be used: {gas_to_use}")

    if gas_to_use < gas_estimate:
        print("Warning: Affordable gas limit is lower than estimate. This might fail.")

    construct_txn = EscrowContract.constructor(PLATFORM_ADDRESS).build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'chainId': CHAIN_ID,
        'gas': gas_to_use,
        'gasPrice': gas_price
    })

    signed_txn = w3.eth.account.sign_transaction(construct_txn, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    print(f"Transaction sent! Hash: {tx_hash.hex()}")
    
    print("Waiting for transaction receipt...")
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    contract_address = tx_receipt.contractAddress
    print(f"Escrow Contract Deployed at: {contract_address}")
    
    # Update .env with the new contract address
    with open('.env', 'r') as f:
        env_lines = f.readlines()
        
    new_lines = []
    for line in env_lines:
        if line.startswith('SOMNIA_ESCROW_CONTRACT='):
            new_lines.append(f'SOMNIA_ESCROW_CONTRACT={contract_address}\n')
        else:
            new_lines.append(line)
            
    with open('.env', 'w') as f:
        f.writelines(new_lines)
    print("Updated .env with SOMNIA_ESCROW_CONTRACT")

    # 2. Deploy AgentCallback
    print("\nDeploying AgentCallback...")
    callback_data = compiled["agent_callback.sol"]
    CallbackContract = w3.eth.contract(abi=callback_data["abi"], bytecode=callback_data["bytecode"])
    
    try:
        gas_estimate = CallbackContract.constructor().estimate_gas({'from': account.address})
        print(f"Estimated Gas (Callback): {gas_estimate}")
    except:
        gas_estimate = 2000000

    gas_to_use = min(max_gas_by_balance - 500000, int(gas_estimate * 1.2))
    
    construct_txn = CallbackContract.constructor().build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'chainId': CHAIN_ID,
        'gas': gas_to_use,
        'gasPrice': gas_price
    })

    signed_txn = w3.eth.account.sign_transaction(construct_txn, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    print(f"Transaction sent! Hash: {tx_hash.hex()}")
    
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    callback_address = tx_receipt.contractAddress
    print(f"AgentCallback Deployed at: {callback_address}")

    # Update .env with the callback address
    with open('.env', 'a') as f:
        f.write(f'SOMNIA_CALLBACK_CONTRACT={callback_address}\n')
    print("Updated .env with SOMNIA_CALLBACK_CONTRACT")

if __name__ == "__main__":
    deploy()
