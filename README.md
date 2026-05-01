# Task Reminder Cron Job

Sends daily email reminders to clients for tasks that are **not yet past their due date**.
Runs for **free** using GitHub Actions (2,000 free minutes/month on the free plan).

---

## 📁 File Structure

```
your-repo/
├── send_reminders.py              # Main script
├── requirements.txt               # Python dependencies
├── .github/
│   └── workflows/
│       └── task_reminder.yml      # GitHub Actions cron schedule
└── README.md
```

---

## 🗄️ Expected Supabase Schema

### `client_tbl`
| Column         | Type   | Notes                  |
|----------------|--------|------------------------|
| `client_id`    | int / text | **Primary Key**    |
| `client_email` | text   | Recipient email address |
| *(other cols)* | —      | Optional               |

### `task_tbl`
| Column              | Type   | Notes                                             |
|---------------------|--------|---------------------------------------------------|
| `task_id`           | int    | Primary Key                                       |
| `task_name`         | text   | Short name of the task                            |
| `task_description`  | text   | Optional details                                  |
| `task_due_date`     | date   | Format: `YYYY-MM-DD`                              |
| `task_client_id`    | text   | **Comma-separated** client_ids e.g. `"1,3,7"`    |

---

## ⚙️ Setup Steps

### 1 · Push this folder to a GitHub repository

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 2 · Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name      | Value                                             |
|------------------|---------------------------------------------------|
| `SUPABASE_URL`   | Your project URL from Supabase → Settings → API   |
| `SUPABASE_KEY`   | `service_role` secret key (NOT the anon key)      |
| `SENDER_EMAIL`   | `yourname@gmail.com`                              |
| `RESEND_API_KEY` | From resend.com → API Keys           |


### 3 · Adjust the Schedule (optional)

Edit `.github/workflows/task_reminder.yml`:
```yaml
- cron: "0 8 * * *"   # 08:00 UTC = 13:30 IST
```
Use [crontab.guru](https://crontab.guru) to build your preferred time.

### 4 · Test it manually

GitHub → **Actions tab** → `Daily Task Reminder` → **Run workflow** → Watch the logs.

Don't wait for the daily schedule — trigger it immediately:

Click the "Actions" tab in your repo
Click "Daily Task Reminder" on the left
Click "Run workflow" → "Run workflow" (green button)
Click the running job to watch the live logs
You should see ✅ Sent to client@email.com in the output
---

## 🔐 Security Notes

- Use the **`service_role`** Supabase key so Row Level Security (RLS) doesn't block reads.
- **Never** commit secrets to the repo. GitHub Secrets are encrypted at rest.
- The Gmail App Password only grants Mail access, not full account access.

---

## 💡 How It Works

```
GitHub Actions (08:00 UTC daily)
        │
        ▼
send_reminders.py
        │
        ├─ Query task_tbl WHERE task_due_date >= TODAY
        │
        ├─ Split task_client_id  →  ["1", "3", "7"]
        │
        ├─ Bulk-fetch client emails from client_tbl
        │
        └─ Send HTML reminder email via Gmail SMTP
                to each client for each due task
```
