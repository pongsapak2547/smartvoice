"""Friendly runtime settings page."""

import streamlit as st

st.set_page_config(page_title="SmartVoice - Settings", page_icon="⚙️", layout="wide")

from smartvoice.env_settings import (
    DEMO_PRESET,
    REAL_AI_PRESET,
    env_bool,
    mask_secret,
    read_env,
    write_env,
)
from smartvoice.preflight import run_preflight_checks
from smartvoice.ui_helpers import get_current_user, init_page

init_page()

st.title("⚙️ Settings")
st.caption("ปรับโหมด demo และ AI ได้จากหน้านี้ โดยไม่ต้องเปิดไฟล์ `.env` เอง")

current_user, current_role = get_current_user()
if not current_user:
    st.warning("กรุณา login ที่ sidebar ก่อนปรับ settings")
    st.stop()

if current_role not in {"Admin", "Supervisor"}:
    st.error("เฉพาะ Admin หรือ Supervisor เท่านั้นที่ปรับ settings ได้")
    st.stop()

values = read_env()

# Whisper model → recommended Backend/Device/Compute (single source of truth).
# Editing this table is enough — auto-match below picks it up.
_WHISPER_MODELS = [
    "biodatlab/distill-whisper-th-large-v3",
    "large-v3",
    "large-v3-turbo",
]
_WHISPER_BACKENDS = ["auto", "transformers", "faster-whisper"]
_WHISPER_DEVICES = ["auto", "cpu", "cuda"]
_WHISPER_COMPUTES = ["auto", "float16", "int8"]

_WHISPER_RECOMMENDATIONS = {
    "biodatlab/distill-whisper-th-large-v3": {
        "backend": "transformers", "device": "cuda", "compute": "float16",
        "note": "HF transformers model ภาษาไทย — เหมาะกับ NVIDIA GPU (fp16); ถ้าไม่มี GPU ให้ตั้ง Device = cpu",
    },
    "large-v3": {
        "backend": "faster-whisper", "device": "cuda", "compute": "float16",
        "note": "CT2 native — ต้องการ NVIDIA GPU + CUDA + cuDNN; CPU mode ใช้ Compute = int8",
    },
    "large-v3-turbo": {
        "backend": "faster-whisper", "device": "cuda", "compute": "float16",
        "note": "Turbo variant — เร็วกว่า large-v3 ~2x บน GPU เดียวกัน",
    },
}


def _safe(saved, allowed, fallback):
    return saved if saved in allowed else fallback


# Initialize session_state once from .env so the form below shows saved values.
if "whisper_model_pick" not in st.session_state:
    st.session_state["whisper_model_pick"] = _safe(
        values.get("WHISPER_MODEL", _WHISPER_MODELS[0]), _WHISPER_MODELS, _WHISPER_MODELS[0],
    )
if "whisper_backend_pick" not in st.session_state:
    st.session_state["whisper_backend_pick"] = _safe(
        values.get("WHISPER_BACKEND", "transformers"), _WHISPER_BACKENDS, "transformers",
    )
if "whisper_device_pick" not in st.session_state:
    st.session_state["whisper_device_pick"] = _safe(
        values.get("WHISPER_DEVICE", "auto"), _WHISPER_DEVICES, "auto",
    )
if "whisper_compute_pick" not in st.session_state:
    st.session_state["whisper_compute_pick"] = _safe(
        values.get("WHISPER_COMPUTE", "auto"), _WHISPER_COMPUTES, "auto",
    )


def _apply_whisper_recommendation():
    """Auto-match Backend/Device/Compute when user picks a new Whisper model.

    Runs as on_change callback BEFORE the dependent selectboxes re-render,
    so it's legal to mutate their session_state keys.
    """
    rec = _WHISPER_RECOMMENDATIONS.get(st.session_state.get("whisper_model_pick", ""))
    if not rec:
        return
    st.session_state["whisper_backend_pick"] = rec["backend"]
    st.session_state["whisper_device_pick"] = rec["device"]
    st.session_state["whisper_compute_pick"] = rec["compute"]


mode_col, status_col = st.columns([1.2, 1])

with mode_col:
    st.subheader("Quick Mode")
    st.write("เลือก preset แล้วกด Apply เพื่อบันทึกลง `.env`")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Use Demo Laptop Mode", use_container_width=True):
            write_env(DEMO_PRESET)
            st.success("Saved demo mode. Restart the app to apply all settings.")
            st.rerun()
    with c2:
        if st.button("Use Real AI Mode", use_container_width=True):
            write_env(REAL_AI_PRESET)
            st.success("Saved real AI mode. Add HF token if needed, then restart.")
            st.rerun()

with status_col:
    st.subheader("Current Mode")
    is_demo = env_bool(values, "MOCK_STT", default=False)
    st.metric("STT", "Demo / Mock" if is_demo else "Real AI")
    token = values.get("HF_TOKEN", "")
    st.caption(f"HF token: `{mask_secret(token) or 'not set'}`")

st.divider()

st.subheader("Demo & AI Settings")

# Not wrapped in st.form: forms batch widget updates until submit, which
# would block the Whisper-model → Backend/Device/Compute auto-match from
# running live. Regular widgets + an explicit Save button preserve that UX.
demo_mode = st.toggle(
    "Demo mode (skip real STT and use mock transcripts)",
    value=env_bool(values, "MOCK_STT", default=False),
)

st.markdown("#### Real AI")
hf_token = st.text_input(
    "HuggingFace token",
    value="",
    type="password",
    placeholder="Leave blank to keep current token",
    help="Required for pyannote speaker diarization in real AI mode.",
)
clear_hf_token = st.checkbox("Clear saved HuggingFace token")

ollama_base_url = st.text_input(
    "Ollama base URL",
    value=values.get("OLLAMA_BASE_URL", "http://localhost:11434"),
)
ollama_model = st.text_input(
    "Ollama model",
    value=values.get("OLLAMA_MODEL", "scb10x/llama3.1-typhoon2-8b-instruct"),
)

st.markdown("#### Speech model")
whisper_model = st.selectbox(
    "Whisper model", _WHISPER_MODELS,
    key="whisper_model_pick", on_change=_apply_whisper_recommendation,
)
_rec = _WHISPER_RECOMMENDATIONS.get(whisper_model, {})
if _rec:
    st.caption(
        f"💡 แนะนำสำหรับโมเดลนี้: Backend = `{_rec['backend']}`, "
        f"Device = `{_rec['device']}`, Compute = `{_rec['compute']}` — {_rec['note']}"
    )
whisper_backend = st.selectbox("Backend", _WHISPER_BACKENDS, key="whisper_backend_pick")
whisper_device = st.selectbox("Device", _WHISPER_DEVICES, key="whisper_device_pick")
whisper_compute = st.selectbox("Compute", _WHISPER_COMPUTES, key="whisper_compute_pick")

submitted = st.button("Save Settings", use_container_width=True, type="primary")

if submitted:
    updates = {
        "MOCK_STT": "true" if demo_mode else "false",
        "OLLAMA_BASE_URL": ollama_base_url.strip() or "http://localhost:11434",
        "OLLAMA_MODEL": ollama_model.strip(),
        "WHISPER_MODEL": whisper_model,
        "WHISPER_BACKEND": whisper_backend,
        "WHISPER_DEVICE": whisper_device,
        "WHISPER_COMPUTE": whisper_compute,
    }
    if clear_hf_token:
        updates["HF_TOKEN"] = ""
    elif hf_token.strip():
        updates["HF_TOKEN"] = hf_token.strip()

    write_env(updates)
    st.success("Saved to `.env`. Restart the app with `run.bat` so every module uses the new settings.")

st.divider()

st.subheader("Readiness Checks")
for check in run_preflight_checks():
    if check.ok:
        st.success(f"{check.name}: {check.detail}")
    elif check.severity == "error":
        st.error(f"{check.name}: {check.detail}")
    else:
        st.warning(f"{check.name}: {check.detail}")
