from fastapi import APIRouter, HTTPException, Path  # type: ignore
from uuid import uuid4, UUID
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

BLOCKFROST_API_KEY = os.getenv("BLOCKFROST_PROJECT_ID")
network =  BLOCKFROST_API_KEY[:7].lower()


@router.post("/",
    summary="Load a new wallet",
    description="Loads and stores a new Cardano wallet from a 24-word mnemonic. The mnemonic is encrypted and the wallet address is derived from the root key.",
    tags=["Wallets"],
    responses={
        200: {
            "description": "Wallet created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "address": "addr1q..."
                    }
                }
            }
        },
        400: {
            "description": "Bad request, e.g., duplicate wallet address",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "A wallet with this address already exists."
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    }
    )
def create_wallet(data: WalletCreate):
    session = SessionLocal()
    try:

        cardano_network = Network.MAINNET if network == "mainnet" else Network.TESTNET
        

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

@router.get("/",
    summary="List all available wallets",
    description="Shows a list of all wallets stored in the database, including their IDs, names, addresses, and creation dates.",
    tags=["Wallets"],
    responses={
        200: {
            "description": "List of wallets retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "name": "My Wallet",
                            "address": "addr1q...",
                            "created_at": "2023-10-01T12:00:00Z"
                        }
                    ]
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    }
    )
def list_wallets():
    session = SessionLocal()
    try:
        return [
            {"id": w.id, "name": w.name, "address": w.address, "created_at": w.created_at}
            for w in session.query(Wallet).all()
        ]
    finally:
        session.close()

@router.get("/{wallet_id}",
    summary="Get wallet details",
    description="Retrieves detailed information about a specific wallet by its ID, including its name, address, balance, and creation date.",
    tags=["Wallets"],
    responses={
        200: {
            "description": "Wallet details retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "My Wallet",
                        "address": "addr1q...",
                        "balance": 1000.0,
                        "created_at": "2023-10-01T12:00:00Z"
                    }
                }
            }
        },
        404: {
            "description": "Wallet not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Wallet not found"
                    }
                }
            }
        },
        422: {
            "description": "Validation error, e.g., invalid wallet ID format",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid wallet ID format"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    }
    )
def get_wallet(wallet_id: str):
    session = SessionLocal()
    try:

        if not wallet_id or len(wallet_id) != 36:
            raise HTTPException(status_code=422, detail="Invalid wallet ID format")
        # Validate UUID format
        try:
            UUID(wallet_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid wallet ID format")
        

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
    except HTTPException:
        raise  # re-raise cleanly
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@router.delete("/wallets/{wallet_id}", 
                status_code=204,
                summary="Delete a wallet",
                description="Deletes a wallet from the database by its ID. This action is irreversible and will remove all associated data.",
                tags=["Wallets"],
                responses={
                    204: {"description": "Wallet deleted successfully"},
                    404: {"description": "Wallet not found"},
                    422: {"description": "Validation error, e.g., invalid wallet ID format"},
                    500: {"description": "Internal server error"}
                }
                )
def delete_wallet(wallet_id: str = Path(..., description="UUID of the wallet to delete")):
    session = SessionLocal()
    try:

        if not wallet_id or len(wallet_id) != 36:
            raise HTTPException(status_code=422, detail="Invalid wallet ID format")
        # Validate UUID format
        try:
            UUID(wallet_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid wallet ID format")
        
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

@router.post(
    "/generate",
    summary="Generate mnemonic",
    description="Generates a new random 24-word BIP-39 mnemonic.",
    tags=["Wallets"],
    responses={
        200: {
            "description": "A new 24-word mnemonic",
            "content": {
                "application/json": {
                    "example": {
                        "mnemonic": "sword lottery inch lens smart remember february ..."
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to generate mnemonic: <error message>"
                    }
                }
            }
        }
    }
)
def generate_mnemonic():
    try:
        mnemonic = crypto.bip32.HDWallet.generate_mnemonic()
        return {"mnemonic": mnemonic}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate mnemonic: {str(e)}")