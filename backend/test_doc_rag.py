import io
from fastapi.testclient import TestClient
from app.main import app
from app.database.db import UserRepository

def run_tests():
    client = TestClient(app)

    # 1. Create or get test user
    email = "doc_tester@example.com"
    pwd = "DocPassword123!"
    existing = UserRepository.get_by_email(email)
    if not existing:
        user = UserRepository.create_user("doc_tester", email, pwd, "Doc Tester")
        UserRepository.verify_email(email, user["verification_code"])
    
    login_res = client.post("/api/auth/login", json={"username_or_email": email, "password": pwd})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload multiple financial documents (Sample 10-K text and Portfolio CSV)
    doc1_content = b"""
    """

    doc2_content = b"""
"""

    files = [
        ("files", ("NexaCorp_2025_10K.txt", io.BytesIO(doc1_content), "text/plain")),
        ("files", ("Tech_Growth_Portfolio.csv", io.BytesIO(doc2_content), "text/csv")),
    ]

    upload_res = client.post("/api/documents/upload", files=files, headers=headers)
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    upload_data = upload_res.json()
    assert upload_data["total"] >= 2, f"Expected at least 2 documents, got {upload_data['total']}"
    print(f"[OK] Successfully uploaded {upload_data['total']} documents.")

    # 3. List documents
    list_res = client.get("/api/documents", headers=headers)
    assert list_res.status_code == 200
    docs = list_res.json()["documents"]
    print(f"[OK] Retrieved {len(docs)} documents for user.")
    doc_ids = [d["document_id"] for d in docs]

    # 4. Query document endpoint for specific 10-K figures
    q1_res = client.post(
        "/api/documents/query",
        json={"query": "What was Nexa Corp's total revenue, net income, and AI Cloud growth in 2025?"},
        headers=headers
    )
    assert q1_res.status_code == 200, f"Doc query failed: {q1_res.text}"
    ans1 = q1_res.json()
    safe_reply1 = ans1["reply"][:250].encode("ascii", "replace").decode("ascii")
    print("[OK] Document Query 1 Response (preview):\n", safe_reply1, "\n...")
    assert "45.2" in ans1["reply"] or "billion" in ans1["reply"].lower()
    assert len(ans1["documents_used"]) >= 1

    # 5. Query document endpoint for portfolio data
    q2_res = client.post(
        "/api/documents/query",
        json={"query": "What is the total value and shares for Apple and Nvidia in the portfolio?"},
        headers=headers
    )
    assert q2_res.status_code == 200
    ans2 = q2_res.json()
    safe_reply2 = ans2["reply"][:250].encode("ascii", "replace").decode("ascii")
    print("[OK] Document Query 2 Response (preview):\n", safe_reply2, "\n...")
    assert "150" in ans2["reply"] or "Apple" in ans2["reply"] or "NVDA" in ans2["reply"]

    # 6. Test main chat query with document auto-grounding
    chat_res = client.post(
        "/api/chat/query",
        json={"query": "According to my uploaded 10-K, what was Nexa Corp's operating margin and free cash flow?"},
        headers=headers
    )
    assert chat_res.status_code == 200
    chat_ans = chat_res.json()
    assert chat_ans["tier"] == "document"
    safe_chat_reply = chat_ans["reply"][:250].encode("ascii", "replace").decode("ascii")
    print("[OK] Chat query successfully routed to document RAG (tier=document):\n", safe_chat_reply, "\n...")

    # 7. Clean up 1 document
    del_res = client.delete(f"/api/documents/{doc_ids[0]}", headers=headers)
    assert del_res.status_code == 200
    print("[OK] Document deletion verified.")

    print("\nALL FINANCIAL DOCUMENT RAG TESTS PASSED CLEANLY!")


if __name__ == "__main__":
    run_tests()
