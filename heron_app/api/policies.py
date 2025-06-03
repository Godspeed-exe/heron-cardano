from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from heron_app.schemas.policy import CreatePolicyRequest, PolicyResponse
from heron_app.db.models.minting_policies import MintingPolicy
from heron_app.db.database import SessionLocal
from cryptography.fernet import Fernet
import os
from heron_app.utils.cardano import generate_policy

router = APIRouter()

@router.post("/", response_model=PolicyResponse)
def create_policy(request: CreatePolicyRequest):
    session = SessionLocal()
    if session.query(MintingPolicy).filter_by(name=request.name).first():
        raise HTTPException(status_code=400, detail="Policy name already exists")

    policy_id, skey, locking_slot = generate_policy(request.lock_date)
    fernet = Fernet(os.environ["WALLET_ENCRYPTION_KEY"])
    encrypted_key = fernet.encrypt(skey.encode())

    new_policy = MintingPolicy(
        name=request.name,
        policy_id=policy_id,
        encrypted_policy_skey=encrypted_key.decode(),
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

@router.get("/", response_model=list[PolicyResponse])
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