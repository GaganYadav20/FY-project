import os
import json
import uuid
import random
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.core.security import hash_password, verify_password

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CHATS_FILE = os.path.join(DATA_DIR, "chats.json")


def _ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    if not os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def load_users() -> Dict[str, Dict[str, Any]]:
    _ensure_data_dir()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_users(users: Dict[str, Dict[str, Any]]):
    _ensure_data_dir()
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def load_chats() -> Dict[str, List[Dict[str, Any]]]:
    _ensure_data_dir()
    try:
        with open(CHATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_chats(chats: Dict[str, List[Dict[str, Any]]]):
    _ensure_data_dir()
    with open(CHATS_FILE, "w", encoding="utf-8") as f:
        json.dump(chats, f, indent=2)



class UserRepository:
    @staticmethod
    def get_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        users = load_users()
        return users.get(user_id)

    @staticmethod
    def get_by_email(email: str) -> Optional[Dict[str, Any]]:
        users = load_users()
        email_lower = email.strip().lower()
        for user in users.values():
            if user.get("email", "").lower() == email_lower:
                return user
        return None

    @staticmethod
    def get_by_username(username: str) -> Optional[Dict[str, Any]]:
        users = load_users()
        username_lower = username.strip().lower()
        for user in users.values():
            if user.get("username", "").lower() == username_lower:
                return user
        return None

    @staticmethod
    def create_user(username: str, email: str, password: str, full_name: str) -> Dict[str, Any]:
        users = load_users()
        user_id = str(uuid.uuid4())
        hashed_pwd = hash_password(password)
        now_str = datetime.now(timezone.utc).isoformat()

        verification_code = f"{random.randint(100000, 999999)}"

        user_data = {
            "id": user_id,
            "username": username.strip(),
            "email": email.strip().lower(),
            "hashed_password": hashed_pwd,
            "full_name": full_name.strip(),
            "is_verified": False,
            "verification_code": verification_code,
            "created_at": now_str,
        }

        users[user_id] = user_data
        save_users(users)
        return user_data

    @staticmethod
    def verify_email(email: str, code: str) -> bool:
        users = load_users()
        user = UserRepository.get_by_email(email)
        if not user:
            return False
        
        if user.get("verification_code") == code.strip():
            user["is_verified"] = True
            user["verification_code"] = None
            users[user["id"]] = user
            save_users(users)
            return True
        return False

    @staticmethod
    def resend_verification_code(email: str) -> Optional[str]:
        users = load_users()
        user = UserRepository.get_by_email(email)
        if not user:
            return None
        new_code = f"{random.randint(100000, 999999)}"
        user["verification_code"] = new_code
        users[user["id"]] = user
        save_users(users)
        return new_code

    @staticmethod
    def authenticate(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
        identifier = username_or_email.strip().lower()
        user = UserRepository.get_by_email(identifier) or UserRepository.get_by_username(identifier)
        if not user:
            return None
        if verify_password(password, user["hashed_password"]):
            return user
        return None


class ChatRepository:
    @staticmethod
    def get_user_sessions(user_id: str) -> List[Dict[str, Any]]:
        chats = load_chats()
        user_chats = chats.get(user_id, [])
        # Return summary list sorted by updated_at descending
        summaries = []
        for session in user_chats:
            summaries.append({
                "id": session.get("id"),
                "title": session.get("title", "New Chat"),
                "created_at": session.get("created_at", datetime.now(timezone.utc).isoformat()),
                "updated_at": session.get("updated_at", session.get("created_at", datetime.now(timezone.utc).isoformat())),
                "message_count": len(session.get("messages", []))
            })
        summaries.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return summaries

    @staticmethod
    def get_session(user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        chats = load_chats()
        user_chats = chats.get(user_id, [])
        for session in user_chats:
            if session.get("id") == session_id:
                return session
        return None

    @staticmethod
    def save_session(user_id: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        chats = load_chats()
        if user_id not in chats:
            chats[user_id] = []
        
        user_chats = chats[user_id]
        session_id = session_data.get("id") or f"session_{int(datetime.now().timestamp() * 1000)}"
        now_str = datetime.now(timezone.utc).isoformat()
        
        existing_idx = None
        for idx, s in enumerate(user_chats):
            if s.get("id") == session_id:
                existing_idx = idx
                break
        
        formatted_session = {
            "id": session_id,
            "title": session_data.get("title") or "New Chat",
            "created_at": session_data.get("created_at") or now_str,
            "updated_at": now_str,
            "messages": session_data.get("messages", [])
        }
        
        if existing_idx is not None:
            # Preserve original created_at if existing
            formatted_session["created_at"] = user_chats[existing_idx].get("created_at", formatted_session["created_at"])
            user_chats[existing_idx] = formatted_session
        else:
            user_chats.insert(0, formatted_session)
        
        chats[user_id] = user_chats
        save_chats(chats)
        return formatted_session

    @staticmethod
    def append_message(user_id: str, session_id: str, message: Dict[str, Any], title: Optional[str] = None) -> Dict[str, Any]:
        chats = load_chats()
        if user_id not in chats:
            chats[user_id] = []
        
        user_chats = chats[user_id]
        now_str = datetime.now(timezone.utc).isoformat()
        
        # Ensure message has id and created_at
        if not message.get("id"):
            message["id"] = f"msg_{uuid.uuid4().hex[:12]}"
        if not message.get("created_at"):
            message["created_at"] = now_str
        
        target_session = None
        for s in user_chats:
            if s.get("id") == session_id:
                target_session = s
                break
        
        if target_session is None:
            target_session = {
                "id": session_id,
                "title": title or (message.get("text", "")[:30] + "..." if len(message.get("text", "")) > 30 else message.get("text", "New Chat")),
                "created_at": now_str,
                "updated_at": now_str,
                "messages": [message]
            }
            user_chats.insert(0, target_session)
        else:
            if title:
                target_session["title"] = title
            target_session["updated_at"] = now_str
            target_session["messages"].append(message)
            # Move updated session to top
            user_chats.remove(target_session)
            user_chats.insert(0, target_session)
            
        chats[user_id] = user_chats
        save_chats(chats)
        return target_session

