from fastapi import APIRouter, HTTPException, Path  # type: ignore
from uuid import uuid4
from datetime import datetime
import os
from cryptography.fernet import Fernet
from pycardano import crypto, ExtendedSigningKey, Address, Network
from blockfrost import ApiUrls
from sqlalchemy.exc import IntegrityError # type: ignore
import psycopg2 # type: ignore

from heron_app.schemas.wallet import WalletCreate
from heron_app.db.database import SessionLocal
from heron_app.db.models.wallet import Wallet
from heron_app.utils.cardano import get_balance
from heron_app.workers.start_wallet_worker import start_worker

router = APIRouter()

@router.post("/")
def create_wallet(data: WalletCreate):
    session = SessionLocal()
    try:
        network = os.getenv('network')
        base_url = ApiUrls.preprod.value if network == "testnet" else ApiUrls.mainnet.value
        cardano_network = Network.TESTNET if network == "testnet" else Network.MAINNET

        root_key = crypto.bip32.HDWallet.from_mnemonic(data.mnemonic)
        payment_key = root_key.derive_from_path("m/1852'/1815'/0'/0/0")
        staking_key = root_key.derive_from_path("m/1852'/1815'/0'/2/0")
        payment_skey = ExtendedSigningKey.from_hdwallet(payment_key)
        staking_skey = ExtendedSigningKey.from_hdwallet(staking_key)

        address = Address(
            payment_part=payment_skey.to_verification_key().hash(),
            staking_part=staking_skey.to_verification_key().hash(),
            network=cardano_network
        )

        fernet = Fernet(os.environ["WALLET_ENCRYPTION_KEY"])
        encrypted_key = fernet.encrypt(data.mnemonic.encode())

        wallet_record = Wallet(
            id=str(uuid4()),
            name=data.name,
            address=str(address),
            encrypted_root_key=encrypted_key.decode(),
            created_at=datetime.utcnow()
        )
        session.add(wallet_record)
        session.commit()

        start_worker(wallet_record.id)

        return {"id": wallet_record.id, "address": wallet_record.address}

    except IntegrityError as e:
        session.rollback()
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            raise HTTPException(status_code=400, detail="A wallet with this address already exists.")
        raise HTTPException(status_code=500, detail="Database integrity error.")
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@router.get("/")
def list_wallets():
    session = SessionLocal()
    try:
        return [
            {"id": w.id, "name": w.name, "address": w.address, "created_at": w.created_at}
            for w in session.query(Wallet).all()
        ]
    finally:
        session.close()

@router.get("/{wallet_id}")
def get_wallet(wallet_id: str):
    session = SessionLocal()
    try:
        wallet = session.query(Wallet).filter(Wallet.id == wallet_id).first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        balance = get_balance(wallet.address)
        return {
            "id": wallet.id,
            "name": wallet.name,
            "address": wallet.address,
            "balance": balance,
            "created_at": wallet.created_at
        }
    finally:
        session.close()

@router.delete("/wallets/{wallet_id}", status_code=204)
def delete_wallet(wallet_id: str = Path(..., description="UUID of the wallet to delete")):
    session = SessionLocal()
    try:
        wallet = session.query(Wallet).filter(Wallet.id == wallet_id).first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        session.delete(wallet)
        session.commit()
    except HTTPException:
        raise  # re-raise cleanly
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
