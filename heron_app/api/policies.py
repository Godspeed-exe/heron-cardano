from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from heron_app.schemas.policy import CreatePolicyRequest, PolicyResponse
from heron_app.db.models.minting_policies import MintingPolicy
from heron_app.db.database import SessionLocal
from cryptography.fernet import Fernet
import os
from heron_app.utils.cardano import generate_policy

router = APIRouter()

@router.post("/", 
            summary="Create a new minting policy",
            description="Creates a new minting policy with a specified name and lock date. The policy ID and secret key are generated and stored securely.",
            status_code=201,
            responses={
                201: {
                    "description": "Policy created successfully",
                    "content": {
                        "application/json": {
                            "example": {
                                "name": "My Minting Policy",
                                "policy_id": "policy1xyz...",
                                "locking_slot": 123456,
                                "created_at": "2023-10-01T12:00:00Z"
                            }
                        }
                    }
                },
                400: {
                    "description": "Bad request, policy name already exists",
                    "content": {
                        "application/json": {
                            "example": {
                                "detail": "Policy name already exists"
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
            },
            response_model=PolicyResponse
        )
def create_policy(request: CreatePolicyRequest):
    session = SessionLocal()
    if session.query(MintingPolicy).filter_by(name=request.name).first():
        raise HTTPException(status_code=400, detail="Policy name already exists")

    policy_id, skey, locking_slot = generate_policy(request.lock_date)
    fernet = Fernet(os.environ["WALLET_ENCRYPTION_KEY"])

    print(f"Generated policy ID: {policy_id}")
    print(f"Generated secret key: {skey}")
    encrypted_key = fernet.encrypt(skey.encode())

    new_policy = MintingPolicy(
        name=request.name,
        policy_id=policy_id,
        encrypted_policy_skey=encrypted_key.decode("utf-8"),
        locking_slot=locking_slot
    )
    session.add(new_policy)
    session.commit()
    session.refresh(new_policy)

    return PolicyResponse(
        name=new_policy.name,
        policy_id=new_policy.policy_id,
        locking_slot=new_policy.locking_slot,
        created_at=new_policy.created_at
    )

@router.get("/", 
            summary="List all minting policies",
            description="Retrieves a list of all minting policies stored in the database, including their names, IDs, locking slots, and creation dates.",
            status_code=200,
            responses={
                200: {
                    "description": "List of policies retrieved successfully",
                    "content": {
                        "application/json": {
                            "example": [
                                {
                                    "name": "My Minting Policy",
                                    "policy_id": "policy1xyz...",
                                    "locking_slot": 123456,
                                    "created_at": "2023-10-01T12:00:00Z"
                                }
                            ]
                        }
                    }
                },
                422: {
                    "description": "Validation error, e.g., invalid policy ID format",
                    "content": {
                        "application/json": {
                            "example": {
                                "detail": "Validation error message"
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
            },
            response_model=list[PolicyResponse]
            )
def list_policies():
    session = SessionLocal()
    return [
        PolicyResponse(
            name=p.name,
            policy_id=p.policy_id,
            locking_slot=p.locking_slot,
            created_at=p.created_at
        )
        for p in session.query(MintingPolicy).all()
    ]