import os
import sys
from pathlib import Path

from mnemonic import Mnemonic
from eth_account import Account

Account.enable_unaudited_hdwallet_features()

# For Solana derivation
import hashlib
import hmac
from base58 import b58encode


# ============================================================
# Configuration
# ============================================================
NUM_ACCOUNTS = 15  # <-- Change this to set the number of iterations

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
CHROME_ACCOUNTS_DIR = CONFIG_DIR / "chrome_accounts"

ACCOUNTS_FILE = CONFIG_DIR / "accounts.py"
AUTO_SIDS_FILE = CONFIG_DIR / "auto_sids.py"


def generate_mnemonic(strength: int = 256) -> str:
    """Generate a BIP39 mnemonic (seed phrase)."""
    m = Mnemonic("english")
    return m.generate(strength=strength)


def derive_evm_address(mnemonic: str) -> str:
    """Derive EVM (Ethereum) address from mnemonic using BIP44 path m/44'/60'/0'/0/0."""
    account = Account.from_mnemonic(mnemonic)
    return account.address


def derive_solana_address(mnemonic: str) -> str:
    """Derive Solana address from mnemonic using BIP44 path m/44'/501'/0'/0'.

    Solana uses Ed25519 curve which requires special handling.
    We derive the seed from mnemonic and then use SLIP-0010 derivation.
    """
    from nacl.signing import SigningKey

    # Generate seed from mnemonic (BIP39)
    seed = Mnemonic("english").to_seed(mnemonic)

    # SLIP-0010 master key generation for Ed25519
    I = hmac.new(b"ed25519 seed", seed, hashlib.sha512).digest()
    master_key = I[:32]
    chain_code = I[32:]

    def derive_ed25519_child(key, chain_code, index):
        """Derive a child key using hardened derivation for Ed25519."""
        hardened_index = index + 0x80000000
        data = b"\x00" + key + hardened_index.to_bytes(4, "big")
        I = hmac.new(chain_code, data, hashlib.sha512).digest()
        return I[:32], I[32:]

    current_key = master_key
    current_chain = chain_code

    path_indices = [44, 501, 0, 0]
    for idx in path_indices:
        current_key, current_chain = derive_ed25519_child(
            current_key, current_chain, idx
        )

    signing_key = SigningKey(current_key)
    public_key_bytes = signing_key.verify_key.encode()
    return b58encode(public_key_bytes).decode()


def create_account_directory(account_name: str) -> Path:
    """Create a directory for the chrome account."""
    account_dir = CHROME_ACCOUNTS_DIR / account_name
    account_dir.mkdir(parents=True, exist_ok=True)
    return account_dir


def get_start_index():
    """Read existing accounts and return the next index."""
    if not ACCOUNTS_FILE.exists():
        return 1

    existing_accounts = {}
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        local_vars = {}
        exec(content, {}, local_vars)
        existing_accounts = local_vars.get("accounts", ())
    except Exception as e:
        print(f"Warning: Could not read existing accounts: {e}")
        return 1

    if not existing_accounts:
        return 1

    max_index = 0
    for acc in existing_accounts:
        name = acc.get("name", "")
        if name.startswith("auto_"):
            try:
                num = int(name[5:])
                if num > max_index:
                    max_index = num
            except ValueError:
                continue

    return max_index + 1


def get_existing_sids():
    """Read existing SIDs from auto_sids.py."""
    if not AUTO_SIDS_FILE.exists():
        return {}

    try:
        with open(AUTO_SIDS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        local_vars = {}
        exec(content, {}, local_vars)
        return local_vars.get("accounts", {})
    except Exception as e:
        print(f"Warning: Could not read existing SIDs: {e}")
        return {}


def get_existing_accounts():
    """Read existing accounts from accounts.py."""
    if not ACCOUNTS_FILE.exists():
        return []

    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        local_vars = {}
        exec(content, {}, local_vars)
        return list(local_vars.get("accounts", ()))
    except Exception as e:
        print(f"Warning: Could not read existing accounts: {e}")
        return []


def format_account_name(index: int) -> str:
    """Format account name with zero-padded number: 001, 002, ..., 010, ..., 100, ..."""
    return f"auto_{index:03d}"


def generate_accounts(num_accounts: int):
    """Generate accounts with seed phrases, EVM and Solana addresses, continuing from existing ones."""
    start_index = get_start_index()
    existing_accounts = get_existing_accounts()
    existing_sids = get_existing_sids()

    accounts_list = list(existing_accounts)
    sids_dict = dict(existing_sids)

    base_port = 9330

    for i in range(start_index, start_index + num_accounts):
        account_name = format_account_name(i)
        mnemonic = generate_mnemonic()

        evm_address = derive_evm_address(mnemonic)
        solana_address = derive_solana_address(mnemonic)

        account_dir = create_account_directory(account_name)

        port = base_port + i
        account = {
            "status": "active",
            "name": account_name,
            "id": account_name,
            "wallet_password": "asdfj*KK",
            "email": "",
            "solana": solana_address,
            "evm": evm_address,
            "profile_directory": f"{account_name}",
            "debugging_port": port,
        }
        accounts_list.append(account)
        sids_dict[account_name] = mnemonic

        print(f"[{i - start_index + 1}/{num_accounts}] Created {account_name}")
        print(f"  EVM: {evm_address}")
        print(f"  SOL: {solana_address}")
        print(f"  SID: {mnemonic}")
        print(f"  Dir: {account_dir}")
        print()

    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        f.write("accounts = (\n")
        for acc in accounts_list:
            f.write("    {\n")
            for key, value in acc.items():
                f.write(f"        '{key}': {repr(value)},\n")
            f.write("    },\n")
        f.write(")\n")

    with open(AUTO_SIDS_FILE, "w", encoding="utf-8") as f:
        f.write("accounts = {\n")
        for name, sid in sids_dict.items():
            f.write(f"    '{name}': '{sid}',\n")
        f.write("}\n")

    print(f"Added {num_accounts} accounts (starting from index {start_index})")
    print(f"Total accounts: {len(accounts_list)}")
    print(f"Accounts saved to: {ACCOUNTS_FILE}")
    print(f"Seed phrases saved to: {AUTO_SIDS_FILE}")


if __name__ == "__main__":
    generate_accounts(NUM_ACCOUNTS)
