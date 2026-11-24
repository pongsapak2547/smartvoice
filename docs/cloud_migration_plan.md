# SmartVoice — แผนย้าย Local สู่ Cloud และเอกสารส่งต่อ

อัปเดต implementation 15 พฤศจิกายน 2026: branch `codex/aws-pilot-high-fixes` เพิ่ม PostgreSQL compatibility, schema version 1, SQLite read-only migration และ PostgreSQL backup/restore พร้อม tests บน PostgreSQL 17.12 localhost แล้ว ยังไม่ deploy หรือย้ายข้อมูลจริง ดู `PROJECT_STATUS.md` และ runbook ใน `deploy/aws-ec2/README.md` เนื้อหาด้านล่างเป็น design/handover เดิม บางรายการที่เขียนว่า Planned ได้ทำเฉพาะส่วน compatibility แล้ว; PostgreSQL hosting, distributed worker/storage และ production acceptance ยังไม่เสร็จ

ตรวจ source วันที่ 15 พฤศจิกายน 2026 (Asia/Bangkok) ที่ commit `0c66644077e2d2e5fc930167a4116278d4eaa8d4` ซึ่งตรงกับ GitHub `master` และ remote HEAD ก่อนเริ่มงาน; working tree สะอาด งานส่งต่อนี้แก้เอกสารเท่านั้น

## 1. Executive summary

SmartVoice เปลี่ยนส่วน AI เป็น API-only แล้ว: ส่งเสียงให้ pyannoteAI และส่งข้อความให้ Typhoon แต่เว็บ Streamlit, SQLite, ไฟล์เสียง/หลักฐาน และ background threads ยังทำงานบนเครื่องที่เปิดแอป จึงยังไม่ใช่ระบบ Cloud Production

เป้าหมายคือให้พนักงานหลายคนในบริษัทใช้ระบบส่วนกลาง โดยไม่ต้องมีเครื่อง GPU สำหรับ AI การใช้ API ลดภาระติดตั้งและดูแลโมเดล แต่เพิ่มการพึ่งพาอินเทอร์เน็ต ผู้ให้บริการ ค่าใช้จ่ายต่อการใช้งาน และข้อพิจารณาการส่งข้อมูลลูกค้าออกนอกระบบบริษัท

**Current phase: Phase 4 — PostgreSQL Migration Design.** แบบ PostgreSQL, storage และ AWS ในเอกสารนี้เป็น **Planned / Not Implemented** ทั้งหมด หมายเลข Phase เป็นหมวดแผน ไม่ได้หมายความว่า Phase ก่อนหน้าผ่านครบแล้ว ยังต้องตรวจ live API, security และสภาพแวดล้อม AWS จริง

ตามข้อมูลส่งต่อจาก PM เคยทดลอง AWS Academy EC2 แล้ว แต่รอบนี้ไม่ได้เข้าตรวจบัญชีหรือ instance จึงไม่ยืนยันว่าเวอร์ชัน API-only ล่าสุด deploy สำเร็จ และไม่มีหลักฐาน Production Cloud Architecture ที่ผ่านการทดสอบ ห้ามใช้ผล unit tests เป็นหลักฐานว่า Cloud พร้อมใช้งาน

## 2. จุดเริ่มต้นและประวัติที่ยืนยันได้

ระบบเดิมใช้ Whisper STT, Pyannote diarization และ Ollama LLM บนเครื่องเดียวกับเว็บ การดาวน์โหลดโมเดล การจัด RAM/VRAM และ dependencies ของ GPU ทำให้การติดตั้ง/ใช้งานบนเครื่องสเปคต่ำยุ่งยาก เป้าหมายของ PM คือย้ายภาระ AI ออกและเตรียมระบบส่วนกลางสำหรับหลายคน ไม่ใช่เปลี่ยนกติกาวิเคราะห์สายหรือสิทธิ์พนักงาน

ประวัติ Git ที่มีเริ่มจาก `df0ef44` ซึ่งมี API adapters อยู่แล้ว จึงไม่ควรอ้างว่า Git เก็บทุกขั้นของการพัฒนาจาก Local ล้วน; architecture เดิมอ้างอิงเอกสารประวัติและส่วน Local ใน source ของ commit แรก จากนั้น `e01aa7a` ปรับ ignore rules และ `0c66644` ถอดการรัน Local AI ออก การเปรียบเทียบ `df0ef44..0c66644` ไม่พบการแก้ `db.py`, `pipeline.py`, `prompts.py`, `insight_rules.py`, `auth.py`, `customer_entry.py`, `sales_orders.py` หรือ `case_workflow.py`

PostgreSQL เป็นเป้าหมายสำหรับฐานข้อมูลส่วนกลางและงานเขียนพร้อมกันหลายผู้ใช้ พร้อมการจัดการ transaction/backup ที่เหมาะกับการปฏิบัติงานบริษัท ไม่ได้หมายความว่า SQLite ใช้หลายผู้ใช้ไม่ได้เลย AWS เป็นตัวเลือก hosting ที่สอดคล้องกับการทดลอง Academy เดิมและแผนแยก compute/database/storage แต่ยังต้องตัดสินงบประมาณ สิทธิ์บริการ ภูมิภาค และทีมดูแล

## 3. Architecture ก่อนและหลัง

```text
เดิม (ประวัติ)
Audio → Local Whisper → Local Pyannote → Local Ollama
      → Business rules / insight validation → SQLite → Streamlit

ปัจจุบัน (Implemented in source)
Audio บน local disk → pyannoteAI API (STT + diarization)
      → pipeline / speaker rules ↔ Typhoon API (correction, cleanup, analysis)
      → insight_rules → SQLite → Streamlit
      + checkpoint ข้างไฟล์เสียง + daemon threads ใน process ของเว็บ

เป้าหมาย (Planned / Not Implemented)
ผู้ใช้ → HTTPS → Streamlit → Database access layer → PostgreSQL
                    ↓                    ↑
            private object storage   durable job state
                    ↕                    ↕
                  worker → pyannoteAI / Typhoon → rules เดิม
```

ฐานข้อมูลใหม่เพียงอย่างเดียวไม่ทำให้ audio processing กระจายหลายเครื่องได้ ปัจจุบัน locks, stop flag และคิวอยู่ในหน่วยความจำของ process; checkpoint เป็นไฟล์ ไม่ใช่ distributed lock ต้องออกแบบ worker และ storage แยกต่างหากก่อนเพิ่ม replicas

## 4. งานที่ทำแล้วและสิ่งที่รักษาไว้

| ไฟล์/ส่วน | สิ่งที่ยืนยันจาก source ปัจจุบัน | เหตุผล/ขอบเขต |
|---|---|---|
| `smartvoice/stt/orchestrator.py` | upload, submit job, polling, ตรวจ segment, บันทึกและใช้ checkpoint | แทน local STT/diarization โดยคืน segment ให้ pipeline เดิม |
| `smartvoice/ollama_client.py` | เรียก Typhoon chat completions เท่านั้น | คง import name เดิมเพื่อ compatibility; ไม่ใช่ Ollama runtime |
| `smartvoice/config.py`, `env_settings.py`, `pages/4_Settings.py` | provider API-only, keys/model/timeouts, ปฏิเสธ provider Local เก่า | ผู้ดูแลต้องยืนยันการตั้งค่าเอง; ไม่แก้ `.env` จริงอัตโนมัติ |
| `requirements.txt`, `requirements-api.txt`, `pyproject.toml`, `run.bat`, `run.sh` | dependencies/launchers สำหรับ API | ไม่ต้องติดตั้ง Local AI; ไม่ลบ packages/cache ที่มีอยู่ |
| `smartvoice/preflight.py`, `ui_helpers.py`, หน้า Admin | readiness/config และแสดง provider API | readiness ไม่ได้ยืนยันเครดิตหรือ live API |
| `smartvoice/stt/transcribe.py`, `scripts/compare_stt_models.py` | ถูกถอดออกแล้ว | ห้ามคืน local inference; helpers ข้อความใน audio/diarize ยังอยู่ |
| `tests/test_api_only.py`, `test_api_backends.py` | API-only/config/payload/error/checkpoint checks | ใช้ mocks ไม่ใช่บริการจริง |

พฤติกรรมที่ยังต้องรักษา: authentication และ role permissions, speaker correction/splitters และลำดับ pipeline, prompts, insight validation, auto case assignment, soft delete/cancel/restore, audit trail, สูตรรายงาน และการผูกลูกค้า/SO ยังคงใช้ SQLite 9 ตารางและ runtime storage บน disk ไม่มี PostgreSQL adapter หรือ object storage ในงานนี้

`MOCK_STT` จำลองเฉพาะเสียง; LLM ยังต้องใช้ Typhoon key จึงไม่ใช่โหมด offline ทั้งระบบ

### API errors และ checkpoint

- Typhoon ตรวจ missing key, connection/HTTP errors รวม 429, completion ขาด/ว่าง/ถูกตัด และ JSON ที่ประมวลผลไม่ได้ โดยไม่บันทึกผลวิเคราะห์ default เป็นความสำเร็จเงียบ ๆ ไม่พบระบบ retry/backoff สำหรับคำขอเสียเงินอัตโนมัติ
- pyannoteAI เก็บ `<audio-path>.smartvoice-api.json` มี signature จาก hash เสียง/รุ่น/key, job ID และ output เมื่อสำเร็จ ถ้า signature เดิมและมี output ใช้ผลเดิม; ถ้ามี job ID จะติดตามงานเดิม การเปลี่ยน key/model/audio อาจทำให้เริ่มงานใหม่และเสียเงินใหม่
- ก่อน submit จะบันทึก `submitting`; ถ้าส่งแล้วไม่ได้ ID จะหยุดเพื่อให้ตรวจ job history ก่อนล้าง checkpoint ไม่รับรอง exactly-once ข้ามเครื่อง การกดหยุดในแอปไม่ใช่ยกเลิก job ที่ผู้ให้บริการรับแล้ว
- checkpoint อ่านไม่ได้, job ล้มเหลว, segment ไม่ถูกต้อง และ timeout แสดงเป็นข้อผิดพลาด การรันซ้ำอาจใช้ STT เดิมแต่เรียก LLM ใหม่ จึงอาจมีค่าใช้จ่ายซ้ำ
- checkpoint มีข้อความส่วนตัว ต้องป้องกันเหมือนเสียง/ฐานข้อมูล ห้ามใส่ Git หรือ log เนื้อหาเพื่อ debug

## 5. Current SQLite schema และผล audit

อ้างอิง `smartvoice/db.py:init_db`, `_create_sales_order_tables`, `_migrate*` และ [database_design.md](database_design.md) เป็น 9 **application tables** ไม่รวม SQLite internal tables การตรวจนี้อ่าน source ไม่ได้เปิดฐานข้อมูลลูกค้าจริง

| ตาราง | หน้าที่และข้อกำหนดที่ต้องคง |
|---|---|
| `calls` | hash ไฟล์ UNIQUE, transcript/analysis/status, case_id; created_at คือเวลา upload ไม่ใช่เวลาโทร |
| `customers` | phone UNIQUE ทั้งแถวปกติและแถวซ่อน; phone อาจ NULL |
| `warranty_registrations` | registration_no UNIQUE NOT NULL, customer FK, cancelled แยกจาก hidden |
| `sales_orders` | so_number UNIQUE, customer FK ที่ว่างได้, soft delete |
| `sales_order_lines` | รายการสินค้า FK → SO, แทนที่ทั้งชุดเมื่อบันทึก SO |
| `call_customer_links` | call/customer/warranty FK, id PK; ไม่มี UNIQUE ของ call_id ใน schema ปัจจุบัน |
| `cases` | customer FK, เจ้าของ/สถานะ/เวลารับและปิดเคส |
| `users` | username UNIQUE COLLATE NOCASE, password hash, role, is_active |
| `audit_log` | append-only ตามเส้นทางแอป; actor/entity เป็น snapshot ข้อความ ไม่มี FK ไปผู้ใช้ |

| ข้อสังเกตจาก design review | ผลตรวจ source และผลต่อการออกแบบ |
|---|---|
| SQLite coupling | ยืนยัน: `db.py` ใช้ sqlite3.Connection/Row, `?`, lastrowid และ PRAGMA; `auth.py`, `customer_entry.py`, `audit.py` จับ sqlite3 exceptions; `scripts/compare_llm_models.py` และ tests บางตัวเข้าถึง SQLite โดยตรง |
| `INSERT OR REPLACE` | ยืนยันใน `link_call_customer`; ไม่มี UNIQUE(call_id) และไม่ได้ส่ง id เข้า insert จึงไม่ควรตีความว่าเป็น upsert หนึ่ง link ต่อสาย ปัจจุบันสามารถมีหลาย link แต่ reader ใช้ fetchone ต้องให้ PM ตัดสิน cardinality และตรวจ duplicate ก่อนเพิ่ม constraint |
| customer/warranty check-then-insert | ยืนยัน: ตรวจหาเดิมคนละ connection ก่อน INSERT; UNIQUE กันข้อมูลซ้ำ แต่ผู้แพ้ race อาจได้ exception แทน existing id ต้องคงสัญญา idempotent ของ low-level functions และข้อความปฏิเสธ/restore ของ UI |
| concurrent case claiming | ยืนยัน: `claim_case` ใช้ UPDATE เดียว WHERE assignee_username IS NULL AND status != 'closed' และตรวจ rowcount; release/status ตรวจเจ้าของแบบไม่สน case ใน WHERE ต้องรักษาไว้ |
| concurrent SO import | `save_sales_order` บันทึกหัว/ลบรายการเดิม/ใส่รายการใหม่ใน transaction ต่อ SO แต่ SELECT ก่อน INSERT ยังมี race; `import_orders` loop commit ทีละ SO และ audit หลังจบ ไม่ใช่ atomic ทั้งไฟล์; fallback manual customer link อ่านก่อน transaction |
| username uniqueness | ยืนยัน COLLATE NOCASE ทั้ง schema และ lookup; username validation จำกัด ASCII ต้องคงการล็อกอิน/เจ้าของเคสไม่สนตัวพิมพ์ |
| last active Admin | `auth.would_remove_last_admin` อ่าน/นับแยกจาก `db.update_user`; ยังไม่มี transaction เดียวป้องกัน Admin สองคนปิดกันพร้อมกัน |
| SQLite-specific SQL | ยืนยัน GROUP_CONCAT ใน `get_open_cases_by_customer`, PRAGMA table_info/foreign_keys/busy_timeout, AUTOINCREMENT, COLLATE NOCASE, `?`, lastrowid และ dynamic column migrations |
| JSON / time | JSON เก็บ TEXT, audit dumps/loads; `_now` สร้าง UTC ISO string ระดับวินาที; วันที่โทร derive จาก filename ต้องตรวจผู้เรียกก่อนเปลี่ยนชนิด return |
| distributed processing | ยืนยัน `ui_helpers.launch_processing*` ใช้ daemon threads และ process locks; `processing_control` เก็บ state ใน module memory ไม่ได้ประสานหลาย server |

## 6. PostgreSQL design — Planned / Not Implemented

### 6.1 Database access layer และ compatibility

ข้อเสนอให้คง public functions/return shape ของ `smartvoice.db` เป็น facade แล้วแยก connection, query dialect, transaction และ exception translation ภายใน adapter SQLite/PostgreSQL เพื่อลดผลต่อหน้า UI และกฎธุรกิจ ไม่ใช้การแทน `?` ใน SQL ทุกจุดแบบข้อความโดยไม่เข้าใจ query

ก่อน implementation ให้เลือก psycopg หรือ SQLAlchemy Core พร้อม migration tooling และ PostgreSQL major version ที่ hosting รองรับ กำหนด domain exceptions เช่น duplicate/unavailable แทนการให้ business modules จับ sqlite3 โดยตรง บริหาร connection ต่อ operation/transaction, ปิดหรือคืน pool เมื่อ error, จำกัด pool ตามจำนวน web/worker processes ห้ามแชร์ connection เดียวระหว่าง threads

แผนเริ่มด้วย contract tests ของ facade บน SQLite แล้วทดสอบชุดเดียวกันบน PostgreSQL จริงใน test environment; mocks ไม่พอสำหรับ locks, isolation, collation และ constraints ใช้ versioned schema migrations แทนการให้ทุก web process แข่ง ALTER TABLE ตอนเริ่มระบบ

| ส่วน | ข้อเสนอ compatibility ที่ต้องทดสอบ |
|---|---|
| IDs | integer identity + INSERT RETURNING id; migration รักษา id เดิมและตั้ง sequence ให้พ้น max id |
| FK / delete | รักษา FK/nullability/cascade ตาม schema จริง; ห้ามเพิ่ม cascade ลบลูกค้า/ทะเบียน/SO; warranty.so_number ยังไม่ใช่ FK เพราะลงทะเบียนก่อนนำเข้า SO ได้ |
| JSON | ระยะแรกคง TEXT เพื่อลดการเปลี่ยนรูปแบบ return; JSONB เป็นทางเลือกภายหลัง ต้องตรวจ invalid JSON และ null/empty/dict/list ก่อนแปลง |
| Timestamps | เป้าหมาย TIMESTAMPTZ UTC แต่ adapter คืน ISO string ตาม contract เดิม; date-only แยก DATE; ห้ามตีความเวลาโทรในชื่อไฟล์เป็น upload time หรือเลื่อน UTC+7 ซ้ำ |
| Money / quantity | SQLite ใช้ REAL; ประเมิน NUMERIC precision/scale และ rounding โดยเทียบยอดเดิม ห้ามเปลี่ยนสูตร/ยอดย้อนหลังเงียบ ๆ; ตัดสินก่อน freeze schema |
| Boolean | เลือก BOOLEAN หรือคง 0/1 ใน compatibility layer; ตรวจ truthiness และ query เดิมทุกจุด |
| Username | เสนอ unique index บน lower(username) พร้อม lower lookup/ownership comparison; ไม่บังคับใช้ extension จนตรวจ hosting; เก็บ display spelling เดิม |
| GROUP_CONCAT | ใช้ string_agg(id::text, ',') โดยคงรูปแบบ call_ids/null และกำหนด ordering ที่ชัดเจน; ทดสอบ GROUP BY และ LEFT JOIN |
| PRAGMA / NOCASE / placeholders | แยก dialect, ใช้ parameter binding ของ driver; ตรวจ LIKE/ILIKE, NULL sorting และ pagination เพื่อรักษาผลค้นหาและลำดับ |

### 6.2 Transactions และ concurrency

ข้อเสนอต่อไปนี้ต้องทำ integration tests ก่อนรับรอง:

1. **Case claim:** คง conditional UPDATE เดียวพร้อม affected-row/RETURNING ตรวจผู้ชนะหนึ่งคน รวม closed case และ release/status โดยเจ้าของที่ถูกต้อง ไม่เปลี่ยนเป็น SELECT แล้ว UPDATE
2. **Customer/warranty:** ให้ UNIQUE constraint เป็นผู้ตัดสินท้ายสุด ใช้ conflict-aware insert แล้วอ่าน existing id ใน transaction/statement ถัดไปตาม isolation; ไม่ overwrite ข้อมูลเดิมหรือคืนแถวซ่อนเป็นการสร้างสำเร็จของ UI โดยอัตโนมัติ ไม่ใช้ partial UNIQUE เฉพาะแถวที่ไม่ซ่อน
3. **SO:** serialize ต่อ so_number รวมกรณียังไม่มีแถวด้วย upsert/lock strategy ที่ตกลงแล้ว หัวและรายการทั้งหมดอยู่ transaction เดียว ย้ายการรักษา manual customer link เข้ามาในขอบเขตนั้น กำหนดว่า concurrent edit จะ last-writer-wins หรือ reject stale version; PM ต้องเลือก atomic ทั้งไฟล์หรือราย SO พร้อม partial-result reporting ปัจจุบันเป็นราย SO
4. **Last Admin:** ตรวจและแก้ใน transaction เดียวโดย serialize ทุก operation ที่เปลี่ยน membership/active ของ Admin ด้วย shared guard row หรือ transaction advisory lock เดียวกัน การล็อกเฉพาะ user เป้าหมายคนละแถวไม่พอ ต้องรวม bootstrap และเส้นทาง backend ทั้งหมด
5. **Soft delete:** ซ่อน customer และ warranties ที่เกี่ยวข้องใน transaction เดียว รักษา hidden_with_customer เพื่อกู้เฉพาะรายการที่ซ่อนตามลูกค้า ไม่ใช้ timestamp จับคู่; cancelled คงเป็นสถานะแยก และ SO re-save ปัจจุบันกู้จากซ่อน ต้องคงหรือขออนุมัติเปลี่ยนอย่างชัดเจน
6. **Audit:** ปัจจุบัน `audit.record` เปิดงานเขียนแยกและไม่ raise เมื่อ SQLite error จึงไม่รับประกัน atomic audit+business action ต้องรักษา behavior เดิมก่อน การเปลี่ยนเป็น mandatory transactional audit/outbox เป็น policy decision ของ PM พร้อม tests ไม่แอบเปลี่ยนใน migration
7. **External calls:** ไม่ถือ DB lock ระหว่างรอ AI หรือส่ง Discord; commit ผลก่อน side effect และออกแบบ retry/idempotency แยก การ retry transaction ที่ deadlock/serialization ต้องมีขอบเขตและไม่ยิง API เสียเงินซ้ำ

พื้นฐาน SQL ของข้อเสนออ้างอิง [PostgreSQL INSERT / ON CONFLICT / RETURNING](https://www.postgresql.org/docs/current/sql-insert.html) และ [locking](https://www.postgresql.org/docs/current/explicit-locking.html); ยังไม่ใช่ผลทดสอบ implementation ของ SmartVoice

### 6.3 Authentication consistency

รักษา password hash และ username เดิม, least-privilege ของ unknown role, role guards ทุกหน้า, ไม่มี Admin password reset และไม่ลบ user จาก UI ปัจจุบัน authenticate ตรวจ DB ก่อน `.env` fallback และเมื่อ DB read error อาจตกไป fallback ด้วย ต้องให้ PM ตัดสินว่าจะ fail closed ใน production หรือคง fallback ที่ควบคุมอย่างไร พร้อม tests ห้ามเปลี่ยนเงียบ ๆ

Session อยู่ใน Streamlit session_state; ต้องทดสอบ refresh/restart, role change/disable ระหว่าง session และ multi-instance routing ใน Phase 7 ไม่ถือว่า PostgreSQL ทำให้ sessions แชร์กันเอง และต้องวางแผน bootstrap Admin ก่อนเปิดรับผู้ใช้จริงโดยไม่บันทึก credential ใน Git

## 7. Roadmap และเงื่อนไขผ่านแต่ละ Phase

| Phase | สถานะจริง ณ handover | งานต่อและ dependency / gate |
|---|---|---|
| 1 — AI API Migration | Implemented in source; automated mocks มีผลเดิม 541 passed; live API ยังไม่ยืนยัน | ตรวจ keys/credits/models ด้วยเสียงที่อนุญาต เทียบ transcript/QA/latency/cost; ไม่ผ่านให้หยุดขยาย rollout ไม่คืน Local inference |
| 2 — Cloud Readiness | มี config, preflight, ignore/redaction บางส่วน; security readiness ยังไม่ผ่านการรับรอง | ทบทวนข้อมูลส่วนตัว, environment/secrets, bootstrap account, local paths, runtime permissions, Thai PDF fonts, dependencies และ network egress; ต้องผ่านก่อนเปิดใช้งานจริง |
| 3 — AWS Experiment | PM แจ้งว่าเคยทดลอง Academy EC2; version/config ล่าสุดยังไม่ตรวจ | ขอสิทธิ์และตรวจ commit/config/region/quota/lab lifecycle ก่อน controlled deployment; ไม่ถือว่า Academy มีทุกบริการหรือเหมาะกับ production |
| 4 — PostgreSQL Migration | **Design ในเอกสารนี้เท่านั้น** | ตัดสิน schema/DAL/concurrency → contract tests → adapter/versioned migrations → dry-run บนข้อมูลสังเคราะห์ → integration/race/restore tests → อนุมัติ cutover ข้อมูลจริง |
| 5 — Cloud Storage and Processing | Planned / Not Implemented | private object storage, file metadata, durable jobs, worker lease/heartbeat, idempotency, cancellation, retry/manual reconciliation; ต้องมี design ร่วมกับ Phase 4 ก่อนหลาย replicas |
| 6 — Cloud Deployment | Planned / Not Implemented | networking/HTTPS/compute/PostgreSQL hosting/secrets/backups/logging/alerts; ผ่าน Phase 2, API verification, DB/storage recovery gates และอนุมัติงบก่อน deployment |
| 7 — Multi-user Validation | ยังไม่ทำ load/concurrency/security acceptance บน cloud | role/access tests, concurrent claim/import/admin edits, peak workload, session/restart, API outage, restore drill; PM/IT รับมอบก่อน production rollout |

Phase 2 และการตรวจสอบ Phase 3 ทำเป็นงานเตรียมได้ระหว่าง Phase 4 แต่ห้ามนำลำดับเลขมาใช้ข้าม acceptance gates ตั้งเป้าจำนวนผู้ใช้พร้อมกัน ขนาดไฟล์/จำนวนสายต่อวัน latency และค่าใช้จ่ายร่วมกับ PM ก่อน load test

## 8. AWS architecture proposal — Planned / Not Implemented

ข้อเสนอเริ่มจาก deployment ขนาดเล็กที่ควบคุมได้: HTTPS ingress/reverse proxy หรือ load balancer → Streamlit compute; แยก worker เมื่อมี durable job design; PostgreSQL ใน private network (พิจารณา RDS เมื่อสิทธิ์และงบรองรับ); private object storage สำหรับเสียงและหลักฐาน; secrets service/environment injection; centralized logs/metrics ที่ไม่เก็บเนื้อหาลูกค้า

หาก Academy ไม่อนุญาตบริการที่เสนอ ให้ IT ประเมินทางเลือกทดลอง เช่น compute เดียวกับ persistent disk และฐานข้อมูลทดสอบ โดยระบุข้อจำกัด single point of failure ชัดเจน ไม่เรียกว่า production และไม่ย้ายข้อมูลลูกค้าจริงเพื่อหลบข้อจำกัดของ Lab

รายการที่ต้องออกแบบก่อนสร้างทรัพยากร: region/ที่ตั้งข้อมูล, IAM least privilege, security groups, private DB ไม่มี public access, outbound HTTPS ไป API, TLS/WebSocket ของ Streamlit, encrypted disk/object/database/backup, network cost และการปิดทรัพยากรทดลองตามอายุ Lab ใช้ RDS automated backups/snapshots/restore ตาม [AWS backup documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_CommonTasks.BackupRestore.html) หากเลือก RDS; ยังไม่ได้สร้างหรือทดสอบในงานนี้

Processing เป้าหมายต้องมี job owner/lease, heartbeat, bounded retries, dead-letter/manual review, API job ID และ result checkpoint ที่ durable; ป้องกันการประมวลผลสายเดียวพร้อมกันหลาย worker และระวัง side effects หลัง timeout การเข้าถึง object ใช้ authorization ของแอปและ URL อายุสั้นตามจำเป็น ห้ามทำ bucket public หรือใช้ filename ที่มีเบอร์โทรเป็น public URL

## 9. Security และ data protection

เสียง, transcript, checkpoint, หลักฐานซื้อ, DB, audit, exports และ logs อาจมีข้อมูลลูกค้า กำหนดผู้เข้าถึง อายุเก็บ การลบ/กู้ และผู้อนุมัติการส่งข้อมูลให้ pyannoteAI/Typhoon ก่อน live test/production ให้ PM/ผู้รับผิดชอบข้อมูลทบทวนเงื่อนไขผู้ให้บริการและนโยบายบริษัท; เอกสารนี้ไม่รับรอง compliance

ห้าม commit `.env`, secrets, database/dumps/backups, audio, transcripts, checkpoints, logs หรือข้อมูลลูกค้า การตรวจ `.gitignore` พบครอบคลุมหมวดเหล่านี้แล้ว แต่ ignore ไม่ใช่การ scan และไม่ลบไฟล์ที่ tracked อยู่ ต้องตรวจ staged diff ทุกครั้ง ใช้ secret manager สำหรับ production แทนการแก้ `.env` บนหลาย replicas และกำหนด rotation โดยคำนึงว่าเปลี่ยน pyannote key อาจทำให้ checkpoint signature เปลี่ยน

Audit redaction ปัจจุบันปิดบัง key ตามชื่อ field ไม่ใช่ตัวกรองข้อมูลส่วนตัวทั่วไป ห้าม log request/response หรือ signed URL ทั้งก้อน ทดสอบสิทธิ์ upload/download/export และการเข้าถึงเคส/หลักฐานทุก role โดยคง business permissions เดิม

## 10. Tests, migration validation, backup และ rollback

### หลักฐานการทดสอบ

รายงาน Codex เดิมใน PROJECT_STATUS ระบุ **541 passed in 85.42s** สำหรับ `tests/` รวม `test_config.py` หลัง API-only; เป็น automated tests ที่ mock APIs ไม่ใช่ live API end-to-end ผล 552/492 ในประวัติเก่าไม่ใช่ baseline ปัจจุบัน `test_config.py` ปัจจุบันเหลือ pure helpers ไม่ต้องโหลด torch

ผลรันจริงในงานเอกสารนี้: **541 passed in 89.25s** รวม `test_config.py` ดูคำสั่งและ environment ที่ [PROJECT_STATUS.md](../PROJECT_STATUS.md) แยกจากผลเก่า ไม่ได้ทดสอบ live APIs, AWS, PostgreSQL, distributed processing หรือ production load ในรอบนี้

### แผน validation ก่อนย้ายจริง — ยังไม่ได้ทำ

1. ใช้ข้อมูลสังเคราะห์ก่อน จากนั้นสำเนาที่ได้รับอนุมัติและปกป้องแล้ว ตรวจ row counts ทั้ง 9 ตาราง, IDs/FKs/orphans, unique values รวมแถวซ่อน, duplicate links, JSON ที่ parse ไม่ได้, timezone/date, money totals และ file checksums/path mapping ไม่แก้ source DB เพื่อให้ผ่าน
2. Import แบบรักษา IDs และความสัมพันธ์ในลำดับ dependency รองรับ calls/cases จาก schema ที่ migrate แล้ว ตรวจ rollback เมื่อ batch ล้มเหลว และ reset sequences; เปรียบเทียบ normalized row digests และ query/report outputs โดยไม่เผยข้อมูลในรายงาน
3. รัน business/permissions/auth/audit/soft-delete tests ทั้ง adapters และ PostgreSQL integration tests แบบหลาย independent connections/processes: รับเคสมีผู้ชนะหนึ่งคน, SO ไม่มีรายการปนข้าม transaction, duplicate customer/warranty/user มีผลแน่นอน, Admin เหลืออย่างน้อยหนึ่งคน รวม timeout/deadlock และ worker crash
4. Rehearse cutover และ restore บน staging ตั้ง RPO/RTO และ maintenance window กับ PM ก่อนรับรอง เวลาหยุดและความจุยังไม่ทราบจนกว่าจะวัดจริง

### Backup / cutover / rollback — ต้องได้รับอนุมัติก่อนข้อมูลจริง

ก่อน cutover หยุด uploads/writes และ drain/หยุด workers อย่างควบคุม บันทึก pending API job IDs สร้าง consistent SQLite backup ด้วยวิธีที่รองรับ SQLite หรือหลังปิด writers ไม่คัดลอกไฟล์สดอย่างเดาสุ่ม เก็บ runtime objects/checkpoints กับ checksum manifest และ commit/config version ที่จับคู่กัน แยก secrets ออกจาก backup report ตรวจ restore ได้ก่อนเปลี่ยน DSN

เก็บฐานเดิม read-only ห้าม dual-write ระหว่างสอง backend เปิด PostgreSQL หลัง validation ผ่านและ PM อนุมัติ หากยังไม่มี write ใหม่สามารถหยุดแอปแล้วกลับ SQLite snapshot เดิมพร้อมเวอร์ชันที่เข้าคู่กันได้ หาก PostgreSQL รับ write ใหม่แล้ว **ห้ามสลับกลับไฟล์เก่าทันที** ต้องหยุด writes, สำรองปลายทาง, reconcile/export delta ด้วยเครื่องมือที่ทดสอบแล้วและขออนุมัติผลกระทบ หรือเลือก forward fix

Rollback/หยุด rollout เมื่อพบข้อมูลไม่ครบ, FK/uniqueness ผิด, lost updates, สิทธิ์หรือ last-admin invariant พัง, restore ไม่ผ่าน หรือเกิน SLO/error/cost thresholds ที่ PM กำหนด External API ที่ submit แล้วไม่ได้ย้อนกลับด้วย DB restore ต้อง reconcile job history เพื่อเลี่ยงค่าใช้จ่ายซ้ำ

## 11. Risks, unresolved decisions และงานถัดไปตามลำดับ

| ลำดับ | สิ่งที่ต้องตัดสิน/ทำ | ผู้ร่วมตัดสินและผลลัพธ์ที่ต้องได้ |
|---|---|---|
| P0 | ยืนยัน Git/source และ review แบบ Phase 4 | Claude Code + PM: ยืนยัน scope, ไม่เริ่ม API migration ใหม่ |
| P0 | link cardinality, SO import atomicity/conflict policy, audit guarantee, auth fallback | PM + developer: compatibility contract ชัดก่อนเพิ่ม constraints หรือเปลี่ยน behavior |
| P0 | DAL/driver/migration tooling, PostgreSQL version, JSON/time/money representation | Developer + IT: schema mapping และ test matrix ที่ review ได้ |
| P1 | เขียน contract/race tests แล้วเตรียม PostgreSQL adapter บนข้อมูลสังเคราะห์ | Claude Code: งาน implementation ถัดไปหลังยืนยันข้อเลือก; แยก PR จากเอกสารนี้ |
| P1 | API acceptance ด้วยข้อมูลที่อนุญาต; ตรวจ AWS experiment แบบ read-only เมื่อได้รับสิทธิ์ | PM + IT: รุ่น/เครดิต/latency/quality/cost และ EC2 commit/config ที่ยืนยันได้ |
| P1 | Storage/worker design และ security review | Developer + IT: lease/recovery/secrets/access/retention ที่ทำงานข้าม process |
| P2 | Migration rehearsal, backup restore, load/security acceptance | PM + IT: RPO/RTO/SLO, downtime, budget, rollback และการอนุมัติ cutover |

ความเสี่ยงเปิด: ไม่เคยยืนยัน live API จาก tests นี้, race conditions ที่ต้องทดสอบจริง, audit ไม่ atomic, local processing ไม่ทน process crash แบบ distributed, session/role consistency หลายเครื่อง, Lab constraints และค่าใช้จ่ายบริการภายนอก เอกสาร README/SETUP/AGENTS/architecture เก่าบางส่วนยังมีคำอธิบาย Local; ใช้คำประกาศ API-only ล่าสุดและ source เป็นหลัก โดยเฉพาะคำเตือน launcher Local เดิมใน SETUP ไม่ใช่พฤติกรรม launcher ปัจจุบัน งานนี้ไม่แก้เอกสารนอกสามไฟล์ที่อนุญาต

## 12. Instructions for Claude Code / PM

1. อ่าน [AGENTS.md](../AGENTS.md) ก่อน โดยให้ API-only update ด้านบนมาก่อนแนวทาง Local ประวัติ แล้วอ่าน [PROJECT_STATUS.md](../PROJECT_STATUS.md) และเอกสารนี้
2. ตรวจ `git status`, branch, local HEAD และ latest remote commit ก่อนแก้ ห้าม reset/ทับงานค้าง หากต่างจาก baseline ให้ตรวจ diff และดำเนินต่อจากความคืบหน้าจริง
3. ไม่ทำ API-only migration ซ้ำ ไม่คืน Whisper/Pyannote/Ollama local dependencies รักษา `.env`, data, installed packages และ model caches เดิม
4. เริ่มงานพัฒนาถัดไปด้วย **PostgreSQL Phase 4 implementation preparation**: review unresolved decisions, นิยาม facade contract/schema และ tests ก่อน implementation รักษา business rules, permissions, soft delete/cancel/restore และ audit semantics
5. ห้าม deploy หรือ migrate ข้อมูลลูกค้าจริงโดยไม่มี approval; การมี branch นี้ไม่ใช่อนุมัติสร้าง AWS resources หรือส่งข้อมูลลูกค้าไป API
6. Keep secrets/runtime data out of Git ตรวจ changed/staged files และ stage แบบระบุชื่อ ห้าม `git add .`/`git add -A` สำหรับ handover นี้
7. รัน relevant tests และ full suite ตาม AGENTS ก่อน commit พร้อมอัปเดต PROJECT_STATUS หลังงานสำคัญ แยก mocked tests จาก live API/PostgreSQL/cloud evidence ทุกครั้ง

## 13. Source references สำหรับพัฒนาต่อ

| ประเด็น | แหล่งใน repository |
|---|---|
| ภาพรวม/ติดตั้ง/ประวัติ | [README](../README.md), [SETUP](../SETUP.md), [CHANGELOG](../CHANGELOG.md), [architecture](architecture.md), [database design](database_design.md) |
| Schema/CRUD/transactions | [db.py](../smartvoice/db.py): get_connection, init_db, link_call_customer, save_sales_order, claim_case, update_user |
| Auth/last Admin | [auth.py](../smartvoice/auth.py): authenticate, would_remove_last_admin; หน้า Users |
| Business writes | [customer_entry.py](../smartvoice/customer_entry.py), [sales_orders.py](../smartvoice/sales_orders.py), [case_workflow.py](../smartvoice/case_workflow.py), [audit.py](../smartvoice/audit.py) |
| API/checkpoints | [orchestrator.py](../smartvoice/stt/orchestrator.py), [ollama_client.py](../smartvoice/ollama_client.py), [config.py](../smartvoice/config.py) |
| Rules/processing/storage | [pipeline.py](../smartvoice/pipeline.py), [insight_rules.py](../smartvoice/insight_rules.py), [processing_control.py](../smartvoice/processing_control.py), [ui_helpers.py](../smartvoice/ui_helpers.py), [file_manager.py](../smartvoice/file_manager.py) |
| Verification | [test_api_only.py](../tests/test_api_only.py), [test_api_backends.py](../tests/test_api_backends.py), tests/test_db.py, test_auth.py, test_case_workflow.py, test_customer_entry.py, test_sales_orders.py, test_audit.py, test_pipeline.py, test_insight_rules.py |

Branch ส่งต่อที่ตั้งใจใช้: `docs/cloud-migration-handover` บน repository เดิม [SojiKlay/smartvoice-master](https://github.com/SojiKlay/smartvoice-master) ไม่มี merge เข้า master; ให้ตรวจ commit/push result ในรายงานส่งมอบ ไม่ใช้ข้อความในเอกสารนี้เป็นหลักฐานว่า push สำเร็จแล้ว
