import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
from supabase import create_client, Client


# ── Supabase connection ────────────────────────────────────────────────────────
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]          # service_role key (bypasses RLS)

# ── Gmail SMTP credentials ─────────────────────────────────────────────────────
GMAIL_USER: str  = os.environ["GMAIL_USER"]             # your-email@gmail.com
GMAIL_PASS: str  = os.environ["GMAIL_APP_PASSWORD"]     # Gmail App Password (not account password)

TODAY = date.today().isoformat()   # "YYYY-MM-DD"


def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_pending_tasks(sb: Client) -> list[dict]:
    """
    Returns tasks whose due date is today or in the future (not past).
    task_client_id is a comma-separated string of client_id values.
    """
    response = (
        sb.table("task_tbl")
        .select("*")
        .gte("task_due_date", TODAY)          # due date >= today  →  not past
        .execute()
    )
    return response.data or []


def fetch_clients_by_ids(sb: Client, client_ids: list[str]) -> dict[str, str]:
    """
    Returns {client_id: client_email} for the given list of ids.
    """
    if not client_ids:
        return {}

    response = (
        sb.table("client_tbl")
        .select("client_id, client_email")
        .in_("client_id", client_ids)
        .execute()
    )
    return {str(row["client_id"]): row["client_email"] for row in (response.data or [])}


def build_email(to_address: str, task: dict) -> MIMEMultipart:
    task_id       = task.get("task_id", "N/A")
    task_name     = task.get("task_name", "your assigned task")
    task_due_date = task.get("task_due_date", "N/A")
    task_desc     = task.get("task_description", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"⏰ Reminder: Task #{task_id} is due on {task_due_date}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = to_address

    plain = f"""Hello,

This is a friendly reminder that the following task is due soon:

  Task ID   : {task_id}
  Task Name : {task_name}
  Due Date  : {task_due_date}
  Details   : {task_desc}

Please complete it before the due date.

Regards,
Task Reminder System
"""

    html = f"""
<html>
  <body style="font-family: Arial, sans-serif; color: #333; padding: 20px;">
    <h2 style="color: #d9534f;">⏰ Task Reminder</h2>
    <p>Hello,</p>
    <p>This is a friendly reminder that the following task is due soon:</p>
    <table style="border-collapse: collapse; width: 100%; max-width: 500px;">
      <tr style="background:#f5f5f5;">
        <td style="padding:8px 12px; border:1px solid #ddd;"><strong>Task ID</strong></td>
        <td style="padding:8px 12px; border:1px solid #ddd;">{task_id}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px; border:1px solid #ddd;"><strong>Task Name</strong></td>
        <td style="padding:8px 12px; border:1px solid #ddd;">{task_name}</td>
      </tr>
      <tr style="background:#f5f5f5;">
        <td style="padding:8px 12px; border:1px solid #ddd;"><strong>Due Date</strong></td>
        <td style="padding:8px 12px; border:1px solid #ddd; color:#d9534f;"><strong>{task_due_date}</strong></td>
      </tr>
      {"<tr><td style='padding:8px 12px; border:1px solid #ddd;'><strong>Details</strong></td><td style='padding:8px 12px; border:1px solid #ddd;'>"+task_desc+"</td></tr>" if task_desc else ""}
    </table>
    <br>
    <p>Please complete it before the due date.</p>
    <p style="color:#999; font-size:12px;">— Task Reminder System</p>
  </body>
</html>
"""

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))
    return msg


def send_emails(messages: list[tuple[str, MIMEMultipart]]) -> None:
    if not messages:
        print("No emails to send today.")
        return

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        for to_address, msg in messages:
            server.sendmail(GMAIL_USER, to_address, msg.as_string())
            print(f"  ✅ Sent to {to_address}")


def main() -> None:
    print(f"🗓  Running task reminder for {TODAY}")
    sb = get_supabase_client()

    # 1. Fetch all non-past tasks
    tasks = fetch_pending_tasks(sb)
    print(f"   Found {len(tasks)} pending task(s).")

    if not tasks:
        print("   Nothing to do. Exiting.")
        return

    # 2. Collect every unique client_id across all tasks
    all_client_ids: set[str] = set()
    for task in tasks:
        raw: str = str(task.get("task_client_id", ""))
        ids = [cid.strip() for cid in raw.split(",") if cid.strip()]
        all_client_ids.update(ids)

    # 3. Bulk-fetch client emails in one query
    client_email_map = fetch_clients_by_ids(sb, list(all_client_ids))
    print(f"   Resolved {len(client_email_map)} unique client email(s).")

    # 4. Build one email per (client, task) pair
    emails_to_send: list[tuple[str, MIMEMultipart]] = []
    for task in tasks:
        raw: str = str(task.get("task_client_id", ""))
        task_client_ids = [cid.strip() for cid in raw.split(",") if cid.strip()]

        for cid in task_client_ids:
            email_addr = client_email_map.get(cid)
            if email_addr:
                emails_to_send.append((email_addr, build_email(email_addr, task)))
            else:
                print(f"  ⚠️  No email found for client_id={cid} (task_id={task.get('task_id')})")

    print(f"   Sending {len(emails_to_send)} email(s)…")
    send_emails(emails_to_send)
    print("✅ Done.")


if __name__ == "__main__":
    main()
