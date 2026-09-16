"""
Email Service — sends OTP verification emails via Resend API.

Uses the Resend Python SDK for reliable email delivery.
Falls back to console logging when Resend API key is not configured.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger("IRIUM_EMAIL")


def _build_otp_html(otp_code: str, user_name: str = "User") -> str:
    """Build a styled HTML email body for OTP verification."""
    return f"""\
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: 0 auto;
                background: #0f0f1a; border-radius: 16px; overflow: hidden; border: 1px solid #2a2a4a;">

        <!-- Header -->
        <div style="background: linear-gradient(135deg, #6366f1, #8b5cf6); padding: 32px 24px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700; letter-spacing: 1px;">
                ⚡ IRIUM
            </h1>
            <p style="margin: 8px 0 0; color: rgba(255,255,255,0.85); font-size: 14px;">
                AI Financial Research &amp; Multi-Agent Assistant
            </p>
        </div>

        <!-- Body -->
        <div style="padding: 36px 28px; color: #e0e0e0;">
            <p style="font-size: 16px; margin: 0 0 20px;">
                Hello <strong>{user_name}</strong>,
            </p>
            <p style="font-size: 15px; line-height: 1.6; margin: 0 0 28px; color: #b0b0c8;">
                Your email verification code is below. Please enter this 6-digit code
                in the IRIUM app to complete your registration.
            </p>

            <!-- OTP Box -->
            <div style="text-align: center; margin: 0 0 28px;">
                <div style="display: inline-block; background: #1a1a2e; border: 2px solid #6366f1;
                            border-radius: 12px; padding: 18px 40px; letter-spacing: 12px;
                            font-size: 34px; font-weight: 800; color: #a78bfa; font-family: 'Courier New', monospace;">
                    {otp_code}
                </div>
            </div>

            <p style="font-size: 13px; line-height: 1.5; color: #7a7a96; margin: 0 0 8px;">
                This code is valid for a single use. If you did not request this, you can safely ignore this email.
            </p>
        </div>

        <!-- Footer -->
        <div style="background: #0a0a15; padding: 18px 28px; text-align: center;
                    border-top: 1px solid #1e1e38;">
            <p style="margin: 0; font-size: 12px; color: #555570;">
                &copy; 2026 IRIUM &mdash; Intelligent Research &amp; Insights Unified Model
            </p>
        </div>
    </div>
    """


def send_otp_email(
    to_email: str,
    otp_code: str,
    user_name: str = "User",
    subject: str = "IRIUM — Your Email Verification Code",
) -> bool:
    """
    Send an OTP verification email via Resend.

    Returns True if the email was sent (or logged to console), False on error.
    """

    resend_api_key: str = settings.RESEND_API_KEY
    from_email: str = settings.RESEND_FROM_EMAIL

    # ---------- fallback: no Resend API key → console only ----------
    if not resend_api_key or resend_api_key.startswith("re_your"):
        logger.warning("RESEND_API_KEY not configured — printing OTP to console instead.")
        print(f"\n=======================================================")
        print(f"  [IRIUM EMAIL SERVICE] Verification OTP for {to_email}: {otp_code}")
        print(f"=======================================================\n")
        return True

    # ---------- send via Resend ----------
    try:
        import resend

        resend.api_key = resend_api_key

        params: resend.Emails.SendParams = {
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": _build_otp_html(otp_code, user_name),
        }

        email = resend.Emails.send(params)
        logger.info(f"OTP email sent successfully to {to_email} (Resend ID: {email.get('id', 'N/A')})")
        return True

    except Exception as exc:
        logger.error(f"Failed to send OTP email to {to_email} via Resend: {exc}")
        # Fallback to console so the user isn't completely blocked
        print(f"\n[IRIUM EMAIL SERVICE — RESEND FAILED] OTP for {to_email}: {otp_code}\n")
        return False
