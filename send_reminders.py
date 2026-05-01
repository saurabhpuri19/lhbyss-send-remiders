import os
import resend
from datetime import date
from supabase import create_client, Client


# ── Supabase connection ────────────────────────────────────────────────────────
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]   # service_role key (bypasses RLS)

# ── Resend credentials ─────────────────────────────────────────────────────────
resend.api_key        = os.environ["RESEND_API_KEY"]
SENDER_EMAIL: str     = os.environ["SENDER_EMAIL"]  # e.g. onboarding@yourdomain.com
                                                     # or onboarding@resend.dev for testing

TODAY = date.today().isoformat()   # "YYYY-MM-DD"


# ──────────────────────────────────────────────────────────────────────────────
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
        .gte("task_due_date", TODAY)    # due date >= today  →  not past
        .execute()
    )
    return response.data or []


def fetch_clients_by_ids(sb: Client, client_ids: list[str]) -> dict[str, str]:
    """Returns {client_id: client_email} for the given list of ids."""
    if not client_ids:
        return {}

    response = (
        sb.table("client_tbl")
        .select("client_id, client_email")
        .in_("client_id", client_ids)
        .execute()
    )
    return {str(row["client_id"]): row["client_email"] for row in (response.data or [])}


def build_html(task: dict) -> str:
    task_id       = task.get("task_id", "N/A")
    task_name     = task.get("task_name", "your assigned task")
    task_due_date = task.get("task_due_date", "N/A")
    task_desc     = task.get("task_description", "")

    desc_row = (
        f"<tr><td style='padding:8px 12px;border:1px solid #ddd;'>"
        f"<strong>Details</strong></td>"
        f"<td style='padding:8px 12px;border:1px solid #ddd;'>{task_desc}</td></tr>"
        if task_desc else ""
    )

    return f"""
<html>
  <body style="font-family:Arial,sans-serif;color:#333;padding:20px;">
    <h2 style="color:#d9534f;">⏰ Task Reminder</h2>
    <p>Hello,</p>
    <p>This is a friendly reminder that the following task is due soon:</p>
    <table style="border-collapse:collapse;width:100%;max-width:500px;">
      <tr style="background:#f5f5f5;">
        <td style="padding:8px 12px;border:1px solid #ddd;"><strong>Task ID</strong></td>
        <td style="padding:8px 12px;border:1px solid #ddd;">{task_id}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #ddd;"><strong>Task Name</strong></td>
        <td style="padding:8px 12px;border:1px solid #ddd;">{task_name}</td>
      </tr>
      <tr style="background:#f5f5f5;">
        <td style="padding:8px 12px;border:1px solid #ddd;"><strong>Due Date</strong></td>
        <td style="padding:8px 12px;border:1px solid #ddd;color:#d9534f;">
          <strong>{task_due_date}</strong>
        </td>
      </tr>
      {desc_row}
    </table>
    <br>
    <p>Please complete it before the due date.</p>
    <p style="color:#999;font-size:12px;">— Task Reminder System</p>
  </body>
</html>
"""


def build_text(task: dict) -> str:
    return (
        f"Hello,\n\n"
        f"This is a friendly reminder that the following task is due soon:\n\n"
        f"  Task ID   : {task.get('task_id', 'N/A')}\n"
        f"  Task Name : {task.get('task_name', 'N/A')}\n"
        f"  Due Date  : {task.get('task_due_date', 'N/A')}\n"
        f"  Details   : {task.get('task_description', '')}\n\n"
        f"Please complete it before the due date.\n\n"
        f"Regards,\nTask Reminder System"
    )


def send_emails(emails: list[dict]) -> None:
    if not emails:
        print("   No emails to send today.")
        return

    for item in emails:
        to_addr  = item["to"]
        task     = item["task"]
        task_id  = task.get("task_id", "N/A")
        due_date = task.get("task_due_date", "N/A")

        params: resend.Emails.SendParams = {
            "from":    SENDER_EMAIL,
            "to":      [to_addr],
            "subject": f"⏰ Reminder: Task #{task_id} is due on {due_date}",
            "html":    build_html(task),
            "text":    build_text(task),
        }

        response = resend.Emails.send(params)
        print(f"  ✅ Sent to {to_addr}  (Resend id: {response['id']})")


# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    print(f"🗓  Running task reminder for {TODAY}")
    sb = get_supabase_client()

    tasks = fetch_pending_tasks(sb)
    print(f"   Found {len(tasks)} pending task(s).")

    if not tasks:
        print("   Nothing to do. Exiting.")
        return

    all_client_ids: set[str] = set()
    for task in tasks:
        raw: str = str(task.get("task_client_id", ""))
        ids = [cid.strip() for cid in raw.split(",") if cid.strip()]
        all_client_ids.update(ids)

    client_email_map = fetch_clients_by_ids(sb, list(all_client_ids))
    print(f"   Resolved {len(client_email_map)} unique client email(s).")

    emails_to_send: list[dict] = []
    for task in tasks:
        raw: str = str(task.get("task_client_id", ""))
        task_client_ids = [cid.strip() for cid in raw.split(",") if cid.strip()]

        for cid in task_client_ids:
            email_addr = client_email_map.get(cid)
            if email_addr:
                emails_to_send.append({"to": email_addr, "task": task})
            else:
                print(f"  ⚠️  No email for client_id={cid} (task_id={task.get('task_id')})")

    print(f"   Sending {len(emails_to_send)} email(s)…")
    send_emails(emails_to_send)
    print("✅ Done.")


if __name__ == "__main__":
    main()