import base64
import io
from fastapi.testclient import TestClient
from app.main import app
from app.database.db import UserRepository

def run_tests():
    client = TestClient(app)

    # 1. Login user
    email = "doc_tester@example.com"
    pwd = "DocPassword123!"
    login_res = client.post("/api/auth/login", json={"username_or_email": email, "password": pwd})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Prepare sample PDF as base64
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "MICROSOFT CORP - Q3 FINANCIAL REPORT\nQuarterly Revenue: $61.9 Billion (Up 17% YoY)\nAzure & Cloud Revenue: $26.7 Billion (Up 31% YoY)\nNet Income: $21.9 Billion\nDiluted EPS: $2.94", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    # 3. Test sending in-chat query with PDF attachment
    session_id = f"test_session_{int(1000)}"
    req_payload = {
        "query": "What is the quarterly revenue and Azure growth in this attached report?",
        "session_id": session_id,
        "attachments": [
            {
                "name": "MSFT_Q3_Report.pdf",
                "type": "application/pdf",
                "data": f"data:application/pdf;base64,{b64_pdf}",
                "size": len(pdf_bytes)
            }
        ]
    }

    res = client.post("/api/chat/query", json=req_payload, headers=headers)
    assert res.status_code == 200, f"Query failed: {res.text}"
    data = res.json()
    assert data["tier"] == "attachment"
    safe_reply = data["reply"].encode("ascii", "replace").decode("ascii")
    print("[OK] In-Chat PDF Attachment Response:\n", safe_reply[:300], "\n...")
    assert "61.9" in data["reply"] or "Azure" in data["reply"] or "Microsoft" in data["reply"]

    # 4. Verify message persistence with attachments in session history
    session_res = client.get(f"/api/chat/sessions/{session_id}", headers=headers)
    assert session_res.status_code == 200
    session_data = session_res.json()
    user_msg = session_data["messages"][0]
    assert user_msg["sender"] == "user"
    assert user_msg["attachments"] is not None
    assert user_msg["attachments"][0]["name"] == "MSFT_Q3_Report.pdf"
    print("[OK] Session history preserved attached file metadata correctly.")

    print("\nALL IN-CHAT ATTACHMENT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
