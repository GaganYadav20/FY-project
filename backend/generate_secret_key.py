"""
Generate a cryptographically secure SECRET_KEY for JWT tokens.
Run this script to generate a new secure key.
"""

import secrets
import string

def generate_secret_key(length: int = 64) -> str:
    """
    Generate a cryptographically secure random string.
    
    Args:
        length: Length of the key (default: 64)
        
    Returns:
        Secure random string
    """
    # Use secrets module for cryptographically strong random numbers
    alphabet = string.ascii_letters + string.digits + string.punctuation
    
    # Remove characters that might cause issues in .env files
    safe_alphabet = alphabet.replace('"', '').replace("'", '').replace('\\', '').replace('`', '')
    
    key = ''.join(secrets.choice(safe_alphabet) for _ in range(length))
    return key


def generate_multiple_keys():
    """Generate multiple keys for different purposes."""
    print("=" * 70)
    print("SECURE KEY GENERATOR - IRIUM Multi-Agent Research System")
    print("=" * 70)
    print()
    
    # Generate SECRET_KEY for JWT
    secret_key = generate_secret_key(64)
    print("1. SECRET_KEY (for JWT tokens):")
    print(f"   {secret_key}")
    print()
    
    # Generate database encryption key (optional)
    db_key = generate_secret_key(32)
    print("2. DATABASE_ENCRYPTION_KEY (optional, for encrypting sensitive data):")
    print(f"   {db_key}")
    print()
    
    # Generate API key for internal services (optional)
    api_key = generate_secret_key(48)
    print("3. INTERNAL_API_KEY (optional, for internal service auth):")
    print(f"   {api_key}")
    print()
    
    print("=" * 70)
    print("USAGE INSTRUCTIONS:")
    print("=" * 70)
    print()
    print("1. Copy the SECRET_KEY above")
    print("2. Open backend/.env file")
    print("3. Replace the current SECRET_KEY value with the new one")
    print()
    print("Example in .env file:")
    print(f'SECRET_KEY={secret_key}')
    print()
    print("⚠️  IMPORTANT:")
    print("   - Never commit this key to Git")
    print("   - Use different keys for dev/staging/production")
    print("   - Rotate keys every 90 days")
    print("   - Store production key in secure vault (AWS Secrets Manager, etc.)")
    print()
    print("=" * 70)


if __name__ == "__main__":
    generate_multiple_keys()
