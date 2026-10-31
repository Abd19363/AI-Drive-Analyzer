import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)


def _send_smtp_email(to_email: str, subject: str, text_body: str, html_body: str = None) -> bool:
    """Send an email via SMTP if configured, otherwise fallback to logging."""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.info(
            "\n[ADMIN NOTIFICATION EMAIL (SMTP Not Configured - Logging Simulation)]\n"
            "To: %s\nSubject: %s\nBody:\n%s\n",
            to_email,
            subject,
            text_body,
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
        msg["To"] = to_email

        part1 = MIMEText(text_body, "plain")
        msg.attach(part1)

        if html_body:
            part2 = MIMEText(html_body, "html")
            msg.attach(part2)

        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        if settings.SMTP_PORT == 587:
            server.starttls()
        if settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(msg["From"], [to_email], msg.as_string())
        server.quit()
        logger.info("[EMAIL SENT] Successfully sent notification to %s", to_email)
        return True
    except Exception as e:
        logger.warning("[EMAIL ERROR] Failed to send email via SMTP to %s: %s", to_email, e)
        return False


async def notify_super_admin_of_registration(
    applicant_name: str,
    applicant_email: str,
    super_admin_email: str,
    request_note: str = None
) -> bool:
    """Notify the main admin (developer) that a new user requested admin registration."""
    if not super_admin_email:
        logger.warning("[ADMIN NOTIFY] No Super Admin email found to send registration request notification.")
        return False

    subject = f"[AI-Drive Analyzer] Action Required: New Admin Registration Request from {applicant_name}"
    req_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    text_body = f"""Hello Lead Admin,

A user has requested registration as a User Admin on the AI-Drive Analyzer platform:

  • Applicant Name: {applicant_name}
  • Applicant Email: {applicant_email}
  • Request Date: {req_time}
  • Reason for Access: {request_note or 'No specific note provided'}

Security Policy Reminder:
User Admins will only be permitted to view query audit records (queries asked, files referenced, and files analyzed) scoped to their account. They will NOT have access to Lead Admin technical telemetry, other users' queries, or confidential system configurations.

To Approve or Reject this request, please log in to your Lead Admin Dashboard:
{settings.FRONTEND_URL}?portal=admin

Best regards,
AI-Drive Analyzer Security & Access Gateway
"""

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
      <h2 style="color: #1e3a8a; margin-top: 0;">New User Admin Access Request</h2>
      <p style="color: #475569; font-size: 14px;">A user has submitted an access request for the User Admin portal:</p>
      
      <table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px;">
        <tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 8px 0; color: #64748b; font-weight: bold; width: 140px;">Applicant Name:</td>
          <td style="padding: 8px 0; color: #0f172a;">{applicant_name}</td>
        </tr>
        <tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 8px 0; color: #64748b; font-weight: bold;">Applicant Email:</td>
          <td style="padding: 8px 0; color: #0f172a;"><strong>{applicant_email}</strong></td>
        </tr>
        <tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 8px 0; color: #64748b; font-weight: bold;">Request Time:</td>
          <td style="padding: 8px 0; color: #0f172a;">{req_time}</td>
        </tr>
        <tr>
          <td style="padding: 8px 0; color: #64748b; font-weight: bold;">Reason for Access:</td>
          <td style="padding: 8px 0; color: #0f172a;">{request_note or 'No note provided'}</td>
        </tr>
      </table>

      <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px; margin: 20px 0; font-size: 12px; color: #475569;">
        <strong>Privacy Isolation:</strong> User Admins can only view query activity records scoped to their account. They cannot view system technical metrics or other users' private queries.
      </div>

      <p style="margin-top: 24px;">
        <a href="{settings.FRONTEND_URL}?portal=admin" style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: bold;">
          Review & Approve in Lead Admin Dashboard
        </a>
      </p>
    </div>
    """

    return await asyncio.to_thread(
        _send_smtp_email,
        super_admin_email,
        subject,
        text_body,
        html_body,
    )


async def send_password_reset_email(
    to_email: str,
    verification_code: str,
    recipient_name: str = "Admin User"
) -> bool:
    """Send a password reset verification code email."""
    subject = f"[AI-Drive Analyzer] Password Reset Verification Code: {verification_code}"
    
    text_body = f"""Hello {recipient_name},

You have requested to reset your password for the AI-Drive Analyzer Admin Portal.

Your 6-digit verification code is:

    ==================================
                 {verification_code}
    ==================================

This code is valid for 15 minutes.

Enter this code on the password reset page along with your new password to complete the update.

If you did not make this request, you can safely ignore this email. Your password will remain unchanged.

Best regards,
AI-Drive Analyzer Security & Access Gateway
"""

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 540px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
      <h2 style="color: #0f172a; margin-top: 0; font-size: 20px;">Password Reset Verification</h2>
      <p style="color: #475569; font-size: 14px; line-height: 1.5;">
        Hello <strong>{recipient_name}</strong>,<br>
        We received a request to reset your password for your Admin Portal account.
      </p>
      
      <div style="background: linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%); border: 1px dashed #3b82f6; border-radius: 8px; padding: 18px; text-align: center; margin: 24px 0;">
        <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 6px;">Your 6-Digit Verification Code</div>
        <div style="font-size: 32px; font-weight: 800; letter-spacing: 0.25em; color: #1e3a8a; font-family: monospace;">{verification_code}</div>
        <div style="font-size: 11px; color: #64748b; margin-top: 6px;">Expires in 15 minutes</div>
      </div>

      <p style="color: #64748b; font-size: 13px; line-height: 1.5;">
        Enter this verification code in the Admin Portal along with your new chosen password to update your account.
      </p>
      
      <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
      
      <p style="color: #94a3b8; font-size: 11px; margin-bottom: 0;">
        If you did not request a password reset, please ignore this email or contact support. Your password remains safe and unchanged.
      </p>
    </div>
    """

    return await asyncio.to_thread(
        _send_smtp_email,
        to_email,
        subject,
        text_body,
        html_body,
    )


async def notify_applicant_of_status(
    applicant_name: str,
    applicant_email: str,
    status: str
) -> bool:
    """Notify the applicant whether their admin request was approved or rejected."""
    is_approved = status == "APPROVED"
    subject = (
        f"[AI-Drive Analyzer] Admin Access Request Approved"
        if is_approved
        else f"[AI-Drive Analyzer] Admin Access Request Update"
    )

    if is_approved:
        text_body = f"""Hello {applicant_name},

Great news! The Lead Admin has APPROVED your User Admin access request on AI-Drive Analyzer.

You can now sign in to the User Admin Portal at:
{settings.FRONTEND_URL}?portal=admin

Important: Please use the same email and password as your User Portal account to log in. You now have full access to inspect your query activity, referenced files, and analysis status without requiring further approvals.

Best regards,
AI-Drive Analyzer Administration
"""
    else:
        text_body = f"""Hello {applicant_name},

Thank you for your interest. Your request for User Admin access on AI-Drive Analyzer was reviewed by the Lead Admin and could not be approved at this time.

If you believe this was an error, please reach out with an updated request note.

Best regards,
AI-Drive Analyzer Administration
"""

    return await asyncio.to_thread(
        _send_smtp_email,
        applicant_email,
        subject,
        text_body,
    )
