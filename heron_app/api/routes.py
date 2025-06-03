from fastapi import APIRouter  # type: ignore
from heron_app.api.wallets import router as wallet_router
from heron_app.api.transactions import router as tx_router
from heron_app.api.policies import router as policy_router


router = APIRouter()

router.include_router(wallet_router, prefix="/wallets", tags=["wallets"])
router.include_router(tx_router, prefix="/transactions", tags=["transactions"])
router.include_router(policy_router, prefix="/policies", tags=["policies"])