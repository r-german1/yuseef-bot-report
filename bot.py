"""
Enhanced Report Bot - Complete Rewrite
Features: Registration flow removed, Open for all, Balance set to 800M, Sorani Kurdish only, Protection
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
BOT_TOKEN = os.getenv("BOT_TOKEN", "8927591228:AAGdIn4qL1xVXpH-jQ-lX_Ccgsy5jMByol4")

OWNER_ID = int(os.getenv("OWNER_ID", "7643191802"))
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
 'enter_code': {'ku': '✅ کۆدەکە بە سەرکەوتوویی نێردرا!\n'
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
    return "ku"

def t(user_id, key, **kwargs):
    lang = get_lang(user_id)
    text = T.get(key, {}).get("ku", key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass
    return text


def localized_error(user_id, result, fallback_key):
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
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT DEFAULT '',
        first_name TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        balance INTEGER DEFAULT 800000000,
        lang TEXT DEFAULT 'ku',
        registered INTEGER DEFAULT 1,
        logged_out INTEGER DEFAULT 0,
        session_sent INTEGER DEFAULT 0,
        user_session TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
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
    
    new_cols = [
        ('proxy', 'TEXT'), ('device_model', 'TEXT'), ('system_version', 'TEXT'), 
        ('app_version', 'TEXT'), ('api_id', 'INTEGER'), ('api_hash', 'TEXT'),
        ('lang_code', 'TEXT'), ('system_lang_code', 'TEXT'), ('cool_until', 'REAL')
    ]
    user_new_cols = [('user_session', 'TEXT'), ('approved', 'INTEGER DEFAULT 1')]
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
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO users (id, username, first_name, balance, registered, approved) VALUES (?, ?, ?, 800000000, 1, 1)",
        (user_id, username, first_name)
    )
    # Ensure balance is always set to 800M for everyone
    conn.execute("UPDATE users SET balance = 800000000, registered = 1, approved = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_owner(user_id):
    return user_id == OWNER_ID

def is_approved(user_id):
    return True

def set_approved(user_id, value):
    pass

def approval_request_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📨 داواکاریی ڕاستەوخۆ", callback_data="request_activation")]])

def owner_approval_kb(user_id):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ وەرگرتنی بەکارهێنەر", callback_data=f"approve_user_{user_id}"), InlineKeyboardButton("❌ ڕەتکردنەوە", callback_data=f"reject_user_{user_id}")]])

def is_registered(user_id):
    return True

def is_logged_out(user_id):
    return False

def set_registered(user_id, phone="", session=""):
    pass

async def check_user_session(user_id):
    return True

def set_logged_out(user_id, value):
    pass

def set_session_sent(user_id):
    pass

def get_user_balance(user_id):
    return 800000000

def update_balance(user_id, amount):
    pass

def get_new_balance(user_id):
    return 800000000

def get_user_total_spent(user_id):
    return 0

async def send_code_to_phone(user_id, phone):
    clean_phone = phone.replace("+", "").replace(" ", "")
    print(f"[DEBUG] send_code_to_phone: user={user_id}, phone={phone}")
    
    if user_id in pending_clients:
        try:
            await pending_clients[user_id]['client'].disconnect()
        except:
            pass
        del pending_clients[user_id]
    
    api_id, api_hash = API_ID, API_HASH
    
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
    import re
    cleaned = re.sub(r'[^A-Za-z0-9_\-]', '', session_string)
    if not cleaned:
        return cleaned
    cleaned = cleaned.rstrip('=')
    version, payload = cleaned[0], cleaned[1:]
    raw_len = (len(payload) * 3) // 4
    if raw_len == 263:
        target = 352
    elif raw_len == 273:
        target = 364
    else:
        return cleaned
    missing = target - len(payload)
    if missing > 0:
        cleaned = version + payload + '=' * missing
    elif missing < 0:
        cleaned = version + payload[:target]
    return cleaned


async def validate_session_string(session_string):
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

REASON_CODES = {
    'porn': types.InputReportReasonPornography(),
    'hack': types.InputReportReasonChildAbuse(),
    'terror': types.InputReportReasonViolence(),
    'drugs': types.InputReportReasonIllegalDrugs(),
    'scam': types.InputReportReasonFake(),
    'weapons': types.InputReportReasonOther(),
    'abuse': types.InputReportReasonViolence(),
    'other': types.InputReportReasonOther(),
    'spam': types.InputReportReasonSpam(),
}

TARGET_KEYWORDS = [
    'hack', 'cheat', 'vip', 'mod', 'config', 'injector', 'bypass', 'script', 'pubg', 'esp', 'aimbot',
    'هاک', 'چیت', 'بۆت', 'ڤای پی', 'کۆد', 'سێرڤەر', 'ئەپدیت', 'بایپاس', 'فایل', 'لینکی بۆت'
]
TARGET_EXTENSIONS = ['.apk', '.zip', '.rar', '.lua', '.txt', '.exe', '.ipa']

async def _scan_for_target_posts(client, channel_entity):
    target_msg_ids = []
    try:
        async for message in client.iter_messages(channel_entity, limit=20):
            is_target = False
            if message.text:
                text_lower = message.text.lower()
                if any(kw in text_lower for kw in TARGET_KEYWORDS):
                    is_target = True
                if ('t.me/' in text_lower or '@' in text_lower) and any(k in text_lower for k in ['hack', 'cheat', 'هاک', 'چیت']):
                    is_target = True
            
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
    if isinstance(reason_obj, types.InputReportReasonPornography): return 'Pornography'
    if isinstance(reason_obj, types.InputReportReasonOther): return 'Other'
    if isinstance(reason_obj, types.InputReportReasonViolence): return 'Violence'
    if isinstance(reason_obj, types.InputReportReasonIllegalDrugs): return 'IllegalDrugs'
    if isinstance(reason_obj, types.InputReportReasonFake): return 'Fake'
    if isinstance(reason_obj, types.InputReportReasonPersonalDetails): return 'PersonalDetails'
    if isinstance(reason_obj, types.InputReportReasonSpam): return 'Spam'
    return 'Other'


async def _check_account_health(client):
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

async def _human_warmup(client, target_entity=None):
    try:
        await client.get_me()
        await asyncio.sleep(random.uniform(1, 2))
        
        if random.random() < 0.2:
            await _check_account_health(client)
        
        popular_channels = ['@telegram', '@durov', '@news', '@GeekyKurd', '@KurdishNews', '@KurdSatNews', '@RudawEnglish']
        target = random.choice(popular_channels)
        try:
            entity = await client.get_entity(target)
            msgs = await client.get_messages(entity, limit=random.randint(5, 10))
            for m in msgs:
                if m.media and random.random() < 0.3:
                    await asyncio.sleep(random.uniform(1, 3))
            await asyncio.sleep(random.uniform(2, 4))
        except: pass
        
        try:
            from telethon.tl.functions.account import UpdateStatusRequest
            await client(UpdateStatusRequest(offline=False))
        except: pass

        try:
            from telethon.tl.functions.contacts import SearchRequest
            queries = ['news', 'kurd', 'tech', 'bot', 'channel', 'kurdistan', 'sport']
            await client(SearchRequest(q=random.choice(queries), limit=5))
        except: pass
        
        if target_entity:
            async for message in client.iter_messages(target_entity, limit=5):
                pass
            await asyncio.sleep(random.uniform(1.5, 3.0))
    except:
        pass

async def _resolve_entity(client, channel_username):
    try:
        if random.random() < 0.4:
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
            await asyncio.sleep(random.uniform(1, 2))
            entity = await client.get_entity(uname_try)
            if entity is not None:
                return entity, None
        except Exception as e:
            last_err = f"Resolve failed ({uname_try}): {str(e)[:60]}"
            continue
    
    try:
        from telethon.tl.functions.contacts import SearchRequest
        result = await client(SearchRequest(q=uname, limit=10))
        if result and result.chats:
            for chat in result.chats:
                if hasattr(chat, 'username') and chat.username and uname.lower() in chat.username.lower():
                    entity = await client.get_entity(chat.id)
                    if entity is not None:
                        return entity, None
            if result.chats:
                entity = await client.get_entity(result.chats[0].id)
                return entity, None
    except Exception as e:
        last_err = f"Search failed: {str(e)[:60]}"
    
    return None, last_err


async def _send_one_report(section, channel_username, message_ids, report_reason):
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

                battery_level = random.randint(15, 95)
                is_charging = random.choice([True, False])
                connection_type = random.choice(['wifi', '4g', '5g'])
                
                if 'battery_level' not in section:
                    section['battery_level'] = battery_level
                    section['connection_type'] = connection_type

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
                
                try:
                    await asyncio.wait_for(client.connect(), timeout=15)
                except Exception as ce:
                    return False, f"CONNECTION_FAILED: {str(ce)}"

                if not await client.is_user_authorized():
                    await client.disconnect()
                    return False, "Not authorized (Session revoked or expired)"
                
                await asyncio.wait_for(client.get_me(), timeout=10)

                try:
                    from telethon.tl.functions.contacts import SearchRequest
                    await client(SearchRequest(q=channel_username, limit=5))
                    await asyncio.sleep(random.uniform(2, 4))
                except: pass

                entity, resolve_err = await _resolve_entity(client, channel_username)
                if entity is None:
                    await client.disconnect()
                    return False, resolve_err or "Channel not found"

                await _human_warmup(client, entity)
                await asyncio.sleep(random.uniform(3, 7))
                
                try:
                    from telethon.tl.functions.channels import GetFullChannelRequest
                    await client(GetFullChannelRequest(channel=entity))
                except: pass

                try:
                    msgs = await client.get_messages(entity, limit=12)
                    if msgs:
                        await client.send_read_acknowledge(entity, max_id=msgs[0].id)
                        
                        for m in msgs[:5]:
                            if m.media:
                                await asyncio.sleep(random.uniform(2, 5))
                        
                        try:
                            from telethon.tl.functions.messages import SendReactionRequest
                            reaction = random.choice(['👎', '🤡', '😡'])
                            await client(SendReactionRequest(
                                peer=entity,
                                msg_id=msgs[0].id,
                                reaction=[types.ReactionEmoji(emoticon=reaction)]
                            ))
                        except: pass

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

                joined_now = False
                try:
                    from telethon.tl.functions.channels import JoinChannelRequest
                    await client(JoinChannelRequest(entity))
                    joined_now = True
                    await asyncio.sleep(random.uniform(5, 12))
                except:
                    pass

                try:
                    from telethon.tl.functions.messages import SetTypingRequest
                    await client(SetTypingRequest(
                        peer=entity,
                        action=types.SendMessageChooseContactAction()
                    ))
                    await asyncio.sleep(random.uniform(1, 2))
                except: pass

                found_posts = []
                if not message_ids:
                    found_posts = await _scan_for_target_posts(client, entity)
                
                reason_label = _reason_label(report_reason)
                
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

                if message_ids:
                    result = await client(ReportRequest(
                        peer=entity,
                        id=message_ids,
                        reason=report_reason,
                        message=final_complaint
                    ))
                else:
                    result = await client(ReportPeerRequest(
                        peer=entity,
                        reason=report_reason,
                        message=final_complaint
                    ))
                
                if result:
                    if joined_now:
                        try:
                            from telethon.tl.functions.channels import LeaveChannelRequest
                            await asyncio.sleep(random.uniform(5, 10))
                            await client(LeaveChannelRequest(entity))
                        except: pass

                    await _safe_disconnect(client)
                    return found_posts if found_posts else True, None
                else:
                    await _safe_disconnect(client)
                    return False, "Server rejected the report request"

            except asyncio.CancelledError:
                await _safe_disconnect(client)
                raise
            except FloodWaitError as e:
                wait_secs = e.seconds if hasattr(e, 'seconds') else 30
                if client:
                    await _safe_disconnect(client)
                return False, f"FloodWait {wait_secs}s"
            except Exception as e:
                err_str = str(e).lower()
                is_transport_error = ("checksum" in err_str or "session id" in err_str or
                                      "wrong session" in err_str or "invalid buffer" in err_str or
                                      "invalid checksum" in err_str or "sent invalid buffer" in err_str)
                if is_transport_error and _retry_left > 0:
                    _retry_left -= 1
                    if client:
                        await _safe_disconnect(client)
                        client = None
                    continue
                if is_transport_error or "session has been revoked" in err_str or "phone banned" in err_str:
                    if client:
                        await _safe_disconnect(client)
                    try:
                        conn = sqlite3.connect(DB_FILE)
                        conn.execute("UPDATE sections SET status = 'inactive' WHERE phone = ?", (section['phone'],))
                        conn.commit()
                        conn.close()
                    except: pass
                    return False, "SESSION_DEAD"
                if client:
                    await _safe_disconnect(client)
                return False, f"{str(e)[:100]}"

async def _safe_disconnect(client, label=""):
    if client is None:
        return
    try:
        await client.disconnect()
    except Exception:
        try:
            await asyncio.wait_for(client.disconnect(), timeout=3)
        except Exception:
            pass

async def send_reports_core(link, rtype, max_reports, section_count=-1, endless=False, 
                            progress_msg=None, update=None, query=None, user_id=None, report_control_id=None):
    conn = get_db()
    all_sections = conn.execute("SELECT * FROM sections WHERE status = 'active'").fetchall()
    conn.close()
    
    if section_count == -1 or section_count >= len(all_sections):
        sections = all_sections
    else:
        sections = all_sections[:section_count]
    
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
    
    hybrid_mode = (rtype == 'hybrid')
    target_posts = []
    if target_msg_id:
        target_posts = [target_msg_id]
    
    report_reason = REASON_CODES.get(rtype if not hybrid_mode else 'hack', REASON_CODES['spam'])
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
    reasons_cycle = list(REASON_CODES.values())
    try:
        reason_idx = reasons_cycle.index(report_reason)
    except ValueError:
        reason_idx = 0
    
    if report_control_id is not None:
        active_report_tasks[report_control_id] = asyncio.current_task()
    
    try:
        while (total_attempted < max_reports) if max_reports > 0 else True:
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

            import time
            now_ts = time.time()
            
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
                await asyncio.sleep(5)
                continue
            
            section = valid_section
            current_reason = reasons_cycle[reason_idx % len(reasons_cycle)]
            reason_idx += 1
            total_attempted += 1
            
            current_msg_ids = []
            if hybrid_mode or target_msg_id:
                if total_attempted % 2 == 0:
                    current_msg_ids = []
                else:
                    current_msg_ids = target_posts if target_posts else []
            
            ok, err = await _send_one_report(section, channel_username, current_msg_ids, current_reason)
            
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
            
            delay = random.uniform(5, 12)
            if total_attempted % 7 == 0:
                delay += random.uniform(20, 40)
            
            await asyncio.sleep(delay)
            
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
        if report_control_id is not None:
            active_report_tasks.pop(report_control_id, None)
        return
    
    if report_control_id is not None:
        active_report_tasks.pop(report_control_id, None)
    
    conn = get_db()
    conn.execute(
        "INSERT INTO reports (user_id, target_link, report_type, target_name, sections_used, success_count, fail_count, status, report_count, cost) VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?)",
        (user_id or 0, link, rtype, channel_username, len(sections), success, failed, total_attempted, 0)
    )
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

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""
    
    ensure_user(user_id, username, first_name)
    
    state = user_states.get(user_id, {}).get('state', None)
    data = user_states.get(user_id, {}).get('data', {})
    
    text = update.message.text.strip()
    
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
            await update.message.reply_text(phone, reply_markup=go_back(user_id, "owner"))
        return
    
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
    
    await update.message.reply_text(
        t(user_id, "user_menu"),
        parse_mode="HTML",
        reply_markup=user_main_menu(user_id)
    )
