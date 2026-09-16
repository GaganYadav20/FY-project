from fastapi.testclient import TestClient
from app.main import app
from app.database.db import UserRepository, ChatRepository

def run_tests():
    client = TestClient(app)

    # 1. Create and verify test user
    username = "history_tester"
    email = "history_tester@example.com"
    pwd = "TesterPassword123!"
    
    existing = UserRepository.get_by_email(email)
    if not existing:
        user = UserRepository.create_user(username, email, pwd, "History Tester")
        UserRepository.verify_email(email, user["verification_code"])
    else:
        user = existing

    # 2. Log in
    login_res = client.post("/api/auth/login", json={"username_or_email": email, "password": pwd})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Post a query
    q1_res = client.post("/api/chat/query", json={"query": "Hello IRIUM assistant"}, headers=headers)
    assert q1_res.status_code == 200, f"Query 1 failed: {q1_res.text}"
    s_id1 = q1_res.json()["session_id"]
    assert s_id1, "session_id was not returned"

    # 4. Post follow up query in same session
    q2_res = client.post("/api/chat/query", json={"query": "What is the PE ratio of Apple?", "session_id": s_id1}, headers=headers)
    assert q2_res.status_code == 200, f"Query 2 failed: {q2_res.text}"

    # 5. Fetch sessions
    sessions_res = client.get("/api/chat/sessions", headers=headers)
    assert sessions_res.status_code == 200, f"Get sessions failed: {sessions_res.text}"
    sessions = sessions_res.json()
    assert len(sessions) >= 1, "Expected at least 1 session"
    print(f"[OK] Found {len(sessions)} chat session(s) in backend.")

    # 6. Fetch specific session details
    detail_res = client.get(f"/api/chat/sessions/{s_id1}", headers=headers)
    assert detail_res.status_code == 200, f"Get session detail failed: {detail_res.text}"
    detail = detail_res.json()
    assert len(detail["messages"]) >= 4, f"Expected at least 4 messages, got {len(detail['messages'])}"
    print(f"[OK] Session messages retrieved: {len(detail['messages'])} messages.")

    # 7. Check persistence directly in ChatRepository
    persisted = ChatRepository.get_user_sessions(user["id"])
    assert len(persisted) >= 1, "Persisted sessions should exist in DB"
    print(f"[OK] Database persistence verified: {len(persisted)} session(s) retained.")

    # 8. Simulate fresh login
    login_res2 = client.post("/api/auth/login", json={"username_or_email": email, "password": pwd})
    assert login_res2.status_code == 200
    token2 = login_res2.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    restored_res = client.get("/api/chat/sessions", headers=headers2)
    assert restored_res.status_code == 200
    restored_sessions = restored_res.json()
    assert len(restored_sessions) >= 1
    print(f"[OK] Re-login history restoration verified: {len(restored_sessions)} session(s) restored.")

    print("\nSUCCESS: All chat history tests passed cleanly!")

if __name__ == "__main__":
    run_tests()
