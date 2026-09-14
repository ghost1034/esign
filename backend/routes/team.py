"""Standalone account and organization management."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from core.database import get_db
from dependencies.auth import verify_firebase_token
from models.db_models import User, Firm, UserRole
from services.team_scope import ensure_user_row, get_user_firm
from services import team_service
from services.esign.admin_service import esign_admin_service
from services.rate_limit import rate_limiter

router = APIRouter(prefix="/api/team", tags=["team"])
account_router = APIRouter(prefix="/api/account", tags=["account"])

class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
class TeamJoin(BaseModel):
    code: str = Field(min_length=6, max_length=6)
class MemberUpdate(BaseModel):
    role: Literal["admin", "member"]
class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    photo_url: str | None = Field(default=None, max_length=2000)

def profile(db, token):
    return ensure_user_row(db, user_id=token["uid"], email=token["email"], display_name=token.get("name"), photo_url=token.get("picture"))

def member_json(user):
    return {"user_id": user.id, "email": user.email, "display_name": user.display_name,
            "photo_url": user.photo_url, "role": "admin" if user.role == UserRole.ADMIN else "member",
            "title": user.title, "created_at": user.created_at}

def current(db, token, admin=False):
    profile(db, token)
    user, firm = get_user_firm(db, token["uid"])
    # Serialize membership mutations, including last-administrator checks.
    db.query(Firm).filter(Firm.id == firm.id).with_for_update().one()
    db.refresh(user)
    if user.firm_id != firm.id: raise HTTPException(403, "Organization membership changed")
    if admin and user.role != UserRole.ADMIN: raise HTTPException(403, "Organization administrator required")
    return user, firm

def detail(db, firm, admin):
    return {"firm": {"id": str(firm.id), "name": firm.name},
            "members": [member_json(u) for u in team_service.list_members(db, firm.id)],
            "invite_code": team_service.get_invite_code(db, firm.id) if admin else None}

@router.get("/onboarding-status")
def onboarding(token=Depends(verify_firebase_token), db: Session=Depends(get_db)):
    user = profile(db, token)
    return {"needs_onboarding": user.firm_id is None}

@router.get("")
def get_team(token=Depends(verify_firebase_token), db: Session=Depends(get_db)):
    user, firm = current(db, token)
    return detail(db, firm, user.role == UserRole.ADMIN)

@router.post("/create")
def create(payload: TeamCreate, token=Depends(verify_firebase_token), db: Session=Depends(get_db)):
    user = profile(db, token)
    db.query(User).filter(User.id == user.id).with_for_update().one()
    db.refresh(user)
    firm, _ = team_service.create_firm_for_user(db, user, payload.name.strip())
    esign_admin_service._ensure_defaults(db, firm.id); db.commit()
    return detail(db, firm, True)

@router.post("/join")
def join(payload: TeamJoin, token=Depends(verify_firebase_token), db: Session=Depends(get_db)):
    if not rate_limiter.check("team-join", token["uid"], 10, 3600): raise HTTPException(429, "Too many attempts")
    user = profile(db, token)
    db.query(User).filter(User.id == user.id).with_for_update().one()
    db.refresh(user)
    firm = team_service.join_firm_by_code(db, user, payload.code)
    esign_admin_service._ensure_defaults(db, firm.id); db.commit()
    return detail(db, firm, user.role == UserRole.ADMIN)

@router.put("")
def rename(payload: TeamCreate, token=Depends(verify_firebase_token), db: Session=Depends(get_db)):
    _, firm = current(db, token, True)
    team_service.update_firm_name(db, firm.id, payload.name.strip())
    return detail(db, firm, True)

@router.post("/invite-code")
def rotate(token=Depends(verify_firebase_token), db: Session=Depends(get_db)):
    _, firm = current(db, token, True)
    return {"invite_code": team_service.generate_invite_code(db, firm.id)}

@router.put("/members/{user_id}")
def update_member(user_id: str, payload: MemberUpdate, token=Depends(verify_firebase_token), db: Session=Depends(get_db)):
    actor, firm = current(db, token, True)
    # Audit is committed with the membership change.
    esign_admin_service._audit(db, actor, "member.role_changed", "user", user_id, {"role": payload.role})
    user = team_service.update_member(db, firm.id, user_id, role="admin" if payload.role == "admin" else "analyst", persona=None, title=None, set_role=True, set_persona=False, set_title=False)
    return member_json(user)

@router.delete("/members/{user_id}")
def remove(user_id: str, successor_user_id: str | None=None, token=Depends(verify_firebase_token), db: Session=Depends(get_db)):
    actor, firm = current(db, token, True)
    team_service.remove_member(db, firm.id, user_id, successor_user_id=successor_user_id, actor_user_id=actor.id)
    return {"success": True}

@account_router.get("")
def get_account(token=Depends(verify_firebase_token), db: Session=Depends(get_db)):
    return member_json(profile(db, token))

@account_router.put("")
def update_account(payload: ProfileUpdate, token=Depends(verify_firebase_token), db: Session=Depends(get_db)):
    user = profile(db, token)
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(user, key, value)
    db.commit(); return member_json(user)

@account_router.post("/sync")
def sync(token=Depends(verify_firebase_token), db: Session=Depends(get_db)):
    return member_json(profile(db, token))

@account_router.get("/phone-availability")
def phone_availability(phone_number: str, token=Depends(verify_firebase_token), db: Session=Depends(get_db)):
    return {"available": not db.query(User).filter(User.phone_number == phone_number, User.id != token["uid"]).first()}
