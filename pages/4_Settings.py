"""Friendly runtime settings page."""

import streamlit as st

st.set_page_config(page_title="SmartVoice — ตั้งค่าระบบ", layout="wide")

from smartvoice.env_settings import (
    DEMO_PRESET,
    REAL_AI_PRESET,
    env_bool,
    mask_secret,
    read_env,
    write_env,
)
from smartvoice import audit as audit_trail
from smartvoice import discord_notify
from smartvoice.auth import PAGE_SETTINGS
from smartvoice.preflight import run_preflight_checks
from smartvoice.ui_helpers import audit, init_page

# Admin/Supervisor only (see smartvoice.auth.ROLE_PERMISSIONS).
current_user, current_role = init_page(PAGE_SETTINGS)

st.title("ตั้งค่าระบบ")
st.caption(
    "ปรับโหมดการทำงานของ AI และการแจ้งเตือน Discord ได้จากหน้านี้ โดยไม่ต้องแก้ไฟล์ `.env` เอง "
    "— ค่าส่วนใหญ่มีผลหลังเปิดโปรแกรมใหม่ (ปิดแล้วเปิด run.bat อีกครั้ง)"
)


@st.cache_data(ttl=300, show_spinner="กำลังตรวจความพร้อมของระบบ...")
def _cached_preflight_checks():
    return run_preflight_checks()

values = read_env()

mode_col, status_col = st.columns([1.2, 1])

with mode_col:
    st.subheader("เลือกโหมดด่วน")
    st.write("กดปุ่มเดียวเพื่อตั้งค่าทั้งชุด")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("โหมดสาธิต (ใช้บทสนทนาตัวอย่าง)", use_container_width=True,
                     help="ใช้บทสนทนาตัวอย่างแทนการถอดเสียงจริง — เหมาะกับโน้ตบุ๊กหรือการนำเสนอ"):
            write_env(DEMO_PRESET)
            audit(
                audit_trail.UPDATE, audit_trail.ENTITY_SETTINGS,
                entity_label="Demo Laptop Mode", changes=dict(DEMO_PRESET),
            )
            st.success("บันทึกโหมดสาธิตแล้ว — ปิดและเปิดโปรแกรมใหม่เพื่อให้มีผล")
            st.rerun()
    with c2:
        if st.button("โหมดใช้งานจริง (AI เต็มรูปแบบ)", use_container_width=True,
                     help="ถอดเสียงและแยกผู้พูดด้วย pyannoteAI และวิเคราะห์ด้วย Typhoon API"):
            write_env(REAL_AI_PRESET)
            audit(
                audit_trail.UPDATE, audit_trail.ENTITY_SETTINGS,
                entity_label="Real AI Mode", changes=dict(REAL_AI_PRESET),
            )
            st.success("บันทึกโหมด API แล้ว — ตั้งค่า API keys แล้วเปิดโปรแกรมใหม่")
            st.rerun()

with status_col:
    st.subheader("โหมดปัจจุบัน")
    is_demo = env_bool(values, "MOCK_STT", default=False)
    st.metric("การถอดเสียง", "โหมดสาธิต" if is_demo else "ใช้งานจริง")
    st.caption("ถอดเสียง: pyannoteAI API | วิเคราะห์: Typhoon API")

st.divider()

st.subheader("ตั้งค่าโดยละเอียด")

demo_mode = st.toggle(
    "โหมดสาธิต (ไม่ถอดเสียงจริง ใช้บทสนทนาตัวอย่าง)",
    value=env_bool(values, "MOCK_STT", default=False),
    help="เปิดเพื่อใช้บทสนทนาตัวอย่าง การวิเคราะห์ข้อความยังต้องใช้คีย์ Typhoon",
)

st.markdown("#### AI สำหรับการใช้งานจริง")
stt_provider = "pyannote_api"
llm_provider = "typhoon"
st.caption("บริการถอดเสียงและแยกผู้พูด: pyannoteAI API | บริการวิเคราะห์ข้อความ: Typhoon API")
api_updates = {}
if stt_provider == "pyannote_api" or llm_provider == "typhoon":
    st.info("โหมด API ส่งเสียงหรือบทสนทนาให้ผู้ให้บริการภายนอก และมีค่าใช้บริการตามบัญชีของคุณ")
    st.caption("ตั้งค่า key แล้วต้องเปิดโปรแกรมใหม่ การตรวจความพร้อมตรวจเพียงว่ามี key ยังไม่ยืนยันสิทธิ์หรือเครดิต")
if stt_provider == "pyannote_api":
    st.caption("ถอดเสียงด้วย Whisper Large v3 Turbo พร้อมแยกผู้พูด ไม่ต้องติดตั้งโมเดลหรือ GPU")
    api_updates["STT_API_MODEL"] = "faster-whisper-large-v3-turbo"
    api_updates["PYANNOTE_API_MODEL"] = st.selectbox(
        "รุ่น Pyannote API", ["precision-2", "precision-3"],
        index=1 if values.get("PYANNOTE_API_MODEL") == "precision-3" else 0,
        key="_pyannote_api_model",
        help="เลือกรุ่นที่บัญชี pyannoteAI ใช้แยกผู้พูดในไฟล์เสียง",
    )
if llm_provider == "typhoon":
    api_updates["TYPHOON_MODEL"] = st.text_input(
        "รุ่น Typhoon API", value=values.get("TYPHOON_MODEL", "typhoon-v2.5-30b-a3b-instruct"),
        help="เปลี่ยนเป็น typhoon-v2.1-12b-instruct เพื่อทดลองรุ่นเล็กลงได้ตามสิทธิ์ของบัญชี",
        key="_typhoon_api_model",
    ).strip()
for field, enabled in (("PYANNOTE_API_KEY", stt_provider == "pyannote_api"), ("TYPHOON_API_KEY", llm_provider == "typhoon")):
    if enabled:
        st.caption(f"{field}: {'ตั้งค่าไว้แล้ว' if values.get(field) else 'ยังไม่ได้ตั้งค่า'}")
        secret = st.text_input(
            field, type="password", help="กรอกคีย์ของบริการนี้เมื่อต้องการเปลี่ยนค่า",
            placeholder="เว้นว่างเพื่อใช้ค่าเดิม", key=f"_api_secret_{field}",
        )
        clear = st.checkbox(f"ลบ {field} ที่บันทึกไว้", key=f"_api_clear_{field}")
        if clear:
            api_updates[field] = ""
        elif secret.strip():
            api_updates[field] = secret.strip()
st.markdown("#### แจ้งเตือน Discord")
st.caption(
    "ส่งข้อความเข้าช่อง Discord ทุกครั้งที่มีคนรับเคส คืนเคส ปิดเคส หรือเปิดเคสอีกครั้ง — "
    "สร้าง webhook ได้ที่ Discord: ตั้งค่าช่อง → Integrations → Webhooks → New Webhook → Copy Webhook URL"
)
_saved_webhook = values.get(discord_notify.ENV_KEY, "")
st.caption(f"Webhook ปัจจุบัน: `{mask_secret(_saved_webhook) or 'ยังไม่ได้ตั้งค่า (ไม่ส่งแจ้งเตือน)'}`")
discord_webhook = st.text_input(
    "Discord webhook URL",
    value="",
    type="password",
    placeholder="เว้นว่างไว้ = ใช้ค่าเดิม",
    help="URL นี้เป็นความลับ — ใครมี URL ก็โพสต์เข้าช่องได้ ระบบจึงไม่แสดงเต็มและไม่บันทึกลง Audit log",
    key="_discord_webhook_input",
)
clear_discord_webhook = st.checkbox("ปิดการแจ้งเตือน Discord (ลบ webhook ที่บันทึกไว้)")
if st.button("ส่งข้อความทดสอบ", key="_discord_test_btn",
             help="ใช้ URL ที่พิมพ์ไว้ด้านบน ถ้าเว้นว่างจะใช้ค่าที่บันทึกไว้"):
    _ok, _detail = discord_notify.post(
        discord_notify.build_test_payload(current_user),
        url=discord_webhook.strip() or None,
    )
    (st.success if _ok else st.error)(_detail)

submitted = st.button("บันทึกการตั้งค่า", use_container_width=True, type="primary")

if submitted:
    updates = {
        "STT_PROVIDER": stt_provider,
        "LLM_PROVIDER": llm_provider,
        **api_updates,
        "MOCK_STT": "true" if demo_mode else "false",
    }

    webhook_error = None
    if clear_discord_webhook:
        updates[discord_notify.ENV_KEY] = ""
    elif discord_webhook.strip():
        if discord_notify.is_valid_webhook_url(discord_webhook):
            updates[discord_notify.ENV_KEY] = discord_webhook.strip()
        else:
            webhook_error = (
                "ไม่ได้บันทึก Discord webhook — URL ต้องขึ้นต้นด้วย "
                "`https://discord.com/api/webhooks/` (ค่าอื่นบันทึกแล้วตามปกติ)"
            )

    # HF_TOKEN / DISCORD_WEBHOOK_URL are redacted by smartvoice.audit before they reach the log.
    changed = audit_trail.diff_fields(values, updates)
    write_env(updates)
    if changed:
        audit(
            audit_trail.UPDATE, audit_trail.ENTITY_SETTINGS,
            entity_label="Save Settings", changes=changed,
        )
    st.success("บันทึกแล้ว — ปิดและเปิดโปรแกรมใหม่เพื่อให้ค่าใหม่มีผลทุกส่วน (โหมด API: python -m streamlit run Home.py)")
    if webhook_error:
        st.error(webhook_error)


st.divider()

st.subheader("ตรวจความพร้อมของระบบ")
if st.button("ตรวจสอบใหม่", key="_settings_recheck"):
    _cached_preflight_checks.clear()
for check in _cached_preflight_checks():
    if check.ok:
        st.success(f"{check.name}: {check.detail}")
    elif check.severity == "error":
        st.error(f"{check.name}: {check.detail}")
    else:
        st.warning(f"{check.name}: {check.detail}")
