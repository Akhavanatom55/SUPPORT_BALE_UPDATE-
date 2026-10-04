import json
import os
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO
from pathlib import Path

import requests
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()
from sqlalchemy import DateTime, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()
BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = Path(os.environ["DB_FILE"]).expanduser() if os.environ.get("DB_FILE") else BASE_DIR / "data" / "support_bot.db"
BACKUP_LOCK = threading.Lock()
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(128), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PanelUser(db.Model):
    __tablename__ = "panel_users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BaleAdmin(db.Model):
    __tablename__ = "bale_admins"
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(64), unique=True, nullable=False)
    display_name = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BaleUser(db.Model):
    __tablename__ = "bale_users"
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(64), unique=True, nullable=False)
    first_name = db.Column(db.String(255), default="")
    last_name = db.Column(db.String(255), default="")
    username = db.Column(db.String(255), default="")
    state = db.Column(db.Text, default="")
    is_blocked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow)


class GeminiKey(db.Model):
    __tablename__ = "gemini_keys"
    id = db.Column(db.Integer, primary_key=True)
    api_key = db.Column(db.Text, nullable=False)
    label = db.Column(db.String(128), default="")
    priority = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_exhausted = db.Column(db.Boolean, default=False)
    exhausted_until = db.Column(db.DateTime, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Faq(db.Model):
    __tablename__ = "faqs"
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    view_count = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CannedResponse(db.Model):
    __tablename__ = "canned_responses"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    keywords = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Ticket(db.Model):
    __tablename__ = "tickets"
    id = db.Column(db.Integer, primary_key=True)
    user_chat_id = db.Column(db.String(64), nullable=False)
    user_name = db.Column(db.String(255), default="")
    subject = db.Column(db.Text, default="")
    status = db.Column(db.String(32), default="open")
    assigned_admin_chat_id = db.Column(db.String(64), nullable=True)
    ai_enabled = db.Column(db.Boolean, default=True)
    rating = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TicketMessage(db.Model):
    __tablename__ = "ticket_messages"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, nullable=False)
    sender = db.Column(db.String(16), nullable=False)
    sender_name = db.Column(db.String(255), default="")
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Broadcast(db.Model):
    __tablename__ = "broadcasts"
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


MODELS = [
    Setting,
    PanelUser,
    BaleAdmin,
    BaleUser,
    GeminiKey,
    Faq,
    CannedResponse,
    Ticket,
    TicketMessage,
    Broadcast,
]

DEFAULT_SETTINGS = {
    "BALE_BOT_TOKEN": os.environ.get("BALE_BOT_TOKEN", ""),
    "WEBHOOK_SECRET": os.environ.get("WEBHOOK_SECRET", "change-this-webhook-secret"),
    "PUBLIC_BASE_URL": os.environ.get("PUBLIC_BASE_URL", ""),
    "GEMINI_MODEL": os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
    "GEMINI_SYSTEM_PROMPT": (
        "شما دستیار هوشمند پشتیبانی هستید. مودب، دقیق و کوتاه به زبان فارسی پاسخ بده. "
        "اگر پاسخ را نمی‌دانی صادقانه بگو و پیشنهاد بده کاربر درخواست خود را برای تیم پشتیبانی انسانی ثبت کند."
    ),
    "GROUP_CHAT_ID": os.environ.get("GROUP_CHAT_ID", ""),
    "BOT_NAME": os.environ.get("BOT_NAME", "ربات پشتیبانی"),
    "ORGANIZATION_NAME": os.environ.get("ORGANIZATION_NAME", "تیم پشتیبانی"),
    "AI_ENABLED": os.environ.get("AI_ENABLED", "true"),
    "WELCOME_MESSAGE": os.environ.get(
        "WELCOME_MESSAGE",
        "سلام 👋\nبه ربات پشتیبانی خوش آمدید.\nاز منوی زیر می‌توانید درخواست جدید ثبت کنید یا سوالات متداول را مشاهده کنید.",
    ),
}


def _database_uri():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url
    path = _writable_db_file()
    return f"sqlite:///{path.as_posix()}"


def _writable_db_file():
    """Pick a writable location for SQLite (the app dir may be read-only on Belmo)."""
    global DB_FILE
    candidates = [DB_FILE]
    for extra in (
        Path(tempfile.gettempdir()) / "support_bot" / "support_bot.db",
        Path.home() / ".support_bot" / "support_bot.db",
    ):
        if extra not in candidates:
            candidates.append(extra)
    last_error = None
    for cand in candidates:
        try:
            cand.parent.mkdir(parents=True, exist_ok=True)
            probe = cand.parent / ".write_test"
            probe.write_text("ok")
            probe.unlink()
            if cand != candidates[0]:
                print(
                    f"[WARN] {candidates[0].parent} is not writable; using {cand}. "
                    "Data may be lost on restart - set DATABASE_URL (PostgreSQL) for persistence.",
                    flush=True,
                )
            DB_FILE = cand
            return cand
        except OSError as exc:
            last_error = exc
    raise RuntimeError(f"No writable location for the SQLite database: {last_error}")


def _engine_options():
    opts = {"pool_pre_ping": True}
    if not os.environ.get("DATABASE_URL", "").strip():
        opts["connect_args"] = {"timeout": 30}
    return opts


def get_setting(key):
    row = db.session.get(Setting, key)
    return row.value if row else DEFAULT_SETTINGS.get(key, "")


def set_setting(key, value):
    row = db.session.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=str(value))
        db.session.add(row)
    else:
        row.value = str(value)
        row.updated_at = datetime.utcnow()
    db.session.commit()


def env_admin_ids():
    return {x.strip() for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}


def all_admin_ids():
    ids = set(env_admin_ids())
    ids.update(x.chat_id for x in BaleAdmin.query.all())
    return ids


def is_bale_admin(chat_id):
    return str(chat_id) in all_admin_ids()


def get_state(chat_id):
    u = BaleUser.query.filter_by(chat_id=str(chat_id)).first()
    if not u or not u.state:
        return {"step": "", "data": {}}
    try:
        return json.loads(u.state)
    except Exception:
        return {"step": "", "data": {}}


def set_state(chat_id, step, data=None):
    u = BaleUser.query.filter_by(chat_id=str(chat_id)).first()
    if not u:
        u = BaleUser(chat_id=str(chat_id))
        db.session.add(u)
    u.state = json.dumps({"step": step, "data": data or {}}, ensure_ascii=False)
    db.session.commit()


def reset_state(chat_id):
    u = BaleUser.query.filter_by(chat_id=str(chat_id)).first()
    if u:
        u.state = ""
        db.session.commit()


def upsert_bale_user(sender):
    chat_id = str(sender.get("id"))
    u = BaleUser.query.filter_by(chat_id=chat_id).first()
    if not u:
        u = BaleUser(chat_id=chat_id)
        db.session.add(u)
    u.first_name = sender.get("first_name", "") or ""
    u.last_name = sender.get("last_name", "") or ""
    u.username = sender.get("username", "") or ""
    u.last_seen_at = datetime.utcnow()
    db.session.commit()
    return u


def main_keyboard(admin=False):
    rows = [
        [{"text": "📝 ثبت درخواست جدید"}, {"text": "❓ سوالات متداول"}],
        [{"text": "📂 درخواست های من"}],
    ]
    if admin:
        rows.append([{"text": "🛠 پنل مدیریت"}])
    return {"keyboard": rows, "resize_keyboard": True}


def inline(rows):
    return {"inline_keyboard": rows}


def admin_keyboard():
    return inline([
        [{"text": "🧾 درخواست‌های باز", "callback_data": "admin:tickets"}],
        [{"text": "➕ افزودن سوال متداول", "callback_data": "admin:faq:add"}, {"text": "➖ حذف سوال متداول", "callback_data": "admin:faq:list"}],
        [{"text": "🔑 مدیریت کلید Gemini", "callback_data": "admin:gemini:menu"}],
        [{"text": "👤 مدیریت ادمین‌ها", "callback_data": "admin:admins:list"}],
        [{"text": "📦 دریافت دیتابیس", "callback_data": "admin:db:export"}, {"text": "📥 ارسال دیتابیس", "callback_data": "admin:db:import"}],
        [{"text": "📣 ارسال پیام همگانی", "callback_data": "admin:broadcast"}],
        [{"text": "🔗 لینک پنل مدیریت وب", "callback_data": "admin:panel:link"}],
    ])


def faq_keyboard(items, delete=False):
    rows = []
    for f in items:
        rows.append([{"text": ("🗑 " if delete else "❓ ") + (f.question or "")[:48], "callback_data": (f"admin:faq:delete:{f.id}" if delete else f"faq:view:{f.id}")}])
    rows.append([{"text": "🔙 بازگشت", "callback_data": "admin:menu" if delete else "menu:main"}])
    return inline(rows)


def ticket_user_keyboard(ticket_id):
    return inline([
        [{"text": "✅ مشکلم حل شد", "callback_data": f"ticket:close:{ticket_id}"}, {"text": "🙋 پشتیبان انسانی", "callback_data": f"ticket:escalate:{ticket_id}"}],
    ])


def rating_keyboard(ticket_id):
    return inline([[{"text": "⭐" * n, "callback_data": f"ticket:rate:{ticket_id}:{n}"} for n in range(1, 6)]])


def admin_ticket_keyboard(ticket_id, ai_enabled=True):
    return inline([
        [{"text": "✍️ پاسخ به کاربر", "callback_data": f"admin:ticket:reply:{ticket_id}"}],
        [{"text": "🤖 خاموش کردن AI" if ai_enabled else "🤖 روشن کردن AI", "callback_data": f"admin:ticket:ai:{ticket_id}"}, {"text": "✅ بستن تیکت", "callback_data": f"admin:ticket:close:{ticket_id}"}],
        [{"text": "🔙 بازگشت", "callback_data": "admin:tickets"}],
    ])


def gemini_keyboard(keys):
    rows = [[{"text": ("⛔" if k.is_exhausted else "✅") + " " + (k.label or f"کلید #{k.id}"), "callback_data": f"admin:gemini:delete:{k.id}"}] for k in keys]
    rows += [[{"text": "➕ افزودن کلید جدید", "callback_data": "admin:gemini:add"}], [{"text": "🔙 بازگشت", "callback_data": "admin:menu"}]]
    return inline(rows)


def admins_keyboard(admins):
    rows = [[{"text": f"🗑 {a.display_name or a.chat_id}", "callback_data": f"admin:admins:remove:{a.chat_id}"}] for a in admins]
    rows += [[{"text": "➕ افزودن ادمین", "callback_data": "admin:admins:add"}], [{"text": "🔙 بازگشت", "callback_data": "admin:menu"}]]
    return inline(rows)


class BaleClient:
    BASE_URL = "https://tapi.bale.ai"

    def __init__(self, token=None):
        self.token = token or get_setting("BALE_BOT_TOKEN")

    def call(self, method, payload=None):
        if not self.token:
            return {"ok": False, "description": "BALE_BOT_TOKEN is not configured"}
        try:
            r = requests.post(f"{self.BASE_URL}/bot{self.token}/{method}", json=payload or {}, timeout=10)
            return r.json()
        except Exception as exc:
            return {"ok": False, "description": str(exc)}

    def send_message(self, chat_id, text_value, markup=None):
        data = {"chat_id": str(chat_id), "text": str(text_value)}
        if markup:
            data["reply_markup"] = markup
        return self.call("sendMessage", data)

    def send_document(self, chat_id, content, filename, caption=None):
        if not self.token:
            return {"ok": False, "description": "BALE_BOT_TOKEN is not configured"}
        try:
            data = {"chat_id": str(chat_id)}
            if caption:
                data["caption"] = caption
            files = {"document": (filename, content, "application/octet-stream")}
            r = requests.post(f"{self.BASE_URL}/bot{self.token}/sendDocument", data=data, files=files, timeout=60)
            return r.json()
        except Exception as exc:
            return {"ok": False, "description": str(exc)}

    def get_file(self, file_id):
        return self.call("getFile", {"file_id": file_id})

    def download_file(self, path):
        try:
            r = requests.get(f"{self.BASE_URL}/file/bot{self.token}/{path}", timeout=60)
            return r.content if r.ok else None
        except Exception:
            return None

    def answer_callback(self, callback_id, text=None, alert=False):
        data = {"callback_query_id": callback_id}
        if text is not None:
            data["text"] = text
        if alert:
            data["show_alert"] = True
        return self.call("answerCallbackQuery", data)

    def set_webhook(self, url):
        return self.call("setWebhook", {"url": url})

    def delete_webhook(self):
        return self.call("deleteWebhook")

    def webhook_info(self):
        return self.call("getWebhookInfo")



def create_ticket(chat_id, name, body):
    ticket = Ticket(user_chat_id=str(chat_id), user_name=name, subject=body[:120], status="open", ai_enabled=True)
    db.session.add(ticket)
    db.session.flush()
    db.session.add(TicketMessage(ticket_id=ticket.id, sender="user", sender_name=name, body=body))
    db.session.commit()
    return ticket.id


def ai_reply(history, system_prompt):
    model = get_setting("GEMINI_MODEL") or DEFAULT_MODEL
    keys = GeminiKey.query.filter_by(is_active=True).order_by(GeminiKey.priority.asc()).all()
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        keys = [GeminiKey(id=0, api_key=env_key, label="Environment API Key")] + keys
    now = datetime.utcnow()
    usable = [k for k in keys if k.id == 0 or not k.is_exhausted or (k.exhausted_until and k.exhausted_until < now)]
    if not usable:
        return None

    contents = [{"role": h["role"], "parts": [{"text": h["text"]}]} for h in history]
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 600},
    }
    for key in usable:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key.api_key}", json=payload, timeout=45)
            if r.status_code in (403, 429):
                if key.id:
                    key.is_exhausted = True
                    key.exhausted_until = datetime.utcnow() + timedelta(hours=1)
                    db.session.commit()
                continue
            if r.status_code != 200:
                continue
            data = r.json()
            parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
            answer = "".join(p.get("text", "") for p in parts).strip()
            if answer:
                if key.id:
                    key.is_exhausted = False
                    key.last_used_at = datetime.utcnow()
                    db.session.commit()
                return answer
        except Exception:
            continue
    return None


def notify_admins(ticket_id):
    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        return
    client = BaleClient()
    text_value = f"🆕 تیکت #{ticket.id}\n👤 {ticket.user_name}\n📝 {ticket.subject}\n\nبرای پاسخ دکمه زیر را بزنید."
    targets = set(all_admin_ids())
    group = get_setting("GROUP_CHAT_ID")
    if group:
        targets.add(group)
    for target in targets:
        client.send_message(target, text_value, admin_ticket_keyboard(ticket.id, ticket.ai_enabled))


def handle_user_text(chat_id, sender, text_value, admin):
    name = " ".join([sender.get("first_name", ""), sender.get("last_name", "")]).strip() or sender.get("username") or str(chat_id)
    state = get_state(chat_id)

    # Global commands/buttons always win over an unfinished state.
    if text_value == "/start":
        reset_state(chat_id)
        BaleClient().send_message(chat_id, get_setting("WELCOME_MESSAGE"), main_keyboard(admin))
        return
    if text_value in ("/admin", "🛠 پنل مدیریت"):
        if not admin:
            BaleClient().send_message(chat_id, "⛔ شما دسترسی مدیریت ندارید.")
        else:
            reset_state(chat_id)
            BaleClient().send_message(chat_id, "🛠 پنل مدیریت ربات — یک گزینه را انتخاب کنید:", admin_keyboard())
        return
    if text_value in ("❓ سوالات متداول", "/faq"):
        items = Faq.query.filter_by(is_published=True).order_by(Faq.sort_order.asc(), Faq.id.desc()).limit(30).all()
        if not items:
            BaleClient().send_message(chat_id, "در حال حاضر سوال متداولی ثبت نشده است.")
        else:
            BaleClient().send_message(chat_id, "❓ سوالات متداول — یکی را انتخاب کنید:", faq_keyboard(items))
        return
    if text_value == "📂 درخواست های من":
        items = Ticket.query.filter_by(user_chat_id=str(chat_id)).order_by(Ticket.id.desc()).limit(10).all()
        if not items:
            BaleClient().send_message(chat_id, "شما هنوز درخواستی ثبت نکرده‌اید.")
        else:
            labels = {"open": "🟢 باز", "answered": "🟡 پاسخ داده‌شده", "closed": "⚪️ بسته‌شده"}
            BaleClient().send_message(chat_id, "\n".join(f"#{x.id} — {labels.get(x.status, x.status)} — {(x.subject or '')[:40]}" for x in items))
        return
    if text_value == "📝 ثبت درخواست جدید":
        set_state(chat_id, "awaiting_ticket_text")
        BaleClient().send_message(chat_id, "✏️ لطفاً متن درخواست یا سوال خود را بنویسید و ارسال کنید:")
        return

    step = state.get("step")
    if step == "awaiting_ticket_text":
        ticket_id = create_ticket(chat_id, name, text_value)
        reset_state(chat_id)
        BaleClient().send_message(chat_id, f"✅ درخواست شما با شماره #{ticket_id} ثبت شد.\nبه زودی پاسخ داده می‌شود.", main_keyboard(admin))
        try_ai_or_notify(ticket_id, chat_id, text_value)
        return
    if step == "admin_reply_ticket" and admin:
        ticket_id = int(state.get("data", {}).get("ticket_id", 0) or 0)
        ticket = db.session.get(Ticket, ticket_id)
        if ticket:
            db.session.add(TicketMessage(ticket_id=ticket.id, sender="admin", sender_name=name, body=text_value))
            ticket.status = "answered"
            ticket.assigned_admin_chat_id = str(chat_id)
            ticket.updated_at = datetime.utcnow()
            db.session.commit()
            BaleClient().send_message(ticket.user_chat_id, f"💬 پاسخ پشتیبانی برای درخواست #{ticket.id}:\n\n{text_value}")
        reset_state(chat_id)
        BaleClient().send_message(chat_id, f"✅ پاسخ شما برای تیکت #{ticket_id} ارسال شد.", admin_keyboard())
        return
    if step == "admin_faq_question" and admin:
        set_state(chat_id, "admin_faq_answer", {"question": text_value})
        BaleClient().send_message(chat_id, "✅ سوال ذخیره شد. حالا پاسخ این سوال را بنویسید:")
        return
    if step == "admin_faq_answer" and admin:
        q = str(state.get("data", {}).get("question", ""))
        db.session.add(Faq(question=q, answer=text_value, sort_order=0, is_published=True))
        db.session.commit()
        reset_state(chat_id)
        BaleClient().send_message(chat_id, "✅ سوال متداول جدید اضافه شد.", admin_keyboard())
        return
    if step == "admin_gemini_key" and admin:
        db.session.add(GeminiKey(api_key=text_value, label=f"کلید {text_value[:6]}***", priority=0, is_active=True))
        db.session.commit()
        reset_state(chat_id)
        BaleClient().send_message(chat_id, "✅ کلید Gemini اضافه شد.", admin_keyboard())
        return
    if step == "admin_add_admin" and admin:
        parts = text_value.split()
        if not parts or not parts[0].isdigit():
            BaleClient().send_message(chat_id, "❌ شناسه عددی معتبر نیست. دوباره ارسال کنید.")
            return
        cid = parts[0]
        if not BaleAdmin.query.filter_by(chat_id=cid).first():
            db.session.add(BaleAdmin(chat_id=cid, display_name=" ".join(parts[1:])))
            db.session.commit()
        reset_state(chat_id)
        BaleClient().send_message(chat_id, f"✅ ادمین {cid} اضافه شد.", admin_keyboard())
        return
    if step == "admin_broadcast" and admin:
        set_state(chat_id, "admin_broadcast_confirm", {"text": text_value})
        BaleClient().send_message(chat_id, f"پیام زیر برای همه کاربران ارسال شود؟\n\n«{text_value}»", inline([[{"text": "✅ بله، ارسال شود", "callback_data": "admin:broadcast:confirm"}, {"text": "❌ انصراف", "callback_data": "admin:menu"}]]))
        return
    if step == "admin_db_import" and admin:
        BaleClient().send_message(chat_id, "📥 فایل پشتیبان را به صورت Document ارسال کنید؛ پیام متنی نادیده گرفته شد. برای لغو /start بزنید.")
        return

    # Free text becomes a support ticket.
    ticket = Ticket.query.filter(Ticket.user_chat_id == str(chat_id), Ticket.status != "closed").order_by(Ticket.id.desc()).first()
    if not ticket:
        ticket_id = create_ticket(chat_id, name, text_value)
    else:
        ticket_id = ticket.id
        db.session.add(TicketMessage(ticket_id=ticket_id, sender="user", sender_name=name, body=text_value))
        db.session.commit()
    try_ai_or_notify(ticket_id, chat_id, text_value)


def try_ai_or_notify(ticket_id, chat_id, last_text):
    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        return
    if ticket.ai_enabled and get_setting("AI_ENABLED") in ("true", "1", "True"):
        faq_rows = Faq.query.filter_by(is_published=True).limit(20).all()
        faq_context = "\n\n".join(f"س: {f.question}\nج: {f.answer}" for f in faq_rows)
        history = TicketMessage.query.filter_by(ticket_id=ticket_id).order_by(TicketMessage.id.asc()).limit(20).all()
        prompt = get_setting("GEMINI_SYSTEM_PROMPT") + (f"\n\nسوالات متداول:\n{faq_context}" if faq_context else "")
        answer = ai_reply([{"role": "user" if m.sender == "user" else "model", "text": m.body} for m in history], prompt)
        if answer:
            db.session.add(TicketMessage(ticket_id=ticket_id, sender="ai", sender_name="دستیار هوشمند", body=answer))
            db.session.commit()
            BaleClient().send_message(chat_id, f"🤖 {answer}", ticket_user_keyboard(ticket_id))
            return
    notify_admins(ticket_id)


def export_database_payload():
    data = {}
    for model in MODELS:
        rows = []
        for obj in model.query.all():
            row = {}
            for col in inspect(model).columns:
                value = getattr(obj, col.key)
                if isinstance(value, datetime):
                    value = value.isoformat()
                row[col.key] = value
            rows.append(row)
        data[model.__tablename__] = rows
    return {"exportedAt": datetime.utcnow().isoformat() + "Z", "version": 2, "data": data}


def _parse_value(model, col, value):
    if value is None:
        return None
    if isinstance(col.type, DateTime):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                return None
    return value


def import_database_payload(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise ValueError("ساختار فایل پشتیبان نامعتبر است")
    table_map = {m.__tablename__: m for m in MODELS}
    with BACKUP_LOCK:
        try:
            # Delete children before parents.
            for model in [TicketMessage, Ticket, Broadcast, CannedResponse, Faq, GeminiKey, BaleUser, BaleAdmin, PanelUser, Setting]:
                model.query.delete()
            db.session.commit()
            for table, model in table_map.items():
                rows = payload["data"].get(table, [])
                columns = {c.key: c for c in inspect(model).columns}
                for raw in rows:
                    clean = {k: _parse_value(model, columns[k], v) for k, v in raw.items() if k in columns}
                    db.session.add(model(**clean))
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise


def sqlite_integrity_ok(raw_bytes):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        f.write(raw_bytes)
        temp_path = f.name
    try:
        con = sqlite3.connect(temp_path)
        result = con.execute("PRAGMA integrity_check").fetchone()[0]
        con.close()
        return result == "ok", temp_path
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        return False, temp_path


def handle_document(chat_id, document):
    client = BaleClient()
    state = get_state(chat_id)
    if state.get("step") != "admin_db_import" or not is_bale_admin(chat_id):
        return
    file_id = document.get("file_id")
    info = client.get_file(file_id)
    path = (info.get("result") or {}).get("file_path")
    if not path:
        client.send_message(chat_id, "❌ دریافت فایل ناموفق بود.")
        return
    raw = client.download_file(path)
    if raw is None:
        client.send_message(chat_id, "❌ دانلود فایل ناموفق بود.")
        return
    filename = document.get("file_name", "backup.json").lower()
    try:
        if filename.endswith(".json") or raw.lstrip().startswith(b"{"):
            import_database_payload(json.loads(raw.decode("utf-8")))
            client.send_message(chat_id, "✅ دیتابیس از روی فایل JSON با موفقیت بازیابی شد.", admin_keyboard())
        else:
            client.send_message(chat_id, "⚠️ برای بازیابی پایدار، فایل JSON پشتیبان را ارسال کنید. فایل خام SQLite در نسخه‌های PostgreSQL قابل بازیابی نیست.", admin_keyboard())
    except Exception as exc:
        client.send_message(chat_id, f"❌ خطا در بازیابی دیتابیس: {exc}", admin_keyboard())
    finally:
        reset_state(chat_id)


def handle_callback(cb):
    client = BaleClient()
    chat_id = str((cb.get("from") or {}).get("id"))
    admin = is_bale_admin(chat_id)
    data = cb.get("data", "")
    client.answer_callback(cb.get("id"))
    parts = data.split(":")
    ns = parts[0] if parts else ""
    action = parts[1] if len(parts) > 1 else ""
    rest = parts[2:]

    if ns == "menu" and action == "main":
        client.send_message(chat_id, "منوی اصلی:", main_keyboard(admin)); return
    if ns == "menu" and action == "faq":
        items = Faq.query.filter_by(is_published=True).order_by(Faq.sort_order.asc(), Faq.id.desc()).limit(30).all()
        client.send_message(chat_id, "❓ سوالات متداول:", faq_keyboard(items)); return
    if ns == "faq" and action == "view" and rest:
        f = db.session.get(Faq, int(rest[0]))
        if f:
            f.view_count = (f.view_count or 0) + 1; db.session.commit()
            client.send_message(chat_id, f"❓ {f.question}\n\n{f.answer}", inline([[{"text": "🙋 همچنان سوال دارم", "callback_data": f"ticket:fromfaq:{f.id}"}], [{"text": "🔙 بازگشت", "callback_data": "menu:faq"}]]))
        return
    if ns == "ticket" and action == "fromfaq":
        set_state(chat_id, "awaiting_ticket_text")
        client.send_message(chat_id, "✏️ سوال دقیق خودتان را بنویسید:"); return
    if ns == "ticket" and action == "close" and rest:
        t = db.session.get(Ticket, int(rest[0]))
        if t and t.user_chat_id == chat_id:
            t.status = "closed"; t.updated_at = datetime.utcnow(); db.session.commit()
            client.send_message(chat_id, "ممنون! لطفاً تجربه خود را امتیاز دهید:", rating_keyboard(t.id))
        return
    if ns == "ticket" and action == "escalate" and rest:
        t = db.session.get(Ticket, int(rest[0]))
        if t and t.user_chat_id == chat_id:
            t.ai_enabled = False; t.status = "open"; db.session.commit()
            client.send_message(chat_id, "✅ درخواست شما برای پشتیبان انسانی ارسال شد.")
            notify_admins(t.id)
        return
    if ns == "ticket" and action == "rate" and len(rest) >= 2:
        t = db.session.get(Ticket, int(rest[0]))
        if t and t.user_chat_id == chat_id:
            t.rating = int(rest[1]); db.session.commit(); client.send_message(chat_id, "🙏 از بازخورد شما سپاسگزاریم.", main_keyboard(admin))
        return

    if not admin:
        return
    if ns == "admin" and action == "menu":
        client.send_message(chat_id, "🛠 پنل مدیریت ربات:", admin_keyboard()); return
    if ns == "admin" and action == "tickets":
        tickets = Ticket.query.filter(Ticket.status != "closed").order_by(Ticket.id.desc()).limit(15).all()
        rows = [[{"text": f"#{t.id} {t.user_name} — {(t.subject or '')[:30]}", "callback_data": f"admin:ticket:open:{t.id}"}] for t in tickets]
        rows.append([{"text": "🔙 بازگشت", "callback_data": "admin:menu"}])
        client.send_message(chat_id, "🧾 درخواست‌های باز:", inline(rows)); return
    if ns == "admin" and action == "ticket" and rest:
        sub = rest[0]; ticket_id = int(rest[1]) if len(rest) > 1 else 0; t = db.session.get(Ticket, ticket_id)
        if not t: return
        if sub == "open":
            client.send_message(chat_id, f"#️⃣ تیکت #{t.id}\n👤 {t.user_name}\n📝 {t.subject}\nوضعیت: {t.status}", admin_ticket_keyboard(t.id, t.ai_enabled)); return
        if sub == "reply":
            set_state(chat_id, "admin_reply_ticket", {"ticket_id": t.id}); client.send_message(chat_id, "✏️ پاسخ خود را ارسال کنید:"); return
        if sub == "ai":
            t.ai_enabled = not bool(t.ai_enabled); db.session.commit(); client.send_message(chat_id, "✅ وضعیت AI تغییر کرد.", admin_ticket_keyboard(t.id, t.ai_enabled)); return
        if sub == "close":
            t.status = "closed"; t.updated_at = datetime.utcnow(); db.session.commit(); client.send_message(chat_id, "✅ تیکت بسته شد.", admin_keyboard()); return
    if ns == "admin" and action == "faq":
        sub = rest[0] if rest else ""
        if sub == "add": set_state(chat_id, "admin_faq_question"); client.send_message(chat_id, "✏️ سوال جدید را ارسال کنید:"); return
        if sub == "list":
            items = Faq.query.order_by(Faq.id.desc()).all(); client.send_message(chat_id, "🗑 انتخاب سوال برای حذف:", faq_keyboard(items, delete=True)); return
        if sub == "delete" and len(rest) > 1:
            f = db.session.get(Faq, int(rest[1]));
            if f: db.session.delete(f); db.session.commit()
            client.send_message(chat_id, "✅ سوال حذف شد.", admin_keyboard()); return
    if ns == "admin" and action == "gemini":
        sub = rest[0] if rest else ""
        if sub == "menu": client.send_message(chat_id, "🔑 کلیدهای Gemini:", gemini_keyboard(GeminiKey.query.order_by(GeminiKey.priority.asc()).all())); return
        if sub == "add": set_state(chat_id, "admin_gemini_key"); client.send_message(chat_id, "✏️ API Key جمینی را ارسال کنید:"); return
        if sub == "delete" and len(rest) > 1:
            k = db.session.get(GeminiKey, int(rest[1]));
            if k: db.session.delete(k); db.session.commit()
            client.send_message(chat_id, "✅ کلید حذف شد.", admin_keyboard()); return
    if ns == "admin" and action == "admins":
        sub = rest[0] if rest else ""
        if sub == "list": client.send_message(chat_id, "👤 مدیریت ادمین‌ها:", admins_keyboard(BaleAdmin.query.order_by(BaleAdmin.id.asc()).all())); return
        if sub == "add": set_state(chat_id, "admin_add_admin"); client.send_message(chat_id, "✏️ شناسه عددی (chat id) ادمین جدید را ارسال کنید:"); return
        if sub == "remove" and len(rest) > 1:
            a = BaleAdmin.query.filter_by(chat_id=rest[1]).first();
            if a: db.session.delete(a); db.session.commit()
            client.send_message(chat_id, "✅ ادمین حذف شد.", admin_keyboard()); return
    if ns == "admin" and action == "db":
        sub = rest[0] if rest else ""
        if sub == "export":
            raw = json.dumps(export_database_payload(), ensure_ascii=False, indent=2).encode("utf-8")
            client.send_document(chat_id, raw, f"database-backup-{int(datetime.utcnow().timestamp())}.json", "📦 پشتیبان کامل دیتابیس")
            return
        if sub == "import":
            set_state(chat_id, "admin_db_import")
            client.send_message(chat_id, "📥 فایل JSON پشتیبان را ارسال کنید. اطلاعات فعلی جایگزین می‌شود.")
            return
    if ns == "admin" and action == "broadcast":
        if rest and rest[0] == "confirm":
            state = get_state(chat_id); body = str(state.get("data", {}).get("text", "")); reset_state(chat_id)
            users = BaleUser.query.filter_by(is_blocked=False).all(); sent = failed = 0
            for u in users:
                result = client.send_message(u.chat_id, "📣 " + body)
                if result.get("ok"): sent += 1
                else: failed += 1
            db.session.add(Broadcast(body=body, sent_count=sent, failed_count=failed)); db.session.commit()
            client.send_message(chat_id, f"✅ پیام ارسال شد. موفق: {sent} | ناموفق: {failed}", admin_keyboard()); return
        set_state(chat_id, "admin_broadcast"); client.send_message(chat_id, "✏️ متن پیام همگانی را ارسال کنید:"); return
    if ns == "admin" and action == "panel" and rest and rest[0] == "link":
        base = (get_setting("PUBLIC_BASE_URL") or "").rstrip("/")
        url = f"{base}/admin/login" if base else "PUBLIC_BASE_URL تنظیم نشده است."
        client.send_message(chat_id, f"🔗 لینک پنل مدیریت وب:\n{url}", admin_keyboard())


def handle_update(update):
    if update.get("message"):
        msg = update["message"]
        sender = msg.get("from") or {}
        chat_id = str(sender.get("id") or msg.get("chat", {}).get("id"))
        upsert_bale_user(sender)
        if msg.get("document"):
            handle_document(chat_id, msg["document"])
            return
        text_value = (msg.get("text") or "").strip()
        if text_value:
            handle_user_text(chat_id, sender, text_value, is_bale_admin(chat_id))
    elif update.get("callback_query"):
        handle_callback(update["callback_query"])


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("panel_user_id"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def ensure_first_admin_and_settings():
    """Idempotent seeding - safe even if another process seeds at the same time."""
    with db.session.no_autoflush:
        for key, value in DEFAULT_SETTINGS.items():
            try:
                if db.session.get(Setting, key) is None:
                    db.session.add(Setting(key=key, value=value))
                    db.session.commit()
            except IntegrityError:
                db.session.rollback()
        username = os.environ.get("ADMIN_PANEL_USERNAME", "admin")
        password = os.environ.get("ADMIN_PANEL_PASSWORD", "admin123456")
        try:
            if PanelUser.query.count() == 0:
                db.session.add(PanelUser(username=username, password_hash=generate_password_hash(password)))
                db.session.commit()
        except IntegrityError:
            db.session.rollback()


def init_database():
    """Create tables + seed data. Serialised across gunicorn workers with a file lock and retried on races."""
    lock_fh = None
    try:
        try:
            import fcntl

            lock_fh = open(Path(tempfile.gettempdir()) / "support_bot_init.lock", "a+")
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
        except Exception:
            lock_fh = None
        last_error = None
        for attempt in range(8):
            try:
                db.create_all()
                ensure_first_admin_and_settings()
                return
            except (IntegrityError, OperationalError, ProgrammingError) as exc:
                db.session.rollback()
                last_error = exc
                time.sleep(0.4 * (attempt + 1))
        raise last_error
    finally:
        if lock_fh is not None:
            try:
                import fcntl

                fcntl.flock(lock_fh, fcntl.LOCK_UN)
                lock_fh.close()
            except Exception:
                pass


def maybe_register_webhook(base_url):
    if os.environ.get("AUTO_REGISTER_WEBHOOK", "true").lower() not in ("1", "true", "yes", "on"):
        return
    token = get_setting("BALE_BOT_TOKEN")
    if not token:
        return
    base = (get_setting("PUBLIC_BASE_URL") or base_url or "").rstrip("/")
    if not base:
        return
    if get_setting("PUBLIC_BASE_URL") != base:
        set_setting("PUBLIC_BASE_URL", base)
    secret = get_setting("WEBHOOK_SECRET")
    if not secret or secret == "change-this-webhook-secret":
        return
    url = f"{base}/api/bale/webhook/{secret}"
    try:
        info = BaleClient().webhook_info()
        current = ((info.get("result") or {}).get("url") or "") if isinstance(info, dict) else ""
        if current != url:
            BaleClient().set_webhook(url)
    except Exception:
        pass


def create_app():
    app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent.parent / "templates"), static_folder=str(Path(__file__).resolve().parent.parent / "static"))
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
        SQLALCHEMY_DATABASE_URI=_database_uri(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS=_engine_options(),
        MAX_CONTENT_LENGTH=20 * 1024 * 1024,
    )
    db.init_app(app)
    with app.app_context():
        init_database()

    @app.get("/")
    def home():
        return render_template("home.html", settings=DEFAULT_SETTINGS)

    @app.get("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify(ok=True, database="ok", time=datetime.utcnow().isoformat())
        except Exception as exc:
            return jsonify(ok=False, error=str(exc)), 500

    @app.get("/api/health")
    def api_health():
        return health()

    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        try:
            maybe_register_webhook(request.url_root)
        except Exception:
            pass
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = PanelUser.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                session.clear(); session["panel_user_id"] = user.id; session["panel_username"] = user.username
                return redirect(request.args.get("next") or url_for("dashboard"))
            flash("نام کاربری یا رمز عبور اشتباه است.", "error")
        return render_template("login.html")

    @app.get("/admin/logout")
    def logout():
        session.clear(); return redirect(url_for("login"))

    @app.get("/admin")
    @login_required
    def dashboard():
        counts = {
            "users": BaleUser.query.count(),
            "open": Ticket.query.filter(Ticket.status != "closed").count(),
            "faq": Faq.query.filter_by(is_published=True).count(),
            "admins": len(all_admin_ids()),
        }
        recent = Ticket.query.order_by(Ticket.id.desc()).limit(8).all()
        return render_template("dashboard.html", counts=counts, recent=recent)

    @app.route("/admin/tickets", methods=["GET", "POST"])
    @login_required
    def tickets_page():
        if request.method == "POST":
            tid = int(request.form.get("ticket_id", 0))
            action = request.form.get("action")
            t = db.session.get(Ticket, tid)
            if t:
                if action == "reply":
                    body = request.form.get("body", "").strip()
                    if body:
                        db.session.add(TicketMessage(ticket_id=t.id, sender="admin", sender_name=session.get("panel_username", "admin"), body=body))
                        t.status = "answered"; t.updated_at = datetime.utcnow(); t.assigned_admin_chat_id = None
                        db.session.commit(); BaleClient().send_message(t.user_chat_id, f"💬 پاسخ پشتیبانی برای درخواست #{t.id}:\n\n{body}")
                elif action == "close":
                    t.status = "closed"; t.updated_at = datetime.utcnow(); db.session.commit()
                elif action == "toggle_ai":
                    t.ai_enabled = not bool(t.ai_enabled); db.session.commit()
            return redirect(url_for("tickets_page"))
        status = request.args.get("status", "all")
        q = Ticket.query.order_by(Ticket.id.desc())
        if status in {"open", "answered", "closed"}:
            q = q.filter_by(status=status)
        items = q.limit(100).all()
        return render_template("tickets.html", tickets=items)

    @app.get("/admin/tickets/<int:ticket_id>")
    @login_required
    def ticket_detail(ticket_id):
        ticket = db.session.get(Ticket, ticket_id)
        if not ticket: return "Not found", 404
        messages = TicketMessage.query.filter_by(ticket_id=ticket_id).order_by(TicketMessage.id.asc()).all()
        return render_template("ticket_detail.html", ticket=ticket, messages=messages)

    @app.route("/admin/faq", methods=["GET", "POST"])
    @login_required
    def faq_page():
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                q = request.form.get("question", "").strip(); a = request.form.get("answer", "").strip()
                if q and a:
                    db.session.add(Faq(question=q, answer=a)); db.session.commit()
            elif action == "delete":
                f = db.session.get(Faq, int(request.form.get("id", 0)))
                if f: db.session.delete(f); db.session.commit()
            elif action == "toggle":
                f = db.session.get(Faq, int(request.form.get("id", 0)))
                if f: f.is_published = not f.is_published; db.session.commit()
            return redirect(url_for("faq_page"))
        return render_template("faq.html", faqs=Faq.query.order_by(Faq.id.desc()).all())

    @app.route("/admin/gemini", methods=["GET", "POST"])
    @login_required
    def gemini_page():
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                key = request.form.get("api_key", "").strip()
                if key: db.session.add(GeminiKey(api_key=key, label=request.form.get("label", "").strip() or f"کلید {key[:6]}***")); db.session.commit()
            elif action == "delete":
                k = db.session.get(GeminiKey, int(request.form.get("id", 0)))
                if k: db.session.delete(k); db.session.commit()
            return redirect(url_for("gemini_page"))
        return render_template("gemini.html", keys=GeminiKey.query.order_by(GeminiKey.priority.asc(), GeminiKey.id.desc()).all())

    @app.route("/admin/admins", methods=["GET", "POST"])
    @login_required
    def admins_page():
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                cid = request.form.get("chat_id", "").strip()
                if cid.isdigit() and not BaleAdmin.query.filter_by(chat_id=cid).first():
                    db.session.add(BaleAdmin(chat_id=cid, display_name=request.form.get("display_name", "").strip())); db.session.commit()
            elif action == "delete":
                a = db.session.get(BaleAdmin, int(request.form.get("id", 0)))
                if a: db.session.delete(a); db.session.commit()
            return redirect(url_for("admins_page"))
        return render_template("admins.html", admins=BaleAdmin.query.order_by(BaleAdmin.id.desc()).all(), env_admins=sorted(env_admin_ids()))

    @app.route("/admin/broadcast", methods=["GET", "POST"])
    @login_required
    def broadcast_page():
        if request.method == "POST":
            body = request.form.get("body", "").strip()
            if body:
                client = BaleClient(); users = BaleUser.query.filter_by(is_blocked=False).all(); sent = failed = 0
                for user in users:
                    result = client.send_message(user.chat_id, "📣 " + body)
                    if result.get("ok"): sent += 1
                    else: failed += 1
                db.session.add(Broadcast(body=body, sent_count=sent, failed_count=failed)); db.session.commit()
                flash(f"ارسال انجام شد: {sent} موفق، {failed} ناموفق.", "success")
            return redirect(url_for("broadcast_page"))
        return render_template("broadcast.html", broadcasts=Broadcast.query.order_by(Broadcast.id.desc()).limit(30).all())

    @app.route("/admin/settings", methods=["GET", "POST"])
    @login_required
    def settings_page():
        editable = ["PUBLIC_BASE_URL", "GROUP_CHAT_ID", "BOT_NAME", "ORGANIZATION_NAME", "GEMINI_MODEL", "GEMINI_SYSTEM_PROMPT", "WELCOME_MESSAGE", "AI_ENABLED"]
        if request.method == "POST":
            for key in editable:
                if key in request.form: set_setting(key, request.form.get(key, ""))
            flash("تنظیمات ذخیره شد.", "success")
            return redirect(url_for("settings_page"))
        values = {key: get_setting(key) for key in editable}
        return render_template("settings.html", values=values)

    @app.route("/admin/backup", methods=["GET", "POST"])
    @login_required
    def backup_page():
        if request.method == "POST":
            uploaded = request.files.get("backup")
            if not uploaded or not uploaded.filename:
                flash("فایل انتخاب نشده است.", "error")
            else:
                try:
                    raw = uploaded.read()
                    import_database_payload(json.loads(raw.decode("utf-8")))
                    flash("بازیابی دیتابیس با موفقیت انجام شد.", "success")
                except Exception as exc:
                    flash(f"خطا در بازیابی: {exc}", "error")
            return redirect(url_for("backup_page"))
        return render_template("backup.html")

    @app.get("/admin/backup/download")
    @login_required
    def backup_download():
        raw = json.dumps(export_database_payload(), ensure_ascii=False, indent=2).encode("utf-8")
        return send_file(BytesIO(raw), mimetype="application/json", as_attachment=True, download_name=f"database-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json")

    @app.route("/admin/webhook", methods=["POST"])
    @login_required
    def webhook_manage():
        action = request.form.get("action")
        base = (get_setting("PUBLIC_BASE_URL") or request.url_root.rstrip("/")).rstrip("/")
        secret = get_setting("WEBHOOK_SECRET")
        url = f"{base}/api/bale/webhook/{secret}"
        result = BaleClient().set_webhook(url) if action == "set" else BaleClient().delete_webhook()
        flash((result.get("description") or ("وبهوک ثبت شد." if result.get("ok") else "خطا در وبهوک")), "success" if result.get("ok") else "error")
        return redirect(url_for("settings_page"))

    @app.get("/api/bale/webhook/<secret>")
    def bale_webhook(secret):
        expected = get_setting("WEBHOOK_SECRET")
        if not secret or secret != expected:
            return jsonify(ok=False), 403
        update = request.get_json(silent=True) or {}
        try:
            handle_update(update)
            return jsonify(ok=True)
        except Exception as exc:
            app.logger.exception("Bale update failed")
            return jsonify(ok=False, error=str(exc)), 500

    @app.get("/api/bale/webhook-status")
    @login_required
    def webhook_status():
        return jsonify(BaleClient().webhook_info())

    @app.route("/api/admin/backup/import", methods=["POST"])
    @login_required
    def api_backup_import():
        if "file" not in request.files:
            return jsonify(ok=False, error="file is required"), 400
        try:
            import_database_payload(json.loads(request.files["file"].read().decode("utf-8")))
            return jsonify(ok=True)
        except Exception as exc:
            return jsonify(ok=False, error=str(exc)), 400

    return app
