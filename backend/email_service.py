import logging
import random
import os
import aiosmtplib
from email.message import EmailMessage

logger = logging.getLogger("prism.email")

async def send_otp_email(to_email: str, name: str) -> str:
    """
    Generate a 6-digit OTP and send it via email using SMTP.
    """
    # Generate a random 6-digit code
    otp_code = str(random.randint(100000, 999999))
    
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    
    if not smtp_server or not smtp_user or not smtp_pass:
        logger.error("Missing SMTP configuration in environment variables!")
        # Fallback to mock if misconfigured temporarily
        logger.info(f"MOCK OTP CODE: [ {otp_code} ]")
        return otp_code

    message = EmailMessage()
    message["From"] = f"Prism AI <{smtp_user}>"
    message["To"] = to_email
    message["Subject"] = "Your Prism AI Verification Code"
    
    content = f"Hi {name},\n\nWelcome to Prism AI! Your registration verification code is:\n\n{otp_code}\n\nThis code will expire in 10 minutes.\n\nThanks,\nThe Prism AI Team"
    message.set_content(content)
    
    logger.info(f"Sending real OTP email to {to_email}...")
    
    try:
        await aiosmtplib.send(
            message,
            hostname=smtp_server,
            port=smtp_port,
            start_tls=True,
            username=smtp_user,
            password=smtp_pass,
        )
        logger.info(f"OTP successfully delivered to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        raise e
        
    return otp_code
