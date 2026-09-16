#!/usr/bin/env python3

import requests
import json
import os

def test_document_analysis():
    """Test the document analysis API with a sample document"""
    
    base_url = "http://localhost:8000/api"
    
    print("🧪 Testing Document Analysis API...")
    
    # Test 1: Health check
    print("\n1. Health Check:")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return
    
    # Test 2: Test document upload (we'll create a simple image)
    print("\n2. Document Upload Test:")
    
    # Create a simple test image using PIL
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # Create a simple test document image
        img = Image.new('RGB', (800, 600), color='white')
        draw = ImageDraw.Draw(img)
        
        # Add some text content
        try:
            # Try to use a default font
            font = ImageFont.load_default()
        except:
            font = None
        
        # Sample financial document content
        text_content = [
            "FINANCIAL REPORT 2024",
            "",
            "Revenue: $1,250,000",
            "Profit: $325,000", 
            "Assets: $2,100,000",
            "Liabilities: $850,000",
            "",
            "Key Metrics:",
            "- Profit Margin: 26%",
            "- ROA: 15.5%",
            "- Current Ratio: 2.47"
        ]
        
        y_position = 50
        for line in text_content:
            draw.text((50, y_position), line, fill='black', font=font)
            y_position += 30
        
        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        # Upload the test document
        files = {'file': ('test_financial_report.png', img_bytes, 'image/png')}
        
        response = requests.post(f"{base_url}/documents/upload", files=files)
        
        print(f"   Upload Status: {response.status_code}")
        if response.status_code == 200:
            upload_result = response.json()
            print(f"   Document ID: {upload_result['document_id']}")
            print(f"   Filename: {upload_result['filename']}")
            print(f"   File Type: {upload_result['file_type']}")
            print(f"   Status: {upload_result['status']}")
            
            document_id = upload_result['document_id']
            
            # Test 3: Document Query
            print("\n3. Document Query Test:")
            
            queries = [
                "What is the total revenue?",
                "What is the profit margin?", 
                "Calculate the debt-to-asset ratio.",
                "What are the key financial metrics mentioned?"
            ]
            
            for i, query in enumerate(queries, 1):
                print(f"\n   Query {i}: {query}")
                
                query_data = {
                    "document_id": document_id,
                    "query_text": query
                }
                
                try:
                    response = requests.post(f"{base_url}/documents/query", json=query_data)
                    print(f"   Status: {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        print(f"   Answer: {result['answer']}")
                        if result.get('evidence'):
                            print(f"   Evidence: {result['evidence']}")
                        if result.get('calculation'):
                            print(f"   Calculation: {result['calculation']}")
                        if result.get('source'):
                            print(f"   Source: {result['source']}")
                    else:
                        print(f"   ❌ Query failed: {response.text}")
                        
                except Exception as e:
                    print(f"   ❌ Query error: {e}")
        else:
            print(f"   ❌ Upload failed: {response.text}")
            return
            
    except Exception as e:
        print(f"   ❌ Test setup failed: {e}")
        return
    
    print("\n✅ Document Analysis API test completed!")

if __name__ == "__main__":
    test_document_analysis()