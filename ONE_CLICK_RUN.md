# SmartVoice one-click run guide

ใช้ Python 3.10–3.12, อินเทอร์เน็ต และบัญชี pyannoteAI/Typhoon ที่มี API keys และเครดิต ไม่ต้องติดตั้งโมเดลหรือ GPU

## Windows

เปิด `run.bat` ตัว launcher จะสร้าง `.venv` หากยังไม่มี ติดตั้ง dependencies สำหรับ API สร้าง `.env` จาก template เฉพาะเมื่อยังไม่มี และเปิดแอปที่ `http://localhost:8501`
หากไม่มี Python ตัว launcher เสนอติดตั้ง Python 3.11 โดยให้ผู้ใช้ยืนยันก่อน

## macOS / Linux

ติดตั้ง Python และ venv แล้วรัน `chmod +x run.sh` ตามด้วย `./run.sh`

## ตั้งค่า API

เข้าสู่ระบบ เปิด Settings เลือกโหมดใช้งานจริง ตั้ง `PYANNOTE_API_KEY` และ `TYPHOON_API_KEY` แล้วบันทึกและเปิดแอปใหม่
ค่าเริ่มต้นคือ `STT_PROVIDER=pyannote_api` และ `LLM_PROVIDER=typhoon` เครื่องที่ยังใช้ `local`/`ollama` ต้องบันทึกค่าใหม่ใน Settings ก่อนประมวลผล
การเรียก API ส่งเสียงให้ pyannoteAI และส่งบทสนทนาให้ Typhoon; readiness ตรวจเฉพาะการตั้งค่า ไม่ยืนยันเครดิตหรือสิทธิ์จริง

## โหมดสาธิต

`MOCK_STT=true` ใช้บทสนทนาตัวอย่างแทนการถอดเสียง การวิเคราะห์ยังเรียก Typhoon API จึงต้องมี key และเครดิต ไม่ใช่โหมด offline

## อัปเดตจากรุ่นเดิม

ตัว launcher ไม่ติดตั้งหรือเปิด Ollama, PyTorch, CUDA หรือโมเดล Local อีกแล้ว และไม่ถอนแพ็กเกจหรือลบโมเดลที่มีอยู่ในเครื่อง
ฐานข้อมูล ไฟล์เสียง checkpoints และ `.env` เดิมยังอยู่ ห้ามเพิ่มไฟล์เหล่านี้ลง Git

## Authentication

ทุกหน้าต้องเข้าสู่ระบบก่อน ไม่มีโหมดใช้งานแบบไม่ล็อกอิน

**ครั้งแรก:** ถ้ายังไม่มีบัญชีใดในระบบ แอปจะสร้างบัญชีให้อัตโนมัติ

| Username | Password |
|---|---|
| `admin` | `admin1234` |

1. เข้าสู่ระบบด้วยบัญชีนี้ แล้ว **เปลี่ยนรหัสผ่านทันที** ที่กล่องบัญชีใน sidebar → `เปลี่ยนรหัสผ่าน` (ระบบเตือนค้างจนกว่าจะเปลี่ยน)
2. เข้าหน้า `จัดการผู้ใช้` → สร้างบัญชีให้พนักงานแต่ละคนพร้อมกำหนดบทบาท

ผู้ดูแลระบบตั้งหรือรีเซ็ตรหัสผ่านของคนอื่นไม่ได้ และไม่มีการลบบัญชีถาวร — ทำได้แค่เปิด/ปิดใช้งาน

**บัญชีสำรองจากไฟล์ (ไม่บังคับ)** — สำหรับกู้ระบบกรณีลืมรหัส Admin ทุกบัญชี:

```bash
python scripts/make_password_hash.py admin Admin
```

จากนั้นนำผลลัพธ์ไปใส่ใน `.env` (ระบบตรวจบัญชีในฐานข้อมูลก่อน แล้วค่อยตกมาที่ `.env`):

```env
SMARTVOICE_USERS=admin|Admin|pbkdf2_sha256$...
```

## Packaging options

ก่อน zip โปรเจค ให้ตัดสิ่งเหล่านี้ออก:

- `.venv`
- `.git`
- `.env`
- `data/raw_audio`
- `data/models`
- `data/logs`
- `data/warranty_proofs` (รูปใบเสร็จ/สลิปของลูกค้าจริง)
- local DB เช่น `data/smartvoice.db` — นอกจากข้อมูลลูกค้าแล้ว ในนี้ยังมีใบสั่งขาย, บัญชีพนักงาน และ `audit_log` (ชื่อผู้ใช้, ชื่อลูกค้า, ประวัติการใช้งาน) ด้วย
- `smartvoice.egg-info` และ `*.egg-info`
- `.claude/`, `.worktrees/`, `.pytest_cache/`, `.pytest_tmp/`
- temporary reports เช่น `_anomaly_report.txt`

ถ้าต้องการ installer แบบ self-contained จริง ๆ ให้พิจารณา Docker หรือ PyInstaller ภายหลัง โดย Docker มักเสถียรกว่าสำหรับ stack ที่มี Torch, pyannote, CUDA, และ Ollama
