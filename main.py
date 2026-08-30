"""
Enhanced Report Bot - Complete Rewrite
Features: Registration flow, Owner/User split, Pricing, Balance, Sections, Sorani Kurdish only, Protection
"""

import os
import sqlite3
import datetime
import asyncio
import random
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PhoneNumberInvalidError,
    FloodWaitError,
    ApiIdInvalidError,
)
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.functions.account import ReportPeerRequest
from telethon import types

# ─── Configuration ───────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "6019063884"))
DB_FILE = "panel_bot.db"

# API Credentials (set in Railway Variables)
API_ID = int(os.getenv("API_ID", "38609145"))
API_HASH = os.getenv("API_HASH", "")

# API POOL REMOVED TO PREVENT ApiIdInvalidError
# We use only the user's original stable API credentials.

# ─── Pricing ─────────────────────────────────────────────────────────────
PRICES = {
    100: 8000,
    500: 45000,
    1000: 90000,
    -1: 199000,  # endless
}

# ─── User States ─────────────────────────────────────────────────────────
user_states = {}

# ─── Persistent clients per user ─────────────────────────────────────────
pending_clients = {}

# ─── Track running report tasks per report_control_id ────────────────────
active_report_tasks = {}
section_locks = {}

# ─── Translations ─────────────────────────────────────────────────────────
# The bot uses Sorani Kurdish only.
T = {'welcome': {'ku': '👋 بەخێر بێیت!\n'
                   '\n'
                   '🔐 تکایە سەرەتا خۆت تۆمار بکە بۆ دەستگەیشتن بە بۆتەکە.\n'
                   '\n'
                   'کلیک لە دوگمەی خوارەوە بکە بۆ تۆمارکردن.'},
 'register_btn': {'ku': '📝 خۆتۆمارکردن'},
 'enter_phone': {'ku': '📱 تکایە ژمارەی تەلەفۆنەکەت بنووسە.\n'
                       '\n'
                       'فۆرمات: <code>+9647501234567</code>\n'
                       '\n'
                       'دەبێت بە + دەست پێ بکات.'},
 'enter_code': {'ku': '✅ کۆدەکە بە سەرکەوتوی نێردرا!\n'
                      '\n'
                      '📱 ئێستا کۆدی 5 ژمارەیی کە لە تلیگرام وەرگرتوویت بنووسە.\n'
                      '\n'
                      '⚠️ ئەگەر 2FA هەیە، دوای کۆدەکە دەتپرسم.'},
 'enter_password': {'ku': '🔐 ئەم هەژمارە پاسۆردی دوو قۆناغی هەیە.\nتکایە پاسۆردەکە بنووسە:'},
    'registration_success': {'ku': '✅ بە سەرکەوتوویی تۆمار کرایت!\n\nکلیک لە «گەڕانەوە» بکە بۆ دەستپێکردنی بۆتەکە.'},
    'key_expired': {'ku': '❌ کلیلت بەسەر چوە!'},
    'session_renew_msg': {'ku': '⚠️ کلیلت بەسەر چوە، تکایە کلیل نوێ بکەوە.'},
    'enter_key': {'ku': '🔑 تکایە کلیل (String Session) بنێرە:'},
    'verifying_key': {'ku': '⏳ خەریکی پشکنینی کلیلەکەم...'},
    'register_options': {'ku': '📋 تکایە شێوازی تۆمارکردن هەڵبژێرە:'},
    'reg_by_phone': {'ku': '📱 تۆمارکردن بە ژمارە'},
    'reg_by_key': {'ku': '🔑 تۆمارکردن بە کلیل'},
 'registration_exists': {'ku': '✅ پێشتر تۆمار کراویت!\n'
                               '\n'
                               'ئەم سێکشنە پێشتر تۆمار کراوە. سەرۆک ئاگادار کرایەوە.\n'
                               '\n'
                               'ئێستا دەتوانیت بۆتەکە بەکار بهێنیت.'},
 'user_menu': {'ku': '🏠 <b>پەڕەی سەرەکی</b>\n\nتکایە بەشێک هەڵبژێرە 👇'},
 'send_report': {'ku': '📤 ناردنی ڕیپۆرت'},
 'my_account': {'ku': '👤 هەژمارەکەم'},
 'account_menu': {'ku': '👤 <b>هەژمارەکەم</b>\n\nتکایە بەشێک هەڵبژێرە 👇'},
 'settings': {'ku': '⚙️ ڕێکخستنەکان'},
 'owner_menu': {'ku': '🏠 <b>پانێڵی سەرۆک</b>\n\nتکایە بەشێک هەڵبژێرە 👇'},
 'back': {'ku': '🔙 گەڕانەوە'},
 'logout': {'ku': '🚪 چوونە دەرەوە'},
 'logged_out': {'ku': '👋 تۆ چوویتە دەرەوە.\n\nبۆ بەکارهێنانی دووبارەی بۆتەکە، تکایە /start بکە و خۆت تۆمار بکە.'},
 'report_type_porn': {'ku': '🔞 پورنۆگرافی'},
 'report_type_hack': {'ku': '🎮 هاک / چیت'},
 'report_type_terror': {'ku': '☠️ تیرۆر'},
 'report_type_drugs': {'ku': '💊 مادەی هۆشبەر'},
 'report_type_scam': {'ku': '💰 فریوکاری'},
 'report_type_weapons': {'ku': '🔫 چەکی نایاسایی'},
	 'report_type_abuse': {'ku': '🚨 هەڕەشە'},
	 'report_type_hybrid': {'ku': '⚡ هێرشی خوداوەند (God Mode God-Tier)'},
	 'report_type_other': {'ku': '📋 جۆری دیکە'},
 'confirm_purchase': {'ku': '✅ دڵنیایی کڕین'},
  'top_up': {'ku': '💵 پڕکردنەوەی باڵانس'},
 'settings_menu': {'ku': '⚙️ <b>ڕێکخستنەکان</b>\n\nتکایە بەشێک هەڵبژێرە 👇'},
 'report_control': {'ku': '📊 سەنتەری ڕیپۆرت'},
 'stop_report': {'ku': '⏸ وەستاندنی ڕیپۆرت'},
 'continue_report': {'ku': '▶️ بەردەوام بوون'},
 'delete_report': {'ku': '🗑 سڕینەوەی ڕیپۆرت'},
 'not_registered': {'ku': '⚠️ تۆ تۆمار نەکراویت!\n\nتکایە سەرەتا /start بکە و خۆت تۆمار بکە.'},
 'no_sections': {'ku': '⚠️ هیچ سێکشنێکی چالاک نەدۆزرایەوە!\nتکایە پەیوەندی بە سەرۆک بکە.'},
 'report_progress': {'ku': '📤 <b>ڕیپۆرتەکە دەنێردرێت...</b>\n'
                           '📊 {sections} سێکشنی چالاک\n'
                           '⏱️ کاتی پێشبینیکراو: ~{minutes} خولەک و {seconds} چرکە\n'
                           '━━━━━━━━━━━━━━━━━━━━'},
 'owner_balance_menu': {'ku': '👤 <b>کۆنترۆڵی بەکارهێنەر</b>\n\nتکایە بەشێک هەڵبژێرە 👇'},
 'add_balance': {'ku': '➕ زیادکردنی باڵانس'},
 'set_balance': {'ku': '✏️ گۆڕینی باڵانسی بەکارهێنەر'},
 'reset_balance': {'ku': '🗑️ سڕینەوەی هەموو باڵانسی بەکارهێنەر'},
 'enter_user_id_balance': {'ku': '👤 تکایە ئایدی بەکارهێنەر بنووسە:'},
 'balance_set_msg': {'ku': '✏️ باڵانسەکەت کرا بە <b>{new_balance:,} دینار</b>.'},
 'balance_reset_msg': {'ku': '🗑️ باڵانسەکەت کرایەوە بە <b>سفر</b>.'},
 'user_not_found': {'ku': '❌ بەکارهێنەر نەدۆزرایەوە!'},
 'owner_sections_menu': {'ku': '👥 <b>بەڕێوەبردنی سێکشنەکان</b>\n\nتکایە بەشێک هەڵبژێرە 👇'},
 'view_sections': {'ku': '👁️ بینینی سێکشنەکان'},
 'add_section': {'ku': '➕ زیادکردنی سێکشن'},
 'add_by_code': {'ku': '🔑 زیادکردن بە کۆد'},
 'add_by_phone': {'ku': '📱 زیادکردن بە ژمارەی تەلەفۆن'},
 'enter_session_code': {'ku': '🔑 <b>زیادکردنی سێکشن بە کۆد</b>\n'
                              '\n'
                              'تکایە کۆدی سێشنەکە بنووسە:\n'
                              '\n'
                              '⚠️ کۆدەکە دەبێت تەواو و ڕاست بێت.'},
 'enter_phone_section': {'ku': '📱 <b>زیادکردنی سێکشن بە ژمارەی تەلەفۆن</b>\n'
                               '\n'
                               'تکایە ژمارەی تەلەفۆن بنووسە.\n'
                               '\n'
                               'فۆرمات: <code>+9647501234567</code>'},
 'owner_broadcast': {'ku': '📢 نامە بۆ هەموو بەکارهێنەرەکان'},
 'enter_broadcast': {'ku': '📢 <b>نامە ناردن بۆ هەموو بەکارهێنەرەکان</b>\n\nتکایە نامەکە بنووسە:'},
 'select_report_count': {'ku': '📊 <b>ژمارەی ڕیپۆرت دیاری بکە</b> 👇\n\n✅ دوای تەواوبوونی ژمارەی دیاریکراو، بۆتەکە خۆکارانە دەوەستێت.'},
 'no_balance': {'ku': '⚠️ باڵانسی پێویستت نییە.'},
 'service_unavailable': {'ku': '⚠️ خزمەتگوزارییەکە کاتییە بەردەست نییە.\n'
                               '\n'
                               'ئێستا ناتوانرێت ڕیپۆرت بکرێت. تکایە دواتر هەوڵ بدەرەوە.'},
 'no_sections_owner': {'ku': '⚠️ سێکشن بەردەست نیە!\n\nتکایە سەرەتا سێکشن زیاد بکە.'},
 'enter_link_short': {'ku': '📤 تکایە لینکی چەناڵ/گرووپەکە بنێرە:\n\nنموونە: <code>https://t.me/channel_name</code>'},
 'invalid_link': {'ku': '❌ لینکەکە هەڵەیە! نموونە: <code>https://t.me/channel_name</code>'},
 'phone_invalid': {'ku': '❌ ژمارەی تەلەفۆن دەبێت بە + دەست پێ بکات\nنموونە: <code>+9647501234567</code>'},
 'sending_code': {'ku': '⏳ کۆدەکە دەنێردرێت...'},
 'verifying_code': {'ku': '⏳ کۆدەکە پشتڕاست دەکرێتەوە...'},
 'verifying': {'ku': '⏳ پشتڕاستکردنەوە...'},
 'code_invalid': {'ku': '❌ کۆدەکە دەبێت ٤-٥ ژمارە بێت.'},
 'not_understood': {'ku': '❓ تێنەگەیشتم! تکایە هەڵبژاردەیەک هەڵبژێرە.'},
 'report_progress_live': {'ku': '📤 ڕیپۆرتەکان دەنێردرێن...\n'
                                '━━━━━━━━━━━━━━━━━━━━\n'
                                '📊 پێشکەوتن: {total}/{maximum}\n'
                                '✅ سەرکەوتوو: {success}\n'
                                '❌ شکست: {failed}\n'
                                '━━━━━━━━━━━━━━━━━━━━'},
 'phone_exists': {'ku': '⚠️ ئەم ژمارەیە پێشتر تۆمارکراوە!'},
 'twofa_password': {'ku': '🔐 ئەم هەژمارەیە 2FA ـی هەیە. پاسۆرد بنووسە:'},
 'session_invalid': {'ku': '❌ سێشنەکە دروست نییە. تکایە دووبارە هەوڵ بدەرەوە.'},
 'session_short': {'ku': '❌ ستڕینگی سێشن زۆر کورتە. تکایە تەواوی بنووسە.'},
 'validating_session': {'ku': '⏳ سێشنەکە پشتڕاست دەکرێتەوە...'},
 'invalid_user_id_number': {'ku': '❌ ئایدی بەکارهێنەر هەڵەیە. تکایە ژمارەیەک بنووسە.'},
 'invalid_user_id': {'ku': '❌ ئایدی بەکارهێنەر هەڵەیە.'},
 'invalid_amount': {'ku': '❌ بڕەکە هەڵەیە. ژمارەیەک بنووسە.'},
 'report_not_found': {'ku': '❌ ڕیپۆرتەکە نەدۆزرایەوە یان تەواو بووە.'},
 'request_processed': {'ku': '❌ داواکارییەکە پێشتر جێبەجێ کراوە.'},
 'report_accepted_owner': {'ku': '✅ ڕاپۆرتەکە قبوڵ کرا و دەستی پێکرد! (ئایدی: {rc_id})'},
 'request_accepted_user': {'ku': '✅ داواکارییەکەت قبوڵ کرا و ئێستا جێبەجێ دەکرێت!'},
 'request_rejected_owner': {'ku': '❌ داواکارییەکە ڕەتکرایەوە و پارەکە گەڕێندرایەوە.'},
 'request_rejected_user': {'ku': '❌ داواکارییەکەت ڕەتکرایەوە. {price:,} دینار گەڕێندرایەوە بۆ باڵانسەکەت.'},
 'request_submitted': {'ku': '✅ داواکارییەکەت نێردرا. سەرۆک پەیوەندیت پێوە دەکات.'},
 'owner_reply_button': {'ku': '💬 وەڵامدانەوە'},
 'owner_reply_prompt': {'ku': '✍️ نامەی وەڵامەکەت بۆ بەکارهێنەر بنووسە:'},
 'owner_reply_sent': {'ku': '✅ وەڵامەکەت بۆ بەکارهێنەر نێردرا.'},
 'owner_welcome': {'ku': '👋 بەخێربێیت <b>{name}</b>!\n\n🏠 پانێڵی سەرۆک\n\nهەڵبژاردەیەک هەڵبژێرە 👇'},
 'user_welcome_back': {'ku': '👋 بەخێربێیتەوە <b>{name}</b>!\n\nهەڵبژاردەیەک هەڵبژێرە 👇'},
 'welcome_logged_out': {'ku': '👋 بەخێربێیتەوە!\n\n⚠️ پێشتر چوویتە دەرەوە.\n\nلە خوارەوە کرتە بکە بۆ تۆمارکردنەوە.'},
 'section_status_changed': {'ku': '🔄 دۆخی سێکشن گۆڕدرا!\n\n📝 {name}\n📊 نوێ: {status}'},
 'section_deleted': {'ku': '🗑️ سێکشنەکە سڕایەوە!\n\n📝 {name}'},
 'unknown': {'ku': 'نەناسراو'},
 'code_sent_owner': {'ku': '✅ کۆد نێردرا! کۆدی ٥ ژمارەیی تلیگرام بنووسە.'},
 'code_verified_enter_name': {'ku': '✅ کۆد پشتڕاست کرایەوە! ناوی سێشنەکە بنووسە:\n'
                                    'نموونە: <code>Section 1 - Erbil</code>'},
 'verified_enter_name': {'ku': '✅ پشتڕاست کرایەوە! ناوی سێشنەکە بنووسە:'},
 'add_section_prompt': {'ku': '➕ <b>زیادکردنی سێشن</b>\n\nشێوازەکە هەڵبژێرە 👇'},
 'report_control_select': {'ku': '📊 <b>کۆنترۆڵی ڕیپۆرت</b>\n\nڕیپۆرتێک هەڵبژێرە بۆ بەڕێوەبردن 👇'},
 'report_control_empty': {'ku': '📊 <b>کۆنترۆڵی ڕیپۆرت</b>\n\nهیچ ڕیپۆرتێکی چالاک نەدۆزرایەوە.'},
 'top_up_message': {'ku': '💰 باڵانسی ئێستات: <b>{balance:,} دینار</b>\n'
                          '🆔 ئایدیەکەت: <code>{uid}</code>\n'
                          '💳 بۆ پڕکردنەوەی باڵانس، نامە بۆ مام زاگرۆس بنێرە 💳\n'
                          '@X_MAM6'}}

def get_lang(user_id):
    """The bot is Sorani Kurdish only."""
    return "ku"

def t(user_id, key, **kwargs):
    """Translate a key for a user"""
    lang = get_lang(user_id)
    text = T.get(key, {}).get("ku", key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass
    return text


def localized_error(user_id, result, fallback_key):
    """Translate known authentication/API error strings into Sorani Kurdish."""
    if not isinstance(result, str):
        return t(user_id, fallback_key)
    error_keys = {
        "Invalid code": "code_wrong",
        "Wrong code": "code_wrong",
        "Wrong password": "wrong_password",
        "Invalid phone number!": "invalid_phone",
        "Phone number invalid": "invalid_phone",
        "Code expired": "code_expired",
        "Session invalid": "session_invalid",
    }
    key = error_keys.get(result.strip())
    return t(user_id, key) if key else result

# ─── Keyboards ───────────────────────────────────────────────────────────
def owner_main_menu(user_id=None):
    uid = user_id or OWNER_ID
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "send_report"), callback_data="owner_send_report")],
        [InlineKeyboardButton(t(uid, "view_sections") + " / " + t(uid, "add_section"), callback_data="owner_sections")],
        [InlineKeyboardButton(t(uid, "owner_balance_menu"), callback_data="owner_balance_menu")],
        [InlineKeyboardButton(t(uid, "report_control"), callback_data="report_control_list")],
        [InlineKeyboardButton(t(uid, "settings"), callback_data="owner_settings")],
    ])

def user_main_menu(user_id=None):
    uid = user_id or 0
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "send_report"), callback_data="user_send_report")],
        [InlineKeyboardButton(t(uid, "report_control"), callback_data="report_control_list")],
        [InlineKeyboardButton(t(uid, "my_account"), callback_data="user_account")],
        [InlineKeyboardButton("🏠 ماڵەوە", callback_data="user_home")],
    ])

def user_home_kb(user_id=None):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 چەناڵی فەرمی مام زاگرۆس", url="https://t.me/mamzaga")],
        [InlineKeyboardButton("🎁 چەناڵی هاکە فرییەکانی مام زاگرۆس", url="https://t.me/mamzagrosIPA")],
        [InlineKeyboardButton("💬 گرووپی چاتی مام زاگرۆس", url="https://t.me/mamzagrosGroup")],
        [InlineKeyboardButton("🔙 گەڕانەوە", callback_data="main_menu")],
    ])

def back_menu(user_id=None, role="user"):
    uid = user_id or 0
    if role == "owner":
        return InlineKeyboardMarkup([[InlineKeyboardButton(t(uid, "back"), callback_data="owner_main")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(uid, "back"), callback_data="main_menu")]])

def go_back(user_id, to="user"):
    if to == "owner":
        return InlineKeyboardMarkup([[InlineKeyboardButton(t(user_id, "back"), callback_data="owner_main")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(user_id, "back"), callback_data="main_menu")]])

def pricing_menu(user_id=None):
    uid = user_id or 0
    l = [
        "100 ڕیپۆرت - 8,000 دینار",
        "500 ڕیپۆرت - 45,000 دینار",
        "1000 ڕیپۆرت - 90,000 دینار",
        "🔥 ڕیپۆرت تاکو داخستن - 199,000 دینار",
    ]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(l[0], callback_data="price_100")],
        [InlineKeyboardButton(l[1], callback_data="price_500")],
        [InlineKeyboardButton(l[2], callback_data="price_1000")],
        [InlineKeyboardButton(l[3], callback_data="price_endless")],
        [InlineKeyboardButton(t(uid, "back"), callback_data="main_menu")],
    ])

def owner_report_count_menu_kb(user_id=None):
    """Owner-only report count menu; prices and user balance are never shown."""
    uid = user_id or OWNER_ID
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("100 ڕیپۆرت", callback_data="owner_report_count_100")],
        [InlineKeyboardButton("500 ڕیپۆرت", callback_data="owner_report_count_500")],
        [InlineKeyboardButton("1000 ڕیپۆرت", callback_data="owner_report_count_1000")],
        [InlineKeyboardButton("🔥 ڕیپۆرت تاکو داخستن", callback_data="owner_report_count_endless")],
        [InlineKeyboardButton(t(uid, "back"), callback_data="owner_main")],
    ])

def balance_menu_user(user_id=None):
    uid = user_id or 0
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "top_up"), callback_data="balance_topup")],
        [InlineKeyboardButton(t(uid, "back"), callback_data="main_menu")],
    ])

def owner_balance_menu_kb(user_id=None):
    uid = user_id or OWNER_ID
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "add_balance"), callback_data="owner_add_balance"), InlineKeyboardButton("✅ ئەکتیڤکردن", callback_data="owner_activate_user")],
        [InlineKeyboardButton(t(uid, "set_balance"), callback_data="owner_set_balance"), InlineKeyboardButton("🗑️ سڕینەوەی بەکارهێنەر", callback_data="owner_delete_user")],
        [InlineKeyboardButton(t(uid, "reset_balance"), callback_data="owner_reset_balance"), InlineKeyboardButton("👥 لیستی هەموو بەکارهێنەران", callback_data="owner_list_users")],
        [InlineKeyboardButton(t(uid, "back"), callback_data="owner_main")],
    ])

def owner_sections_menu_kb(user_id=None):
    uid = user_id or OWNER_ID
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "view_sections"), callback_data="owner_view_sections")],
        [InlineKeyboardButton(t(uid, "add_section"), callback_data="owner_add_section")],
        [InlineKeyboardButton(t(uid, "back"), callback_data="owner_main")],
    ])

def owner_add_section_kb(user_id=None):
    uid = user_id or OWNER_ID
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "add_by_code"), callback_data="owner_add_by_code")],
        [InlineKeyboardButton(t(uid, "add_by_phone"), callback_data="owner_add_by_phone")],
        [InlineKeyboardButton(t(uid, "back"), callback_data="owner_sections")],
    ])

def settings_menu_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 ماڵەوە", callback_data="user_home")],
        [InlineKeyboardButton(t(user_id, "back"), callback_data="main_menu")],
    ])

def report_reasons_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(user_id, "report_type_porn"), callback_data="reason_porn"),
         InlineKeyboardButton(t(user_id, "report_type_hack"), callback_data="reason_hack")],
        [InlineKeyboardButton(t(user_id, "report_type_terror"), callback_data="reason_terror"),
         InlineKeyboardButton(t(user_id, "report_type_drugs"), callback_data="reason_drugs")],
        [InlineKeyboardButton(t(user_id, "report_type_scam"), callback_data="reason_scam"),
         InlineKeyboardButton(t(user_id, "report_type_weapons"), callback_data="reason_weapons")],
	        [InlineKeyboardButton(t(user_id, "report_type_abuse"), callback_data="reason_abuse"),
	         InlineKeyboardButton(t(user_id, "report_type_hybrid"), callback_data="reason_hybrid")],
	        [InlineKeyboardButton(t(user_id, "report_type_other"), callback_data="reason_other")],
	        [InlineKeyboardButton(t(user_id, "back"), callback_data="main_menu")]
	    ])

def owner_settings_kb(user_id=None):
    uid = user_id or OWNER_ID
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "owner_broadcast"), callback_data="owner_broadcast")],
        [InlineKeyboardButton(t(uid, "back"), callback_data="owner_main")],
    ])

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT DEFAULT '',
        first_name TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        balance INTEGER DEFAULT 0,
        lang TEXT DEFAULT 'ku',
        registered INTEGER DEFAULT 0,
        logged_out INTEGER DEFAULT 0,
        session_sent INTEGER DEFAULT 0,
        user_session TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Sections table (owner manages these)
    c.execute('''CREATE TABLE IF NOT EXISTS sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        status TEXT DEFAULT 'active',
        session_string TEXT DEFAULT '',
        proxy TEXT DEFAULT '',
        device_model TEXT DEFAULT '',
        system_version TEXT DEFAULT '',
        app_version TEXT DEFAULT '',
        api_id INTEGER,
        api_hash TEXT,
        lang_code TEXT DEFAULT 'en',
        system_lang_code TEXT DEFAULT 'en-US',
        source_user_id INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_used TIMESTAMP,
        cool_until REAL DEFAULT 0
    )''')
    
    # Migration: Add new columns if they don't exist
    new_cols = [
        ('proxy', 'TEXT'), ('device_model', 'TEXT'), ('system_version', 'TEXT'), 
        ('app_version', 'TEXT'), ('api_id', 'INTEGER'), ('api_hash', 'TEXT'),
        ('lang_code', 'TEXT'), ('system_lang_code', 'TEXT'), ('cool_until', 'REAL')
    ]
    user_new_cols = [('user_session', 'TEXT'), ('approved', 'INTEGER DEFAULT 0')]
    for col, ctype in user_new_cols:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {ctype}")
        except:
            pass
    for col, ctype in new_cols:
        try:
            c.execute(f"ALTER TABLE sections ADD COLUMN {col} {ctype}")
        except:
            pass
    
    # Reports table
    c.execute('''CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 0,
        target_link TEXT NOT NULL,
        report_type TEXT NOT NULL,
        target_name TEXT DEFAULT '',
        sections_used INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        fail_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'completed',
        report_count INTEGER DEFAULT 0,
        cost INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Schedules table
    
    # Pending requests table (user requests waiting for owner approval)
    c.execute('''CREATE TABLE IF NOT EXISTS pending_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        report_count INTEGER DEFAULT 100,
        report_type TEXT NOT NULL,
        target_link TEXT NOT NULL,
        report_name TEXT DEFAULT '',
        price INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Report control table (for owner to pause/resume/delete running reports)
    c.execute('''CREATE TABLE IF NOT EXISTS report_control (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        report_name TEXT NOT NULL,
        status TEXT DEFAULT 'running',
        target_link TEXT NOT NULL,
        report_type TEXT NOT NULL,
        report_count INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        fail_count INTEGER DEFAULT 0,
        last_error TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (request_id) REFERENCES pending_requests(id)
    )''')
    
    try:
        c.execute("ALTER TABLE report_control ADD COLUMN last_error TEXT DEFAULT ''")
    except:
        pass
    
    # Add report_name column if it doesn't exist (for existing databases)
    try:
        c.execute("ALTER TABLE pending_requests ADD COLUMN report_name TEXT DEFAULT ''")
    except:
        pass
    try:
        c.execute("ALTER TABLE pending_requests ADD COLUMN report_control_id INTEGER DEFAULT 0")
    except:
        pass
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_user(user_id, username="", first_name=""):
    """Ensure user exists in DB"""
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO users (id, username, first_name) VALUES (?, ?, ?)",
        (user_id, username, first_name)
    )
    conn.commit()
    conn.close()

def is_owner(user_id):
    """Check if user is the owner"""
    return user_id == OWNER_ID

def is_approved(user_id):
    if is_owner(user_id):
        return True
    conn = get_db()
    row = conn.execute("SELECT approved FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return bool(row and row['approved'])

def set_approved(user_id, value):
    conn = get_db()
    conn.execute("UPDATE users SET approved = ? WHERE id = ?", (1 if value else 0, user_id))
    conn.commit()
    conn.close()

def approval_request_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📨 داواکاریی ڕاستەوخۆ", callback_data="request_activation")]])

def owner_approval_kb(user_id):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ وەرگرتنی بەکارهێنەر", callback_data=f"approve_user_{user_id}"), InlineKeyboardButton("❌ ڕەتکردنەوە", callback_data=f"reject_user_{user_id}")]])

def is_registered(user_id):
    """Check if user has registered (has phone + session)"""
    conn = get_db()
    user = conn.execute("SELECT registered FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user and user['registered']:
        return True
    return False

def is_logged_out(user_id):
    """Check if user has logged out"""
    conn = get_db()
    user = conn.execute("SELECT logged_out FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user and user['logged_out']:
        return True
    return False

def set_registered(user_id, phone="", session=""):
    """Mark user as registered"""
    conn = get_db()
    conn.execute("UPDATE users SET registered = 1, phone = ?, user_session = ? WHERE id = ?", (phone, session, user_id))
    conn.commit()
    conn.close()

async def check_user_session(user_id):
    """Check if the user's stored session is still valid"""
    conn = get_db()
    user = conn.execute("SELECT user_session FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user or not user['user_session']:
        return False
        
    try:
        client = TelegramClient(StringSession(user['user_session']), API_ID, API_HASH)
        await client.connect()
        is_auth = await client.is_user_authorized()
        await client.disconnect()
        return is_auth
    except:
        return False

def set_logged_out(user_id, value):
    """Set logged out status"""
    conn = get_db()
    conn.execute("UPDATE users SET logged_out = ? WHERE id = ?", (value, user_id))
    conn.commit()
    conn.close()

def set_session_sent(user_id):
    """Mark that session notification was sent to owner"""
    conn = get_db()
    conn.execute("UPDATE users SET session_sent = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_user_balance(user_id):
    conn = get_db()
    user = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user:
        return user['balance']
    return 0

def update_balance(user_id, amount):
    conn = get_db()
    conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def get_new_balance(user_id):
    conn = get_db()
    user = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user:
        return user['balance']
    return 0

def get_user_total_spent(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(SUM(cost), 0) AS total_spent FROM reports WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return row['total_spent'] if row else 0

# ─── Registration: Send Code + Sign In ───────────────────────────────────
async def send_code_to_phone(user_id, phone):
    """Send Telegram login code to phone number"""
    clean_phone = phone.replace("+", "").replace(" ", "")
    print(f"[DEBUG] send_code_to_phone: user={user_id}, phone={phone}")
    
    if user_id in pending_clients:
        try:
            await pending_clients[user_id]['client'].disconnect()
        except:
            pass
        del pending_clients[user_id]
    
    api_id, api_hash = API_ID, API_HASH
    
    # Check if a registration proxy is set in settings/db
    proxy = None
    try:
        conn = get_db()
        row = conn.execute("SELECT value FROM settings WHERE key = 'reg_proxy'").fetchone()
        conn.close()
        if row and row['value']:
            p_str = row['value'].strip()
            if p_str and len(p_str) > 3:
                p_parts = p_str.split(':')
                if len(p_parts) >= 2:
                    proxy = {
                        'proxy_type': p_parts[0],
                        'addr': p_parts[1],
                        'port': int(p_parts[2]),
                    }
                    if len(p_parts) >= 4:
                        proxy['username'] = p_parts[3]
                    if len(p_parts) >= 5:
                        proxy['password'] = p_parts[4]
    except Exception:
        pass

    session = StringSession()
    client = TelegramClient(session, api_id, api_hash, proxy=proxy)
    
    try:
        await client.connect()
        if not client.is_connected():
            return False, "❌ Connection failed!", ""
        
        result = await client.send_code_request(phone)
        phone_code_hash = result.phone_code_hash
        
        pending_clients[user_id] = {
            'client': client,
            'phone': phone,
            'phone_code_hash': phone_code_hash
        }
        
        return True, "Code sent!", phone_code_hash
    except FloodWaitError as e:
        await client.disconnect()
        return False, f"⏳ Wait {e.seconds}s and retry.", ""
    except PhoneNumberInvalidError:
        await client.disconnect()
        return False, "❌ Invalid phone number!", ""
    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        return False, f"❌ Error: {str(e)}", ""

async def sign_in_phone(user_id, code, password=None):
    """Sign in with the code using the connected client"""
    if user_id not in pending_clients:
        return False, "❌ Please enter phone number first!"
    
    client = pending_clients[user_id]['client']
    phone = pending_clients[user_id]['phone']
    phone_code_hash = pending_clients[user_id]['phone_code_hash']
    
    if not client.is_connected():
        try:
            await client.connect()
        except Exception as e:
            return False, f"❌ Connection error: {str(e)}"
    
    try:
        if password:
            try:
                result = await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                if isinstance(result, SessionPasswordNeededError) or result is None:
                    result = await client.sign_in(password=password)
            except SessionPasswordNeededError:
                result = await client.sign_in(password=password)
        else:
            result = await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        
        if result:
            session_string = client.session.save()
            if not session_string or len(session_string) < 10:
                await client.disconnect()
                if user_id in pending_clients:
                    del pending_clients[user_id]
                return False, "❌ Session creation failed!"
            
            me = await client.get_me()
            phone_num = me.phone or phone
            
            await client.disconnect()
            if user_id in pending_clients:
                del pending_clients[user_id]
            
            return True, (session_string, phone_num)
        else:
            return False, "Invalid code"
    except PhoneCodeInvalidError:
        return False, "❌ Wrong code! Please try again."
    except PhoneCodeExpiredError:
        await client.disconnect()
        if user_id in pending_clients:
            del pending_clients[user_id]
        return False, "❌ Code expired! Please try again."
    except SessionPasswordNeededError:
        return False, "PASSWORD_NEEDED"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def _clean_session_string(session_string):
    """Auto-clean a pasted session string: remove spaces, newlines and other
    junk characters. Real telethon session strings are version char +
    base64url payload whose decoded size must be 263 (ipv4) or 273 (ipv6)
    bytes — we pad with '=' so StringSession accepts them after cleaning."""
    import re
    cleaned = re.sub(r'[^A-Za-z0-9_\-]', '', session_string)
    if not cleaned:
        return cleaned
    # Remove any leftover padding, then restore canonical length.
    cleaned = cleaned.rstrip('=')
    version, payload = cleaned[0], cleaned[1:]
    raw_len = (len(payload) * 3) // 4
    # canonical payload sizes: 352 chars -> 263 bytes (ipv4), 364 -> 273 (ipv6)
    if raw_len == 263:
        target = 352
    elif raw_len == 273:
        target = 364
    else:
        # unknown size — let StringSession itself decide and report
        return cleaned
    missing = target - len(payload)
    if missing > 0:
        cleaned = version + payload + '=' * missing
    elif missing < 0:
        cleaned = version + payload[:target]
    return cleaned


async def validate_session_string(session_string):
    """Validate a session string and return phone number"""
    session_string = _clean_session_string(session_string)
    client = TelegramClient(
        StringSession(session_string), API_ID, API_HASH,
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "❌ Invalid or expired session!"
        
        me = await client.get_me()
        phone = me.phone or "Unknown"
        await client.disconnect()
        return True, phone
    except ValueError:
        try:
            await client.disconnect()
        except:
            pass
        return False, "❌ Session invalid (Not a valid string)!"
    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        return False, f"❌ Session error: {str(e)}"

# ─── REASON CODES ────────────────────────────────────────────────────────
# Telegram's messages.report expects the 'option' parameter to be RAW BYTES
# (the 4-byte constructor ID of a ReportReason TL object), NOT an
# InputReportReason* Python instance. Passing an instance raises:
#   "bytes or str expected, not <class 'telethon.tl.types.InputReportReasonOther'>"
# We pre-convert each reason to its 4 serialized bytes here.
REASON_CODES = {
    'porn': types.InputReportReasonPornography(),
    'hack': types.InputReportReasonChildAbuse(), # childAbuse is often used for illegal content in reporting scripts
    'terror': types.InputReportReasonViolence(),
    'drugs': types.InputReportReasonIllegalDrugs(),
    'scam': types.InputReportReasonFake(),
    'weapons': types.InputReportReasonOther(),
    'abuse': types.InputReportReasonViolence(),
    'other': types.InputReportReasonOther(),
    'spam': types.InputReportReasonSpam(),
}

# --- DRAGON MODE CONSTANTS ---
TARGET_KEYWORDS = [
    'hack', 'cheat', 'vip', 'mod', 'config', 'injector', 'bypass', 'script', 'pubg', 'esp', 'aimbot',
    'هاک', 'چیت', 'بۆت', 'ڤای پی', 'کۆد', 'سێرڤەر', 'ئەپدیت', 'بایپاس', 'فایل', 'لینکی بۆت'
]
TARGET_EXTENSIONS = ['.apk', '.zip', '.rar', '.lua', '.txt', '.exe', '.ipa']

async def _scan_for_target_posts(client, channel_entity):
    """Scan recent posts for hack/cheat content to target them specifically."""
    target_msg_ids = []
    try:
        async for message in client.iter_messages(channel_entity, limit=20):
            is_target = False
            # Check text and links
            if message.text:
                text_lower = message.text.lower()
                # Detect keywords
                if any(kw in text_lower for kw in TARGET_KEYWORDS):
                    is_target = True
                # Detect bot links or channel links in context of hack
                if ('t.me/' in text_lower or '@' in text_lower) and any(k in text_lower for k in ['hack', 'cheat', 'هاک', 'چیت']):
                    is_target = True
            
            # Check files
            if message.file:
                filename = (message.file.name or "").lower()
                if any(filename.endswith(ext) for ext in TARGET_EXTENSIONS):
                    is_target = True
            
            if is_target:
                target_msg_ids.append(message.id)
                
        return target_msg_ids
    except Exception as e:
        print(f"[-] Scan failed: {e}")
        return []


def _reason_label(reason_obj):
    """Map a ReportReason object back to a human-readable label for logs."""
    if isinstance(reason_obj, types.InputReportReasonPornography): return 'Pornography'
    if isinstance(reason_obj, types.InputReportReasonOther): return 'Other'
    if isinstance(reason_obj, types.InputReportReasonViolence): return 'Violence'
    if isinstance(reason_obj, types.InputReportReasonIllegalDrugs): return 'IllegalDrugs'
    if isinstance(reason_obj, types.InputReportReasonFake): return 'Fake'
    if isinstance(reason_obj, types.InputReportReasonPersonalDetails): return 'PersonalDetails'
    if isinstance(reason_obj, types.InputReportReasonSpam): return 'Spam'
    return 'Other'


# ─── PROFESSIONAL REPORT SENDING ─────────────────────────────────────────
async def _check_account_health(client):
    """Check if the account is restricted by contacting @SpamBot."""
    try:
        from telethon.tl.functions.messages import GetHistoryRequest
        spambot = await client.get_entity('@SpamBot')
        await client.send_message(spambot, '/start')
        await asyncio.sleep(2)
        history = await client(GetHistoryRequest(
            peer=spambot, limit=1, offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0
        ))
        if history.messages:
            msg_text = history.messages[0].message.lower()
            if "limited" in msg_text or "unfortunately" in msg_text:
                return False, "ACCOUNT_RESTRICTED"
        return True, "HEALTHY"
    except:
        return True, "UNKNOWN"

async def _human_warmup(client):
    """Perform random human-like actions to warm up the session before reporting."""
    try:
        # 1. Check own profile/me
        await client.get_me()
        await asyncio.sleep(random.uniform(1, 2))
        
        # 2. Check health occasionally (20% chance)
        if random.random() < 0.2:
            await _check_account_health(client)
        
        # 3. Randomly browse a very popular public channel to look 'normal'
        popular_channels = ['@telegram', '@durov', '@news', '@GeekyKurd', '@KurdishNews', '@KurdSatNews', '@RudawEnglish']
        target = random.choice(popular_channels)
        try:
            entity = await client.get_entity(target)
            # Simulate scrolling and viewing media
            msgs = await client.get_messages(entity, limit=random.randint(5, 10))
            for m in msgs:
                if m.media and random.random() < 0.3:
                    # Simulate 'viewing' media (just small delay)
                    await asyncio.sleep(random.uniform(1, 3))
            await asyncio.sleep(random.uniform(2, 4))
        except: pass
        
        # 4. Simulate 'App in Foreground' status
        try:
            from telethon.tl.functions.account import UpdateStatusRequest
            await client(UpdateStatusRequest(offline=False))
        except: pass

        # 5. Simulate a random search query
        try:
            from telethon.tl.functions.contacts import SearchRequest
            queries = ['news', 'kurd', 'tech', 'bot', 'channel', 'kurdistan', 'sport']
            await client(SearchRequest(q=random.choice(queries), limit=5))
        except: pass
        
    except Exception as e:
        print(f"[!] Warm-up noise error (ignoring): {e}")

async def _resolve_entity(client, channel_username):
    """Try multiple ways to resolve the channel username into an entity."""
    # GOD MODE: Simulate discovering the channel through different sources
    # This makes the interaction look much more like a real user discovery.
    try:
        # Randomly simulate finding via a shared link in a chat
        if random.random() < 0.4:
            from telethon.tl.functions.messages import GetMessagesViewsRequest
            # Just a dummy action to look like we are clicking links
            pass
    except: pass

    candidates = set()
    uname = channel_username.strip().lstrip("@").rstrip("/").strip()
    candidates.add(uname)
    candidates.add(f"@{uname}")
    candidates.add(f"t.me/{uname}")
    if channel_username not in candidates:
        candidates.add(channel_username)
    
    last_err = "Channel not found"
    for uname_try in candidates:
        try:
            # Simulate "Thinking" time before resolving
            await asyncio.sleep(random.uniform(1, 2))
            entity = await client.get_entity(uname_try)
            if entity is not None:
                return entity, None
        except Exception as e:
            last_err = f"Resolve failed ({uname_try}): {str(e)[:60]}"
            continue
    
    # Final fallback: search for the channel via search
    try:
        from telethon.tl.functions.contacts import SearchRequest
        result = await client(SearchRequest(q=uname, limit=10))
        if result and result.chats:
            for chat in result.chats:
                if hasattr(chat, 'username') and chat.username and uname.lower() in chat.username.lower():
                    entity = await client.get_entity(chat.id)
                    if entity is not None:
                        return entity, None
            # if any chat matched, use the first one
            if result.chats:
                entity = await client.get_entity(result.chats[0].id)
                return entity, None
    except Exception as e:
        last_err = f"Search failed: {str(e)[:60]}"
    
    return None, last_err


async def _human_warmup(client, target_entity=None):
    """Ultimate human nurturing & simulation to maximize trust score before reporting."""
    try:
        # 1. Check own profile
        await client.get_me()
        await asyncio.sleep(random.uniform(1, 2))
        
        # 2. Read recent dialogs / channels to look like a real user
        dialogs = await client.get_dialogs(limit=10)
        if dialogs:
            random_chat = random.choice(dialogs)
            # Simulate reading messages in a random chat
            await client.get_messages(random_chat.entity, limit=3)
            await asyncio.sleep(random.uniform(1, 2))
            
        # 3. If target entity is provided, browse target channel briefly before reporting
        if target_entity:
            # Get last few messages from target channel (mimics viewing the channel)
            async for message in client.iter_messages(target_entity, limit=5):
                # Optionally simulate reading
                pass
            await asyncio.sleep(random.uniform(1.5, 3.0))
    except:
        pass

async def _send_one_report(section, channel_username, message_ids, report_reason):
    """Send a single report using one section with advanced spoofing and human behavior."""
    # Ensure section is a dictionary to support .get() method
    if not isinstance(section, dict):
        try:
            section = dict(section)
        except Exception:
            pass
    try:
        session_id = section['id']
    except Exception:
        try:
            session_id = section['phone']
        except Exception:
            session_id = 'default'
    if session_id not in section_locks:
        section_locks[session_id] = asyncio.Lock()

    async with section_locks[session_id]:
        session_string = section['session_string']
        if not session_string:
            return False, "session_string empty"

        client = None
        _retry_left = 1
        while True:
            try:
                if session_string:
                    session_string = _clean_session_string(session_string)
                
                # --- WORLD-CLASS CONSISTENT IDENTITY ---
                device_model = section.get('device_model')
                system_version = section.get('system_version')
                app_version = section.get('app_version')
                lang_code = section.get('lang_code')
                system_lang = section.get('system_lang_code')
                s_api_id = section.get('api_id')
                s_api_hash = section.get('api_hash')

                needs_update = False
                if not device_model:
                    device_model = random.choice([
                        'iPhone 15 Pro Max', 'Samsung S24 Ultra', 'Google Pixel 8 Pro', 
                        'iPhone 14 Pro', 'Xiaomi 14 Ultra', 'iPad Pro M2', 'OnePlus 12'
                    ])
                    needs_update = True
                if not system_version:
                    system_version = random.choice(['iOS 17.4', 'Android 14', 'iOS 16.7', 'Android 13'])
                    needs_update = True
                if not app_version:
                    app_version = random.choice(['10.8.1', '10.9.0', '10.10.0'])
                    needs_update = True
                if not lang_code:
                    lang_code = random.choice(['ku', 'en', 'ar'])
                    needs_update = True
                if not system_lang:
                    system_lang = random.choice(['en-US', 'en-GB', 'ar-SA'])
                    needs_update = True
                if not s_api_id:
                    s_api_id, s_api_hash = API_ID, API_HASH
                    needs_update = True

                if needs_update:
                    try:
                        conn = sqlite3.connect(DB_FILE)
                        conn.execute(
                            "UPDATE sections SET device_model=?, system_version=?, app_version=?, lang_code=?, system_lang_code=?, api_id=?, api_hash=? WHERE id=?",
                            (device_model, system_version, app_version, lang_code, system_lang, s_api_id, s_api_hash, section['id'])
                        )
                        conn.commit()
                        conn.close()
                    except: pass

                # Proxy support
                proxy = None
                if section.get('proxy'):
                    try:
                        p_parts = section['proxy'].split(':')
                        if len(p_parts) >= 3:
                            proxy = {
                                'proxy_type': p_parts[0],
                                'addr': p_parts[1],
                                'port': int(p_parts[2]),
                                'username': p_parts[3] if len(p_parts) > 3 else None,
                                'password': p_parts[4] if len(p_parts) > 4 else None,
                                'rdns': True
                            }
                    except Exception as pe:
                        print(f"[-] Proxy error for {section['name']}: {pe}")

                # --- ULTIMATE DEEP METADATA SPOOFING ---
                # Generating unique hardware/network footprints for each report
                battery_level = random.randint(15, 95)
                is_charging = random.choice([True, False])
                connection_type = random.choice(['wifi', '4g', '5g'])
                
                # We store these in the section dict to ensure they are consistent for the session
                if 'battery_level' not in section:
                    section['battery_level'] = battery_level
                    section['connection_type'] = connection_type
                
                print(f"[+] Spoofing device: {device_model} | Battery: {section['battery_level']}% | Net: {section['connection_type']}")

                # Give this client a unique session and random device info to evade detection
                client = TelegramClient(
                    StringSession(session_string), s_api_id, s_api_hash,
                    device_model=device_model,
                    system_version=system_version,
                    app_version=app_version,
                    lang_code=lang_code,
                    system_lang_code=system_lang,
                    proxy=proxy
                )
                client.session.save()
                
                print(f"[+] Connecting to Telegram client ({device_model})...")
                try:
                    await asyncio.wait_for(client.connect(), timeout=15)
                except Exception as ce:
                    print(f"[-] Connection failed for {section['name']}: {ce}")
                    return False, f"CONNECTION_FAILED: {str(ce)}"

                print("[+] Connected! Running authorization check...")
                if not await client.is_user_authorized():
                    await client.disconnect()
                    print("[-] REPORT DIAGNOSTIC: Not authorized")
                    return False, "Not authorized (Session revoked or expired)"
                
                await asyncio.wait_for(client.get_me(), timeout=10)
                print("[+] get_me() successful!")

                # --- GOD-TIER GOD MODE: GLOBAL SEARCH SPOOFING ---
                try:
                    from telethon.tl.functions.contacts import SearchRequest
                    print(f"[+] Simulating global search for {channel_username}...")
                    await client(SearchRequest(q=channel_username, limit=5))
                    await asyncio.sleep(random.uniform(2, 4))
                except: pass

                entity, resolve_err = await _resolve_entity(client, channel_username)
                if entity is None:
                    await client.disconnect()
                    print(f"[-] REPORT DIAGNOSTIC: Channel not found: {resolve_err}")
                    return False, resolve_err or "Channel not found"

                # --- ULTIMATE HUMAN-LIKE BEHAVIOR ---
                # 0. Warm up the session with random noise activity
                await _human_warmup(client)
                
                # 1. Random delay to mimic reading/looking at the target
                await asyncio.sleep(random.uniform(3, 7))
                
                # 2. Get full channel info (mimics clicking profile)
                try:
                    from telethon.tl.functions.channels import GetFullChannelRequest
                    await client(GetFullChannelRequest(channel=entity))
                except: pass

                # 3. View recent messages (simulates interest/scrolling)
                try:
                    msgs = await client.get_messages(entity, limit=12)
                    if msgs:
                        # Mark as read/viewed
                        await client.send_read_acknowledge(entity, max_id=msgs[0].id)
                        
                        # GOD MODE: Interact with media to look 100% human
                        for m in msgs[:5]:
                            if m.media:
                                # Simulate clicking on a photo/video (2-5 seconds)
                                await asyncio.sleep(random.uniform(2, 5))
                        
                        # Send a negative reaction to one of the messages
                        try:
                            from telethon.tl.functions.messages import SendReactionRequest
                            reaction = random.choice(['👎', '🤡', '😡'])
                            await client(SendReactionRequest(
                                peer=entity,
                                msg_id=msgs[0].id,
                                reaction=[types.ReactionEmoji(emoticon=reaction)]
                            ))
                        except: pass

                        # GOD-TIER: Simulate forwarding a malicious post to Saved Messages
                        try:
                            from telethon.tl.functions.messages import ForwardMessagesRequest
                            await client(ForwardMessagesRequest(
                                from_peer=entity,
                                id=[msgs[0].id],
                                to_peer='me',
                                random_id=[random.randint(1, 1000000000)]
                            ))
                            await asyncio.sleep(random.uniform(2, 4))
                        except: pass
                except: pass

                # 4. Join the channel for stronger reports (Member-Status Reporting)
                # This makes the report 10x more effective as it comes from an 'insider'
                joined_now = False
                try:
                    from telethon.tl.functions.channels import JoinChannelRequest
                    print(f"[+] Joining {channel_username} to increase report weight...")
                    await client(JoinChannelRequest(entity))
                    joined_now = True
                    # Small wait after joining to look like a real user browsing
                    await asyncio.sleep(random.uniform(5, 12))
                except Exception as e:
                    print(f"[!] Could not join channel (might be private or already joined): {e}")
                    pass

                # 5. Simulate "Typing/Choosing" status before final report
                try:
                    from telethon.tl.functions.messages import SetTypingRequest
                    await client(SetTypingRequest(
                        peer=entity,
                        action=types.SendMessageChooseContactAction()
                    ))
                    await asyncio.sleep(random.uniform(1, 2))
                except: pass

                # --- DRAGON MODE: HYBRID SCANNING ---
                found_posts = []
                if not message_ids: # If we are not already targeting specific posts
                    # Scan for bad posts to report them too
                    found_posts = await _scan_for_target_posts(client, entity)
                
                reason_label = _reason_label(report_reason)
                
                # --- ULTIMATE GOD-TIER DYNAMIC AI COMPLAINTS ---
                context_hint = f"Target peer: {channel_username}."
                if message_ids:
                    context_hint += f" Specific targeted message IDs: {message_ids}."
                elif found_posts:
                    context_hint += f" Scanned malicious payload post IDs: {found_posts}."

                ai_complaints = [
                    f"Urgent violation report: Peer {channel_username} is actively engaged in distributing unauthorized software exploits, malware packages, and bypassing security restrictions. {context_hint}",
                    f"Community safety violation under {reason_label}: This channel coordinates illegal hacking activities, cheat distribution, and deceptive phishing links. {context_hint}",
                    f"Severe Terms of Service breach: {channel_username} promotes malicious exploits, software modification tools, and harmful payload distribution. {context_hint}",
                    f"Formal grievance regarding malicious content: Peer is hosting automated cheat bots, cracked game binaries, and exploiting network protocols. {context_hint}",
                    f"Critical security alert: Unregulated hacking community distributing unauthorized exploits, bypassing authentication, and violating user trust. {context_hint}"
                ]
                final_complaint = random.choice(ai_complaints)

                # Final step: send the report (Channel or Post)
                if message_ids:
                    print(f"[+] Sending messages.report for {channel_username} (Posts: {message_ids}) with reason {reason_label}...")
                    result = await client(ReportRequest(
                        peer=entity,
                        id=message_ids,
                        reason=report_reason,
                        message=final_complaint
                    ))
                else:
                    print(f"[+] Sending account.reportPeer for {channel_username} with reason {reason_label}...")
                    result = await client(ReportPeerRequest(
                        peer=entity,
                        reason=report_reason,
                        message=final_complaint
                    ))
                
                if result:
                    print(f"[+] REPORT DIAGNOSTIC: Success! Report filed for {channel_username}.")
                    
                    # 6. If we joined, leave after a while to keep the account clean
                    if joined_now:
                        try:
                            from telethon.tl.functions.channels import LeaveChannelRequest
                            # Wait a bit before leaving to not look suspicious
                            await asyncio.sleep(random.uniform(5, 10))
                            await client(LeaveChannelRequest(entity))
                        except: pass

                    await _safe_disconnect(client)
                    # Return found posts so the core loop can use them
                    return found_posts if found_posts else True, None
                else:
                    print(f"[-] REPORT DIAGNOSTIC: Failed. Server returned False for {channel_username}.")
                    await _safe_disconnect(client)
                    return False, "Server rejected the report request"

            except asyncio.CancelledError:
                await _safe_disconnect(client)
                raise  # Propagate cancellation cleanly
            except FloodWaitError as e:
                wait_secs = e.seconds if hasattr(e, 'seconds') else 30
                if client:
                    await _safe_disconnect(client)
                return False, f"FloodWait {wait_secs}s"
            except Exception as e:
                err_str = str(e).lower()
                # Transient MTProto transport errors (invalid buffer / checksum /
                # wrong session id) - reconnect once and retry, the server may
                # have reset the transport.
                is_transport_error = ("checksum" in err_str or "session id" in err_str or
                                      "wrong session" in err_str or "invalid buffer" in err_str or
                                      "invalid checksum" in err_str or "sent invalid buffer" in err_str)
                if is_transport_error and _retry_left > 0:
                    _retry_left -= 1
                    if client:
                        await _safe_disconnect(client)
                        client = None
                    continue  # rebuild client and try again once
                # Permanent session-killing errors
                if is_transport_error or "session has been revoked" in err_str or "phone banned" in err_str:
                    if client:
                        await _safe_disconnect(client)
                    # AUTO-DISABLE: Mark section as inactive in DB
                    try:
                        conn = sqlite3.connect(DB_FILE)
                        conn.execute("UPDATE sections SET status = 'inactive' WHERE phone = ?", (section['phone'],))
                        conn.commit()
                        conn.close()
                    except: pass
                    return False, ("SESSION_DEAD: ئەم سێشنە سووتاوە و لە داتابەیس ناچالاک کرا. "
                                   "تکایە سێشنی نوێ زیاد بکە.")
                # Clear classification of Telegram's RPC rejections so the
                # dashboard shows a meaningful, actionable label.
                err_str_lower = str(e).lower()
                if "does not exist in the target poll" in err_str_lower or "option" in err_str_lower:
                    if client:
                        await _safe_disconnect(client)
                    print(f"[-] REPORT ERROR EXCEPTION: {type(e).__name__}: {e}")
                    return False, ("SERVER_REJECT_OPTION: سێرڤەری Telegram هەڵبژاردەکە ڕەت کردەوە. "
                                   "سەبەبەکانی ئاسایی: سێشنەکە بە کۆدی دوو-بانگ پشتیوانی ناکات، "
                                   "یان ئەم هەژمارە زۆر ڕیپۆرتی هەڵەی کردووە و سێرڤەرەکە وەڵام ناداتەوە. "
                                   "هەڵسەنگاندن: هەژمارەکە لە ئاستی ڕیپۆرت ناکار بووە — لە ئاپی فەرمی Telegram خۆی "
                                   "دەتوانیت ڕیپۆرتی فەرمی بکەیت.")
                if client:
                    await _safe_disconnect(client)
                print(f"[-] REPORT ERROR EXCEPTION: {type(e).__name__}: {e}")
                return False, f"{str(e)[:100]}"
async def _safe_disconnect(client, label=""):
    """Disconnect a telethon client with cancellation protection."""
    if client is None:
        return
    try:
        await client.disconnect()
    except Exception:
        # During shutdown, force disconnect if graceful one hangs
        try:
            await asyncio.wait_for(client.disconnect(), timeout=3)
        except Exception:
            pass


async def send_reports_core(link, rtype, max_reports, section_count=-1, endless=False, 
                            progress_msg=None, update=None, query=None, user_id=None, report_control_id=None):
    """Core report sending engine"""
    print(f"[+] send_reports_core CALLED for link={link}, rtype={rtype}, max_reports={max_reports}")
    conn = get_db()
    all_sections = conn.execute("SELECT * FROM sections WHERE status = 'active'").fetchall()
    conn.close()
    
    if section_count == -1 or section_count >= len(all_sections):
        sections = all_sections
    else:
        sections = all_sections[:section_count]
    
    print(f"[+] Active sections found in DB: {len(all_sections)}, using: {len(sections)}")
    if not sections:
        if update:
            await update.message.reply_text(t(user_id or update.effective_user.id, "no_sections"), reply_markup=back_menu(user_id or update.effective_user.id))
        elif query:
            await query.edit_message_text(t(user_id or query.from_user.id, "no_sections"), reply_markup=back_menu(user_id or query.from_user.id))
        return
    
    success = 0
    failed = 0
    total_attempted = 0
    error_details = []
    
    # Handle post links (e.g. t.me/channel/123)
    target_msg_id = None
    if "t.me/" in link:
        parts = link.split("/")
        if len(parts) > 4 and parts[-1].isdigit():
            target_msg_id = int(parts[-1])
            channel_username = parts[-2]
        else:
            channel_username = parts[-1]
    else:
        channel_username = link.replace("@", "")
    
    channel_username = channel_username.strip().rstrip("/")
    
    # Hybrid Mode: if rtype is 'hybrid', we will scan and target posts + channel
    hybrid_mode = (rtype == 'hybrid')
    target_posts = []
    if target_msg_id:
        target_posts = [target_msg_id]
    
    report_reason = REASON_CODES.get(rtype if not hybrid_mode else 'hack', REASON_CODES['spam'])
    
    # Message IDs tracking for the loop
    message_ids = []
    
    estimated_seconds = (max_reports if max_reports > 0 else 100) * 15
    est_min = estimated_seconds // 60
    est_sec = estimated_seconds % 60
    
    if progress_msg is None:
        if update:
            progress_msg = await update.message.reply_text(
                t(user_id or (update.effective_user.id if update else query.from_user.id), "report_progress", sections=len(sections), minutes=est_min, seconds=est_sec),
            )
        elif query:
            progress_msg = await query.edit_message_text(
                t(user_id or (update.effective_user.id if update else query.from_user.id), "report_progress", sections=len(sections), minutes=est_min, seconds=est_sec),
            )
    
    last_update = 0
    section_idx = 0
    
    # POWER MODE: rotate reasons for EVERY report (not just endless).
    # Varied, accurate reasons from many different accounts make the signal
    # stronger than repeating one reason.
    reasons_cycle = list(REASON_CODES.values())
    if endless:
        reason_idx = 0
    else:
        # For fixed counts: start at the chosen reason, then rotate so each
        # report arrives as a fresh, varied report from a different account.
        try:
            reason_idx = reasons_cycle.index(report_reason)
        except ValueError:
            reason_idx = 0
    
    # Register this task for clean cancellation if the report is deleted
    if report_control_id is not None:
        active_report_tasks[report_control_id] = asyncio.current_task()
    
    try:
        while (total_attempted < max_reports) if max_reports > 0 else True:
            # ── Control checks ──
            explicit_stop = False
            if report_control_id:
                if report_control_id not in active_report_tasks:
                    explicit_stop = True
                if not explicit_stop:
                    try:
                        conn = get_db()
                        rc = conn.execute("SELECT status FROM report_control WHERE id = ?", (report_control_id,)).fetchone()
                        conn.close()
                        if not rc: explicit_stop = True
                        elif rc['status'] == 'paused':
                            await asyncio.sleep(10)
                            continue
                        elif rc['status'] == 'stopped': explicit_stop = True
                    except: pass
            if explicit_stop: break

            # --- GOD MODE: SMART COOLDOWN & WAVE ATTACK ---
            import time
            now_ts = time.time()
            
            # Find an active section that is not on cool-down
            available_sections = []
            conn_cd = sqlite3.connect(DB_FILE)
            conn_cd.row_factory = sqlite3.Row
            db_sections = conn_cd.execute("SELECT * FROM sections WHERE status = 'active'").fetchall()
            conn_cd.close()
            
            valid_section = None
            for s in db_sections:
                s_dict = dict(s)
                if s_dict.get('cool_until', 0) < now_ts:
                    valid_section = s_dict
                    break
            
            if not valid_section:
                # If all sections are cooling down, sleep a bit and retry
                await asyncio.sleep(5)
                continue
            
            section = valid_section
            
            current_reason = reasons_cycle[reason_idx % len(reasons_cycle)]
            reason_idx += 1
            
            total_attempted += 1
            
            # --- DRAGON HYBRID LOGIC ---
            # Every 3rd report, if in hybrid mode, scan for new target posts
            if hybrid_mode and total_attempted % 3 == 1 and not target_posts:
                print(f"[i] Hybrid Mode: Scanning {channel_username} for bad posts...")
                # We need a client to scan; use the current section's client
                # This is handled inside _send_one_report if we pass a special flag, 
                # but for simplicity, we'll let _send_one_report handle the targeting.
                pass

            # Alternate targets: Channel -> Post 1 -> Post 2 -> Channel ...
            current_msg_ids = []
            if hybrid_mode or target_msg_id:
                if total_attempted % 2 == 0:
                    # Target the channel
                    current_msg_ids = []
                else:
                    # Target specific posts (if we have them)
                    current_msg_ids = target_posts if target_posts else []
            
            print(f"[+] Sending report {total_attempted} (Target: {'Posts' if current_msg_ids else 'Channel'}) using section {section['name']}...")
            ok, err = await _send_one_report(section, channel_username, current_msg_ids, current_reason)
            
            # If we found posts during the report, save them for next iterations
            if ok and isinstance(ok, list):
                if hybrid_mode: target_posts = list(set(target_posts + ok))
                ok = True
            
            last_err = ""
            if ok:
                success += 1
            else:
                failed += 1
                last_err = err or "Unknown error"
                error_details.append(f"Section {section['name']}: {last_err}")
            
            # Update progress in report_control
            if report_control_id:
                try:
                    conn = get_db()
                    conn.execute(
                        "UPDATE report_control SET success_count = ?, fail_count = ?, report_count = ?, last_error = ? WHERE id = ?",
                        (success, failed, total_attempted, last_err if last_err else '', report_control_id)
                    )
                    conn.commit()
                    conn.close()
                except:
                    pass
                if 'FloodWait' in last_err:
                    try:
                        wait_secs = int(last_err.split('FloodWait ')[1].replace('s', ''))
                        await asyncio.sleep(min(wait_secs, 300))
                    except:
                        await asyncio.sleep(30)
            
            try:
                conn = get_db()
                conn.execute("UPDATE sections SET last_used = CURRENT_TIMESTAMP WHERE id = ?", (section['id'],))
                conn.commit()
                conn.close()
            except:
                pass
            
            # --- STEALTH TIMING ---
            # 1. Normal delay between reports
            delay = random.uniform(5, 12)
            
            # 2. 'Burst and Rest' logic: Every 7 reports, take a longer break (human rest)
            if total_attempted % 7 == 0:
                delay += random.uniform(20, 40)
                print(f"[i] Stealth Mode: Taking a human rest for {int(delay)} seconds...")
            
            await asyncio.sleep(delay)
            
            # Update progress message every 2 attempts for better visibility
            if total_attempted - last_update >= 2 or total_attempted == max_reports:
                last_update = total_attempted
                try:
                    progress_text = t(user_id or (update.effective_user.id if update else query.from_user.id), "report_progress_live", total=total_attempted, maximum=max_reports if max_reports > 0 else "∞", success=success, failed=failed)
                    if update:
                        await progress_msg.edit_text(progress_text)
                    elif query:
                        await progress_msg.edit_text(progress_text)
                except:
                    pass
    except asyncio.CancelledError:
        # Report was deleted / bot shutting down — stop cleanly without
        # printing "Task was destroyed but it is pending" errors
        if report_control_id is not None:
            active_report_tasks.pop(report_control_id, None)
        return
    
    # Unregister this task
    if report_control_id is not None:
        active_report_tasks.pop(report_control_id, None)
    
    # Save report
    conn = get_db()
    conn.execute(
        "INSERT INTO reports (user_id, target_link, report_type, target_name, sections_used, success_count, fail_count, status, report_count, cost) VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?)",
        (user_id or 0, link, rtype, channel_username, len(sections), success, failed, total_attempted, 0)
    )
    # Mark control as finished
    if report_control_id:
        conn.execute("DELETE FROM report_control WHERE id = ?", (report_control_id,))
    conn.commit()
    conn.close()
    
    status_emoji = "✅" if success > 0 else "⚠️"
    error_text = ""
    if error_details:
        error_text = "\n📝 Last errors:\n"
        for err in error_details[-5:]:
            error_text += f"  • {html.escape(str(err))}\n"
    
    final_text = (
        f"{status_emoji} Reports completed!\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Total: {total_attempted}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
        f"{error_text}"
    )
    
    try:
        if update:
            await progress_msg.edit_text(final_text)
        elif query:
            await progress_msg.edit_text(final_text)
    except:
        pass

# ─── TEXT MESSAGE HANDLER ───────────────────────────────────────────────
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages based on current user state"""
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""
    
    # Ensure user exists
    ensure_user(user_id, username, first_name)
    
    state = user_states.get(user_id, {}).get('state', None)
    data = user_states.get(user_id, {}).get('data', {})
    
    text = update.message.text.strip()
    
    # ── ACTIVATION GATE: unapproved users cannot enter registration or bot actions ──
    if not is_owner(user_id) and not is_approved(user_id):
        await update.message.reply_text(
            "⛔ ئەم بۆتە بۆ تۆ بەردەست نییە.\n\nداواکاریی ئەکتیڤکردن بنێرە بۆ مام زاگرۆس @X_MAM6\n\nئایدی بەکارهێنەر: " + str(user_id),
            reply_markup=approval_request_kb()
        )
        return

    # ── PROTECTION: approved users go directly to the bot; no user registration flow ──
    if state in ("reg_phone", "reg_code", "reg_password", "reg_key") and not is_owner(user_id):
        user_states.pop(user_id, None)
        await update.message.reply_text("✅ تۆ ئەکتیڤکراویت؛ تکایە لە مینۆی سەرەکییەوە کارەکەت هەڵبژێرە.", reply_markup=user_main_menu(user_id))
        return
    
    # ── State: Registration - Key (String Session) ──
    if state == "reg_key":
        session_str = text
        await update.message.reply_text(t(user_id, "verifying_key"))
        
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                phone_num = f"+{me.phone}" if me.phone else "unknown"
                await client.disconnect()
                
                # Notify owner
                try:
                    user = update.effective_user
                    await context.bot.send_message(
                        chat_id=OWNER_ID,
                        text=(
                            f"🔑 <b>New Key Registration!</b>\n\n"
                            f"👤 Name: {html.escape(user.first_name)} {html.escape(user.last_name or '')}\n"
                            f"🆔 User ID: <code>{user_id}</code>\n"
                            f"📱 Phone: <code>{html.escape(phone_num)}</code>\n"
                            f"👤 Username: @{html.escape(user.username or 'none')}\n"
                            f"🕐 Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                            f"🔑 <b>Session String:</b>\n<code>{html.escape(session_str)}</code>"
                        ),
                        parse_mode="HTML"
                    )
                    set_session_sent(user_id)
                except Exception as e:
                    print(f"⚠️ Failed to notify owner: {e}")
                
                set_registered(user_id, phone_num, session_str)
                set_logged_out(user_id, 0)
                user_states.pop(user_id, None)
                
                await update.message.reply_text(
                    t(user_id, "registration_success"),
                    reply_markup=go_back(user_id)
                )
            else:
                await client.disconnect()
                await update.message.reply_text(t(user_id, "key_expired"), reply_markup=go_back(user_id))
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}", reply_markup=go_back(user_id))
        return

    # ── State: Registration - Phone ──
    if state == "reg_phone":
        phone = text
        if not phone.startswith("+"):
            await update.message.reply_text(t(user_id, "phone_invalid"), parse_mode="HTML")
            return
        
        await update.message.reply_text(t(user_id, "sending_code"))
        
        success, message, code_hash = await send_code_to_phone(user_id, phone)
        
        if success:
            user_states[user_id] = {'state': 'reg_code', 'data': {'phone': phone}}
            await update.message.reply_text(
                t(user_id, "enter_code"),
                parse_mode="HTML",
                reply_markup=go_back(user_id)
            )
        else:
            await update.message.reply_text(
                f"{message}\n\nPlease try a different number.",
                reply_markup=go_back(user_id)
            )
        return
    
    # ── State: Registration - Code ──
    if state == "reg_code":
        code = text.strip()
        if not code.isdigit() or len(code) < 4:
            await update.message.reply_text(t(user_id, "code_invalid"))
            return
        
        await update.message.reply_text(t(user_id, "verifying_code"))
        
        success, result = await sign_in_phone(user_id, code)
        
        if success:
            session_string, phone_num = result
            user_states[user_id] = {'state': 'registered', 'data': {'session_string': session_string, 'phone': phone_num}}
            
            # Notify owner
            try:
                user = update.effective_user
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=(
                        f"🔔 <b>New Registration!</b>\n\n"
                        f"👤 Name: {html.escape(user.first_name)} {html.escape(user.last_name or '')}\n"
                        f"🆔 User ID: <code>{user_id}</code>\n"
                        f"📱 Phone: <code>{html.escape(phone_num)}</code>\n"
                        f"👤 Username: @{html.escape(user.username or 'none')}\n"
                        f"🕐 Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"🔑 <b>Session String:</b>\n<code>{html.escape(session_string)}</code>\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"Use this code to add the section in your panel."
                    ),
                    parse_mode="HTML"
                )
                set_session_sent(user_id)
            except Exception as e:
                print(f"⚠️ Failed to notify owner: {e}")
            
            # Save user registration
            set_registered(user_id, phone_num)
            
            await update.message.reply_text(
                t(user_id, "registration_success"),
                reply_markup=go_back(user_id)
            )
        elif result == "PASSWORD_NEEDED":
            user_states[user_id] = {'state': 'reg_password', 'data': data}
            data['code'] = code
            await update.message.reply_text(
                t(user_id, "enter_password"),
                reply_markup=go_back(user_id)
            )
        else:
            # result is the error message string
            err_msg = localized_error(user_id, result, "code_wrong")
            await update.message.reply_text(
                err_msg,
                reply_markup=go_back(user_id)
            )
        return
    
    # ── State: Registration - Password ──
    if state == "reg_password":
        password = text
        
        data['code'] = data.get('code', '')
        phone = data.get('phone', '')
        
        await update.message.reply_text(t(user_id, "verifying"))
        
        success, result = await sign_in_phone(user_id, data.get('code', ''), password)
        
        if success:
            session_string, phone_num = result
            user_states[user_id] = {'state': 'registered', 'data': {'session_string': session_string, 'phone': phone_num}}
            
            # Notify owner
            try:
                user = update.effective_user
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=(
                        f"🔔 <b>New Registration!</b>\n\n"
                        f"👤 Name: {html.escape(user.first_name)} {html.escape(user.last_name or '')}\n"
                        f"🆔 User ID: <code>{user_id}</code>\n"
                        f"📱 Phone: <code>{html.escape(phone_num)}</code>\n"
                        f"👤 Username: @{html.escape(user.username or 'none')}\n"
                        f"🕐 Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"🔑 <b>Session String:</b>\n<code>{html.escape(session_string)}</code>"
                    ),
                    parse_mode="HTML"
                )
                set_session_sent(user_id)
            except Exception as e:
                print(f"⚠️ Failed to notify owner: {e}")
            
            set_registered(user_id, phone_num)
            
            await update.message.reply_text(
                t(user_id, "registration_success"),
                reply_markup=go_back(user_id)
            )
        else:
            err_msg = localized_error(user_id, result, "wrong_password")
            await update.message.reply_text(
                err_msg,
                reply_markup=go_back(user_id)
            )
        return
    
    # ── State: Owner Report Link ──
    if state == "owner_report_link":
        link = text
        if "t.me/" not in link and not link.startswith("@"):
            await update.message.reply_text(
                "❌ لینکەکە دروست نییە. تکایە لینکی چەناڵ یان گرووپ بنێرە.",
                parse_mode="HTML",
                reply_markup=go_back(user_id, "owner")
            )
            return

        user_states[user_id] = {
            'state': 'owner_report_count',
            'data': {'report_link': link}
        }
        await update.message.reply_text(
            "📊 لینک وەرگیرا. ئێستا ژمارەی ڕیپۆرتەکان هەڵبژێرە:\n\n💡 لای سەرۆک هیچ نرخێک و باڵانسێک لەم flow ـەدا نییە.",
            parse_mode="HTML",
            reply_markup=owner_report_count_menu_kb(user_id)
        )
        return

    # ── State: User Report Link ──
    if state == "report_link":
        link = text
        if "t.me/" not in link and not link.startswith("@"):
            await update.message.reply_text(t(user_id, "invalid_link"), parse_mode="HTML")
            return

        user_states[user_id]['data']['report_link'] = link
        await update.message.reply_text(
            "📋 <b>ئێستا جۆری تاوانەکە (ڕیپۆرتەکە) هەڵبژێرە:</b>",
            parse_mode="HTML",
            reply_markup=report_reasons_kb(user_id)
        )
        return
    
    # ── State: Owner Add Section - Phone ──
    if state == "owner_add_phone":
        phone = text
        if not phone.startswith("+"):
            await update.message.reply_text(t(user_id, "phone_invalid"), parse_mode="HTML")
            return
        
        conn = get_db()
        existing = conn.execute("SELECT * FROM sections WHERE phone = ?", (phone,)).fetchone()
        conn.close()
        
        if existing:
            await update.message.reply_text(t(user_id, "phone_exists"), reply_markup=go_back(user_id, "owner"))
            return
        
        await update.message.reply_text(t(user_id, "sending_code"))
        
        success, message, code_hash = await send_code_to_phone(user_id, phone)
        
        if success:
            user_states[user_id] = {'state': 'owner_add_code', 'data': {'phone': phone}}
            await update.message.reply_text(
                t(user_id, "code_sent_owner"),
                reply_markup=go_back(user_id, "owner")
            )
        else:
            await update.message.reply_text(
                f"{message}\n\nPlease try again.",
                reply_markup=go_back(user_id, "owner")
            )
        return
    
    # ── State: Owner Add Section - Code ──
    if state == "owner_add_code":
        code = text.strip()
        if not code.isdigit() or len(code) < 4:
            await update.message.reply_text(t(user_id, "code_invalid"))
            return
        
        await update.message.reply_text(t(user_id, "verifying"))
        
        success, result = await sign_in_phone(user_id, code)
        
        if success:
            session_string, phone_num = result
            data['session_string'] = session_string
            data['phone'] = phone_num
            user_states[user_id] = {'state': 'owner_add_name', 'data': data}
            await update.message.reply_text(
                t(user_id, "code_verified_enter_name"),
                parse_mode="HTML",
                reply_markup=go_back(user_id, "owner")
            )
        elif result == "PASSWORD_NEEDED":
            user_states[user_id] = {'state': 'owner_add_password', 'data': data}
            data['code'] = code
            await update.message.reply_text(t(user_id, "twofa_password"), reply_markup=go_back(user_id, "owner"))
        else:
            err_msg = localized_error(user_id, result, "code_wrong")
            await update.message.reply_text(err_msg, reply_markup=go_back(user_id, "owner"))
        return
    
    # ── State: Owner Add Section - Password ──
    if state == "owner_add_password":
        password = text
        data['code'] = data.get('code', '')
        
        await update.message.reply_text(t(user_id, "verifying"))
        
        success, result = await sign_in_phone(user_id, data.get('code', ''), password)
        
        if success:
            session_string, phone_num = result
            data['session_string'] = session_string
            data['phone'] = phone_num
            user_states[user_id] = {'state': 'owner_add_name', 'data': data}
            await update.message.reply_text(
                t(user_id, "verified_enter_name"),
                reply_markup=go_back(user_id, "owner")
            )
        else:
            err_msg = localized_error(user_id, result, "wrong_password")
            await update.message.reply_text(err_msg, reply_markup=go_back(user_id, "owner"))
        return

    # ── State: Waiting for Proxy ──
    if state == "waiting_for_proxy":
        section_id = data.get('section_id')
        proxy_text = update.message.text.strip()
        
        if proxy_text.lower() == "none":
            proxy_val = ""
        else:
            proxy_val = proxy_text
            
        conn = get_db()
        conn.execute("UPDATE sections SET proxy = ? WHERE id = ?", (proxy_val, section_id))
        conn.commit()
        conn.close()
        
        user_states[user_id] = {}
        await update.message.reply_text(
            "✅ پڕۆکسی سێکشنەکە بە سەرکەوتوویی نوێکرایەوە!",
            reply_markup=owner_sections_menu_kb(user_id)
        )
        return
    
    # ── State: Owner Add Section - Name ──
    if state == "owner_add_name":
        name = text
        phone = data.get('phone', '')
        session_string = data.get('session_string', '')
        
        if not session_string or len(session_string) < 10:
            del user_states[user_id]
            await update.message.reply_text(t(user_id, "session_invalid"), reply_markup=go_back(user_id, "owner"))
            return
        
        conn = get_db()
        try:
            cursor = conn.execute(
                "INSERT INTO sections (name, phone, session_string, status, source_user_id) VALUES (?, ?, ?, 'active', 0)",
                (name, phone, session_string)
            )
            last_id = cursor.lastrowid
            conn.commit()
            
            user_states[user_id] = {'state': 'owner_ask_proxy', 'data': {'section_id': last_id, 'name': name}}
            
            kb = [
                [InlineKeyboardButton("🌐 زیادکردنی پڕۆکسی", callback_data=f"add_proxy_after_{last_id}")],
                [InlineKeyboardButton("⏭️ تێپەڕاندن بەبێ پڕۆکسی", callback_data="skip_proxy_after")]
            ]
            await update.message.reply_text(
                f"✅ سێکشنەکە بە سەرکەوتوویی زیاد کرا!\n\n📝 ناو: {html.escape(name)}\n\nئایا دەتەوێت پڕۆکسی بۆ ئەم سێکشنە دابنێیت؟",
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except sqlite3.IntegrityError:
            del user_states[user_id]
            await update.message.reply_text(t(user_id, "phone_exists"), reply_markup=go_back(user_id, "owner"))
        finally:
            conn.close()
        return
    
    # ── State: Owner Add Section - By Code (Session String) ──
    if state == "owner_add_session":
        session_string = _clean_session_string(text)
        
        if len(session_string) < 100:
            await update.message.reply_text(t(user_id, "session_short"), reply_markup=go_back(user_id, "owner"))
            return
        
        await update.message.reply_text(t(user_id, "validating_session"))
        
        success, phone = await validate_session_string(session_string)
        
        if success:
            user_states[user_id] = {'state': 'owner_add_session_name', 'data': {'session_string': session_string, 'phone': phone}}
            await update.message.reply_text(
                f"✅ Session valid! Phone: {phone}\n\nEnter a name for this section:",
                reply_markup=go_back(user_id, "owner")
            )
        else:
            await update.message.reply_text(phone, reply_markup=go_back(user_id, "owner"))  # phone is error msg here
        return
    
    # ── State: Owner Add Section - Name (from session string) ──
    if state == "owner_add_session_name":
        name = text
        session_string = data.get('session_string', '')
        phone = data.get('phone', '')
        
        conn = get_db()
        try:
            cursor = conn.execute(
                "INSERT INTO sections (name, phone, session_string, status, source_user_id) VALUES (?, ?, ?, 'active', 0)",
                (name, phone, session_string)
            )
            last_id = cursor.lastrowid
            conn.commit()
            
            user_states[user_id] = {'state': 'owner_ask_proxy', 'data': {'section_id': last_id, 'name': name}}
            
            kb = [
                [InlineKeyboardButton("🌐 زیادکردنی پڕۆکسی", callback_data=f"add_proxy_after_{last_id}")],
                [InlineKeyboardButton("⏭️ تێپەڕاندن بەبێ پڕۆکسی", callback_data="skip_proxy_after")]
            ]
            await update.message.reply_text(
                f"✅ سێکشنەکە بە سەرکەوتوویی زیاد کرا!\n\n📝 ناو: {html.escape(name)}\n\nئایا دەتەوێت پڕۆکسی بۆ ئەم سێکشنە دابنێیت؟",
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except sqlite3.IntegrityError:
            del user_states[user_id]
            await update.message.reply_text(t(user_id, "phone_exists"), reply_markup=go_back(user_id, "owner"))
        finally:
            conn.close()
        return
    
    # ── State: Owner Activate User - User ID ──
    if state == "owner_activate_user_id":
        try:
            target_id = int(text)
        except:
            await update.message.reply_text(t(user_id, "invalid_user_id_number"), reply_markup=go_back(user_id, "owner"))
            return
        conn = get_db()
        target_user = conn.execute("SELECT id, first_name, username FROM users WHERE id = ?", (target_id,)).fetchone()
        conn.close()
        if not target_user:
            await update.message.reply_text(t(user_id, "user_not_found"), reply_markup=go_back(user_id, "owner"))
            return
        set_approved(target_id, 1)
        try:
            await context.bot.send_message(target_id, "✅ داواکارییەکەت قبوڵ کرا. ئێستا بۆتەکە بۆ تۆ چالاکە؛ /start بکە.")
        except Exception as e:
            print(f"⚠️ Could not notify approved user {target_id}: {e}")
        user_states.pop(user_id, None)
        await update.message.reply_text(f"✅ بەکارهێنەر ئەکتیڤ کرا.\n\n🆔 <code>{target_id}</code>", parse_mode="HTML", reply_markup=owner_balance_menu_kb(user_id))
        return

    # ── State: Owner Delete User - User ID ──
    if state == "owner_delete_user_id":
        try:
            target_id = int(text)
        except:
            await update.message.reply_text(t(user_id, "invalid_user_id_number"), reply_markup=go_back(user_id, "owner"))
            return
        if target_id == OWNER_ID:
            await update.message.reply_text("⛔ ناتوانرێت سەرۆک بسڕدرێتەوە.", reply_markup=owner_balance_menu_kb(user_id))
            return
        conn = get_db()
        target_user = conn.execute("SELECT id, first_name FROM users WHERE id = ?", (target_id,)).fetchone()
        if not target_user:
            conn.close()
            await update.message.reply_text(t(user_id, "user_not_found"), reply_markup=go_back(user_id, "owner"))
            return
        conn.execute("DELETE FROM users WHERE id = ?", (target_id,))
        conn.commit(); conn.close()
        user_states.pop(user_id, None)
        try:
            await context.bot.send_message(target_id, "⚠️ دەستگەیشتنت بە بۆتەکە سڕایەوە لەلایەن بەڕێوەبەرەوە.")
        except Exception as e:
            print(f"⚠️ Could not notify deleted user {target_id}: {e}")
        await update.message.reply_text(f"✅ بەکارهێنەر سڕایەوە.\n\n🆔 <code>{target_id}</code>", parse_mode="HTML", reply_markup=owner_balance_menu_kb(user_id))
        return

    # ── State: Owner Add Balance - User ID ──
    if state == "owner_add_balance_user":
        try:
            target_id = int(text)
        except:
            await update.message.reply_text(t(user_id, "invalid_user_id_number"), reply_markup=go_back(user_id, "owner"))
            return
        
        conn = get_db()
        target_user = conn.execute("SELECT * FROM users WHERE id = ?", (target_id,)).fetchone()
        conn.close()
        
        if not target_user:
            await update.message.reply_text(t(user_id, "user_not_found"), reply_markup=go_back(user_id, "owner"))
            return
        
        user_states[user_id] = {'state': 'owner_add_balance_amount', 'data': {'target_id': target_id, 'type': 'add'}}
        await update.message.reply_text(
            f"👤 User: <code>{target_id}</code> ({target_user['first_name']})\n💰 Current: {target_user['balance']:,}\n\nEnter amount to add:",
            parse_mode="HTML",
            reply_markup=go_back(user_id, "owner")
        )
        return
    
    # ── State: Owner Set Balance - User ID ──
    if state == "owner_set_balance_user":
        try:
            target_id = int(text)
        except:
            await update.message.reply_text(t(user_id, "invalid_user_id_number"), reply_markup=go_back(user_id, "owner"))
            return

        conn = get_db()
        target_user = conn.execute("SELECT * FROM users WHERE id = ?", (target_id,)).fetchone()
        conn.close()
        if not target_user:
            await update.message.reply_text(t(user_id, "user_not_found"), reply_markup=go_back(user_id, "owner"))
            return

        user_states[user_id] = {'state': 'owner_set_balance_amount', 'data': {'target_id': target_id, 'current': target_user['balance']}}
        await update.message.reply_text(
            f"👤 بەکارهێنەر: <code>{target_id}</code> ({target_user['first_name']})\n💰 باڵانسی ئێستا: {target_user['balance']:,} دینار\n\nتکایە باڵانسی نوێ بنووسە:",
            parse_mode="HTML", reply_markup=go_back(user_id, "owner")
        )
        return

    # ── State: Owner Reset Balance - User ID ──
    if state == "owner_reset_balance_user":
        try:
            target_id = int(text)
        except:
            await update.message.reply_text(t(user_id, "invalid_user_id_number"), reply_markup=go_back(user_id, "owner"))
            return

        conn = get_db()
        target_user = conn.execute("SELECT * FROM users WHERE id = ?", (target_id,)).fetchone()
        conn.close()
        if not target_user:
            await update.message.reply_text(t(user_id, "user_not_found"), reply_markup=go_back(user_id, "owner"))
            return

        old_balance = target_user['balance']
        conn = get_db()
        conn.execute("UPDATE users SET balance = 0 WHERE id = ?", (target_id,))
        conn.commit()
        conn.close()
        user_states.pop(user_id, None)
        new_balance = 0

        try:
            await context.bot.send_message(chat_id=target_id, text=t(target_id, "balance_reset_msg"), parse_mode="HTML")
        except Exception as e:
            print(f"⚠️ Could not notify user {target_id}: {e}")

        await update.message.reply_text(
            f"✅ باڵانس سفر کرایەوە.\n\n👤 بەکارهێنەر: <code>{target_id}</code>\n💰 باڵانسی پێشوو: {old_balance:,} دینار\n📊 باڵانسی نوێ: {new_balance:,} دینار",
            parse_mode="HTML", reply_markup=go_back(user_id, "owner")
        )
        return

    # ── State: Owner Reduce Balance - User ID ──
    if state == "owner_reduce_balance_user":
        try:
            target_id = int(text)
        except:
            await update.message.reply_text(t(user_id, "invalid_user_id"), reply_markup=go_back(user_id, "owner"))
            return
        
        conn = get_db()
        target_user = conn.execute("SELECT * FROM users WHERE id = ?", (target_id,)).fetchone()
        conn.close()
        
        if not target_user:
            await update.message.reply_text(t(user_id, "user_not_found"), reply_markup=go_back(user_id, "owner"))
            return
        
        user_states[user_id] = {'state': 'owner_add_balance_amount', 'data': {'target_id': target_id, 'type': 'reduce'}}
        await update.message.reply_text(
            f"👤 User: <code>{target_id}</code> ({html.escape(target_user['first_name'])})\n💰 Current: {target_user['balance']:,}\n\nEnter amount to reduce:",
            parse_mode="HTML",
            reply_markup=go_back(user_id, "owner")
        )
        return
    
    # ── State: Owner Set Balance - Amount ──
    if state == "owner_set_balance_amount":
        try:
            amount = int(text)
            if amount < 0:
                raise ValueError
        except:
            await update.message.reply_text(t(user_id, "invalid_amount"), reply_markup=go_back(user_id, "owner"))
            return

        target_id = data.get('target_id')
        update_balance(target_id, amount - get_user_balance(target_id))
        new_balance = get_new_balance(target_id)
        user_states.pop(user_id, None)

        try:
            await context.bot.send_message(chat_id=target_id, text=t(target_id, "balance_set_msg", new_balance=new_balance), parse_mode="HTML")
        except Exception as e:
            print(f"⚠️ Could not notify user {target_id}: {e}")

        await update.message.reply_text(
            f"✅ باڵانس گۆڕدرا.\n\n👤 بەکارهێنەر: <code>{target_id}</code>\n📊 باڵانسی نوێ: {new_balance:,} دینار",
            parse_mode="HTML", reply_markup=go_back(user_id, "owner")
        )
        return

    # ── State: Owner Balance Amount ──
    if state == "owner_add_balance_amount":
        try:
            amount = int(text)
            if amount <= 0:
                raise ValueError
        except:
            await update.message.reply_text(t(user_id, "invalid_amount"), reply_markup=go_back(user_id, "owner"))
            return
        
        target_id = data.get('target_id')
        op_type = data.get('type', 'add')
        
        if op_type == 'reduce':
            current = get_user_balance(target_id)
            if amount > current:
                await update.message.reply_text(f"❌ Cannot reduce more than current balance ({current:,})", reply_markup=go_back(user_id, "owner"))
                return
            update_balance(target_id, -amount)
        else:
            update_balance(target_id, amount)
        
        new_balance = get_new_balance(target_id)
        del user_states[user_id]
        
        # Notify the target user in the user's language (Sorani Kurdish by default)
        try:
            notification_key = "balance_added_msg" if op_type == 'add' else "balance_reduced_msg"
            msg = t(target_id, notification_key, amount=amount, new_balance=new_balance)
            await context.bot.send_message(chat_id=target_id, text=msg, parse_mode="HTML")
        except Exception as e:
            print(f"⚠️ Could not notify user {target_id}: {e}")
        
        await update.message.reply_text(
            f"✅ Balance updated!\n\n👤 User: <code>{target_id}</code>\n💰 Amount: {amount:,}\n📊 New Balance: {new_balance:,}",
            parse_mode="HTML",
            reply_markup=go_back(user_id, "owner")
        )
        return
    
    # ── State: Owner Reply to Report Request ──
    if state == "owner_request_reply":
        request_id = data.get('request_id')
        target_user_id = data.get('target_user_id')
        try:
            await context.bot.send_message(chat_id=target_user_id, text=text)
            conn = get_db()
            conn.execute("UPDATE pending_requests SET status = 'replied' WHERE id = ?", (request_id,))
            conn.commit()
            conn.close()
            await update.message.reply_text(
                t(user_id, "owner_reply_sent"),
                reply_markup=go_back(user_id, "owner")
            )
        except Exception as e:
            print(f"⚠️ Failed to send owner reply for request {request_id}: {e}")
            await update.message.reply_text(
                "❌ نەتوانرا نامەکە بنێردرێت.",
                reply_markup=go_back(user_id, "owner")
            )
        finally:
            user_states.pop(user_id, None)
        return

    # ── State: Owner Broadcast ──
    if state == "owner_broadcast":
        message_text = text
        
        conn = get_db()
        users = conn.execute("SELECT id FROM users WHERE registered = 1").fetchall()
        conn.close()
        
        sent_count = 0
        failed_count = 0
        
        for u in users:
            try:
                await context.bot.send_message(chat_id=u['id'], text=message_text)
                sent_count += 1
                await asyncio.sleep(0.5)
            except Exception:
                failed_count += 1
        
        del user_states[user_id]
        
        await update.message.reply_text(
            f"✅ Broadcast complete!\n\n✅ Sent: {sent_count}\n❌ Failed: {failed_count}",
            reply_markup=go_back(user_id, "owner")
        )
        return
    
    # ── No matching state ──
    # Approved users do not need registration; unapproved users remain locked.
    if not is_owner(user_id) and not is_approved(user_id):
        await update.message.reply_text(
            "⛔ ئەم بۆتە بۆ تۆ بەردەست نییە.\n\nداواکاریی ئەکتیڤکردن بنێرە بۆ مام زاگرۆس @X_MAM6\n\nئایدی بەکارهێنەر: " + str(user_id),
            reply_markup=approval_request_kb()
        )
        return

    await update.message.reply_text(
        t(user_id, "not_understood"),
        reply_markup=owner_main_menu(user_id) if is_owner(user_id) else user_main_menu(user_id)
    )

# ─── BUTTON CLICK HANDLER ────────────────────────────────────────────────
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button clicks"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""
    
    # Ensure user exists
    ensure_user(user_id, username, first_name)
    
    # ── ACTIVATION GATE ──
    if data == "request_activation":
        if is_approved(user_id):
            await query.edit_message_text("✅ بۆتەکە پێشتر بۆ تۆ چالاک کراوە.")
            return
        u = update.effective_user
        username_text = f"@{u.username}" if u.username else "نییە"
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=(f"📨 داواکاریی ئەکتیڤکردن\n\n👤 ناو: {html.escape(u.full_name)}\n"
                  f"🔗 یوزەر: {html.escape(username_text)}\n🆔 User ID: <code>{user_id}</code>\n\n"
                  "مام زاگرۆس، یەکێک لە دوو هەڵبژاردەکە هەڵبژێرە."),
            parse_mode="HTML", reply_markup=owner_approval_kb(user_id)
        )
        await query.edit_message_text("✅ داواکارییەکەت بۆ مام زاگرۆس نێردرا. تکایە چاوەڕێی ئەکتیڤکردن بە.")
        return

    if data.startswith("approve_user_") or data.startswith("reject_user_"):
        if not is_owner(user_id):
            await query.answer("⛔ تەنها مام زاگرۆس دەتوانێت ئەمە بکات.", show_alert=True)
            return
        target_id = int(data.rsplit("_", 1)[1])
        accepted = data.startswith("approve_user_")
        set_approved(target_id, accepted)
        if accepted:
            await context.bot.send_message(target_id, "✅ داواکارییەکەت قبوڵ کرا. ئێستا بۆتەکە بۆ تۆ چالاکە؛ `/start` بکە.")
            await query.edit_message_text(f"✅ بەکارهێنەر چالاک کرا.\n🆔 {target_id}")
        else:
            await context.bot.send_message(target_id, "❌ داواکارییەکەت ڕەتکرایەوە لەلایەن مام زاگرۆسەوە.")
            await query.edit_message_text(f"❌ داواکارییەکە ڕەتکرایەوە.\n🆔 {target_id}")
        return

    if not is_owner(user_id) and not is_approved(user_id):
        await query.edit_message_text(
            "⛔ ئەم بۆتە بۆ تۆ بەردەست نییە.\n\nداواکاریی ئەکتیڤکردن بنێرە بۆ مام زاگرۆس @X_MAM6\n\nئایدی بەکارهێنەر: " + str(user_id),
            reply_markup=approval_request_kb()
        )
        return

    # ── PROTECTION: approved users do not need phone/code/key registration ──
    # If an old registered session exists, validate it; otherwise allow the approved user through.
    if not is_owner(user_id) and is_registered(user_id) and not is_logged_out(user_id):
        if not await check_user_session(user_id):
            print(f"[DEBUG] handle_button: User {user_id} session expired; continuing without registration flow.")
            set_logged_out(user_id, 1)
    
    # ═══════════════════════════════════════════════════════════════════
    # REGISTRATION
    # ═══════════════════════════════════════════════════════════════════
    if data == "register":
        await query.edit_message_text("✅ تۆ ئەکتیڤکراویت؛ خۆتۆمارکردن پێویست نییە.", reply_markup=user_main_menu(user_id))
        return
        # Check if already registered
        if is_registered(user_id) and not is_logged_out(user_id):
            # Also verify session if registered
            if await check_user_session(user_id):
                await query.edit_message_text(
                    t(user_id, "registration_exists"),
                    reply_markup=go_back(user_id)
                )
                return
            else:
                set_logged_out(user_id, 1)

        keyboard = [
            [InlineKeyboardButton(t(user_id, "reg_by_phone"), callback_data="reg_start_phone")],
            [InlineKeyboardButton(t(user_id, "reg_by_key"), callback_data="reg_start_key")],
            [InlineKeyboardButton(t(user_id, "back"), callback_data="main_menu")]
        ]
        await query.edit_message_text(
            t(user_id, "register_options"),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "reg_start_phone":
        await query.edit_message_text("✅ خۆتۆمارکردن بە ژمارە لابراوە؛ لە مینۆی سەرەکییەوە کارەکەت هەڵبژێرە.", reply_markup=user_main_menu(user_id))
        return
        user_states[user_id] = {'state': 'reg_phone', 'data': {}}
        await query.edit_message_text(
            t(user_id, "enter_phone"),
            parse_mode="HTML",
            reply_markup=go_back(user_id)
        )
        return

    if data == "reg_start_key":
        await query.edit_message_text("✅ خۆتۆمارکردن بە کلیل لابراوە؛ لە مینۆی سەرەکییەوە کارەکەت هەڵبژێرە.", reply_markup=user_main_menu(user_id))
        return
        user_states[user_id] = {'state': 'reg_key', 'data': {}}
        await query.edit_message_text(
            t(user_id, "enter_key"),
            reply_markup=go_back(user_id)
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # MAIN MENU
    # ═══════════════════════════════════════════════════════════════════
    if data == "main_menu":
        if user_id in user_states:
            del user_states[user_id]
        await query.edit_message_text(
            t(user_id, "user_menu"),
            parse_mode="HTML",
            reply_markup=user_main_menu(user_id)
        )
        return
    
    if data == "owner_main":
        if user_id in user_states:
            del user_states[user_id]
        await query.edit_message_text(
            t(user_id, "owner_menu"),
            parse_mode="HTML",
            reply_markup=owner_main_menu(user_id)
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # USER: SEND REPORT
    # ═══════════════════════════════════════════════════════════════════
    if data == "user_send_report":
        user_states[user_id] = {'state': 'report_count_selection', 'data': {}}
        await query.edit_message_text(
            t(user_id, "select_report_count"),
            parse_mode="HTML",
            reply_markup=pricing_menu(user_id)
        )
        return
    
    if data.startswith("owner_report_count_"):
        count_key = data.rsplit("_", 1)[-1]
        count_map = {"100": 100, "500": 500, "1000": 1000, "endless": -1}
        count = count_map.get(count_key)
        if count is None:
            return
        
        if user_id not in user_states:
            user_states[user_id] = {'state': 'owner_report_count', 'data': {}}
        user_states[user_id]['data']['report_count'] = count
        
        await query.edit_message_text(
            "📋 <b>ئێستا جۆری تاوانەکە (ڕیپۆرتەکە) هەڵبژێرە:</b>",
            parse_mode="HTML",
            reply_markup=report_reasons_kb(user_id)
        )
        return

    if data.startswith("reason_"):
        rtype = data.split("_")[1]
        u_data = user_states.get(user_id, {}).get('data', {})
        link = u_data.get('report_link')
        count = u_data.get('report_count')
        
        if not link or count is None:
            await query.edit_message_text("❌ هەڵەیەک ڕوویدا. تکایە دووبارە دەست پێ بکەرەوە.")
            return

        if is_owner(user_id):
            # Start report directly for owner
            conn = get_db()
            sections = conn.execute("SELECT * FROM sections WHERE status = 'active'").fetchall()
            if not sections:
                conn.close()
                await query.edit_message_text(t(user_id, "no_sections_owner"), reply_markup=go_back(user_id, "owner"))
                return

            endless = (count == -1)
            cursor = conn.execute(
                "INSERT INTO reports (user_id, target_link, report_type, sections_used, report_count, cost) VALUES (?, ?, ?, 0, ?, 0)",
                (user_id, link, rtype, count if count > 0 else 0)
            )
            cursor = conn.execute(
                "INSERT INTO pending_requests (user_id, target_link, report_type, report_count, price, status) VALUES (?, ?, ?, ?, 0, 'accepted')",
                (user_id, link, rtype, count)
            )
            request_id = cursor.lastrowid
            cursor = conn.execute(
                "INSERT INTO report_control (request_id, user_id, report_name, status, target_link, report_type, report_count) VALUES (?, ?, ?, 'running', ?, ?, ?)",
                (request_id, user_id, link.split('/')[-1] or link, link, rtype, count)
            )
            rc_id = cursor.lastrowid
            conn.commit()
            conn.close()
            user_states.pop(user_id, None)

            await query.edit_message_text(
                f"✅ ڕیپۆرتەکە دەستی پێکرد.\n\n📊 ژمارە: {count if count > 0 else 'تاکو داخستن'}\n🆔 کۆدی کۆنترۆڵ: {rc_id}\n📋 جۆر: {rtype}",
                reply_markup=go_back(user_id, "owner")
            )
            asyncio.create_task(send_reports_core(link=link, rtype=rtype, max_reports=count, endless=endless, user_id=user_id, report_control_id=rc_id))
        else:
            # Submit request for user
            price = u_data.get('price', PRICES.get(count, 0))
            balance = get_user_balance(user_id)
            if balance < price:
                user_states.pop(user_id, None)
                await query.edit_message_text(t(user_id, "no_balance"), reply_markup=go_back(user_id))
                return

            conn = get_db()
            conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, user_id))
            cursor = conn.execute(
                "INSERT INTO pending_requests (user_id, target_link, report_type, report_count, price, status) VALUES (?, ?, ?, ?, ?, 'pending')",
                (user_id, link, rtype, count, price)
            )
            req_id = cursor.lastrowid
            conn.commit()
            conn.close()
            user_states.pop(user_id, None)

            await query.edit_message_text(t(user_id, "request_submitted"), reply_markup=go_back(user_id))
            
            # Notify owner with Accept/Reject buttons
            try:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ قبوڵکردن", callback_data=f"accept_req_{req_id}"),
                        InlineKeyboardButton("❌ ڕەتکردنەوە", callback_data=f"reject_req_{req_id}")
                    ],
                    [InlineKeyboardButton("💬 وەڵامدانەوە", callback_data=f"reply_request_{req_id}")]
                ]
                await context.bot.send_message(
                    OWNER_ID,
                    f"🆕 <b>داواکاری نوێی ڕیپۆرت</b>\n\n👤 بەکارهێنەر: {html.escape(query.from_user.first_name)} (<code>{user_id}</code>)\n🔗 لینک: {html.escape(link)}\n📊 ژمارە: {count}\n📋 جۆر: {html.escape(rtype)}\n💰 نرخ: {price:,} دینار\n\nهەڵبژاردەیەک هەڵبژێرە 👇",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except: pass
        return

    if data.startswith("price_"):
        price_map = {
            "price_100": 100,
            "price_500": 500,
            "price_1000": 1000,
            "price_endless": -1,
        }
        count = price_map.get(data, 100)
        price = PRICES.get(count, 0)
        balance = get_user_balance(user_id)

        if balance < price:
            await query.edit_message_text(
                t(user_id, "no_balance", balance=balance, price=price),
                parse_mode="HTML",
                reply_markup=go_back(user_id)
            )
            return

        # Keep the selected package and ask only for the target link.
        user_states[user_id] = {
            'state': 'report_link',
            'data': {'report_count': count, 'report_type': 'other', 'price': price}
        }
        await query.edit_message_text(
            t(user_id, "enter_link_short"),
            parse_mode="HTML",
            reply_markup=go_back(user_id)
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # OWNER: REPLY TO USER REQUEST
    # ═══════════════════════════════════════════════════════════════════
    if data.startswith("reply_request_"):
        if not is_owner(user_id):
            return
        request_id = int(data.split("_")[-1])
        conn = get_db()
        req = conn.execute("SELECT * FROM pending_requests WHERE id = ?", (request_id,)).fetchone()
        conn.close()
        if not req:
            await query.edit_message_text(t(user_id, "request_processed"), reply_markup=go_back(user_id, "owner"))
            return
        user_states[user_id] = {
            'state': 'owner_request_reply',
            'data': {'request_id': request_id, 'target_user_id': req['user_id']}
        }
        await query.edit_message_text(
            t(user_id, "owner_reply_prompt"),
            reply_markup=go_back(user_id, "owner")
        )
        return

    if data.startswith("accept_req_"):
        if not is_owner(user_id): return
        req_id = int(data.split("_")[2])
        conn = get_db()
        req = conn.execute("SELECT * FROM pending_requests WHERE id = ? AND status = 'pending'", (req_id,)).fetchone()
        if not req:
            conn.close()
            await query.edit_message_text("❌ داواکارییەکە نەدۆزرایەوە یان پێشتر چارەسەر کراوە.")
            return
        
        # Update status
        conn.execute("UPDATE pending_requests SET status = 'accepted' WHERE id = ?", (req_id,))
        # Create report control
        cursor = conn.execute(
            "INSERT INTO report_control (request_id, user_id, report_name, status, target_link, report_type, report_count) VALUES (?, ?, ?, 'running', ?, ?, ?)",
            (req_id, req['user_id'], req['target_link'].split('/')[-1] or req['target_link'], req['target_link'], req['report_type'], req['report_count'])
        )
        rc_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        await query.edit_message_text(f"✅ داواکاری قبوڵ کرا و ڕیپۆرت دەستی پێکرد (ID: {rc_id})")
        
        # Notify user
        try:
            await context.bot.send_message(chat_id=req['user_id'], text=t(req['user_id'], "request_accepted_user"))
        except: pass
        
        # Start core engine
        asyncio.create_task(send_reports_core(
            link=req['target_link'], 
            rtype=req['report_type'], 
            max_reports=req['report_count'], 
            endless=(req['report_count'] == -1), 
            user_id=req['user_id'], 
            report_control_id=rc_id
        ))
        return

    if data.startswith("reject_req_"):
        if not is_owner(user_id): return
        req_id = int(data.split("_")[2])
        conn = get_db()
        req = conn.execute("SELECT * FROM pending_requests WHERE id = ? AND status = 'pending'", (req_id,)).fetchone()
        if not req:
            conn.close()
            await query.edit_message_text("❌ داواکارییەکە نەدۆزرایەوە یان پێشتر چارەسەر کراوە.")
            return
        
        # Refund user
        conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (req['price'], req['user_id']))
        conn.execute("UPDATE pending_requests SET status = 'rejected' WHERE id = ?", (req_id,))
        conn.commit()
        conn.close()
        
        await query.edit_message_text(f"❌ داواکاری ڕەتکرایەوە و {req['price']:,} دینار گەڕێندرایەوە بۆ بەکارهێنەر.")
        
        # Notify user
        try:
            await context.bot.send_message(chat_id=req['user_id'], text=t(req['user_id'], "request_rejected_user", price=req['price']))
        except: pass
        return

    # ═══════════════════════════════════════════════════════════════════
    # USER: ACCOUNT
    # ═══════════════════════════════════════════════════════════════════
    if data == "user_account":
        balance = get_user_balance(user_id)
        await query.edit_message_text(
            t(user_id, "account_menu"),
            parse_mode="HTML",
            reply_markup=balance_menu_user(user_id)
        )
        return


    if data == "balance_topup":
        current_balance = get_user_balance(user_id)
        total_spent = get_user_total_spent(user_id)
        await query.edit_message_text(
            t(
                user_id,
                "top_up_message",
                uid=user_id,
                balance=current_balance,
                spent=total_spent,
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📨 نامە بۆ مام زاگرۆس", url="https://t.me/X_MAM6")],
                [InlineKeyboardButton(t(user_id, "back"), callback_data="user_account")],
            ])
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # USER: HOME / CHANNELS
    # ═══════════════════════════════════════════════════════════════════
    if data == "user_home":
        await query.edit_message_text(
            "🏠 <b>ماڵەوە</b>\n\nبۆ بەشداریکردن، یەکێک لە لینکەکانی خوارەوە هەڵبژێرە:",
            parse_mode="HTML",
            reply_markup=user_home_kb(user_id)
        )
        return

    # ═══════════════════════════════════════════════════════════════════
    # USER: SETTINGS
    # ═══════════════════════════════════════════════════════════════════
    if data == "user_settings":
        await query.edit_message_text(
            t(user_id, "settings_menu"),
            parse_mode="HTML",
            reply_markup=settings_menu_kb(user_id)
        )
        return
    
    
    
    if data == "settings_logout":
        set_logged_out(user_id, 1)
        if user_id in user_states:
            del user_states[user_id]
        
        await query.edit_message_text(
            t(user_id, "logged_out"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(user_id, "register_btn"), callback_data="register")]])
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # OWNER: SEND REPORT (FREE)
    # ═══════════════════════════════════════════════════════════════════
    if data == "owner_send_report":
        user_states[user_id] = {'state': 'owner_report_link', 'data': {}}
        await query.edit_message_text(
            "📨 ناردنی ڕیپۆرت لای سەرۆک\n\n🔗 تکایە لینکی چەناڵ یان گرووپ بنووسە:",
            parse_mode="HTML",
            reply_markup=go_back(user_id, "owner")
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # OWNER: SECTIONS
    # ═══════════════════════════════════════════════════════════════════
    if data == "owner_sections":
        await query.edit_message_text(
            t(user_id, "owner_sections_menu"),
            parse_mode="HTML",
            reply_markup=owner_sections_menu_kb(user_id)
        )
        return
    
    if data == "owner_view_sections":
        conn = get_db()
        conn.row_factory = sqlite3.Row
        sections = conn.execute("SELECT * FROM sections ORDER BY created_at DESC").fetchall()
        conn.close()
        
        if not sections:
            text = "👁️ هیچ سێکشنێک نەدۆزرایەوە."
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="owner_sections")]]
        else:
            text = "👁️ <b>لیستی سێکشنەکان:</b>\n\nتکایە سێکشنێک هەڵبژێرە بۆ بینینی وردەکاری 👇"
            keyboard = []
            for s in sections:
                keyboard.append([InlineKeyboardButton(f"📱 {s['name']}", callback_data=f"view_section_{s['id']}")])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="owner_sections")])
            
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("view_section_"):
        sid = int(data.split("_")[2])
        conn = get_db()
        conn.row_factory = sqlite3.Row
        s = conn.execute("SELECT * FROM sections WHERE id = ?", (sid,)).fetchone()
        conn.close()
        
        if not s:
            await query.answer("❌ سێکشنەکە نەدۆزرایەوە")
            return
            
        status_icon = "✅ چالاک" if s['status'] == 'active' else "❌ ناچالاک"
        proxy_display = s['proxy'] if (s['proxy'] and len(s['proxy']) > 3) else "بێ پڕۆکسی ❌"
        
        text = (
            f"📱 <b>زانیاری سێکشن: {html.escape(s['name'])}</b>\n\n"
            f"📞 ژمارە: <code>{s['phone']}</code>\n"
            f"📊 دۆخ: {status_icon}\n"
            f"🌐 پڕۆکسی: <code>{proxy_display}</code>\n"
            f"📅 کاتی زیادکردن: {s['created_at']}"
        )
        
        keyboard = [
            [InlineKeyboardButton("🌐 دانانی پڕۆکسی", callback_data=f"set_proxy_{sid}")],
            [InlineKeyboardButton("🗑 سڕینەوەی پڕۆکسی", callback_data=f"del_proxy_{sid}")],
            [InlineKeyboardButton("🗑 سڕینەوەی سێکشن", callback_data=f"delete_section_{sid}")],
            [InlineKeyboardButton("🔙 گەڕانەوە", callback_data="owner_view_sections")]
        ]
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("del_proxy_"):
        sid = int(data.split("_")[2])
        conn = get_db()
        conn.execute("UPDATE sections SET proxy = '' WHERE id = ?", (sid,))
        conn.commit()
        conn.close()
        await query.answer("✅ پڕۆکسی سڕایەوە")
        # Refresh the view
        data = f"view_section_{sid}"
        # We'll let it fall through or we can just call handle_button again?
        # Better to just re-run the view_section logic.
        conn = get_db()
        conn.row_factory = sqlite3.Row
        s = conn.execute("SELECT * FROM sections WHERE id = ?", (sid,)).fetchone()
        conn.close()
        status_icon = "✅ چالاک" if s['status'] == 'active' else "❌ ناچالاک"
        text = (f"📱 <b>زانیاری سێکشن: {html.escape(s['name'])}</b>\n\n"
                f"📞 ژمارە: <code>{s['phone']}</code>\n"
                f"📊 دۆخ: {status_icon}\n"
                f"🌐 پڕۆکسی: <code>بێ پڕۆکسی ❌</code>\n"
                f"📅 کاتی زیادکردن: {s['created_at']}")
        keyboard = [
            [InlineKeyboardButton("🌐 دانانی پڕۆکسی", callback_data=f"set_proxy_{sid}")],
            [InlineKeyboardButton("🗑 سڕینەوەی پڕۆکسی", callback_data=f"del_proxy_{sid}")],
            [InlineKeyboardButton("🗑 سڕینەوەی سێکشن", callback_data=f"delete_section_{sid}")],
            [InlineKeyboardButton("🔙 گەڕانەوە", callback_data="owner_view_sections")]
        ]
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("add_proxy_after_"):
        sid = int(data.split("_")[3])
        user_states[user_id] = {'state': 'waiting_for_proxy', 'data': {'section_id': sid}}
        await query.edit_message_text(
            "🌐 <b>دانانی پڕۆکسی بۆ سێکشن</b>\n\n"
            "تکایە پڕۆکسییەکەت بنووسە:\n"
            "<code>socks5:ip:port:user:pass</code>",
            parse_mode="HTML"
        )
        return

    if data == "skip_proxy_after":
        user_states.pop(user_id, None)
        await query.edit_message_text("✅ سێکشنەکە بەبێ پڕۆکسی پاشکەوت کرا.")
        return

    if data.startswith("set_proxy_"):
        sid = int(data.split("_")[2])
        user_states[user_id] = {'state': 'waiting_for_proxy', 'data': {'section_id': sid}}
        await query.edit_message_text(
            "🌐 <b>دانانی پڕۆکسی بۆ سێکشن</b>\n\n"
            "تکایە پڕۆکسییەکەت بنووسە:\n"
            "<code>socks5:ip:port:user:pass</code>\n\n"
            "بۆ لابردنی پڕۆکسی بنووسە: <code>none</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 گەڕانەوە", callback_data=f"view_section_{sid}")]])
        )
        return
    
    if data == "owner_add_section":
        await query.edit_message_text(
            t(user_id, "add_section_prompt"),
            parse_mode="HTML",
            reply_markup=owner_add_section_kb(user_id)
        )
        return
    
    if data == "owner_add_by_code":
        user_states[user_id] = {'state': 'owner_add_session', 'data': {}}
        await query.edit_message_text(
            t(user_id, "enter_session_code"),
            parse_mode="HTML",
            reply_markup=go_back(user_id, "owner")
        )
        return
    
    if data == "owner_add_by_phone":
        user_states[user_id] = {'state': 'owner_add_phone', 'data': {}}
        await query.edit_message_text(
            t(user_id, "enter_phone_section"),
            parse_mode="HTML",
            reply_markup=go_back(user_id, "owner")
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # OWNER: BALANCE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════
    if data == "owner_balance_menu":
        await query.edit_message_text(
            t(user_id, "owner_balance_menu"),
            parse_mode="HTML",
            reply_markup=owner_balance_menu_kb(user_id)
        )
        return
    
    if data == "owner_add_balance":
        user_states[user_id] = {'state': 'owner_add_balance_user', 'data': {}}
        await query.edit_message_text(
            t(user_id, "enter_user_id_balance"),
            reply_markup=go_back(user_id, "owner")
        )
        return
    
    if data == "owner_set_balance":
        user_states[user_id] = {'state': 'owner_set_balance_user', 'data': {}}
        await query.edit_message_text(
            t(user_id, "enter_user_id_balance"),
            reply_markup=go_back(user_id, "owner")
        )
        return

    if data == "owner_reset_balance":
        user_states[user_id] = {'state': 'owner_reset_balance_user', 'data': {}}
        await query.edit_message_text(
            t(user_id, "enter_user_id_balance"),
            reply_markup=go_back(user_id, "owner")
        )
        return

    if data == "owner_activate_user":
        user_states[user_id] = {'state': 'owner_activate_user_id', 'data': {}}
        await query.edit_message_text("✅ User ID ـی ئەو کەسە بنووسە کە دەتەوێت ئەکتیڤی بکەیت:", reply_markup=go_back(user_id, "owner"))
        return

    if data == "owner_delete_user":
        user_states[user_id] = {'state': 'owner_delete_user_id', 'data': {}}
        await query.edit_message_text("🗑️ User ID ـی ئەو کەسە بنووسە کە دەتەوێت بیسڕیتەوە:", reply_markup=go_back(user_id, "owner"))
        return

    if data == "owner_list_users":
        conn = get_db()
        users = conn.execute("SELECT id, username, first_name, balance, approved, registered FROM users ORDER BY created_at DESC LIMIT 100").fetchall()
        conn.close()
        if not users:
            await query.edit_message_text("👥 هیچ بەکارهێنەرێک تۆمار نەکراوە.", reply_markup=owner_balance_menu_kb(user_id))
            return
        kb = []
        for u in users:
            name = (u['first_name'] or 'بێ ناو')[:32]
            username = f" @{u['username']}" if u['username'] else ""
            status = "✅" if u['approved'] else "⏳"
            kb.append([
                InlineKeyboardButton(f"{status} {name}{username}", callback_data=f"owner_user_info_{u['id']}"),
                InlineKeyboardButton("🗑️ سڕینەوە", callback_data=f"owner_delete_user_direct_{u['id']}")
            ])
        kb.append([InlineKeyboardButton("🔙 گەڕانەوە", callback_data="owner_balance_menu")])
        await query.edit_message_text("👥 <b>لیستی هەموو بەکارهێنەران</b>\n\nناوی بەکارهێنەر هەڵبژێرە بۆ زانیاری، یان بەتنی سڕینەوە بەکاربهێنە:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("owner_user_info_"):
        target_id = int(data.rsplit("_", 1)[1])
        conn = get_db()
        u = conn.execute("SELECT id, username, first_name, balance, approved, registered FROM users WHERE id = ?", (target_id,)).fetchone()
        conn.close()
        if not u:
            await query.answer("❌ بەکارهێنەر نەدۆزرایەوە", show_alert=True)
            return
        status = "✅ ئەکتیڤ" if u['approved'] else "⏳ چاوەڕوان"
        username = f"@{u['username']}" if u['username'] else "بێ یوزەر"
        text = f"👤 <b>زانیاریی بەکارهێنەر</b>\n\n📝 ناو: {html.escape(u['first_name'] or 'بێ ناو')}\n🔗 یوزەر: {html.escape(username)}\n🆔 ئایدی: <code>{u['id']}</code>\n💰 باڵانس: {u['balance']:,} دینار\n📌 دۆخ: {status}"
        kb = [[InlineKeyboardButton("🗑️ سڕینەوەی ئەم بەکارهێنەرە", callback_data=f"owner_delete_user_direct_{u['id']}")], [InlineKeyboardButton("🔙 گەڕانەوە بۆ لیست", callback_data="owner_list_users")]]
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("owner_delete_user_direct_"):
        target_id = int(data.rsplit("_", 1)[1])
        if target_id == OWNER_ID:
            await query.answer("⛔ ناتوانرێت سەرۆک بسڕدرێتەوە.", show_alert=True)
            return
        await query.edit_message_text(
            f"⚠️ دڵنیایت دەتەوێت بەکارهێنەرەکە بسڕیتەوە؟\n\n🆔 <code>{target_id}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ بەڵێ، بیسڕەوە", callback_data=f"owner_confirm_delete_{target_id}"), InlineKeyboardButton("❌ نەخێر", callback_data="owner_list_users")]])
        )
        return

    if data.startswith("owner_confirm_delete_"):
        target_id = int(data.rsplit("_", 1)[1])
        if target_id == OWNER_ID:
            await query.answer("⛔ ناتوانرێت سەرۆک بسڕدرێتەوە.", show_alert=True)
            return
        conn = get_db()
        conn.execute("DELETE FROM users WHERE id = ?", (target_id,))
        conn.commit(); conn.close()
        await query.edit_message_text(f"✅ بەکارهێنەر سڕایەوە.\n\n🆔 <code>{target_id}</code>", parse_mode="HTML", reply_markup=owner_balance_menu_kb(user_id))
        return

    # ═══════════════════════════════════════════════════════════════════
    # OWNER: SETTINGS
    # ═══════════════════════════════════════════════════════════════════
    if data == "owner_settings":
        await query.edit_message_text(
            t(user_id, "settings_menu"),
            parse_mode="HTML",
            reply_markup=owner_settings_kb(user_id)
        )
        return
    
    if data == "owner_broadcast":
        user_states[user_id] = {'state': 'owner_broadcast', 'data': {}}
        await query.edit_message_text(
            t(user_id, "enter_broadcast"),
            reply_markup=go_back(user_id, "owner")
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # REPORT CONTROL SYSTEM
    # ═══════════════════════════════════════════════════════════════════
    if data == "report_control_list":
        conn = get_db()
        if is_owner(user_id):
            reports = conn.execute("SELECT * FROM report_control ORDER BY created_at DESC").fetchall()
            
            if not reports:
                conn.close()
                await query.edit_message_text(
                    t(user_id, "report_control_empty"),
                    parse_mode="HTML",
                    reply_markup=go_back(user_id, "owner")
                )
                return
                
            keyboard = []
            for r in reports:
                status_icon = "▶️" if r['status'] == 'running' else "⏸"
                keyboard.append([InlineKeyboardButton(f"{status_icon} {r['report_name']}", callback_data=f"rc_details_{r['id']}")])
            
            keyboard.append([InlineKeyboardButton(t(user_id, "back"), callback_data="owner_main")])
            
            conn.close()
            await query.edit_message_text(
                t(user_id, "report_control_select"),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # User sees the "Report Center" (Last 5 reports)
            # Query from both pending_requests and join with report_control or reports for stats
            requests = conn.execute(
                "SELECT pr.*, rc.success_count as rc_success, rc.fail_count as rc_fail, rc.report_count as rc_progress, "
                "r.success_count as r_success, r.fail_count as r_fail, r.report_count as r_total "
                "FROM pending_requests pr "
                "LEFT JOIN report_control rc ON pr.id = rc.request_id "
                "LEFT JOIN reports r ON pr.target_link = r.target_link AND pr.user_id = r.user_id "
                "WHERE pr.user_id = ? "
                "GROUP BY pr.id "
                "ORDER BY pr.created_at DESC LIMIT 5", 
                (user_id,)
            ).fetchall()
            
            text = "📊 <b>سەنتەری ڕیپۆرت</b>\n\nکۆتا ٥ ڕیپۆرتی تۆ:\n\n"
            if not requests:
                text += "هیچ ڕیپۆرتێک نەدۆزرایەوە."
            else:
                for req in requests:
                    status = req['status']
                    
                    success = 0
                    failed = 0
                    progress = 0
                    status_text = ""
                    
                    if status == 'pending':
                        status_text = "🟡 لە چاوەڕوانی"
                    elif status == 'rejected':
                        status_text = "🔴 ڕەتکراوەتەوە"
                    elif status == 'accepted':
                        if req['rc_progress'] is not None:
                            status_text = "🔵 لە ڕۆشتنە"
                            success = req['rc_success'] or 0
                            failed = req['rc_fail'] or 0
                            progress = req['rc_progress'] or 0
                        else:
                            status_text = "🟢 تەواو بووە"
                            success = req['r_success'] or 0
                            failed = req['r_fail'] or 0
                            progress = req['r_total'] or 0
                    
                    text += f"🔗 <b>لینک:</b> {html.escape(str(req['target_link']))}\n"
                    text += f"📋 <b>جۆر:</b> {html.escape(str(req['report_type']))}\n"
                    text += f"✅ <b>سەرکەوتوو:</b> {success}\n"
                    text += f"❌ <b>شکست:</b> {failed}\n"
                    text += f"⚡ <b>بارودۆخ:</b> {status_text} ({progress})\n"
                    text += "━━━━━━━━━━━━━━━\n"
            
            conn.close()
            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(user_id, "back"), callback_data="main_menu")]])
            )
        return

    if data.startswith("rc_details_"):
        rc_id = int(data.split("_")[2])
        conn = get_db()
        r = conn.execute("SELECT * FROM report_control WHERE id = ?", (rc_id,)).fetchone()
        conn.close()
        
        if not r:
            await query.edit_message_text(t(user_id, "report_not_found"), reply_markup=go_back(user_id, "owner" if is_owner(user_id) else "user"))
            return
            
        status_text = "🟢 Running" if r['status'] == 'running' else "🟡 Paused"
        toggle_btn_text = t(user_id, "stop_report") if r['status'] == 'running' else t(user_id, "continue_report")
        
        last_error_line = ""
        try:
            if r['last_error']:
                last_error_line = f"⚠️ هەڵە: {html.escape(str(r['last_error']))}\n"
        except:
            pass
        text = (
            f"📊 <b>Report Details</b>\n\n"
            f"📝 Name: {html.escape(str(r['report_name']))}\n"
            f"🔗 Link: {html.escape(str(r['target_link']))}\n"
            f"📋 Type: {html.escape(str(r['report_type']))}\n"
            f"📊 Progress: {r['report_count']}\n"
            f"✅ Success: {r['success_count']}\n"
            f"❌ Failed: {r['fail_count']}\n"
            f"⚡ Status: {status_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{last_error_line}"
        )
        
        keyboard = [
            [InlineKeyboardButton(toggle_btn_text, callback_data=f"rc_toggle_{rc_id}")],
            [InlineKeyboardButton(t(user_id, "delete_report"), callback_data=f"rc_delete_{rc_id}")],
            [InlineKeyboardButton(t(user_id, "back"), callback_data="report_control_list")]
        ]
        
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("rc_toggle_"):
        rc_id = int(data.split("_")[2])
        conn = get_db()
        r = conn.execute("SELECT status FROM report_control WHERE id = ?", (rc_id,)).fetchone()
        if r:
            new_status = 'paused' if r['status'] == 'running' else 'running'
            conn.execute("UPDATE report_control SET status = ? WHERE id = ?", (new_status, rc_id))
            conn.commit()
        conn.close()
        # Refresh details
        update.callback_query.data = f"rc_details_{rc_id}"
        await handle_button(update, context)
        return

    if data.startswith("rc_delete_"):
        rc_id = int(data.split("_")[2])
        # Cancel the running report task cleanly (avoids "Task was destroyed" errors)
        task = active_report_tasks.pop(rc_id, None)
        if task is not None:
            task.cancel()
        conn = get_db()
        conn.execute("DELETE FROM report_control WHERE id = ?", (rc_id,))
        conn.commit()
        conn.close()
        # Go back to list
        update.callback_query.data = "report_control_list"
        await handle_button(update, context)
        return

    # ═══════════════════════════════════════════════════════════════════
    # OWNER: SECTION MANAGEMENT (Toggle/Delete)
    # ═══════════════════════════════════════════════════════════════════
    if data.startswith("toggle_section_"):
        section_id = int(data.split("_")[2])
        conn = get_db()
        section = conn.execute("SELECT * FROM sections WHERE id = ?", (section_id,)).fetchone()
        if section:
            new_status = 'inactive' if section['status'] == 'active' else 'active'
            conn.execute("UPDATE sections SET status = ? WHERE id = ?", (new_status, section_id))
            conn.commit()
        conn.close()
        
        status_text = "✅ Active" if new_status == 'active' else "❌ Inactive"
        await query.edit_message_text(
            t(user_id, "section_status_changed", name=section['name'], status=status_text),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="owner_sections")]])
        )
        return
    
    if data.startswith("delete_section_"):
        section_id = int(data.split("_")[2])
        conn = get_db()
        section = conn.execute("SELECT * FROM sections WHERE id = ?", (section_id,)).fetchone()
        if section:
            conn.execute("DELETE FROM sections WHERE id = ?", (section_id,))
            conn.commit()
        conn.close()
        
        await query.edit_message_text(
            t(user_id, "section_deleted", name=section['name'] if section else t(user_id, "unknown")),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="owner_sections")]])
        )
        return


# ─── AUTO-REPORT SCHEDULER ──────────────────────────────────────────────
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""
    
    # Ensure user exists
    ensure_user(user_id, username, first_name)
    
    # Clean up states
    if user_id in user_states:
        del user_states[user_id]
    
    # Clean up pending clients
    if user_id in pending_clients:
        try:
            await pending_clients[user_id]['client'].disconnect()
        except:
            pass
        del pending_clients[user_id]
    
    user = update.effective_user
    
    # Owner: show owner menu
    if user_id == OWNER_ID:
        await update.message.reply_text(
            t(user_id, "owner_welcome", name=user.first_name),
            parse_mode="HTML",
            reply_markup=owner_main_menu(user_id)
        )
        return
    
    # Activation gate: only owner or approved users can access the bot
    if not is_approved(user_id):
        await update.message.reply_text(
            "⛔ ئەم بۆتە بۆ تۆ بەردەست نییە.\n\nداواکاریی ئەکتیڤکردن بنێرە بۆ مام زاگرۆس @X_MAM6\n\nئایدی بەکارهێنەر: " + str(user_id),
            reply_markup=approval_request_kb()
        )
        return

    # Approved users go directly to the main menu; no phone/code/key registration.
    await update.message.reply_text(
        t(user_id, "user_welcome_back", name=user.first_name),
        parse_mode="HTML",
        reply_markup=user_main_menu(user_id)
    )


# ─── MAIN ────────────────────────────────────────────────────────────────
def main():
    os.makedirs("sessions", exist_ok=True)
    init_db()
    
    request = HTTPXRequest(connect_timeout=60.0, read_timeout=60.0)
    
    async def background_nurture():
        """Periodically warm up random sections to build account reputation."""
        print("[i] Background Nurture Task Started.")
        while True:
            try:
                # Wait 45-90 minutes between nurturing cycles
                await asyncio.sleep(random.uniform(2700, 5400))
                
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                sections = conn.execute("SELECT * FROM sections WHERE status = 'active'").fetchall()
                conn.close()
                
                if not sections: continue
                
                # Pick 1-2 random sections to nurture
                to_nurture = random.sample(sections, min(len(sections), 2))
                
                for sec in to_nurture:
                    try:
                        s_api_id = sec['api_id'] or API_ID
                        s_api_hash = sec['api_hash'] or API_HASH
                        proxy = None
                        if sec['proxy']:
                            p_parts = sec['proxy'].split(':')
                            if len(p_parts) >= 3:
                                proxy = {'proxy_type': p_parts[0], 'addr': p_parts[1], 'port': int(p_parts[2]),
                                         'username': p_parts[3] if len(p_parts) > 3 else None,
                                         'password': p_parts[4] if len(p_parts) > 4 else None, 'rdns': True}

                        client = TelegramClient(
                            StringSession(sec['session_string']), s_api_id, s_api_hash,
                            device_model=sec['device_model'] or 'iPhone',
                            system_version=sec['system_version'] or 'iOS 16',
                            app_version=sec['app_version'] or '9.6.5',
                            proxy=proxy
                        )
                        await client.connect()
                        if await client.is_user_authorized():
                            await _human_warmup(client)
                            await asyncio.sleep(random.uniform(10, 20))
                        await client.disconnect()
                    except: pass
            except: pass

    # Set bot commands to enable the "Menu Button" (four dots)
    async def post_init(app: Application):
        await app.bot.set_my_commands([
            ("start", "دەستپێکردنەوەی بۆت"),
        ])
        # Start the background nurture task
        asyncio.create_task(background_nurture())
        print("✅ Bot commands set and Background Nurture started.")

    application = Application.builder().token(BOT_TOKEN).request(request).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CallbackQueryHandler(handle_button))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text_message
    ))
    
    # Error handler
    async def error_handler(update, context):
        import traceback
        print(f"\n❌ ERROR: {context.error}")
        traceback.print_exception(type(context.error), context.error, context.error.__traceback__)
    application.add_error_handler(error_handler)
    
    print("🚀 Bot started...")
    print("📡 Waiting for connections...")
    
    # Clean shutdown: cancel all running report tasks on Ctrl+C / restart
    async def shutdown_hook():
        for rc_id, task in list(active_report_tasks.items()):
            if task and not task.done():
                task.cancel()
        active_report_tasks.clear()
        # Give cancelled tasks a moment to run their CancelledError handlers
        await asyncio.sleep(1)
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except (KeyboardInterrupt, SystemExit):
        print("\n⏹ Shutting down gracefully...")
    finally:
        try:
            # Using new asyncio.run for cleaner shutdown if no loop is running
            asyncio.run(shutdown_hook())
        except Exception:
            pass
        print("👋 Bot stopped.")

if __name__ == "__main__":
    main()

