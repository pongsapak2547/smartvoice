# SmartVoice — คู่มือติดตั้งและเปิดใช้งาน

คู่มือนี้สำหรับ **นักพัฒนา / IT** ที่ติดตั้งระบบครั้งแรก
สำหรับผู้ใช้งานธุรกิจ ให้ดู [`docs/user_manual.md`](docs/user_manual.md)

---

## ใช้งานผ่าน API โดยไม่ติดตั้งโมเดลในเครื่อง

ตั้งแต่ 15 พฤศจิกายน 2026 ตัดการรัน Whisper/Pyannote/Ollama ในเครื่องออกแล้ว ไม่ต้องติดตั้ง GPU, CUDA, PyTorch หรือ HuggingFace token. เว็บ, SQLite และข้อมูล runtime ยังคงอยู่ในเครื่อง/เซิร์ฟเวอร์ ไม่ใช่การ deploy Cloud อัตโนมัติ

### อัปเดตจากรุ่น Local

เปิดหน้า Settings แล้วกดโหมดใช้งานจริง ตั้ง API keys และบันทึก จากนั้นเปิดแอปใหม่ โดยใช้ `STT_PROVIDER=pyannote_api` และ `LLM_PROVIDER=typhoon`. หากยังเป็น `local`/`ollama` จะมีข้อความให้แก้การตั้งค่า; ระบบไม่ส่งข้อมูลไป API ด้วยการเปลี่ยน provider เงียบ ๆ. ตัวแปร `WHISPER_*`, `OLLAMA_*`, `HF_TOKEN` เดิมไม่ได้ใช้งานแล้ว ไม่ลบ `.env`, โมเดลที่ดาวน์โหลดไว้ หรือฐานข้อมูลเดิม

`MOCK_STT=true` ใช้บทสนทนาตัวอย่างแทนเสียงเท่านั้น การวิเคราะห์ยังใช้ Typhoon API และมีค่าใช้จ่าย


โหมดนี้ใช้ Whisper Large v3 Turbo และ Pyannote Precision-2 ผ่าน pyannoteAI STT Orchestration
และใช้ Typhoon API วิเคราะห์ข้อความ เว็บและ SQLite ยังรันในเครื่องหรือ EC2 ได้เหมือนเดิม
ต้องมี API key และเครดิตของทั้งสองบริการ ค่า API ไม่รวมในเครดิต AWS Academy

ตัวติดตั้งทั้ง `run.bat`, `run.sh` และ `requirements.txt` ใช้ dependencies สำหรับ API แล้ว

ติดตั้ง dependencies สำหรับ API ใน virtual environment แล้วเปิดเว็บ:

```powershell
py -3.11 -m venv .venv
& ".venv\Scripts\python.exe" -m pip install -r requirements-api.txt
& ".venv\Scripts\python.exe" -m streamlit run Home.py
```

ถ้ามี `.venv` แล้ว ให้ข้ามคำสั่งสร้าง environment ใช้ Python 3.10/3.11 สำหรับชุด local เดิม
โหมด API ทดสอบเพิ่มเติมได้บน Python 3.12 ไม่ต้องติดตั้ง torch, CUDA, transformers หรือ Ollama
อย่าใช้ `run.bat` / `run.sh` เดิมกับการติดตั้งแบบเบา เพราะ launcher เหล่านั้นติดตั้งชุด local เต็ม
บน Linux ใช้ `.venv/bin/python` แทน `.venv\Scripts\python.exe`

ในหน้าตั้งค่า เลือกบริการเสียงเป็น **Whisper + Pyannote API** และบริการวิเคราะห์เป็น **Typhoon API**
ปิดโหมดสาธิต กรอก API key ในช่องรหัสผ่าน บันทึกแล้วเปิดโปรแกรมใหม่
หรือเพิ่มค่าต่อไปนี้ใน `.env` ฝั่งเซิร์ฟเวอร์ (อย่า commit หรือส่ง key ผ่านแชต):

```dotenv
MOCK_STT=false
STT_PROVIDER=pyannote_api
LLM_PROVIDER=typhoon
PYANNOTE_API_KEY=your-pyannote-key
PYANNOTE_API_MODEL=precision-2
STT_API_MODEL=faster-whisper-large-v3-turbo
TYPHOON_API_KEY=your-typhoon-key
TYPHOON_MODEL=typhoon-v2.5-30b-a3b-instruct
TYPHOON_MAX_TOKENS=4096
AI_API_TIMEOUT=120
AI_JOB_TIMEOUT=1800
```

ลดรุ่น LLM ได้โดยตั้ง `TYPHOON_MODEL=typhoon-v2.1-12b-instruct` ตามสิทธิ์ที่ API รองรับ
ไม่มีการเปลี่ยนรุ่นหรือส่งซ้ำอัตโนมัติเมื่อเกิดข้อผิดพลาด เพื่อไม่ให้คุณภาพและค่าใช้จ่ายเปลี่ยนเงียบ ๆ
STT backend นี้รองรับ Whisper Turbo กับ Precision-2/3; Community-1 ไม่รองรับการถอดเสียงร่วมใน API นี้
ขนาดโมเดล API ไม่กิน RAM/GPU ของเครื่องเว็บ แต่มีผลต่อเวลา ค่าใช้จ่าย และคุณภาพของบริการ

โหมด API ส่งไฟล์เสียงต้นฉบับไปยังพื้นที่ชั่วคราวของ pyannoteAI ผ่าน HTTPS แล้วส่งข้อความไป Typhoon
ตรวจนโยบายข้อมูลของผู้ให้บริการและใช้ข้อมูลที่บริษัทอนุญาตก่อนทดสอบจริง
การตรวจความพร้อมบนหน้าเว็บตรวจว่าตั้งค่า key แล้วเท่านั้น ไม่ได้ยืนยัน key, เครดิต หรือสิทธิ์โมเดล

ระบบเก็บ job ID และผลเสียงต้นฉบับไว้ข้างไฟล์เสียงเป็น `<audio-path>.smartvoice-api.json`
เมื่อ timeout/หยุดแล้วกดประมวลผลใหม่ จะติดตาม job เดิมหรือใช้ผลสำเร็จเดิม ส่วน LLM จะวิเคราะห์ใหม่
การเปลี่ยนไฟล์ รุ่นเสียง หรือบัญชี API จะเริ่มงานเสียงใหม่ ผล cache เป็นข้อมูลลูกค้า ต้องป้องกันและสำรองพร้อมไฟล์เสียง
เมื่อลบเสียงผ่านแอป ระบบลบ checkpoint ของเสียงนั้นด้วย
หาก job ล้มเหลว หมดอายุ หรือส่งงานแล้วไม่ได้รับ job ID ให้ตรวจประวัติงานใน pyannoteAI ก่อน
หากต้องส่งงานใหม่จริง ให้ผู้ดูแลลบเฉพาะ checkpoint ของไฟล์นั้นแล้วกดประมวลผลใหม่ ซึ่งอาจเสียค่าบริการซ้ำ
ปุ่มหยุดหยุดการรอในแอป ไม่ได้ยกเลิกงานหรือค่าใช้จ่ายที่ผู้ให้บริการได้รับไปแล้ว

แนะนำเริ่มด้วยเสียงสั้นหนึ่งสาย ตรวจผู้พูด ข้อความ สรุป QA และสถานะ error ก่อนนำขึ้น EC2
ชุดทดสอบอัตโนมัติใช้คำตอบ API จำลอง ไม่ยืนยันความแม่นยำหรือสิทธิ์ของบัญชีจริง

เอกสารผู้ให้บริการ:
- https://docs.pyannote.ai/tutorials/speech-to-text-diarization
- https://docs.pyannote.ai/tutorials/how-to-upload-files
- https://docs.opentyphoon.ai/en/api-reference/

## หน้าเว็บที่มีตอนนี้

| หน้า (เมนู) | หน้าที่ |
|------|---------|
| หน้าแรก | "งานที่รอคุณ" — เคสที่ยังไม่มีคนรับ, เคสของฉัน, สายผิดปกติรุนแรง + สถานะสาย; ตรวจความพร้อมระบบ (Admin/Supervisor) |
| Dashboard — ภาพรวม / คีย์เวิร์ด แบรนด์ ช่องทาง / สายที่ผิดปกติ / ผลงานพนักงาน / รายการสาย | 5 หน้าใช้ตัวกรองร่วมกัน; ปุ่ม **ส่งออกรายงาน** (PDF, CSV สรุป, CSV รายการสาย) ทุกหน้า |
| จัดการเคส | รับเคส (คนอื่นแย่งไม่ได้), เปลี่ยนสถานะ/ปิดเคส, แจ้ง Discord |
| ลูกค้าและการรับประกัน | คลิกแถวเพื่อดูลูกค้า: ทะเบียนรับประกัน + หลักฐานการซื้อ, ใบสั่งขาย, เคส, สาย |
| ใบสั่งขาย (SO) | ค้นหา/ดูใบสั่งขาย; Admin นำเข้า Excel/CSV, เพิ่ม/แก้ไข, ซ่อน/กู้คืน |
| เพิ่ม/แก้ไขข้อมูลลูกค้า | เพิ่ม / แก้ไข / ซ่อน / กู้คืน ลูกค้าและทะเบียนรับประกัน, ยกเลิกทะเบียน (Cancel), แนบหลักฐานการซื้อ |
| อัปโหลดและประมวลผลเสียง | Upload, process, ค้นหา/กรองสาย, bulk delete, เชื่อมลูกค้า, จัดการ/รวมเคส |
| ประวัติการใช้งาน | audit log ทั้งระบบ — กรอง ค้นหา ดาวน์โหลด CSV |
| ตั้งค่าระบบ | preset Demo / Real AI, ปรับ model config, Discord webhook, ดู readiness checks |
| จัดการผู้ใช้ | เพิ่มบัญชี / เปลี่ยนบทบาท / เปิด-ปิดใช้งาน — ตั้งหรือรีเซ็ตรหัสผ่านของคนอื่นไม่ได้ และไม่มีการลบบัญชีถาวร |

ต้อง login ก่อนจึงจะเห็นหน้าใด ๆ และ sidebar จะแสดงเฉพาะหน้าที่ role นั้นมีสิทธิ์:

| Role | หน้าที่เข้าได้ |
|---|---|
| `Admin` | ทุกหน้า |
| `Supervisor` | ทุกหน้า ยกเว้น `เพิ่ม/แก้ไขข้อมูลลูกค้า` และ `จัดการผู้ใช้` (ดู SO ได้ แต่นำเข้า/แก้ไขไม่ได้) |
| `QA`, `Agent` | หน้าแรก, Dashboard ทั้ง 5 หน้า, จัดการเคส, ลูกค้าและการรับประกัน, ใบสั่งขาย (ดูอย่างเดียว) — QA รับเคสไม่ได้ |

---

## ตั้งค่า Authentication

เปิดแอปครั้งแรก ระบบจะสร้างบัญชีผู้ดูแลให้อัตโนมัติ:

| Username | Password |
|---|---|
| `admin` | `admin1234` |

ขั้นตอนหลัง login ครั้งแรก:

1. sidebar → กล่องบัญชี → `เปลี่ยนรหัสผ่าน` (คำเตือนใน sidebar จะหายไปเมื่อเปลี่ยนแล้ว)
2. sidebar → `จัดการผู้ใช้` → เพิ่มบัญชีพนักงานพร้อมกำหนด role

รหัสผ่านทั้งหมดถูกเก็บเป็น PBKDF2-SHA256 ในตาราง `users` ไม่มีการเก็บ plaintext

ผู้ดูแลระบบ**ตั้งหรือรีเซ็ตรหัสผ่านของพนักงานไม่ได้** — รหัสผ่านเป็นของเจ้าของบัญชี ถ้าพนักงานลืมรหัส ให้ปิดใช้งานบัญชีเดิมแล้วสร้างบัญชีใหม่ (ดู `docs/user_manual.md` หัวข้อ 15.1.1) ทุกการจัดการบัญชีและการเข้าสู่ระบบถูกบันทึกในหน้า `ประวัติการใช้งาน`

### บัญชีสำรองจากไฟล์ (ไม่บังคับ)

ถ้าต้องการบัญชีกู้ระบบที่ไม่ขึ้นกับฐานข้อมูล ให้สร้าง hash:

```powershell
python scripts/make_password_hash.py admin Admin
```

นำค่าที่ได้ไปใส่ใน `.env`:

```env
SMARTVOICE_USERS=admin|Admin|pbkdf2_sha256$...
```

รองรับหลาย user โดยคั่นด้วย `;` — ระบบจะตรวจบัญชีในฐานข้อมูลก่อน แล้วค่อยตกมาที่ `.env`

---

## Troubleshooting

### Upload แล้วไฟล์ไม่ผ่าน

- รองรับเฉพาะ `.wav` และ `.mp3`
- ไฟล์ต้องไม่เกิน 100 MB
- ถ้าเจอ `magic bytes ไม่ตรง` ให้ตรวจไฟล์หรือแปลงใหม่ด้วย `ffmpeg`

### งานค้างในสถานะ processing

- ระบบจะ reset งานเก่าที่ค้างเกิน `PROCESSING_STALE_MINUTES` ตอนเปิดหน้าใหม่
- ถ้าต้องการปิด behavior นี้ ให้ตั้ง `PROCESSING_STALE_MINUTES=0`

### ปุ่ม "รายงาน PDF" กดไม่ได้

- แปลว่าเครื่องไม่มีฟอนต์ภาษาไทย (Windows มี Tahoma อยู่แล้ว — มักเจอบน Linux)
- ติดตั้งฟอนต์ไทย หรือตั้ง `REPORT_FONT_PATH=` เป็น path ของไฟล์ `.ttf` ที่มีภาษาไทย แล้วรีสตาร์ทแอป
- ไฟล์ CSV ยังดาวน์โหลดได้ตามปกติ

### ดู log

- ไฟล์อยู่ที่ `data/logs/smartvoice.log`
- ตั้ง `SMARTVOICE_LOG_LEVEL=DEBUG` ใน `.env` เมื่อต้องการรายละเอียดเพิ่ม

---

## Test Suite

```powershell
& ".venv\Scripts\python.exe" -m pytest tests\ --ignore=tests\test_config.py -q
```

สถานะล่าสุดที่ยืนยันแล้ว: `492 passed` (ทดสอบเมื่อ 2026-10-16)

---

## เอกสารที่เกี่ยวข้อง

- [`README.md`](README.md)
- [`ONE_CLICK_RUN.md`](ONE_CLICK_RUN.md)
- [`docs/user_manual.md`](docs/user_manual.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/database_design.md`](docs/database_design.md)
- [`docs/OMAZZ_RELEASE_CHECKLIST.md`](docs/OMAZZ_RELEASE_CHECKLIST.md)
- [`CHANGELOG.md`](CHANGELOG.md)

## เปรียบเทียบรุ่น LLM ผ่าน API

`python scripts/compare_llm_models.py --models <model-A> <model-B> --allow-api` ส่ง transcript ที่เก็บไว้ไป Typhoon และมีค่าใช้บริการ โดยเปิด DB แบบอ่านอย่างเดียว เก็บรายงานใน `data/llm_compare/` ที่ gitignored. เครื่องมือเปรียบเทียบ STT แบบ Local ถูกถอดออก
