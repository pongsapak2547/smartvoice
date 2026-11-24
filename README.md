# SmartVoice

AI-powered Call Center Analytics สำหรับสายภาษาไทย: รับไฟล์เสียง, ถอดเสียง, แยกผู้พูด, วิเคราะห์คุณภาพการสนทนาด้วย LLM (ตรวจคำตอบของ AI ก่อนบันทึกทุกครั้ง), จัดกลุ่มและติดตามเคสลูกค้า, เก็บข้อมูลลูกค้า / ทะเบียนรับประกัน / ใบสั่งขาย และออกรายงาน — เว็บและข้อมูลอยู่บนเครื่อง/เซิร์ฟเวอร์ ส่วน AI เรียก API

สถานะส่งต่อ: Phase 6 deploy บน AWS Academy เป็น Technical Pilot ตามผลที่ผู้ใช้ยืนยัน; ดูหลักฐาน ข้อจำกัด และงานค้างใน [`PROJECT_STATUS.md`](PROJECT_STATUS.md) คุณภาพ STT/ผู้พูด/AI ยังตรวจรับไม่ครบ

## Tech Stack

| Component | Technology |
|-----------|------------|
| UI | Streamlit แบบ multi-page (`st.navigation` + สิทธิ์ตาม role) |
| Database | SQLite 3 หรือ PostgreSQL ผ่าน `DATABASE_URL` (ต้องรัน migration ก่อน; ดู `deploy/aws-ec2/README.md`) |
| STT | Whisper Large v3 Turbo ผ่าน pyannoteAI API |
| Speaker Diarization | pyannoteAI Precision-2/3 API |
| LLM | Typhoon API |
| รายงาน | `fpdf2` + `uharfbuzz` (PDF ภาษาไทย), `openpyxl` (Excel ใบสั่งขาย) |

## Current Capabilities

**ประมวลผลสาย**
- Upload `.wav` / `.mp3`, ตรวจ magic bytes, จำกัดขนาดไฟล์ 100 MB, และ deduplicate ด้วย SHA-256
- ดึงเบอร์โทร, ทิศทางสาย (Inbound/Outbound), รหัสพนักงาน และเวลาโทรจริงจากชื่อไฟล์อัตโนมัติ; เชื่อมลูกค้า/รับประกันอัตโนมัติจากเบอร์
- ถอดเสียง + diarization + speaker correction แบบหลายชั้น โดยผสม LLM กับ heuristic rules ภาษาไทย
- วิเคราะห์ 5 คำขอแยกกัน: สรุป/หัวข้อ/ประเภทปัญหา, อารมณ์ลูกค้า, คะแนนพนักงาน, สิ่งที่ต้องทำต่อ, ความผิดปกติ
- **AI เสนอ ระบบตัดสิน** (`insight_rules.py`) — คะแนนพนักงานนับเฉพาะข้อที่มีคำพูดของพนักงานในสายจริง, ความผิดปกติต้องมีคำพูดจริงที่มีคำของหมวดนั้น, แบรนด์/ช่องทางนับเฉพาะที่พูดจริงและรวมชื่อสะกดต่างกัน
- จัดกลุ่มเคสอัตโนมัติ (สายจากลูกค้าเดิมภายในไม่กี่ชั่วโมงเข้าเคสเดิมทันที ไม่งั้นให้ LLM เทียบหัวข้อ)

**งานลูกค้า**
- **จัดการเคส** — พนักงานกด "รับเคส" เอง คนอื่นแย่งไม่ได้, เปลี่ยนสถานะ/ปิดเคสได้เฉพาะผู้รับ, แจ้งเตือนเข้า Discord ทุกการรับ/คืน/ปิดเคส; ตารางเคสบอกเรื่องที่ลูกค้าแจ้ง สิ่งที่ต้องทำต่อ และความเร่งด่วน
- **ลูกค้าและการรับประกัน** — คลิกแถวลูกค้าเพื่อดูทะเบียนรับประกัน (พร้อมหลักฐานการซื้อ), ใบสั่งขาย, เคส และสายทั้งหมด
- **ทะเบียนรับประกัน** ตามแบบระบบของบริษัท — เลขที่ SO, Ref Id, สถานะ ใช้งาน/ยกเลิก, แนบรูปใบเสร็จ/สลิป
- **ใบสั่งขาย (SO)** — นำเข้าจาก Excel/CSV (แม่แบบของระบบ หรือไฟล์ export จาก NAV), เพิ่ม/แก้ไขทีละใบ, ดูทั้งใบแบบเดียวกับเอกสารของบริษัท, ผูกกับลูกค้าอัตโนมัติจากเบอร์
- **หน้าเพิ่มข้อมูล** (Admin) — เพิ่ม / แก้ไข / ซ่อน / กู้คืน ลูกค้าและทะเบียนรับประกัน พร้อมตรวจเบอร์และเลขทะเบียนซ้ำ และคำนวณวันหมดประกันอัตโนมัติ

**Dashboard** (5 หน้า ใช้ตัวกรองร่วมกัน)
- ภาพรวม · คีย์เวิร์ด แบรนด์ ช่องทาง · สายที่ผิดปกติ · ผลงานพนักงาน · รายการสาย
- **ส่งออกรายงาน** ทุกหน้า: รายงาน PDF (กราฟและตารางทุกหน้า), สรุปตัวเลข CSV, รายการสาย CSV — ตามตัวกรองที่เลือก เปิดใน Excel แล้วภาษาไทยไม่เพี้ยน
- ตารางที่มีข้อความยาว คลิกช่องไหนก็ได้เพื่อเปิดอ่านเต็มในหน้าต่าง

**ระบบ**
- **Login จริง + สิทธิ์ตาม role** — 4 บทบาท (Admin / Supervisor / QA / Agent), เมนูแสดงเฉพาะหน้าที่มีสิทธิ์, ตรวจสิทธิ์ซ้ำฝั่ง server ทุกหน้า, ล็อก 60 วินาทีเมื่อใส่รหัสผิด 5 ครั้ง
- **นโยบายบัญชี** — Admin เปิด/ปิดบัญชีได้แต่ตั้งหรือรีเซ็ตรหัสผ่านของคนอื่นไม่ได้ และไม่มีการลบบัญชีถาวร
- **ไม่ลบข้อมูลลูกค้าจริง (soft delete)** — "ลบ" ลูกค้า/ทะเบียน/SO คือซ่อน แถวยังอยู่ครบและกู้คืนได้
- **Audit log ทั้งระบบ** — การเข้าสู่ระบบ, บัญชี, ลูกค้า/ทะเบียน/SO, สาย, เคส, การตั้งค่า และการส่งออกรายงาน พร้อมค่าก่อน→หลัง (Admin + Supervisor)
- ภาษาไทยทั้งหน้าจอ เวลาแสดงเป็นเวลาไทย (UTC+7); หน้าแรก / Admin / Dashboard รองรับ 10K+ ไฟล์
- Settings page — ตั้งค่า API keys, รุ่น API, โหมดเสียงตัวอย่าง และ Discord

## Project Structure

```text
smartvoice/
├── Home.py                        # Router (เมนูตาม role) + หน้าแรก "งานที่รอคุณ"
├── pages/
│   ├── 1_📤_Admin.py              # อัปโหลดและประมวลผลเสียง
│   ├── 2_📊_Dashboard.py          # Dashboard — ภาพรวม
│   ├── 3_👥_Customers.py          # ลูกค้าและการรับประกัน
│   ├── 4_Settings.py              # ตั้งค่าระบบ (Admin + Supervisor)
│   ├── 5_👤_Users.py               # จัดการผู้ใช้ (Admin)
│   ├── 6_➕_Data_Entry.py          # เพิ่ม/แก้ไขข้อมูลลูกค้า (Admin)
│   ├── 7_📜_Audit_Log.py           # ประวัติการใช้งาน (Admin + Supervisor)
│   ├── 8_Dashboard_Insights.py    # Dashboard — คีย์เวิร์ด แบรนด์ ช่องทาง
│   ├── 9_Dashboard_Anomaly.py     # Dashboard — สายที่ผิดปกติ
│   ├── 10_Agent_Performance.py    # Dashboard — ผลงานพนักงาน
│   ├── 11_Cases.py                # จัดการเคส (รับเคส / ปิดเคส)
│   ├── 12_Call_Summaries.py       # Dashboard — รายการสาย
│   └── 13_Sales_Orders.py         # ใบสั่งขาย (SO)
├── smartvoice/
│   ├── audit.py                   # Audit trail vocabulary + record()
│   ├── auth.py                    # Login, PBKDF2 hashing, role permissions
│   ├── case_workflow.py           # รับเคส / คืนเคส / เปลี่ยนสถานะ + สรุปเคส
│   ├── cli.py                     # `smartvoice` console entrypoint
│   ├── config.py                  # Environment config ทั้งหมด
│   ├── customer_entry.py          # Validation ของหน้าเพิ่มข้อมูล
│   ├── customer_view.py           # ตาราง/รายละเอียดลูกค้าในหน้าลูกค้า
│   ├── dashboard_common.py        # ตัวกรองร่วม, สไตล์กราฟ, ปุ่มส่งออกรายงาน
│   ├── dashboard_report.py        # รายงาน PDF / CSV + สูตรคะแนนพนักงาน
│   ├── database_backend.py        # PostgreSQL adapter, schema version และ migration
│   ├── db.py                      # SQLite / PostgreSQL CRUD
│   ├── discord_notify.py          # แจ้งเตือน Discord (webhook)
│   ├── env_settings.py            # อ่าน/เขียน `.env` จากหน้า Settings
│   ├── file_manager.py            # Upload validation, SHA-256 dedup, หลักฐานการซื้อ
│   ├── insight_rules.py           # ตรวจคำตอบของ LLM ก่อนบันทึก
│   ├── labels.py                  # คำภาษาไทยของทุกรหัส + เวลาไทย
│   ├── logger.py                  # Rotating logger
│   ├── ollama_client.py           # LLM client + JSON parsing
│   ├── pipeline.py                # Core orchestration
│   ├── preflight.py               # Deployment readiness checks
│   ├── prompts.py                 # Prompt templates
│   ├── sales_orders.py            # นำเข้า/บันทึกใบสั่งขาย + แม่แบบ Excel
│   ├── so_view.py                 # แสดงใบสั่งขายแบบเอกสาร
│   ├── ui_helpers.py              # CSS, login page, role guard, background processing
│   └── stt/
│       ├── audio.py               # Thai text helper (ไม่มี local inference)
│       ├── diarize.py             # Speaker label / grouping helpers
│       ├── orchestrator.py        # Audio → STT → diarization
├── scripts/
│   ├── backfill_topic_detail.py   # Re-classify topic_detail for legacy calls
│   ├── extract_pdf.py
│   ├── generate_er_diagram.py
│   ├── make_password_hash.py
│   ├── scrub_existing_next_actions.py
│   └── seed_mock_data.py
├── tests/                          # pytest suite
├── docs/
│   ├── architecture.md
│   ├── database_design.md
│   ├── OMAZZ_RELEASE_CHECKLIST.md
│   ├── report_corrections.md
│   └── user_manual.md
├── data/                           # runtime data (gitignored)
│   ├── logs/
│   ├── raw_audio/
│   ├── warranty_proofs/            # รูป/PDF หลักฐานการซื้อ
│   └── smartvoice.db
├── AGENTS.md / CLAUDE.md           # คู่มือสำหรับ AI coding agents
├── CHANGELOG.md
├── ONE_CLICK_RUN.md
├── SETUP.md
├── requirements.txt
└── .env.example
```

## Database Tables

| Table | คำอธิบาย |
|-------|----------|
| `calls` | ไฟล์เสียง, transcript, ผลวิเคราะห์ AI, สถานะ, ผู้อัปโหลด, และ `case_id` |
| `customers` | ข้อมูลลูกค้า รวมชื่อเล่นและช่องทาง (soft delete ผ่าน `deleted_at`) |
| `warranty_registrations` | ทะเบียนรับประกัน — เลขที่ SO, Ref Id, สถานะ ใช้งาน/ยกเลิก, หลักฐานการซื้อ (soft delete) |
| `sales_orders` | หัวใบสั่งขาย — วันที่, ข้อมูลการขาย, ผู้ซื้อ, ผู้รับ, ยอดเงิน (soft delete) |
| `sales_order_lines` | รายการสินค้าในใบสั่งขาย |
| `call_customer_links` | ความสัมพันธ์ระหว่างสาย, ลูกค้า, และ warranty |
| `cases` | กลุ่มสายของลูกค้าคนเดียวกันในเรื่องเดียวกัน + ผู้รับเคส |
| `users` | บัญชีพนักงาน — username, ชื่อที่แสดง, role, PBKDF2 hash, สถานะเปิด/ปิด |
| `audit_log` | ประวัติการใช้งานแบบเขียนเพิ่มอย่างเดียว — ใคร ทำอะไร กับอะไร เมื่อไหร่ ค่าก่อน→หลัง |

รายละเอียดคอลัมน์ทั้งหมดอยู่ใน [`docs/database_design.md`](docs/database_design.md)

## First Login

เปิดแอปครั้งแรก ระบบสร้างบัญชี `admin` / `admin1234` ให้อัตโนมัติ — **เปลี่ยนรหัสผ่านทันที** ที่กล่องบัญชีใน sidebar (ระบบจะเตือนค้างไว้จนกว่าจะเปลี่ยน) แล้วสร้างบัญชีพนักงานที่หน้า "จัดการผู้ใช้"

## Quick Start

เวอร์ชันปัจจุบันใช้ API เท่านั้น ไม่ติดตั้งหรือรันโมเดล Local หากอัปเดตจากรุ่นเดิม ให้เปิด Settings แล้วบันทึกโหมด API และ keys; ค่า provider เดิมจะถูกปฏิเสธ ไม่มีการแก้ `.env` อัตโนมัติ


### Windows

```powershell
run.bat
```

ตัว launcher จะสร้าง `.venv`, ติดตั้ง dependency, สร้าง `.env`, ใช้ pyannoteAI/Typhoon APIs โดยไม่ติดตั้งโมเดล Local และเปิด `http://localhost:8501`

## Developer Setup

### เปิดเดโม Omazz ในเครื่อง

จาก root ของ checkout ใช้ PowerShell เปิดแอปพร้อมข้อมูลสาธิตที่สัมพันธ์กันใน SQLite แยก

```powershell
& .venv\Scripts\python.exe scripts\seed_mock_data.py --demo-dir "$env:LOCALAPPDATA\SmartVoice\smartvoice-demo" --serve
```

ครั้งแรกให้ตั้งรหัสผ่านเดโมที่ prompt แล้วเข้าด้วย `demo_admin`, `demo_supervisor`, `demo_qa` หรือ `demo_agent` ใช้รหัสที่ตั้งเดียวกันทั้งสี่บัญชี โปรแกรมเปิดเฉพาะ loopback และปิดการโหลด .env ของ checkout ข้อมูลมี 3 สายจำลอง, 2 ลูกค้า, 2 ทะเบียน, 2 เคส และ 2 ใบสั่งขายพร้อมรายการสินค้า สาธิตได้โดยไม่ต้องประมวลผลเสียงหรือใส่ API key รันคำสั่งเดิมเพื่อใช้ข้อมูลเดิม หากต้องการคืนข้อมูลตั้งต้น ให้ปิดเดโมแล้วเพิ่ม `--reset` และตั้งรหัสใหม่ การ reset มีผลกับการแก้ไขในฐานเดโมนั้น

ใช้ Git และ Python 3.10–3.12 (แนะนำ 3.12 ตามสภาพแวดล้อม EC2) คำสั่งด้านล่างเป็น PowerShell เปิด terminal ใหม่โดยตั้ง working directory เป็น root ของ clone ผ่าน IDE ก่อนรันคำสั่งติดตั้ง

### 1. Clone และแยก Branch

```powershell
git clone https://github.com/SojiKlay/smartvoice-master.git smartvoice-git
```

เปิดโฟลเดอร์ `smartvoice-git` ใน IDE และเปิด terminal ที่ root repository จากนั้น:

```powershell
git status --short
git switch test/phase6-e2e
git log -1 --oneline
git switch -c codex/developer-handoff
```

`test/phase6-e2e` เป็น branch ที่ตรวจในรอบส่งต่อ (HEAD ก่อนแก้เอกสาร `02eacfb`) ให้ยืนยัน branch/release SHA กับเจ้าของงานก่อนเริ่ม; เอกสารส่งต่อนี้ยังรอ Commit/Push จึงยังไม่อยู่ใน clone จนกว่าเจ้าของงานจะเผยแพร่ ใช้ branch ใหม่ต่อหนึ่งงานและส่ง PR ให้ตรวจ ห้าม Merge/Push/Deploy อัตโนมัติ

### 2. Dependencies และ Environment

```powershell
py -3.12 -m venv .venv
& .venv\Scripts\python.exe -m pip install -r requirements.txt
& .venv\Scripts\python.exe -m pip install -e . --no-deps
& .venv\Scripts\python.exe -m pip install pytest
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

`requirements.txt` รวม `requirements-api.txt` และ PostgreSQL driver; ไม่ต้องติดตั้ง CUDA, torch, Ollama หรือ local models แก้เฉพาะ `.env` ในเครื่อง: คง providers เป็น `pyannote_api` / `typhoon`, `AI_API_TIMEOUT=120` และใส่ keys เฉพาะเมื่อต้องทดสอบ API ที่ได้รับอนุมัติ เปิดเว็บ/รัน mock tests ได้โดยไม่ใช้ keys จริง `MOCK_STT=true` จำลองเฉพาะเสียงและ **ยังเรียก Typhoon มีค่าใช้จ่าย**

ห้าม commit `.env`, credentials, DB dumps, runtime data, checkpoints, เสียงหรือข้อมูลลูกค้า ตรวจ `git diff` และ stage เฉพาะชื่อไฟล์งาน; `.gitignore` ไม่แทนการตรวจเนื้อหา

### 3. เตรียม Database และเปิดแอป

**SQLite สำหรับเริ่ม Local:** ตั้ง `DATABASE_URL=` ว่าง และ `DB_PATH=data/smartvoice.db` ใน `.env` ฐานและ schema สร้าง/อัปเดตตอนเปิดแอป ใช้ข้อมูลสังเคราะห์เท่านั้น

**PostgreSQL สำหรับงานที่ต้องตรงกับ Pilot:** ติดตั้ง PostgreSQL ในเครื่อง สร้าง role และฐาน development แยก เช่น `smartvoice_dev` (ไม่ใช้ฐานร่วม/ฐานจริง) ตั้ง `DATABASE_URL=postgresql://<user>:<URL-encoded-password>@127.0.0.1:5432/smartvoice_dev` ใน `.env` แล้วรัน:

```powershell
& .venv\Scripts\python.exe -m scripts.migrate_postgres
& .venv\Scripts\python.exe -m scripts.migrate_postgres --apply
```

คำสั่งแรกเป็น dry-run; `--apply` สร้าง schema v2 หรืออัปเกรด v1 → v2 เว็บตรวจ version แต่ไม่ migrate PostgreSQL เอง `DATABASE_URL` มีผลเหนือ `DB_PATH` ไม่ย้ายข้อมูล SQLite อัตโนมัติ สำรองก่อนอัปเกรดฐานที่มีข้อมูล และอ่าน [migration/restore runbook](deploy/aws-ec2/README.md) หากต้องนำเข้าข้อมูล

```powershell
& .venv\Scripts\python.exe -m streamlit run Home.py --server.address 127.0.0.1
```

เปิด `http://localhost:8501` เปลี่ยนรหัส bootstrap ทันทีตาม First Login; เปิด terminal ใหม่หลังทดสอบเพื่อไม่ให้ค่า environment สำหรับ tests ติดไปกับแอป

### 4. ทำความเข้าใจโค้ดก่อนแก้งาน

อ่าน `PROJECT_STATUS.md` ส่วนล่าสุด → `AGENTS.md` → pipeline ด้านล่าง → `smartvoice/pipeline.py`, `insight_rules.py`, `db.py` / `database_backend.py`, `auth.py` / `ui_helpers.py` และ `migrations/` ตามงาน `AGENTS.md`, `SETUP.md` และเอกสาร architecture เก่าบางส่วนยังมีข้อมูลยุค SQLite/local; ข้อความว่า PostgreSQL/Cloud ยังเป็นแผนไม่ตรงกับ Phase 6 ให้ยึดสถานะล่าสุดและ implementation ปัจจุบัน และรักษากฎ API-only/ข้อมูล/สิทธิ์เดิม

การเปลี่ยนเอกสาร setup นี้ไม่เปลี่ยน architecture; ไฟล์และ processing threads ยังอยู่ในเครื่องแอป ดู launcher เพิ่มเติมใน [`ONE_CLICK_RUN.md`](ONE_CLICK_RUN.md)

## Core Environment Variables

```env
STT_PROVIDER=pyannote_api
LLM_PROVIDER=typhoon
PYANNOTE_API_KEY=
PYANNOTE_API_MODEL=precision-2
STT_API_MODEL=faster-whisper-large-v3-turbo
TYPHOON_API_KEY=
TYPHOON_MODEL=typhoon-v2.5-30b-a3b-instruct
AI_API_TIMEOUT=120
DATABASE_URL=
DB_PATH=data/smartvoice.db
MOCK_STT=false
CASE_RECENCY_HOURS=4.0
SMARTVOICE_USERS=
PROCESSING_STALE_MINUTES=180
DISCORD_WEBHOOK_URL=          # แจ้งเตือนการรับ/ปิดเคส (ว่าง = ไม่ส่ง)
REPORT_FONT_PATH=             # ฟอนต์ไทยของรายงาน PDF (ว่าง = Tahoma/Leelawadee อัตโนมัติ)
```

## Processing Pipeline

```text
Audio (.wav/.mp3)
  → validate + save + optional phone auto-link
  → upload + pyannoteAI API transcription/diarization + checkpoint
  → heuristic cleanup + transcript cleanup LLM
  → speaker correction LLM + deterministic Thai role rules
  → Typhoon analysis 5 requests (JSON parsing, temperature 0)
  → insight_rules: verify quotes, compute scores/flags
  → SQLite / PostgreSQL save
  → auto case assignment
  → Streamlit UI
```

## LLM Output Fields

| Field | Description |
|-------|-------------|
| `summary` | สรุปบทสนทนา |
| `topic` | หัวข้อหลักที่ลูกค้าติดต่อ (จำกัดไว้ 9 หัวข้อ) |
| `topic_detail` | ประเภทความเสียหาย — กรอกเมื่อ `topic="แจ้งปัญหาสินค้า"` เท่านั้น (`ผ้าขาด/ผ้าหุ้มชำรุด`, `เตียง/โครงหัก`, `สปริง/ฟองน้ำยุบ`, `เปื้อน/รอยขีดข่วน`, `กลิ่น/แพ้/ระคายเคือง`, `ความชื้น/น้ำท่วม`, `ขนาด/สเปคผิด`, `อื่นๆ`) |
| `sentiment` | `positive` / `neutral` / `negative` (ตรวจซ้ำด้วยคำพูดลูกค้า) |
| `sentiment_reason` | เหตุผลพร้อมคำพูดของลูกค้า |
| `agent_performance` | `politeness`, `politeness_evidence`, `problem_solving`, `problem_solving_evidence`, `overall_score`, `next_action`, `next_action_owner` — คะแนนคำนวณใหม่ใน Python จากคำพูดที่ยืนยันแล้ว |
| `keywords` | คำสำคัญ |
| `brand_mentions` | แบรนด์ที่ถูกพูดถึงจริงในสาย (ชื่อมาตรฐานเดียว) |
| `platform_mentions` | ช่องทางซื้อ/ติดต่อที่ถูกพูดถึง |
| `anomaly_detected` | พบความผิดปกติหรือไม่ (ต้องมีคำพูดจริงเป็นหลักฐาน) |
| `anomaly_reason` | เหตุผลพร้อมคำพูดจาก transcript |
| `anomaly_severity` | `low` / `medium` / `high` — กำหนดจากหมวด ไม่ใช่จาก LLM |

## Tests

รันทั้ง `tests/` รวม `test_config.py` ใน terminal แยกที่ root repository ใช้ env จำลองและฐานทดสอบ ไม่อ่าน `.env`:

```powershell
$env:STT_PROVIDER='pyannote_api'; $env:LLM_PROVIDER='typhoon'
$env:PYTHON_DOTENV_DISABLED='1'; $env:MOCK_STT='false'
$env:TYPHOON_API_KEY='test-only'; $env:PYANNOTE_API_KEY='test-only'
$env:DATABASE_URL=''; $env:SMARTVOICE_TEST_POSTGRES_URL=''
$env:DISCORD_WEBHOOK_URL=''; $env:SMARTVOICE_USERS=''
$env:DB_PATH=Join-Path $PWD '.pytest_cache/runtime/test.db'
$env:TEMP=Join-Path $PWD '.pytest_cache/temp'; $env:TMP=$env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
& .venv\Scripts\python.exe -m pytest tests\ -q --basetemp=.pytest_cache/work
```

นี่คือ SQLite/mock API regression; PostgreSQL tests จะ skip หากไม่ตั้งฐานทดสอบ และ shell checks อาจ skip หากไม่มี Bash ห้ามรายงาน skip เป็น pass หรือใช้ผลนี้รับรอง live APIs/AWS

สำหรับ PostgreSQL integration ให้เตรียมฐาน **`smartvoice_test` บน localhost เท่านั้น** และตั้ง `SMARTVOICE_TEST_POSTGRES_URL` ใน process ไปฐานนั้น (รับ credentials ผ่านช่องทางปลอดภัย ไม่ commit) คง env จำลองอื่นด้านบนและรัน full suite เดิมอีกครั้ง Fixture จะ **TRUNCATE ข้อมูลในฐานทดสอบ** ต้องไม่ใช้ฐาน development ที่ต้องเก็บข้อมูลหรือฐานจริง ต้องมี `pg_dump`/`pg_restore` ใน PATH; role สำหรับ restore test ต้องสร้างฐานชั่วคราวได้ และ client ต้องเข้ากันได้กับ server

บันทึกจำนวน passed/failed/skipped พร้อมเหตุผล, commit, Python และ backend ทุกครั้ง ผลล่าสุดและผล AWS ที่ผู้ใช้ยืนยันแยกกันใน [`PROJECT_STATUS.md`](PROJECT_STATUS.md)
