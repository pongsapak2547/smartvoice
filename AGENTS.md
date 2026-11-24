# AGENTS.md — Guide for AI Coding Agents

> API-only update (2026-11-15, PM request): Local Whisper/Pyannote inference and Ollama execution have been removed. Use pyannoteAI + Typhoon APIs only; older local-model guidance below is historical. `requirements.txt` installs API dependencies. `ollama_client.py` keeps its import name for compatibility but calls Typhoon only. Do not restore local model dependencies or launchers. `MOCK_STT` mocks speech only; LLM still requires an API key. Retired local-inference/configuration tests were replaced with API-only checks; retain business-rule tests. `tests/test_config.py` now contains only pure text/grouping tests, with no torch or real DB initialization. Existing data, `.env`, installed packages and model caches must not be deleted. See SETUP.md for migration.

คู่มือสำหรับ AI agents (Cascade, Claude Code, Cursor, etc.) ที่ทำงานบน codebase นี้
อ่านไฟล์นี้ก่อนเริ่มแก้งานใหญ่ทุกครั้ง

---

## 1. โปรเจคนี้คืออะไร

**SmartVoice** — AI Call Center Analytics สำหรับสายภาษาไทย

**Pipeline ภาพรวม:** `audio (.wav/.mp3) → pyannoteAI API (Whisper Turbo + Precision diarization) → LLM speaker correction (Typhoon API) → LLM analysis (Typhoon API) → insight_rules (ตรวจคำตอบ AI) → SQLite → Streamlit UI`

เว็บ, SQLite, ไฟล์เสียง, checkpoint และ background threads ยังอยู่บนเครื่องที่รันแอป — PostgreSQL, object storage, distributed worker และ Cloud deployment เป็น **แผนเท่านั้น ยังไม่มีโค้ด** ดู `docs/cloud_migration_plan.md` และ `PROJECT_STATUS.md`

**Domain:** call-centre ของบริษัทขายที่นอน/เฟอร์นิเจอร์ (Restonic, โลตัส) — ลูกค้าโทรเข้าร้องเรียน/ติดตามคำสั่งซื้อ/เคลมประกัน

**Tech:** Python 3.10–3.12, Streamlit 1.55, SQLite, `requests` → pyannoteAI API (`precision-2`/`precision-3` + `faster-whisper-large-v3-turbo`) และ Typhoon API (`typhoon-v2.5-30b-a3b-instruct`), `fpdf2` + `uharfbuzz` (รายงาน PDF), `openpyxl` (Excel) — dependencies ทั้งหมดอยู่ใน `requirements-api.txt` (ไม่มี torch / CUDA / transformers / pyannote.audio / Ollama แล้ว ห้ามนำกลับมา)

---

## 2. Quick-start (commands จริงที่ใช้บ่อย)

**OS:** Windows + PowerShell. **อย่าใช้ `cd`** — ตั้ง `Cwd` แทน

**Working dir:** root ของ repository นี้ (`SojiKlay/smartvoice-master`) — ระวังสับสนกับ repo ยุค Local เดิมที่อาจอยู่ในเครื่องเดียวกัน

**Python interpreter:** `.venv\Scripts\python.exe` (Windows venv path, Python 3.10–3.12)

```powershell
# รัน test ทั้งชุดด้วย API จำลอง — ตั้ง env เฉพาะ process, ไม่อ่าน .env, ไม่ใช้ key จริง
$env:STT_PROVIDER='pyannote_api'; $env:LLM_PROVIDER='typhoon'; $env:PYTHON_DOTENV_DISABLED='1'
$env:TYPHOON_API_KEY='test-only'; $env:PYANNOTE_API_KEY='test-only'
$env:DB_PATH=Join-Path $PWD '.pytest_cache/runtime/test.db'
$env:TEMP=Join-Path $PWD '.pytest_cache/temp'; $env:TMP=$env:TEMP
& ".venv\Scripts\python.exe" -m pytest tests\ -q --basetemp=.pytest_cache/work

# รันเฉพาะไฟล์ (env เดียวกับด้านบน)
& ".venv\Scripts\python.exe" -m pytest tests\test_pipeline.py -v

# เปิดแอป
.venv\Scripts\activate
streamlit run Home.py   # → http://localhost:8501

# หรือใช้ launcher
run.bat                 # Windows
./run.sh                # Linux/macOS
```

**Test baseline ล่าสุด:** 596 tests (ทั้ง `tests/` รวม `test_config.py`) ต้องผ่าน 100% ก่อน commit ทุกครั้ง — 15 พ.ย. 2026: 596 passed บน Python 3.12 ด้วย env ด้านบน (เดิม 541 ก่อนเพิ่ม tests ของงาน security/deploy สำหรับ AWS pilot) เป็น tests ที่ mock API **ไม่ใช่หลักฐาน** ว่า live API / PostgreSQL / Cloud ใช้งานได้

**ก่อนประมวลผลสายจริง:** ต้องตั้ง `PYANNOTE_API_KEY` และ `TYPHOON_API_KEY` (หน้า Settings หรือ `.env`) ทุกสายจะส่งเสียงไป pyannoteAI และส่งข้อความไป Typhoon และมีค่าใช้จ่าย ใช้เฉพาะเสียงที่ได้รับอนุญาตให้ส่งออกภายนอก

**เข้าใช้งานครั้งแรก:** ถ้ายังไม่มีบัญชีใดในระบบ แอปสร้าง `admin` / `admin1234` ให้อัตโนมัติ (มีคำเตือนค้างจนกว่าจะเปลี่ยนรหัสผ่าน)

---

## 3. โครงสร้างไฟล์สำคัญ

```
smartvoice/
├── Home.py                     # Router: login → st.navigation ตามสิทธิ์ของ role + หน้าแรก
├── pages/
│   ├── 1_📤_Admin.py           # อัปโหลดและประมวลผลเสียง / เคส (Admin, Supervisor)
│   ├── 2_📊_Dashboard.py       # Dashboard → ภาพรวม (ทุก role)
│   ├── 3_👥_Customers.py       # ลูกค้าและการรับประกัน — คลิกแถวเปิดรายละเอียด (ทุก role)
│   ├── 4_Settings.py           # ตั้งค่า .env + Discord (Admin, Supervisor)
│   ├── 5_👤_Users.py           # บัญชีพนักงาน — เพิ่ม / เปลี่ยน role / เปิด-ปิด (Admin)
│   ├── 6_➕_Data_Entry.py      # เพิ่ม / แก้ / ซ่อน / กู้คืน / ยกเลิก ลูกค้าและทะเบียน (Admin)
│   ├── 7_📜_Audit_Log.py       # ประวัติการใช้งาน (Admin, Supervisor)
│   ├── 8_Dashboard_Insights.py # Dashboard → คีย์เวิร์ด แบรนด์ ช่องทาง
│   ├── 9_Dashboard_Anomaly.py  # Dashboard → สายที่ผิดปกติ
│   ├── 10_Agent_Performance.py # Dashboard → ผลงานพนักงาน
│   ├── 11_Cases.py             # จัดการเคส — รับเคส / ปิดเคส (ทุก role)
│   ├── 12_Call_Summaries.py    # Dashboard → รายการสาย
│   └── 13_Sales_Orders.py      # ใบสั่งขาย (SO) — ดู: ทุก role, นำเข้า/แก้ไข: Admin
├── smartvoice/                 # Business logic package
│   ├── config.py               # ⚠️ environment vars ทั้งหมดอยู่ที่นี่
│   ├── db.py                   # SQLite schema + migrations + CRUD
│   ├── pipeline.py             # 🔥 Core orchestrator (70 KB) — speaker correction, splitters, merge
│   ├── prompts.py              # 🔥 LLM prompts (54 KB) — system+user สำหรับทุก LLM call
│   ├── ollama_client.py        # LLM client (ชื่อเดิมเพื่อ imports แต่เรียก Typhoon API เท่านั้น) + JSON extraction (5 คำขอวิเคราะห์)
│   ├── insight_rules.py        # 🔥 ตรวจทุกคำตอบของ LLM ก่อนบันทึก (quote, คะแนน, ธง, รายชื่อ)
│   ├── file_manager.py         # Upload + SHA-256 dedup + ชื่อไฟล์ → เบอร์/ทิศทาง/รหัสพนักงาน/เวลาโทร + หลักฐานการซื้อ
│   ├── labels.py               # คำไทยของทุกรหัส + thai_time() (UTC → UTC+7)
│   ├── case_workflow.py        # รับเคส / คืน / เปลี่ยนสถานะ (กันแย่งเคส) + case_brief()
│   ├── discord_notify.py       # แจ้งเตือน Discord (webhook, background, ไม่ raise)
│   ├── dashboard_common.py     # ตัวกรองร่วมของ Dashboard + สไตล์กราฟ + ปุ่มส่งออกรายงาน
│   ├── dashboard_report.py     # รายงาน PDF / CSV + สูตรคะแนนพนักงาน (ไม่ import Streamlit)
│   ├── sales_orders.py         # นำเข้า/บันทึกใบสั่งขาย + แม่แบบ Excel (ไม่ import Streamlit)
│   ├── so_view.py              # แสดง SO แบบเอกสาร (หน้า SO, ลูกค้า, เคส)
│   ├── customer_view.py        # ตาราง + หน้าต่างรายละเอียดลูกค้า
│   ├── ui_helpers.py           # CSS, login page, init_page() role guard, audit() wrapper, processing launcher
│   ├── auth.py                 # PBKDF2 hashing, บัญชี DB/.env, ROLE_PERMISSIONS
│   ├── audit.py                # คำศัพท์ audit trail + record() + redact() + diff_fields()
│   ├── customer_entry.py       # กติกา validate / บันทึก / ซ่อน / กู้คืน / ยกเลิกทะเบียน ของหน้าเพิ่มข้อมูล
│   ├── env_settings.py         # อ่าน/เขียน .env (read_env / write_env / mask_secret) — GPU/combo helpers ถูกถอดแล้ว
│   ├── preflight.py            # Readiness checks: Python, โหมดสาธิต, รหัส bootstrap, มี API key หรือไม่ (ไม่เรียก API)
│   ├── login_guard.py          # กันเดารหัสผ่านฝั่ง server (นับรวมทุก session ใน process)
│   ├── logger.py               # Rotating file logger
│   └── stt/                    # Speech-to-Text sub-package
│       ├── orchestrator.py     # pyannoteAI: upload → job → poll → segments + checkpoint + MOCK_STT
│       ├── audio.py            # has_thai() — helper ข้อความเท่านั้น
│       └── diarize.py          # helpers จัด label ผู้พูด / กลุ่มคำ (ไม่โหลดโมเดล)
│                               # (transcribe.py ถูกถอดออกพร้อม local inference)
├── tests/                      # pytest unit tests
├── data/                       # 🚫 gitignored runtime data (audio, db, logs, models, warranty_proofs)
├── deploy/aws-ec2/             # ติดตั้งบน EC2 เครื่องเดียว (install.sh, systemd, Caddy, backup) + README ภาษาไทย
└── docs/                       # Architecture, DB design, user manual
```

**DB tables:** `calls`, `customers`, `warranty_registrations`, `sales_orders`, `sales_order_lines`, `call_customer_links`, `cases`, `users`, `audit_log`

⚠️ ชื่อไฟล์ใน `pages/` บางไฟล์มี emoji อยู่จริง และ `Home.py` route ไปที่ path ตรงตัวนั้น — ห้ามลบ emoji ออกจาก path (แต่ห้ามใส่ emoji ในป้ายที่ผู้ใช้เห็น ดูข้อ 7.8)

---

## 4. หลักการทำงาน (สำคัญที่สุด)

### 4.1 Bug-fixing discipline
- **หา root cause ก่อนแก้** — อย่าทำ downstream workaround
- ใช้การแก้แบบ minimal upstream fix (มักเป็น 1-line) มากกว่า over-engineer
- เพิ่ม regression test ทุกครั้งที่แก้ bug
- ห้ามลบ/ลดความเข้มงวดของ test ที่มีอยู่ ถ้าไม่ได้รับอนุญาตชัดเจน

### 4.2 Testing discipline
- เขียน test ก่อนทำงาน implementation ใหญ่
- รัน test ทุกครั้งหลังแก้: ทั้งชุด `tests\` ด้วย env API จำลองในข้อ 2
- แยกผล mock tests ออกจากหลักฐาน live API / PostgreSQL / Cloud ทุกครั้งที่รายงาน
- ถ้าทำ test pass ไม่ได้ → **ห้ามแก้ test ให้มันผ่าน** ให้แก้ code แทน

### 4.3 Code style
- **ห้ามเติมหรือลบ comment / docstring** ถ้าไม่ได้สั่ง
- ตามสไตล์ที่มีอยู่ในไฟล์ (snake_case, double-quoted strings, type hints)
- Import ต้องอยู่บนสุดของไฟล์เสมอ — ห้ามใส่กลางไฟล์
- ใช้ regex ที่มี comment กำกับ pattern ภาษาไทยถ้าซับซ้อน

### 4.4 อย่าสร้างไฟล์รก
- ห้ามสร้าง `.md` ใหม่เพื่อสรุปงานตัวเอง
- Sanity script ชั่วคราว (`_*.py`) ต้องลบหลังใช้
- อย่าสร้าง helper module ใหม่ถ้ามี util เดิมที่ทำได้

---

## 5. Pipeline architecture (ส่วนสำคัญที่ agent ต้องเข้าใจ)

### 5.1 Speaker correction multi-pass (`pipeline.py:1408-1459`)

```
1. STT → diarization → grouped segments
2. _split_long_segments_by_sentence()         # pre-split mega-chunks at Thai boundaries
3. ollama_client.correct_speakers()            # LLM-based label correction
4. _aggressive_relabel_from_strong_cues()      # ⭐ deterministic override จาก domain cues
5. Splitters (ในลำดับนี้):
   _split_opening_mixed_turns()
   _split_answer_prefixed_turns()
   _split_embedded_agent_answer_turns()
   _split_mixed_question_answer_turns()
   _split_followup_question_turns()
   _split_embedded_customer_reaction_turns()
   _split_trailing_customer_question_turns()
   _split_leading_agent_continuation_turns()
   _split_mixed_closing_turns()
6. _stabilize_sandwiched_turns()
7. _aggressive_relabel_from_strong_cues()      # อีกรอบ — บน chunks ที่ splitter สร้าง
8. _merge_adjacent_same_speaker()
9. _enforce_role_rules()
10. ollama_client.cleanup_transcript()         # LLM text polish
11. ทำซ้ำ steps 2-9 รอบ 2
12. _apply_domain_normalization()
13. _drop_redundant_opening_segments() / _drop_adjacent_duplicate_segments()
```

**Key insight:** Pyannote มัก mislabel — LLM ก็พลาดบ่อย → ใช้ rule-based override ที่ตรวจ "strong cues" ภาษาไทย:
- **Customer cues:** `พี่(สะดวก|ติดประชุม|ลางาน|...)`, `ได้ไหมลูก`, `ขอเลื่อนวัน`, `ติดตามเรื่องส่ง...`
- **Agent cues:** `พลอย(ขอ|ดู|...)`, `คุณลูกค้า`, `ทางบริษัท`, `กลุ่มบริษัทที่นอน`

### 5.2 LLM analysis (`ollama_client.py`) — AI เสนอ `insight_rules.py` ตัดสิน

5 คำขอแยกกันไปที่ Typhoon API (นอกจากนี้ยังมีแก้ผู้พูด, เกลาข้อความ และจับคู่เคส) temperature 0, `max_tokens` = `TYPHOON_MAX_TOKENS` (ค่าเริ่มต้น 4096) — ไม่ได้ใช้ JSON mode ของบริการ (`json_mode` ใน `chat()` ถูกละไว้) แอปแยก JSON เอง; ค่า `num_ctx` / `format: "json"` ของ Ollama ไม่มีแล้ว:
1. `extract_summary_and_topics()` — summary, topic, **topic_detail**, keywords, brand/platform mentions
2. `analyze_sentiment()` — customer_quote → reason → sentiment (ให้หยิบคำพูดก่อน ป้ายจึงยึดกับหลักฐาน)
3. `evaluate_agent_qa()` — QA checklist: `"found": [{"item": "P1", "quote": ...}]` + `customer_had_problem`
3b. ฟังก์ชันเดียวกัน **แยกคำขอ** สำหรับสิ่งที่ต้องทำต่อ (`prompts.NEXT_ACTION_USER`) — ถามรวมกับ checklist แล้วโมเดลตอบ `pending: false` กับสายที่ยังมีงานค้างชัดเจน
4. `detect_anomaly()` — category + evidence_quote + reason

**คำขอที่ล้มเหลวทำให้สายนั้นล้มเหลว — ไม่บันทึกค่าว่างแบบเงียบ ๆ:** ไม่มี key, เชื่อมต่อไม่ได้/timeout, HTTP ไม่ใช่ 2xx (รวม 429), คำตอบถูกตัด (`finish_reason == "length"`), คำตอบว่าง หรือ JSON อ่านไม่ได้ → `ollama_client.APIError` แล้ว `process_call()` ตั้งสายเป็น `error` ไม่มี retry อัตโนมัติ เพราะทุกครั้งที่ retry มีค่าใช้จ่าย (ทางที่ `except Exception` คืนค่าเดิม/ค่าว่าง ทำงานเฉพาะ provider อื่นที่ `config.api_settings()` ไม่ยอมรับแล้ว) — ผลที่วัดในส่วนนี้ได้จาก Typhoon 8B บน Ollama รุ่นเดิม ยังไม่ได้ตรวจซ้ำกับรุ่น API; Transcript ยาวเกิน `MAX_CHARS` (14,000) ถูกตัด**ช่วงกลาง** (เดิมเก็บแค่ 6,000 ตัวแรก ทำให้ 4 ใน 11 สายจริงเสียช่วงปิดสาย)

**ห้ามเชื่อตัวเลข ธง หรือรายการที่โมเดลส่งมา — `insight_rules.py` คำนวณใหม่** (ทดสอบกับสายจริง 11 สาย ดู `tests/test_insight_rules.py`):
- QA: ข้อหนึ่งนับเมื่อ quote เป็นสิ่งที่พนักงานพูด (`agent_said()`: ไม่อยู่ในบรรทัด `Customer:` หรือเป็นน้ำเสียงพนักงาน — diarization มักทิ้งคำพนักงานเป็น "Speaker 0" หรือรวมไปในบรรทัดลูกค้า); P2 (ค่ะ/ครับ) วัดจากสัดส่วน ไม่ใช้ quote; คะแนน = สัดส่วนข้อที่ใช้ได้ (P3 ใช้เมื่อลูกค้ามีปัญหา) แปลงเป็น 1-5 — prompt เก่าให้ 5/5 ทุกสาย
- สิ่งที่ต้องทำต่อ: `build_next_action()` ต่อ งาน | รายละเอียด | กำหนด | การติดตาม, เติม "ไม่ระบุในสาย (แนะนำ: …)" จากผู้รับผิดชอบ, ตัดของที่หลุดจาก template (`<...>`, `[บริบท]`); `money_action_is_ungrounded()` ปฏิเสธงานคืนเงินในสายที่ไม่คุยเรื่องเงิน
- อารมณ์: `check_sentiment()` — เชิงบวกต้องมีคำชมในคำพูดลูกค้า ("ขอบคุณครับ" อย่างเดียวเคยถูกนับเป็นบวก); ลูกค้าที่สบถ/บอกตรง ๆ ว่าไม่พอใจไม่มีทางเป็นบวก/กลาง
- ความผิดปกติ: `verify_anomaly()` — quote ต้องมีในสายและมีคำของหมวด; ความรุนแรงมาจากตารางหมวด; `keyword_anomaly()` สแกน**เฉพาะบรรทัดลูกค้า**หาคำเรื่องสุขภาพและคำหยาบ; จับคำด้วย `has_keyword()` ที่รู้กับดักภาษาไทย ("แจ้งความต้องการ" ≠ "แจ้งความ")
- แบรนด์/ช่องทาง: `canonical_mentions()` เก็บเฉพาะชื่อที่พูดจริง (คำทักทาย "บริษัทที่นอนโลตัส" ไม่นับ) เป็นชื่อสะกดเดียว; Dashboard จัดกลุ่มข้อมูลเก่าด้วย `canonical_name()`
- หัวข้อ: `normalize_topic()` จำกัดไว้ 9 หัวข้อ

**`topic_detail` vocabulary** (กรอกเมื่อ `topic == "แจ้งปัญหาสินค้า"` เท่านั้น): `ผ้าขาด/ผ้าหุ้มชำรุด`, `เตียง/โครงหัก`, `สปริง/ฟองน้ำยุบ`, `เปื้อน/รอยขีดข่วน`, `กลิ่น/แพ้/ระคายเคือง`, `ความชื้น/น้ำท่วม`, `ขนาด/สเปคผิด`, `อื่นๆ` — clamp ผ่าน `normalize_topic_detail()` (คำหลักเป็นคำทั้งคำ — "รา" เดี่ยว ๆ เคยไปตรงกับ "รายละเอียด")

**เปลี่ยน prompt ต้องทดสอบด้วยการรันวิเคราะห์ 5 คำขอซ้ำบน transcript ที่เก็บไว้** แล้วเทียบกับ prompt เดิม — ถูกกว่ารัน STT ใหม่ทั้งหมด และจับ regression ทุกตัวข้างบนได้

### 5.3 Auto case assignment (`pipeline.py:_auto_assign_case`)

ลำดับการตัดสินใจ:
1. **Recency short-circuit** — ถ้ามี case เปิดอยู่ของลูกค้าคนนี้ภายใน `CASE_RECENCY_HOURS` (default 4h, วัดจากเวลาโทรจริงในชื่อไฟล์) → attach ทันที (ข้าม LLM)
2. **LLM topic match** — ส่ง topic + summary ของสายใหม่ + existing cases → LLM ตัดสินใจว่าจะ attach หรือสร้าง case ใหม่
3. ถ้าไม่ match อะไรเลย → สร้าง case ใหม่

---

## 6. Domain knowledge (ภาษาไทย call center)

### 6.1 Speaker indicators ที่ใช้ใน rule-based logic

| Pattern | บอกว่าเป็น | ตัวอย่าง |
|---------|-----------|---------|
| `สวัสดีค่ะ [บริษัท]` | Agent (เปิดสาย) | "สวัสดีค่ะ กลุ่มบริษัทที่นอนในเครือโลตัสค่ะ" |
| `ทาง(บริษัท\|เรา\|เจ้าหน้าที่)` | Agent | "ทางเราจะตรวจสอบให้" |
| `คุณลูกค้า` | Agent (เรียกอีกฝ่าย) | "คุณลูกค้าสะดวกวันไหนคะ" |
| `พลอย\|พอย + verb` | Agent (พนักงานเรียกตัวเอง) | "พลอยขอตรวจสอบในระบบ" |
| `พี่ + verb` (self-ref) | Customer | "พี่สะดวกวันที่ 8", "พี่ติดประชุม" |
| `(ลูก\|น้อง)` (vocative) | Customer (เรียกพนักงาน) | "ได้ไหมลูก", "นะลูก" |
| `ติดตามเรื่อง...ส่ง` | Customer | "ติดตามเรื่องการส่งที่นอน" |
| `ขอเลื่อนวัน/รับสินค้า` | Customer | "ขอเลื่อนวันรับ" |
| `ขอบคุณค่ะ + สวัสดีค่ะ` (ลงท้าย) | ทั้งคู่พูดได้ — ไม่ใช้แยก |

### 6.2 Anomaly detection rules (`prompts.py:ANOMALY_USER`)

**หลักการ:** Anomaly = เหตุการณ์ที่ต้อง **escalate ให้หัวหน้า** ไม่ใช่แค่ลูกค้าไม่พอใจ
ทุก flag **ต้องมี quote คำพูดจริง** จาก transcript

| Category | ต้องเจอ keyword | Severity |
|----------|----------------|----------|
| A1 ขู่ฟ้อง | "ฟ้อง", "ทนาย", "ดำเนินคดี", "ศาล", "แจ้งความ" | high |
| A2 ขู่ร้องเรียน | "สคบ.", "ร้องเรียน", "กระทรวง", "เพจ", "สื่อ" | high |
| A3 ขอหัวหน้า | "ขอคุยกับหัวหน้า", "ขอสายผู้จัดการ" | medium |
| A4 คำหยาบ | คำด่าจริง / กู-มึง (ไม่ใช่แค่น้ำเสียง) | low |
| B พนักงานผิดระเบียบ | quote คำพูดจริง | high |
| C1 สุขภาพจากสินค้า | "แพ้", "ผื่น", "คัน", "แสบ", "ระคายเคือง", "เชื้อรา", "สารเคมี", "บาดเจ็บ" | medium |
| C2 ภัยพิบัติ / C3 ขอชดเชย | "น้ำท่วม", "ไฟไหม้" / "ค่าเสียหาย", "ชดเชย" | medium / low |

**ห้าม flag** เคสที่ลูกค้าโทรร้องเรียน/ขอคืนสินค้าตามปกติ + ลงท้ายสุภาพ — นั่นคือ negative sentiment ปกติ ไม่ใช่ anomaly

### 6.3 Common STT errors ที่ต้องระวัง
(รายการนี้มาจาก Whisper ภาษาไทยในเครื่องรุ่นเดิม — รุ่น API `faster-whisper-large-v3-turbo` ยังไม่ได้ทดสอบกับสายจริง อาจพลาดคนละแบบ ให้ตรวจในการทดสอบ live ครั้งแรก)
- ชื่อบริษัท "โอมาสนา" / "โนโลตัส" / "ฟิวทู" / "โลตัส" — Whisper สับสนชื่อยี่ห้อบ่อย
- "ที่นอน" บางครั้งเป็น "ที่โน่น" / "ทีเนี่ย"
- เลขโทรศัพท์ Thai มักผิดเป็นไทย-อังกฤษปน

---

## 6.4 Scale-friendly Home / Admin / Dashboard

ทั้งสามหน้าไม่โหลด row ที่ไม่ได้แสดง เพื่อให้ไม่ค้างเมื่อมี 10K+ ไฟล์:

- **Home** (`Home.py`): การ์ด 4 ใบใช้ `db.count_calls_by_status()` — ห้ามกลับไปใช้ `get_all_calls()` (เป็น `SELECT *` ลาก transcript ทุกสายเข้าหน่วยความจำ วัดได้ ~278 ms / ~57 MB ที่ 5,000 สาย). readiness checks ครอบด้วย `@st.cache_data(ttl=300)` เพราะเนื้อใน expander รันทุก rerun แม้พับอยู่ และมันยิง network ~2.6 วินาที — รวมแล้วหน้าแรกจาก 2.9 วินาที เหลือ 0.2 วินาที
- **Admin** (`pages/1_📤_Admin.py`): metric cards ใช้ `db.count_calls_by_status()` (SQL `GROUP BY`) ให้แม่นแม้โหลดแค่ N สายล่าสุด. Load-limit picker default `200 ล่าสุด` ถ้า total > 200. "Process All Pending" lazy query ผ่าน `db.get_pending_call_ids()`. Auto-refresh fragment ใช้ `db.get_processing_calls()` (0-1 row โดยปกติ).
- **Dashboard** (ทุกหน้าผ่าน `dashboard_common.load_filtered_calls()`): load-limit default `1,000 ล่าสุด` ถ้า total > 1000 — analytics ต้อง signal มากกว่าหน้า Admin

## 6.5 Filename-derived filters

Filename รูปแบบ `YYYYMMDDHHMMSS-CALLID.NNN-{AGENT|PHONE}-{PHONE|AGENT}-{Inbound|Outbound}.wav` ใช้สกัด:

- **Phone** — `file_manager.extract_phone_from_filename()` (auto-link ตอน upload)
- **Direction** — `file_manager.extract_direction_from_filename()` → radio filter Inbound/Outbound ที่หน้า Admin
- **Agent extension** — `file_manager.extract_agent_code_from_filename()` → dropdown รหัสพนักงานที่ `10_Agent_Performance.py` (segment 2-5 หลัก ที่ไม่ใช่ timestamp 14 หลักและไม่ใช่เบอร์ไทย)
- **เวลาโทร** — `file_manager.extract_call_time_from_filename()` → "วันที่โทร" ทุกหน้า (`created_at` คือเวลาอัปโหลด)

ไม่ต้อง migrate DB — derive runtime ตอนกรอง

## 6.6 Backfill scripts

- `scripts/scrub_existing_next_actions.py` — ลบ prompt-example placeholder ที่หลุดเข้า `agent_performance` เก่า
- `scripts/backfill_topic_detail.py` — re-classify `topic_detail` ของสายเก่าที่ `topic="แจ้งปัญหาสินค้า"` แต่ยังไม่มี detail (LLM-only, ไม่รัน STT ใหม่)

ทั้งคู่มี `--apply` flag (default = dry-run)

## 6.6.1 AWS pilot (`deploy/aws-ec2/`) และ backup

Stage 1 = ทั้งระบบบน EC2 Ubuntu 24.04 เครื่องเดียว: Caddy (HTTPS) → Streamlit ที่ `127.0.0.1:8501` (systemd `smartvoice`, เขียนได้เฉพาะ `data/` และ `.env`) → SQLite + ไฟล์เสียงบน EBS เข้ารหัส → backup ทุกคืนด้วย `scripts/backup_db.py` (snapshot แบบ read-only + `integrity_check`) แล้ว sync ไป S3 ส่วนตัวถ้าตั้ง bucket
- `sudo bash deploy/aws-ec2/install.sh --domain <ชื่อ> [--s3-bucket <ชื่อ>]` ใช้ทั้งติดตั้งและอัปเดต ไม่แตะ `data/` และ `.env`; คู่มือทีละขั้นที่ `deploy/aws-ec2/README.md`
- `tests/test_deploy_files.py` ตรวจคุณสมบัติด้านความปลอดภัยของไฟล์ deploy (bind loopback, write paths, ไม่มีรหัสเริ่มต้น, LF) — `.gitattributes` บังคับ LF ให้ `*.sh` และ `deploy/**`
- เป็นขั้นทดลอง ไม่ใช่ production: เครื่องเดียว, ประมวลผลใน process เว็บ, ความลับใน `.env`, ยังไม่มี monitoring — repo นี้ไม่สร้าง AWS resource ใด ๆ เอง

## 6.7 Settings page (`pages/4_Settings.py`)

ไม่ใช้ `st.form` — widget ทุกตัวมี `key=` แล้วปุ่ม `st.button("บันทึกการตั้งค่า")` บันทึกทุกค่าลง `.env` พร้อมกัน

โครงสร้างปัจจุบัน:
- ปุ่ม preset "โหมดสาธิต" (`MOCK_STT=true`) / "โหมดใช้งานจริง" — บันทึก audit
- รุ่น pyannoteAI (`precision-2` / `precision-3`; `STT_API_MODEL` ตายตัวเป็น `faster-whisper-large-v3-turbo`) และรุ่น Typhoon (พิมพ์เอง ค่าเริ่มต้น `typhoon-v2.5-30b-a3b-instruct`)
- ช่อง API key แบบรหัสผ่าน: เว้นว่าง = ใช้ค่าเดิม, ติ๊ก = ลบ key ที่บันทึกไว้; หน้าแสดงแค่ว่าตั้งค่าแล้วหรือยัง
- Discord webhook + ปุ่มทดสอบ, ตรวจความพร้อม (cache 5 นาที ตรวจแค่ว่ามี key)
- เปลี่ยน key แล้วต้องเปิดแอปใหม่

Helpers ใน `env_settings.py`: `ensure_env_file()`, `read_env()`, `write_env()` (เขียน `.env` และ `os.environ` ของ process นี้เท่านั้น), `env_bool()`, `mask_secret()` — GPU detection / Whisper combo validation / `_MODEL_RECOMMENDED_COMBO` ถูกถอดออกพร้อม local inference

**หมายเหตุ Cloud:** การบันทึกจากหน้านี้แก้ไฟล์ `.env` บนเครื่องเดียว ใช้กับหลาย instance ไม่ได้ — production ต้องย้ายความลับไป secrets service (แผนใน `docs/cloud_migration_plan.md` §9)

## 6.8 Login, สิทธิ์ และนโยบายบัญชี

`Home.py` เป็น **router** ไม่ใช่แค่หน้าแรก: ยังไม่ login → เห็นแค่หน้าเข้าสู่ระบบ; login แล้ว → `st.navigation()` สร้างเมนูจาก `auth.visible_pages(role)` เท่านั้น หน้าที่ไม่มีสิทธิ์จึงไม่ขึ้นเมนูเลย และพิมพ์ URL ตรง ๆ ก็เข้าไม่ได้

| Role | home | admin | dashboard pages* + cases | customers + sales_orders | data_entry | audit | settings | users |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Supervisor | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| QA | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Agent | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

\* `auth.DASHBOARD_PAGES` — dashboard, insights, anomaly, agent_performance, calls ทุก role เห็นครบพร้อม `cases`; หน้า `sales_orders` ทุก role อ่านได้ ส่วนนำเข้า/แก้ไข/ซ่อน SO ใช้ `can_access(role, PAGE_DATA_ENTRY)` (Admin)

กติกาที่ต้องรักษา:
- ทุกหน้าเริ่มด้วย `user, role = init_page(PAGE_<KEY>)` — ห้ามเช็ค `if role in {...}` เอง
- **เพิ่มหน้าใหม่ต้องครบทุกจุด:** `PAGE_*` constant + `PAGE_ORDER`/`PAGE_LABELS_TH` + `ROLE_PERMISSIONS` + route ใน `_PAGE_SPECS` ของ `Home.py` (ชื่อไทย + `icon=":material/...:"`) + หมวดใน `Home._SECTIONS` + `init_page()` ในไฟล์หน้า (`tests/test_home_entrypoint.py` / `test_usability.py` จับได้ถ้าขาด)
- `normalize_role()` แปลงค่าที่ไม่รู้จักเป็น `Agent` (สิทธิ์ต่ำสุด)
- ต้องเหลือ Admin ที่เปิดใช้งาน ≥ 1 บัญชีเสมอ (`auth.would_remove_last_admin()`)
- **ไม่มีการรีเซ็ตรหัสผ่านโดย Admin — ตามนโยบาย** รหัสผ่านเป็นของเจ้าของบัญชี ตั้งได้ผ่าน `auth.change_password()` ซึ่งบังคับกรอกรหัสเดิมเท่านั้น สิ่งที่ Admin ทำได้คือเปิด/ปิดบัญชี ห้ามเพิ่ม reset helper หรือฟอร์มรีเซ็ต (`tests/test_auth.py` จับได้)
- **หน้าจัดการผู้ใช้ไม่มีปุ่มลบบัญชี** เพราะ `audit_log` อ้างถึงบัญชีเหล่านั้น — ใช้ปิดใช้งานแทน (`db.delete_user()` ยังอยู่แต่ไม่มีหน้าไหนเรียก)
- session อยู่ใน Streamlit session_state — กด F5 = ออกจากระบบ (ยอมรับได้ ไม่มี cookie/JWT)

## 6.9 Soft delete + audit trail

**ลูกค้า ทะเบียนรับประกัน และใบสั่งขายไม่ถูกลบออกจากฐานข้อมูล** — "ลบ" ใน UI คือประทับ `deleted_at` / `deleted_by` แล้วแถวจะหายจาก query ปกติ ห้ามเขียน `DELETE FROM customers` / `warranty_registrations` / `sales_orders`

**ยกเลิกทะเบียน (Cancel) ≠ ซ่อน** — `warranty_registrations.status = 'cancelled'` (`customer_entry.set_warranty_status()`) ทะเบียนยังแสดงทุกหน้าพร้อมสถานะ

- `soft_delete_customer()` ซ่อนลูกค้า **และ** ทะเบียนของเขา (ติดธง `hidden_with_customer = 1`) โดยไม่แตะสาย เคส และการเชื่อมสาย
- `restore_customer()` กู้คืนเฉพาะทะเบียนที่มีธงนั้น — ห้ามใช้ `deleted_at` ที่ตรงกันเป็นตัวจับคู่ เพราะซ่อนสองครั้งในวินาทีเดียวกันจะชนกัน
- ฟังก์ชันอ่านทุกตัวมี `include_deleted=False` เป็นค่าเริ่มต้น; `phone` / `registration_no` เป็น UNIQUE แถวที่ซ่อนจึงยังจองค่าไว้ — ตัวตรวจซ้ำใน `customer_entry` ต้องมองด้วย `include_deleted=True` แล้วบอกให้กู้คืนแทน

**Audit trail** — ทุก action ที่เปลี่ยนข้อมูลต้องผ่าน `audit.record()` (หน้าเว็บเรียก `ui_helpers.audit()` ซึ่งเติมผู้ใช้จาก session ให้) ลงตาราง `audit_log` ดูได้ที่หน้า `7_📜_Audit_Log.py`

| จาก | บันทึกอะไร |
|---|---|
| `ui_helpers` (login flow) | เข้าสู่ระบบ, เข้าสู่ระบบไม่สำเร็จ, ออกจากระบบ, เปลี่ยนรหัสผ่านตัวเอง |
| `customer_entry` | ลูกค้า/ทะเบียน: เพิ่ม, แก้ไข, ซ่อน, กู้คืน, ยกเลิก/เปิดใช้ทะเบียน |
| `sales_orders` | นำเข้า SO (1 entry ต่อไฟล์), เพิ่ม, แก้ไข, ผูกลูกค้า, ซ่อน, กู้คืน |
| `case_workflow` | รับเคส / คืนเคส / เปลี่ยนสถานะ (หน้าเคสและหน้า Admin เรียกผ่าน `ui_helpers.render_case_ownership()`) |
| `dashboard_common` | ส่งออกรายงาน PDF / CSV |
| `5_👤_Users.py` | สร้างบัญชี, เปลี่ยน role, เปิด/ปิดใช้งาน |
| `1_📤_Admin.py` | อัปโหลด/ลบสาย, เชื่อมลูกค้าแบบ manual, เปลี่ยนสถานะ/หัวข้อ/รวมเคส |
| `4_Settings.py` | บันทึก `.env` และปุ่ม preset |

- `audit_log` เป็น **append-only** — ห้ามมีโค้ด UPDATE/DELETE แถวในตารางนี้
- `audit.record()` **ห้าม raise** — log ล้มต้องไม่ทำให้งานของผู้ใช้หาย
- `audit.redact()` ตัดค่า `password` / `password_hash` / `typhoon_api_key` / `pyannote_api_key` / `discord_webhook_url` / `hf_token` ออก (เก็บชื่อฟิลด์ไว้) — ตัดตามชื่อฟิลด์เท่านั้น ไม่ใช่ตัวกรองข้อมูลส่วนบุคคลในข้อความทั่วไป
- entry แบบ `update` เก็บ `{field: [ก่อน, หลัง]}` จาก `audit.diff_fields()` และถ้าไม่มีอะไรเปลี่ยนจะไม่เขียน entry
- เพิ่ม action ใหม่ที่เปลี่ยนข้อมูล → ต้องมี `audit()` ข้าง ๆ (`tests/test_audit.py` ตรวจ)

## 6.10 การรับเคส (กันแย่ง + Discord)

- รับเคสด้วย `db.claim_case()` — `UPDATE ... WHERE assignee_username IS NULL AND status != 'closed'` คำสั่งเดียว กดพร้อมกันสองคนจึงชนะได้คนเดียว เปลี่ยนสถานะผ่าน `db.set_case_status_as_assignee()` ซึ่งตรวจเจ้าของใน `WHERE` ด้วย **ห้ามเปลี่ยนสถานะเคสจากหน้าเว็บด้วย `db.update_case_status()`** — ตัวนั้นสำหรับ pipeline ตั้ง `follow_up` อัตโนมัติเท่านั้น
- เฉพาะผู้รับเคสเปลี่ยนสถานะได้; Admin/Supervisor ปลดการรับเคสของคนอื่นได้ (แต่รับแทนไม่ได้); QA รับเคสไม่ได้
- UI ทุก role อยู่ใน `ui_helpers.render_case_ownership(case, key_suffix)` — key มี case id + suffix เพราะหน้า Admin วาดเคสเดียวกันใต้หลายสาย
- Discord: `DISCORD_WEBHOOK_URL` (หน้า Settings) ว่าง = ไม่ส่ง; URL เป็นความลับ `audit.redact()` ตัดทิ้ง
- ตารางเคสแสดง `case_workflow.case_brief()` (สรุปล่าสุด, ประเภทปัญหา, สิ่งที่ต้องทำต่อ, ความเร่งด่วน) แทนหัวข้อกว้าง ๆ ของสายแรก

## 6.11 Dashboard แบ่งเป็นหน้า

Dashboard เดิมเป็นหน้าเดียว ~1,000 บรรทัด อาจารย์บอกว่าอ่านยาก จึงแยกหน้าละเรื่อง (`auth.DASHBOARD_PAGES`) ใต้หัว **Dashboard** ใน sidebar (`Home._SECTIONS`: `""` = บนสุดไม่มีหัว)

- ทุกหน้าเรียก `dashboard_common.load_filtered_calls()` — แถบตัวกรองร่วม (วันที่ / หัวข้อ / อารมณ์ / จำนวนที่โหลด) แต่ละหน้าวาด widget ของตัวเอง และ Streamlit **ไม่** พาค่าของ widget ไปยัง key เดียวกันบนหน้าอื่น (กลับไปค่าแรกเงียบ ๆ) ค่าจริงจึงอยู่ใน `_keep_*`: `restore_filters()` เขียนกลับ**ทุกรอบ**ก่อนวาด widget และทุก widget มี `on_change=remember_filters`; ช่วงวันที่ที่จำไว้ถูก clamp ให้อยู่ในช่วงของสายที่โหลด เพราะ `st.date_input` raise เมื่อค่าเกิน min/max
- สไตล์กราฟ (`CHART_LAYOUT`, palette, `hbar()`) อยู่ใน `dashboard_common` — กราฟใหม่ใช้ของกลาง อย่า copy ค่า Plotly
- `load_filtered_calls()` วาดปุ่ม **ส่งออกรายงาน** ข้างตัวกรองด้วย (ดู 6.13)

## 6.12 ใบสั่งขาย (SO) + ฟิลด์ทะเบียนตามแบบของบริษัท

บริษัทส่งหน้าจอเปล่าของ "ใบสั่งขาย" (Dynamics NAV) และหน้าลงทะเบียนรับประกันมาเพื่อบอกว่า**ต้องเก็บฟิลด์อะไร** (ข้อมูลจริงให้ไม่ได้ — ห้ามใส่แถวตัวอย่างที่ดูเหมือนจริง แม่แบบ Excel มีแค่หัวคอลัมน์)

- `sales_orders` (หัว) + `sales_order_lines`; `so_number` UNIQUE เป็นกุญแจ upsert — นำเข้าซ้ำ = อัปเดต SO และ**แทนที่รายการสินค้าทั้งชุด**; SO ใช้ซ่อนไม่ลบเหมือนลูกค้า
- รูปแบบนำเข้า **1 แถว = 1 รายการสินค้า** หัว SO ซ้ำทุกแถว จับคอลัมน์จากชื่อที่ normalize แล้ว (`sales_orders.map_columns`) ใช้ได้ทั้งแม่แบบไทยและไฟล์ export NAV; `No.` เดี่ยว ๆ = รหัสสินค้าเมื่อมี `Document No.` ไม่งั้น = เลขที่ SO; ปัญหารายงานเป็นแถว Excel และปุ่มนำเข้ากดไม่ได้
- ยอดที่ว่างคำนวณให้ (`complete_totals`) ค่าในไฟล์ชนะเสมอ; ฟอร์มแก้ไขติ๊ก "คำนวณอัตโนมัติ" ไว้ก็ต่อเมื่อยอดที่เก็บไว้เท่ากับที่รายการสินค้ารวมได้ (`totals_follow_lines`)
- ผูกลูกค้าจากเบอร์ผู้รับ แล้วเบอร์ผู้ซื้อ (`find_customer_id`); นำเข้าซ้ำที่เบอร์ไม่ตรงใครจะไม่ทำให้การผูกเอง (manual) หลุด
- ทะเบียน: `so_number` (อ้างด้วยข้อความ ไม่ใช่ FK — ทะเบียนอาจถูกบันทึกก่อนนำเข้า SO), `ref_id`, `status` active/cancelled, `proof_path` — ไฟล์ผ่าน `file_manager.save_proof_file()` ตรวจชนิดจากเนื้อไฟล์ (jpg/png/webp/pdf) ≤ 10 MB ตั้งชื่อด้วย SHA-256 ใน `data/warranty_proofs/` ไฟล์เก่าไม่ลบ (audit อ้างถึง)
- ลูกค้าเพิ่ม `nick_name`, `channel`

## 6.13 ส่งออกรายงาน Dashboard (PDF / CSV)

- `dashboard_report.py` (ไม่ import Streamlit): `build_report()` → `pdf_report()`, `summary_csv()`; `calls_csv()` 1 แถวต่อสาย; สูตรคะแนนพนักงาน (`scored_calls`, `agent_summary`) อยู่ที่นี่และหน้าผลงานพนักงาน import ไปใช้ — ห้ามเขียนสูตรซ้ำในหน้า
- PDF ใช้ `fpdf2` + `set_text_shaping(True)` (HarfBuzz) ให้สระ/วรรณยุกต์ไทยซ้อนถูก; กราฟเป็นสี่เหลี่ยมวาดเอง (ไม่ต้องมี browser/kaleido); ฟอนต์จาก `REPORT_FONT_PATH` หรือ Tahoma/Leelawadee/Noto Sans Thai/TLWG
- CSV เป็น `utf-8-sig` (Excel อ่านไทยได้เฉพาะมี BOM) และเติม `'` หน้าเซลล์ที่ขึ้นต้น `= + @` (กันสูตร Excel จากข้อความในสาย/ของ LLM)
- ปุ่มใช้ `st.download_button(data=callable, on_click="ignore")` — สร้างไฟล์ตอนกดเท่านั้น และ callable บันทึก audit (`export`) โดยจับผู้ใช้ไว้ตอนวาดปุ่ม เพราะการกดถูกเสิร์ฟนอก page run

## 6.14 UI conventions (สำหรับส่งบริษัท)

- **ไทยบนจอ รหัสใน DB** — สถานะ/อารมณ์/ชื่อฟิลด์ผ่าน `smartvoice.labels`; เวลาใช้ `labels.thai_time()` ห้าม `created_at[:19]` หรือคำว่า "UTC"
- **เมนู:** `Home._PAGE_SPECS` ทุกหน้ามีชื่อไทย + ไอคอน `:material/...:` และ `st.navigation(..., expanded=True)` (ไม่งั้น Streamlit ซ่อนลิงก์เกินตัวที่ 10 ไว้หลัง "View more")
- **หน้าแรกเป็นคิวงาน:** เคสยังไม่มีคนรับ, เคสของฉัน, สายผิดปกติรุนแรง — ลิงก์ส่ง `?owner=unassigned|mine` ซึ่ง `11_Cases.py` ใช้ครั้งเดียวแล้วลบออก
- **ลบต้องถามก่อน:** ลบสาย (ทีละไฟล์/หลายไฟล์) และรวมเคสเปิด `@st.dialog` "ลบถาวร"/"ยกเลิก"; ลบไฟล์ผ่าน `file_manager.remove_audio_file()` ซึ่งรายงานไฟล์ที่ถูกล็อกแทนการ raise
- **คลิกช่องไหนก็ได้เพื่ออ่านแถว:** ตารางข้อความยาว (เคส, รายการสาย, ผลงานพนักงาน, ประวัติการใช้งาน, SO, ลูกค้า) ใช้ `selection_mode=ui_helpers.TABLE_CLICK_MODES` (เลือกช่องอย่างเดียว — โหมดแถวมีช่องติ๊ก และเอาติ๊กออกขณะช่องยังถูกเลือกเคยเปิดหน้าต่างซ้ำ) แล้วเปิด `@st.dialog(width="large")`; `ui_helpers.picked_row()` คืน `(row, is_new)` นับใหม่เฉพาะเมื่อเลือกเพิ่ม และทุกหน้ามีปุ่ม "เปิด…อีกครั้ง"
- **Selection คือตำแหน่งแถว ไม่ใช่ id:** action ที่สลับลำดับตาราง (รับเคสทำให้ `updated_at` เปลี่ยน) ทำให้ selection ชี้แถวอื่น — key ของตารางจึงมี hash ของลำดับแถว และหน้าต่างเปิดซ้ำตาม id ที่จำไว้
- Transcript แสดงผ่าน `ui_helpers.render_transcript()` — ป้าย [พนักงาน]/[ลูกค้า], escape HTML
- แสดง**เวลาที่โทรจริง**จาก `file_manager.extract_call_time_from_filename()`; ข้อความที่ต้องอยู่รอด `st.rerun()` ใช้ session "flash"
- ชื่อโมเดล (STT/LLM) ใน sidebar และ readiness checks บนหน้าแรกแสดงเฉพาะ Admin/Settings

---

## 7. Pitfalls / สิ่งที่เคยพังมาแล้ว

### 7.1 อย่าใช้ `cd` ใน `run_command`
PowerShell ใน Windows → ตั้ง `Cwd` แทน `cd && ...`

### 7.2 `test_config.py` รันรวมกับชุดเต็มได้แล้ว
เดิมไฟล์นี้แก้ env vars และต้องใช้ torch จึงสั่งให้ `--ignore=tests\test_config.py` ตอนนี้เหลือแค่ tests ของ helper ข้อความ/การจัดกลุ่ม จึงรันรวมกับชุดเต็ม (นับรวมใน baseline)

### 7.3 อย่าแก้ `_AGENT_MARKERS` / `_CUSTOMER_MARKERS` แบบเดาๆ
markers ใช้กับ `_enforce_role_rules` ที่ scoring ตำแหน่ง + role — เพิ่ม marker ที่กำกวมจะทำให้ flip ผิด ทำ regression test ครอบคลุมก่อนเพิ่ม

### 7.4 LLM prompt — เลี่ยง nested bullet
ปัญหาที่เจอจริง: LLM (Typhoon 8B) เคย copy sub-bullet เป็น `anomaly_reason` แม้ไม่มีหลักฐาน → ต้องระบุ keyword required list ชัดและสั่ง quote evidence
สำหรับ Agent QA ห้ามใส่ตัวอย่าง Next Action ที่มีข้อมูลจริงปลอม เช่น ยอดเงิน/เบอร์โทร/รหัสสินค้า เพราะ LLM เคย copy ตัวอย่างไปแสดงทุกสาย; ใช้ template นามธรรมและ sanitize output ใน `ollama_client.sanitize_next_action()`

### 7.5 Pipeline เรียง step ผิด
`_aggressive_relabel_from_strong_cues` ต้องเรียก **ก่อน** `_merge_adjacent_same_speaker` ไม่งั้นการรวมจะ lock label ผิดถาวร

### 7.6 `created_at` ใน DB
คือเวลา **upload/process** ไม่ใช่ **วันที่โทรจริง** — วันที่โทรอยู่ใน filename pattern `YYYYMMDDHHMMSS-...`

### 7.7 ตัดข้อความภาษาไทยด้วยจำนวนตัวอักษร
`summary[:100]` เคยทำให้ข้อความขาดกลางคำ ("...คืนสินค้า พนั") เพราะภาษาไทยไม่มีเว้นวรรคระหว่างคำ ตัดที่ไหนก็ลงกลางคำ — แสดงเต็มแล้วปล่อยให้ตัดบรรทัดเอง

### 7.8 ป้ายใน UI ต้องเป็นคำ ไม่ใช่ emoji
อาจารย์ให้เปลี่ยนไอคอนเป็นคำที่สื่อความหมาย — เมนูใช้ไอคอน Material (`:material/...:`) ข้างคำ ตั้งให้ชัดเพื่อไม่ให้ Streamlit หยิบ emoji จากชื่อไฟล์มาใช้; `tests/test_home_entrypoint.py::test_ui_labels_are_words_not_decorative_icons` fail ถ้ามีไอคอนตกแต่งกลับมา (ยกเว้นบรรทัดที่เป็น path ไฟล์ใน `pages/`)

### 7.9 Widget key ของฟอร์มแก้ไขต้องผูกกับ id ของแถว
Streamlit จำค่าของ widget ที่มี `key=` คงที่ข้าม rerun และไม่สนใจ `value=` — เคยทำให้หน้าจัดการผู้ใช้เอาชื่อของบัญชีก่อนหน้าไปบันทึกทับบัญชีใหม่ ใช้ `key=f"_edit_role_{user_id}"`

### 7.10 เนื้อใน `st.expander` รันทุกครั้ง แม้พับอยู่
ของที่ช้า (network, query ใหญ่) ใน expander จะทำงานทุก rerun — ต้อง `@st.cache_data`

### 7.11 Typhoon 8B ลอกทุกอย่างที่ prompt แสดง
ตัวอย่าง action ("ติดตามการโอนเงินคืน"), placeholder (`<เบอร์ที่ลูกค้าให้ไว้>`), รายชื่อแบรนด์ *และ JSON คำตอบที่เติมค่าไว้* (skeleton ที่มี `"done": false` / `"pending": false` กลับมาเหมือนเดิม) — อธิบาย key เป็นคำแทนการให้ skeleton, ไม่ใส่ค่าตัวอย่างจริง แล้วตรวจใน `insight_rules`; คง `sanitize_next_action()` ไว้ในทางแสดงผลสำหรับแถวเก่า

### 7.12 หนึ่งคำขอ หนึ่งงาน
รวมสิ่งที่ต้องทำต่อไว้ในคำขอ QA ทำให้โมเดลทิ้งมัน — ตอนนี้แยกเป็นคำขอของตัวเอง

### 7.13 Widget key เดียวกันสองหน้า ≠ widget เดียวกัน
Streamlit ทิ้งค่าเก่าไว้ใน session state แต่ widget ของหน้าใหม่ไม่สนใจและกลับไปตัวเลือกแรก — ค่าที่ต้องข้ามหน้าให้เก็บใน key ธรรมดาแล้วเขียนกลับทุกรอบ (ดู `dashboard_common.restore_filters`)

### 7.14 fpdf2 ตัดบรรทัดภาษาไทยแบบตัวอักษรค้าง
`multi_cell(..., wrapmode=WrapMode.CHAR)` ค้างไม่จบเมื่อเจอข้อความไทยยาวไม่มีช่องว่างเต็มความกว้าง — รายงานตัดบรรทัดเองด้วย `dashboard_report.wrap_text()` (ไม่แยกพยัญชนะจากสระ/วรรณยุกต์) แล้ววาดทีละบรรทัดด้วย `cell()`

### 7.15 ห้าม log สิ่งที่พูดในสาย
log ออกนอกการควบคุมสิทธิ์ของฐานข้อมูล (journald, ระบบ log กลางบน Cloud) — log ได้แค่ขนาด/id/ชนิด เดิม `correct_speakers()`, `sanitize_evidence()` และ `extract_json()` ใส่คำตอบของโมเดลสูงสุด 400 ตัวอักษร ตอนนี้ไม่ใส่แล้ว และ `tests/test_log_privacy.py` จะ fail ถ้ากลับมา; `process_call()` ยังเก็บ traceback เต็มใน `calls.error_msg` (ในฐานข้อมูล เห็นเฉพาะ Admin/Supervisor)

### 7.16 การล็อกหลังใส่รหัสผิดต้องอยู่ฝั่ง server
เดิมเก็บใน `st.session_state` เปิดแท็บใหม่ก็นับใหม่ ตอนนี้ใช้ `smartvoice/login_guard.py` (นับรวมทั้ง process: ผิด 5 ครั้ง/บัญชี → ล็อก 60 วินาที, ผิด 20 ครั้ง/IP → 5 นาที) ห้ามย้ายกลับไป session_state; `tests/test_login_page.py` ตรวจว่าล็อกข้าม session ได้จริง — ถ้าวันหนึ่งรันหลาย instance ต้องย้ายตัวนับไปที่เก็บกลาง

### 7.17 บัญชี bootstrap บน server ห้ามใช้ `admin1234`
`auth.ensure_default_admin()` ใช้ `SMARTVOICE_BOOTSTRAP_PASSWORD` ถ้าตั้งไว้ (ค่าที่สั้นกว่า 8 ตัวหรือเป็น `admin1234` → ไม่สร้างบัญชีเลย ไม่ถอยกลับไปใช้รหัสที่ทุกคนรู้) และหน้า login จะไม่แสดงรหัส; `deploy/aws-ec2/install.sh` สุ่มค่าให้ ถ้าไม่ตั้ง (ใช้ในเครื่อง) พฤติกรรมเดิมไม่เปลี่ยน

### 7.18 ประมวลผลซ้ำมีค่าใช้จ่าย
STT ใช้ checkpoint `<ไฟล์เสียง>.smartvoice-api.json` ซ้ำได้ แต่ LLM ถูกเรียกใหม่ทุกครั้ง; checkpoint ค้าง `submitting` ต้องตรวจประวัติงานที่ pyannoteAI ก่อนลบ; กดหยุดในแอปไม่ยกเลิกงานฝั่งผู้ให้บริการ; checkpoint มี transcript ดิบ ห้าม commit หรือ log

---

## 8. ก่อน commit / ก่อนปิดงาน

- [ ] รัน `tests\` ทั้งชุดด้วย env API จำลองในข้อ 2 → ผ่าน 100%
- [ ] stage ไฟล์แบบระบุชื่อ และตรวจ staged diff ว่าไม่มี `.env`, key, `data/`, เสียง, checkpoint, ไฟล์ DB หรือข้อความลูกค้า
- [ ] เพิ่ม regression test สำหรับการแก้ bug
- [ ] ลบไฟล์ชั่วคราว `_*.py`, `_*.txt` ออกจาก project root
- [ ] ไม่แตะ `.env` (gitignored — มี secrets)
- [ ] ไม่แตะ `data/` (gitignored — runtime data)
- [ ] ถ้าแก้ schema DB → migration ต้องไม่ break ของเก่า + อัปเดต `docs/database_design.md`
- [ ] ถ้าเปลี่ยน prompt → ทดสอบ end-to-end อย่างน้อย 1 ไฟล์เสียงจริงก่อน (ผ่าน API ที่มีค่าใช้จ่าย — ต้องได้รับอนุมัติเรื่องข้อมูลและค่าใช้จ่าย)
- [ ] action ใหม่ที่เปลี่ยนข้อมูล → มี `audit()` บันทึกไว้
- [ ] ห้ามลบลูกค้า/ทะเบียน/SO/บัญชีผู้ใช้ออกจาก DB จริง — ใช้ซ่อน / ปิดใช้งาน
- [ ] ป้ายใหม่ใน UI เป็นคำ ไม่ใช่ emoji

---

## 9. ไฟล์เอกสารที่เกี่ยวข้อง

| ไฟล์ | เนื้อหา |
|------|---------|
| `CLAUDE.md` | คู่มือสำหรับ Claude Code — เนื้อหาเดียวกับไฟล์นี้ในภาษาอังกฤษ (แก้ไฟล์หนึ่งให้แก้อีกไฟล์ด้วย) |
| `PROJECT_STATUS.md` | สถานะล่าสุด + ผลทดสอบ + งานถัดไป |
| `docs/cloud_migration_plan.md` | แผนย้าย Cloud / PostgreSQL / storage / worker (Planned / Not Implemented) |
| `README.md` | ภาพรวมโปรเจค + tech stack |
| `SETUP.md` | คู่มือติดตั้งเชิงลึก + troubleshooting |
| `ONE_CLICK_RUN.md` | คู่มือ launcher สำหรับเครื่อง demo / handoff |
| `CHANGELOG.md` | ประวัติ release |
| `docs/architecture.md` | โครงสร้าง + data flow |
| `docs/database_design.md` | ER diagram + data dictionary |
| `docs/user_manual.md` | คู่มือผู้ใช้ business |
| `docs/OMAZZ_RELEASE_CHECKLIST.md` | Checklist ก่อนส่งมอบ / live demo |
| `.env.example` | template ของ env vars (อ่านได้ — ไม่มี secret) |

---

## 10. การติดต่อสื่อสาร

- ตอบเป็นภาษาไทย (codebase + UI เป็น Thai-first)
- ตรงประเด็น ไม่ทักทาย ไม่ acknowledgment phrases
- ใช้ Markdown citation format `@<absolute_path>:<line>` เมื่ออ้างอิงโค้ด
- แสดง diff สำคัญด้วย table หรือ before/after เมื่อทำการแก้ไขที่กระทบ output
