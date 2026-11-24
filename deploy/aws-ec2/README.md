# SmartVoice บน AWS EC2 — คู่มือติดตั้งและส่งต่อ Technical Pilot

ติดตั้ง SmartVoice ทั้งระบบบน EC2 เครื่องเดียว เพื่อให้ตัวแทนบริษัทเข้าทดลองใช้ผ่านเบราว์เซอร์ทาง HTTPS

```
ผู้ใช้ ──HTTPS──▶ EC2 (Ubuntu 24.04)
                  ├─ Caddy :443  (ใบรับรอง Let's Encrypt อัตโนมัติ)
                  │    └─▶ Streamlit 127.0.0.1:8501  (systemd: smartvoice)
                  ├─ /opt/smartvoice/app/data   ไฟล์เสียง + หลักฐาน + checkpoints (EBS เข้ารหัส)
                  ├─ PostgreSQL schema v2 (หรือ SQLite ใน data/ หากไม่ตั้ง DATABASE_URL)
                  └─ backup ทุกคืน 02:30 ─▶ S3 ส่วนตัว (ถ้าตั้ง bucket)
                         │
                         └─▶ pyannoteAI API / Typhoon API (ขาออก HTTPS)
```

**ขอบเขต:** แบบนี้เป็น **ขั้นทดลองใช้ ไม่ใช่ production** มีเครื่องเดียว (ถ้าเครื่องล่ม ระบบก็หยุด) และประมวลผลเสียงใน process เดียวกับเว็บ PostgreSQL รองรับแล้วผ่าน `DATABASE_URL`; distributed worker และ object storage สำหรับ runtime ยังเป็นแผน ส่วน S3 ในคู่มือนี้ใช้สำรองข้อมูลเท่านั้น

---

## สถานะส่งต่อ Phase 6

วันที่ 17 พฤศจิกายน 2026 ผู้ใช้ยืนยันว่า Phase 6 บน AWS Academy Learner Lab ทำงานด้วย Ubuntu 24.04, PostgreSQL schema v2 และ Caddy/HTTPS; RBAC ผ่าน 6 รายการ, Case Linking/Retry/Audit และ PostgreSQL backup/restore ด้วยข้อมูลทดสอบผ่านแล้ว STT/AI สำเร็จ 6/6 หลัง Retry โดย 2 ไฟล์เคยติด Typhoon connection/timeout ใช้ `AI_API_TIMEOUT=120` แต่คุณภาพ STT/ผู้พูด/AI ยังตรวจรับไม่ครบ ดู [สถานะและประวัติ](../../PROJECT_STATUS.md)

ผลนี้เป็นรายงานผู้ใช้ ไม่ใช่การตรวจ server ซ้ำโดยผู้จัดเอกสาร และไม่ยืนยันว่า server ยัง online ตลอดเวลา ก่อนส่งมอบให้ผู้ดูแลบันทึก release SHA, schema version, ผู้รับผิดชอบ, domain, ที่เก็บ backup และผล restore ผ่านช่องทางภายในที่เหมาะสม ห้ามใส่ credentials หรือข้อมูลลูกค้าใน repo คำสั่งด้านล่างเป็น runbook สำหรับผู้ดูแลที่ได้รับอนุมัติ ไม่ใช่คำสั่งให้ deploy อัตโนมัติ

<a id="lab-startup"></a>

## เปิดใช้งานหลัง Start Lab และ Start EC2 (Elastic IP — 19 พฤศจิกายน 2026)

**สถานะที่ผู้ใช้ยืนยัน:** EC2 ชื่อ `SmartVoice` บน AWS Academy Learner Lab ผูก Elastic IP `44.221.132.254` และใช้ [https://44-221-132-254.sslip.io](https://44-221-132-254.sslip.io) ผู้ใช้แก้ Caddyfile บน EC2 ด้วยมือให้ใช้โดเมนนี้ เปิด HTTPS สำเร็จ และทดสอบ Stop → Start แล้วเปิด URL เดิมได้ ไม่มีการแก้ Source Code/schema หรือ Deploy แอปใหม่ ก่อนทดสอบ Dashboard แสดง 6 สาย วิเคราะห์เสร็จ 6 สาย; ยังไม่ใช่ผลตรวจจำนวนข้อมูลหลัง Start ผู้จัดเอกสารไม่ได้เข้าตรวจ AWS หรือรันคำสั่งบน EC2 ในรอบนี้

ขั้นตอนสำหรับผู้ดูแลที่ได้รับอนุมัติในครั้งถัดไป (ไม่ต้องติดตั้งหรือ migrate ฐานข้อมูลใหม่เพียงเพราะ Start เครื่อง):

1. เปิด AWS Academy Learner Lab กด **Start Lab** และรอพร้อมใช้งาน จากนั้นเปิด AWS Console ของ Lab เลือก region เดิม
2. ไป EC2 → Instances เลือก `SmartVoice` โดยตรวจ Instance ID ให้ตรงกับเครื่องเดิม หากหยุดอยู่ให้กด **Start instance** รอเป็น `Running` และ status checks ผ่าน หากไม่พบเครื่องเดิมให้หยุดและติดต่อผู้ดูแล ไม่สร้างเครื่องหรือฐานข้อมูลทดแทนทันที
3. ตรวจ Elastic IP `44.221.132.254` ว่ายังจัดสรรในบัญชี/region เดิมและ association ชี้ไปเครื่องที่ถูกต้อง หากไม่ตรงให้หยุดวิเคราะห์ก่อน ไม่ release หรือ allocate IP ใหม่เพื่อทดลอง
4. เปิด URL ด้านบน ตรวจว่าเบราว์เซอร์ไม่มีคำเตือน certificate และเข้าสู่หน้า SmartVoice ได้ Login ด้วยบัญชีเดิม ตรวจ Dashboard/รายการสายด้วยตัวกรองเดิม เทียบกับค่าก่อนหยุดเครื่อง (6 สาย วิเคราะห์เสร็จ 6 สายตามรายงานครั้งนี้) บันทึกผลหลัง Start แยกต่างหาก; ไม่กดประมวลผลซ้ำเพียงเพื่อทดสอบว่าเว็บเปิดได้
5. หากเว็บยังไม่พร้อม ให้ผู้ดูแลเข้า EC2 ผ่านช่องทางที่ได้รับอนุมัติและตรวจตามคำสั่งด้านล่างก่อนเปลี่ยน config หรือ restart บริการ ห้ามแสดง `.env`, credentials หรือเผยแพร่ log ที่มีข้อมูลอ่อนไหว

### ตรวจบริการและ HTTPS โดยไม่แก้ config/ข้อมูล

รันบน EC2 Ubuntu เครื่องเดิมโดยผู้ดูแล:

```bash
systemctl status smartvoice caddy postgresql --no-pager
pg_lsclusters
pg_isready -h 127.0.0.1 -p 5432
curl --fail --silent --show-error --max-time 15 http://127.0.0.1:8501/_stcore/health
curl --fail --silent --show-error --max-time 30 https://44-221-132-254.sslip.io/_stcore/health
sudo journalctl -u smartvoice -u caddy -u postgresql -n 50 --no-pager
```

- SmartVoice และ Caddy ควรเป็น `active (running)`; health endpoint ควรตอบ `ok` คำสั่ง HTTPS ไม่ใช้ `-k` เพื่อให้ตรวจ certificate จริง และต้องเปิด URL จากเบราว์เซอร์นอก EC2 ด้วย เพราะการเรียกจากในเครื่องไม่ยืนยันเส้นทางของผู้ใช้ภายนอก
- PostgreSQL บน Ubuntu อาจแสดง service รวมเป็น `active (exited)` ให้ดู cluster ที่ใช้งานจาก `pg_lsclusters` ว่า `online` และ `pg_isready` ว่า `accepting connections` (ปรับ port หากตั้งไว้ต่างจาก 5432) ผลนี้ยืนยันการรับ connection เท่านั้น ไม่ยืนยัน app credentials/schema/ความครบถ้วนของข้อมูล ต้องประกอบกับการ Login และอ่านข้อมูลผ่านแอป
- หากมี error ให้ตรวจ log ของ cluster unit ที่ระบุจากเครื่องจริงเพิ่มเติม หาก localhost health ผ่านแต่ HTTPS ไม่ผ่าน ให้ตรวจโดเมน Caddy, DNS, certificate และการเข้าถึง 80/443; หาก localhost health ไม่ผ่าน ให้เริ่มจาก SmartVoice/PostgreSQL ไม่ควรแก้ DNS หรือ Deploy ใหม่ทันที
- หากบริการหยุดหรือ failed ให้ผู้ดูแลหาสาเหตุก่อนเริ่มบริการตามขั้นตอนที่อนุมัติ ไม่ต้องรัน `install.sh`, migration หรือ restore เพื่อเปิด Lab ตามปกติ

### รักษาโดเมนเมื่อ Deploy รุ่นใหม่

ไฟล์ `/etc/caddy/Caddyfile` บน EC2 ถูกแก้ด้วยมือให้เป็น `44-221-132-254.sslip.io` ตามรายงานผู้ใช้ แต่ `deploy/aws-ec2/install.sh` สร้างไฟล์ใหม่จาก `Caddyfile.template` ด้วยค่า `--domain` แล้วติดตั้งทับไฟล์นี้ การแก้ด้วยมือจึงไม่ใช่ค่าที่ installer จะเก็บไว้ให้อัตโนมัติ

ก่อน Deploy ที่ได้รับอนุมัติ ให้ผู้ดูแลสำรอง config เดิมอย่างปลอดภัย ตรวจ site address และ reverse proxy ใน Caddyfile แล้วตรวจคำสั่ง deploy ที่เตรียมไว้ว่าใช้ `--domain 44-221-132-254.sslip.io` โดยไม่ใส่ `https://` และไม่มี path (หากเปลี่ยนโดเมนภายหลังให้ใช้ค่าที่อนุมัติล่าสุด) อย่านำคำสั่งในประวัติที่มีโดเมนเก่ามารันตรง ๆ หลัง Deploy ต้องตรวจ Caddy และ HTTPS ที่ URL นี้ซ้ำ ขั้นตอนนี้เป็นข้อควรตรวจสำหรับอนาคต ไม่ใช่การสั่ง Deploy ในรอบเอกสารนี้

**ข้อจำกัด:** Elastic IP คงที่ตราบใดที่ยังจัดสรรและผูกกับ EC2 ที่ถูกต้อง ไม่รับประกันว่าบริการหรือทรัพยากรจะอยู่ตลอดไป AWS Academy ไม่รับประกันการคงอยู่ของทรัพยากรระยะยาว; Lab/EC2 ที่หยุดยังทำให้เว็บหยุด แม้ IP ไม่เปลี่ยน และยังพึ่ง DNS ของ sslip.io กับ certificate ที่ใช้ได้ ผล Stop/Start ครั้งนี้ไม่แทน backup/restore, การตรวจคุณภาพ AI หรือ Production readiness คำเตือน IP อาจเปลี่ยนในหัวข้อเตรียม AWS ด้านล่างยังใช้กับกรณีที่ไม่มี Elastic IP หรือการจัดสรร/ผูก IP เปลี่ยนไป

## 0. ก่อนเริ่ม — ต้องตัดสินใจ/เตรียมให้เรียบร้อย

| เรื่อง | ทำไมต้องรู้ก่อน |
|---|---|
| **ข้อมูลที่จะใช้ทดลอง** | ถ้าใช้เสียงสายจริงของลูกค้า ต้องได้รับอนุมัติให้ส่งเสียงไป pyannoteAI และข้อความไป Typhoon (PDPA / เงื่อนไขผู้ให้บริการ) ถ้ายังไม่ได้ ให้ใช้โหมดสาธิต (ข้อ 7) |
| **บัญชี AWS** | AWS Academy Learner Lab เหมาะกับการซ้อมติดตั้งเท่านั้น: session มีเวลาจำกัดและเครื่องจะหยุดเมื่อหมด session, IP อาจเปลี่ยน, สิทธิ์ IAM และงบจำกัด และเป็นบัญชีเพื่อการศึกษา — ถ้าจะให้ตัวแทนบริษัทเข้าใช้ต่อเนื่อง ควรใช้บัญชี AWS ปกติ **ห้ามใส่ข้อมูลลูกค้าจริงใน Learner Lab** |
| **ชื่อโดเมน** | HTTPS ต้องใช้ชื่อ DNS ที่ชี้มาที่เครื่อง เช่น `smartvoice.<โดเมนบริษัท>` ถ้ายังไม่มี ใช้ชื่อจาก sslip.io ได้ชั่วคราว (เช่น IP `203.0.113.10` → `203-0-113-10.sslip.io`) แต่อาจติดโควตาออกใบรับรองของ Let's Encrypt |
| **API key + เครดิต** | pyannoteAI และ Typhoon ทุกสายที่ประมวลผลมีค่าใช้จ่าย ควรทดสอบสายจริง 1 สายให้ผ่านก่อนเปิดให้บริษัทใช้ |

---

## 1. สร้าง EC2

| ค่า | แนะนำ |
|---|---|
| AMI | **Ubuntu Server 24.04 LTS** (มี Python 3.12 ซึ่งแอปรองรับ 3.10–3.12) |
| ขนาด | `t3.small` (2 GB RAM) สำหรับผู้ใช้ไม่กี่คน, `t3.medium` ถ้าอัปโหลด/ประมวลผลพร้อมกันหลายไฟล์ — ไม่ต้องมี GPU |
| ดิสก์ | gp3 30 GB ขึ้นไป **เปิด Encryption** (ไฟล์เสียงใช้พื้นที่มากที่สุด) |
| Security group ขาเข้า | `443/tcp` และ `80/tcp` จาก `0.0.0.0/0` (80 ใช้ขอใบรับรองและ redirect ไป HTTPS) · `22/tcp` **เฉพาะ IP ของผู้ดูแล** · ห้ามเปิด `8501` |
| Elastic IP | ผูกให้เครื่อง เพื่อให้ IP/DNS ไม่เปลี่ยนเมื่อ stop/start |
| IAM role (ถ้าจะ backup ไป S3) | role ที่เขียนได้เฉพาะ bucket ของ SmartVoice (ใน Learner Lab ใช้ `LabInstanceProfile`) |

ตั้ง DNS record `A` ของโดเมนให้ชี้ไปที่ Elastic IP แล้วรอให้ resolve ได้ก่อนข้อ 3 (Caddy ต้องใช้ขอใบรับรอง)

**S3 bucket สำหรับ backup (แนะนำ):** สร้าง bucket ใหม่ใน region เดียวกัน เปิด **Block all public access**, เปิด default encryption และ versioning

---

## 2. นำโค้ดขึ้นเครื่อง

repository เป็น private — เลือกวิธีใดวิธีหนึ่ง (ห้ามใส่ GitHub token ลงในเครื่องแบบถาวร):

```bash
# บนเครื่องของผู้ดูแล: ทำไฟล์ zip จาก commit ที่ต้องการ (ไม่รวม .env, data/)
git archive --format=tar.gz -o smartvoice.tar.gz HEAD
scp -i <key.pem> smartvoice.tar.gz ubuntu@<domain>:~
```

```bash
# บน EC2
mkdir -p ~/smartvoice-src && tar -xzf ~/smartvoice.tar.gz -C ~/smartvoice-src
```

(อีกวิธี: GitHub deploy key แบบ read-only แล้ว `git clone`)

**ห้ามคัดลอก** `.env`, `data/`, ไฟล์เสียง หรือฐานข้อมูลจากเครื่อง local ขึ้นไปเว้นแต่ได้รับอนุมัติให้ย้ายข้อมูลจริง

---

## 3. ติดตั้ง

```bash
cd ~/smartvoice-src
sudo bash deploy/aws-ec2/install.sh --domain <domain> --s3-bucket <bucket>   # --s3-bucket ไม่บังคับ
```

สคริปต์จะ:
- ติดตั้ง Python venv, ฟอนต์ไทย (สำหรับรายงาน PDF), Caddy และ AWS CLI (เมื่อระบุ bucket)
- คัดลอกโค้ดไป `/opt/smartvoice/app` และสร้าง venv ที่ `/opt/smartvoice/venv`
- **ติดตั้งครั้งแรก:** สร้าง `.env` พร้อม `SMARTVOICE_BOOTSTRAP_PASSWORD` แบบสุ่ม แล้ว **แสดงรหัสนี้ครั้งเดียว** — ระบบบน server จะไม่ใช้ `admin1234`
- หากมี `.env` เดิม ต้องกำหนด `SMARTVOICE_BOOTSTRAP_PASSWORD` ที่ยาวอย่างน้อย 8 ตัวอักษรและไม่ใช่ `admin1234` สคริปต์จะหยุดก่อนเริ่ม service หากไม่มีค่า เป็นค่าว่าง หรือไม่ผ่านเงื่อนไข โดยไม่เขียนทับค่าเดิม ผู้ดูแลต้องตั้งค่าในไฟล์บน server แล้วรันติดตั้งอีกครั้ง การตั้งค่านี้ไม่เปลี่ยนรหัสของบัญชีที่มีอยู่ในฐานข้อมูล
- เปิด service `smartvoice`, ตั้ง backup ทุกคืน และตั้ง HTTPS ผ่าน Caddy

ตรวจสถานะ:

```bash
systemctl status smartvoice caddy
journalctl -u smartvoice -f
```

---

## 4. เข้าใช้งานครั้งแรก

1. เปิด `https://<domain>` → ล็อกอิน `admin` ด้วยรหัสที่สคริปต์แสดง
2. **เปลี่ยนรหัสผ่านทันที** (กล่องบัญชีใน sidebar → เปลี่ยนรหัสผ่าน) — ระบบเตือนจนกว่าจะเปลี่ยน
3. หน้า **ตั้งค่าระบบ** → ใส่ `PYANNOTE_API_KEY`, `TYPHOON_API_KEY` → บันทึก → `sudo systemctl restart smartvoice`
4. ดูหน้าแรก (ส่วนตรวจความพร้อมของผู้ดูแล) ว่าไม่มีข้อผิดพลาด — การตรวจนี้ดูแค่ว่ามี key ยังไม่ยืนยันเครดิต
5. อัปโหลดเสียงทดสอบที่ได้รับอนุญาต **1 สาย** แล้วตรวจผลถอดเสียง/ผู้พูด/สรุป/คะแนน ก่อนเปิดให้คนอื่นใช้

## 5. สร้างบัญชีให้ตัวแทนบริษัท

หน้า **จัดการผู้ใช้** → เพิ่มบัญชีทีละคน เลือกบทบาทตามที่จะให้เห็น (`Agent` / `QA` / `Supervisor`; ให้ `Admin` เฉพาะผู้ดูแลระบบ) ส่งรหัสเริ่มต้นผ่านช่องทางที่ปลอดภัยและให้แต่ละคนเปลี่ยนเอง — ระบบไม่มีปุ่มรีเซ็ตรหัสโดย Admin (ตามนโยบาย) ถ้าลืมรหัสให้ปิดใช้งานบัญชีเดิมแล้วสร้างบัญชีใหม่ด้วยชื่อผู้ใช้อื่น

**การกันเดารหัสผ่าน:** ใส่ผิด 5 ครั้งต่อบัญชีจะล็อกบัญชีนั้น 60 วินาที และผิด 20 ครั้งจาก IP เดียวจะล็อก IP นั้น 5 นาที (ทั้งสำนักงานที่ใช้ IP เดียวกันจะโดนด้วย) นับรวมทุกแท็บ/ทุกเบราว์เซอร์ ตัวนับอยู่ในหน่วยความจำ — รีสตาร์ท service แล้วนับใหม่

## 6. Backup และกู้คืน (เลือกให้ตรง Backend)

- ทุกคืน 02:30 (เวลาไทย) `smartvoice-backup.timer` สำรองไว้ใน `data/backups/`: SQLite เป็น `.db` ที่ตรวจ `integrity_check`; PostgreSQL เป็น custom `.dump` ที่ตรวจ archive listing (เก็บ 14 ชุดล่าสุด) และถ้าตั้ง bucket ไว้จะ sync snapshot + ไฟล์เสียง + หลักฐานไป `s3://<bucket>/smartvoice/` (เข้ารหัส SSE; ไม่ลบของใน S3)
- สั่ง backup ทันที: `sudo systemctl start smartvoice-backup && journalctl -u smartvoice-backup -n 20`
- ตั้ง EBS snapshot รายวัน (AWS Backup / Data Lifecycle Manager) เป็นอีกชั้นหนึ่ง

**กู้คืน SQLite เท่านั้น** (หากตั้ง `DATABASE_URL` ให้ใช้หัวข้อ PostgreSQL Restore ด้านล่าง ห้ามใช้การคัดลอก `.db` แทน PostgreSQL restore):

```bash
sudo systemctl stop smartvoice
sudo -u smartvoice cp /opt/smartvoice/app/data/smartvoice.db /opt/smartvoice/app/data/smartvoice.db.before-restore
sudo -u smartvoice cp /opt/smartvoice/app/data/backups/smartvoice-<เวลา>.db /opt/smartvoice/app/data/smartvoice.db
sudo systemctl start smartvoice
```

(จาก S3: `aws s3 cp s3://<bucket>/smartvoice/backups/smartvoice-<เวลา>.db /tmp/` แล้วคัดลอกแบบเดียวกัน) ข้อมูลที่เกิดหลัง snapshot นั้นจะหายไป และงานที่ส่งให้ API ไปแล้วไม่ย้อนกลับ

## 7. โหมดสาธิต (ยังไม่มีอนุมัติใช้เสียงจริง)

หน้าตั้งค่าระบบ → **โหมดสาธิต** (`MOCK_STT=true`) ใช้บทสนทนาตัวอย่างแทนการถอดเสียง แต่การกดประมวลผลยังเรียก Typhoon และมีค่าใช้จ่าย สำหรับการนำเสนอให้เปิดชุดข้อมูลสาธิตในเครื่องตาม [คู่มือเปิดเดโม](../../README.md#เปิดเดโม-omazz-ในเครื่อง) ซึ่งใช้ฐานแยกจาก EC2

## 8. อัปเดตเวอร์ชัน

นำโค้ดใหม่ขึ้นเครื่อง (ข้อ 2) ในโฟลเดอร์แยกจาก `/opt/smartvoice/app` แล้วรัน `install.sh` คำสั่งเดิมซ้ำ โดยหยุดรับงานและรอ processing จบก่อน สคริปต์ล็อกไม่ให้ติดตั้งซ้อน ตรวจ prerequisites/config เดิม เตรียมโค้ดและ venv ใหม่ใน `/opt/smartvoice/releases/release-XXXXXXXX` และตรวจ PostgreSQL/Caddy ก่อนเปลี่ยนรุ่น `data/` และ `.env` เดิมไม่ถูกคัดลอกหรือเขียนทับ

ก่อนเปลี่ยนโค้ดจริงจะหยุด app และ backup ทั้ง service/timer เก็บสำเนาโค้ดและ config เดิมใน `previous/` ของ release ใหม่ แล้วสลับ `/opt/smartvoice/venv` ไป venv ที่เตรียมไว้ ตรวจ HTTP health ก่อนเปิด backup timer หากล้มเหลวหลังเริ่มเปลี่ยนรุ่น จะพยายามคืนโค้ด/venv/config เดิมและคงบริการหยุดไว้ หากคืนไม่สำเร็จจะแจ้ง `Rollback incomplete` พร้อมที่เก็บสำเนา ไม่ย้อนฐานข้อมูลหรือ `.env` อัตโนมัติ

หากข้อความระบุว่าคืนรุ่นเดิมสำเร็จ ให้ตรวจ config/ฐานข้อมูลว่าตรงกับรุ่นเดิมก่อน แล้วจึง `sudo systemctl restart caddy smartvoice` และ `sudo systemctl start smartvoice-backup.timer` หาก process ถูก kill หรือเครื่องดับระหว่างติดตั้งจน trap ทำงานไม่ได้ ให้คงบริการหยุด สำรองสถานะปัจจุบัน แล้วให้ผู้ดูแลคืนโค้ดจาก `previous/app` โดย exclude `data/`, `.env`, `.env.*` คืน venv จาก `previous/venv` และ config จาก `previous/config` ก่อนเริ่มบริการ ห้ามลบ release directories ที่ venv ปัจจุบันหรือสำเนารุ่นก่อนยังอ้างถึง ตรวจพื้นที่ว่างและจัดการรุ่นเก่าหลังยืนยันการกู้คืนแล้วเท่านั้น การคืนรุ่นไม่ย้อน apt packages ที่ติดตั้งระหว่างเตรียมเครื่อง

การคัดลอกกำหนดเจ้าของไฟล์โค้ดเป็น root ผ่าน `rsync` โดยไม่เปลี่ยนเจ้าของไฟล์หรือโฟลเดอร์ย่อยใน `data/` เดิม หากเคยอัปเดตด้วยสคริปต์รุ่นที่เปลี่ยนเจ้าของข้อมูลเป็น root แล้ว ต้องตรวจและแก้ ownership ของ runtime data แยกต่างหากก่อนเปิดบริการ

## 9. สิ่งที่ระบบนี้ยังไม่มี (รู้ไว้ก่อนเปิดให้ใช้)

- เครื่องเดียว: ไม่มี failover ถ้า EC2 หยุด ระบบหยุด
- งานประมวลผลอยู่ใน process ของเว็บ: รีสตาร์ท = งานที่กำลังทำหยุด
- log ของแอป (`journalctl -u smartvoice`, `data/logs/`) ไม่บันทึกคำพูดลูกค้าจากคำตอบ AI แล้ว แต่ `calls.error_msg` ในฐานข้อมูลยังเก็บ traceback ของสายที่ล้มเหลว (เห็นเฉพาะ Admin/Supervisor)
- การตั้งค่าเก็บใน `.env` บนเครื่อง ยังไม่ใช้ AWS Secrets Manager
- ไม่มี monitoring/alert — อย่างน้อยให้ตั้ง CloudWatch alarm ของ EC2 status check และพื้นที่ดิสก์

## PostgreSQL: เตรียมฐาน ย้ายข้อมูล และกู้คืน

รุ่นนี้เลือก PostgreSQL ผ่าน `DATABASE_URL`; หากไม่กำหนดยังใช้ SQLite ตาม `DB_PATH` การตั้ง URL ไม่ย้ายข้อมูลอัตโนมัติ เว็บตรวจ schema version ก่อนใช้งาน ให้รัน `python -m scripts.migrate_postgres` เพื่อเตรียม schema หรือนำเข้า SQLite

คง IDs, password hashes, soft delete, audit แบบ best-effort, หลาย links ต่อสาย และ transaction รายใบ SO ตามเดิม JSON/วันที่ยังเป็น TEXT และตัวเลขใช้ double precision เพื่อรักษาค่าเดิม ยังไม่เปลี่ยนเงินเป็น NUMERIC เสียง หลักฐานและ speech checkpoints ยังอยู่ใน `data/` ห้ามลบเมื่อย้าย DB

### เตรียม PostgreSQL

เลือก PostgreSQL บน EC2 เดียวกันสำหรับ pilot หรือ RDS ใน private network ตามงบ/region ที่อนุมัติ การเตรียมโค้ดนี้ไม่ได้สร้างทรัพยากรให้ สำหรับ EC2 เดียวกันให้ฟังเฉพาะ localhost และ **ไม่เปิด 5432 ใน Security Group** ตัวอย่างบน Ubuntu 24.04:

```bash
sudo apt-get install postgresql postgresql-client
sudo -u postgres createuser --pwprompt --no-superuser --no-createdb --no-createrole smartvoice
sudo -u postgres createdb --owner=smartvoice --encoding=UTF8 --template=template0 smartvoice
```

กรอกรหัสผ่านเมื่อถูกถาม ไม่ใส่ใน command history ให้ผู้ดูแลตั้ง `DATABASE_URL` ใน `/opt/smartvoice/app/.env` เช่น `postgresql://smartvoice:<URL-encoded-password>@127.0.0.1:5432/smartvoice` โดยคงสิทธิ์ 0600 ของ smartvoice ไม่แสดง URL ที่มีรหัสในรายงาน สำหรับ RDS ให้ใช้ `sslmode=verify-full` และ `sslrootcert` ของ AWS พร้อมจำกัด inbound จาก app เท่านั้น

`pg_dump` ต้องมี major version เท่ากับหรือใหม่กว่า server; installer ติดตั้ง client ของ Ubuntu ซึ่งอาจเก่ากว่า RDS ที่เลือก ตรวจ `pg_dump --version` และเวอร์ชัน server ก่อนเปิด backup timer

### อัปเกรด PostgreSQL v1 → v2 (Phase 6)

ไม่ต้องนำเข้า SQLite ซ้ำ หยุดรับงาน รอ processing จบ สำรอง DB และไฟล์ runtime พร้อมเก็บ config เดิมอย่างปลอดภัย แล้วหยุด app/backup timer/service ตามขั้น cutover ด้านล่าง จาก release ที่เตรียมไว้ รัน `python -m scripts.migrate_postgres` เพื่อตรวจโหมด dry-run แล้ว `python -m scripts.migrate_postgres --apply` ด้วยผู้ใช้ smartvoice และ interpreter ของ release นั้น คำสั่งอ่าน `DATABASE_URL` จาก `.env`; อย่าวาง URL ที่มีรหัสใน command history

ตรวจ `SELECT version FROM smartvoice_schema_version;` ต้องได้ `2` แล้วรัน installer ซ้ำและตรวจ Login/RBAC, Case Linking/Retry/Audit, จำนวนข้อมูล และ backup/restore ในฐานแยกก่อนเปิดใช้งาน ไม่มี down migration อัตโนมัติ; หากจะ rollback ให้จับคู่ code/schema/config และ reconcile write ใหม่ตามหัวข้อ restore ไม่สลับโค้ดเก่ากับ schema ใหม่โดยไม่ตรวจ

### Cutover จาก SQLite

1. ซ้อมด้วยข้อมูลสังเคราะห์ก่อน บันทึกเวอร์ชันโค้ด/config และ path ข้อมูล หยุดรับ uploads รอ processing จบ แล้วหยุด `smartvoice`, `smartvoice-backup.timer`, `smartvoice-backup.service`
2. สำรอง SQLite ด้วย `scripts/backup_db.py --db <ฐานเดิม> --out <โฟลเดอร์สำรองแยก>` พร้อมสำรองไฟล์ `data/`/checkpoints และเก็บ `.env` อย่างปลอดภัยแยกจากรายงาน ตรวจ backup อ่านได้จริงก่อนเปลี่ยน URL
3. เตรียมโค้ดและ venv ด้วย installer รุ่นนี้ เมื่อตั้ง `DATABASE_URL` แล้วแต่ schema ยังไม่พร้อม installer จะหยุดก่อนสลับรุ่น โดยแสดง `Prepared release` ให้ดำเนิน migration จาก `<prepared-release>/app` ด้วย `<prepared-release>/venv/bin/python` แล้วรัน installer ซ้ำ ห้ามข้ามการตรวจ โฟลเดอร์นี้มี symlink ไป `.env` เดิมโดยไม่คัดลอก secrets
4. เลือกนำเข้า SQLite snapshot ไป PostgreSQL **ว่างเท่านั้น** หรือเริ่มฐานใหม่ว่าง รันคำสั่งใน `<prepared-release>/app` ด้วยผู้ใช้ smartvoice ที่อ่าน `.env` ได้ และแทน interpreter ด้านล่างด้วย `<prepared-release>/venv/bin/python` หากยังไม่ได้สลับรุ่น:

```bash
/opt/smartvoice/venv/bin/python -m scripts.migrate_postgres --sqlite <sqlite-snapshot.db>
/opt/smartvoice/venv/bin/python -m scripts.migrate_postgres --sqlite <sqlite-snapshot.db> --apply

# หากต้องการเริ่มใหม่โดยไม่ย้ายข้อมูล ให้ใช้คำสั่งนี้แทนสองคำสั่งข้างบน
/opt/smartvoice/venv/bin/python -m scripts.migrate_postgres --apply
```

ไม่มี `--apply` เป็น dry-run และไม่เขียน PostgreSQL เครื่องมือเปิด SQLite read-only ตรวจ integrity/FKs นำเข้าทั้ง 9 ตารางใน transaction เดียว รักษา IDs ตั้ง sequences ใหม่ และเทียบ row digests ก่อน commit ปฏิเสธปลายทางที่มีข้อมูล ถ้า source schema เก่าหรือผิดเงื่อนไข ให้ตรวจบนสำเนา ไม่แก้ฐานจริงเพื่อให้ผ่าน

5. ตรวจ row counts, บัญชี/สิทธิ์, รับเคส, SO, soft delete/restore และการเปิดไฟล์เสียง/หลักฐานจาก path เดิม การย้าย DB ไม่ย้ายไฟล์หรือแก้ absolute paths ให้อัตโนมัติ
6. รัน installer ซ้ำ เปิด service และทดสอบ backup ทันที สคริปต์อ่าน `DATABASE_URL` จาก `.env` และใช้ `pg_dump` เป็น `.dump` แบบ custom format โดยไม่ส่งรหัสผ่านใน command arguments ตรวจ archive listing ก่อนเผยชื่อสุดท้าย การตรวจ listing ไม่แทน restore drill
7. เปิด timer หลัง backup/restore ผ่านแล้ว ใช้ app process เดียวต่อไป เพราะตัวนับ login และ processing threads ยังไม่แชร์ข้ามเครื่อง

### Restore และ rollback

กู้ `.dump` ไปฐานใหม่ว่างด้วย `pg_restore --exit-on-error --no-owner --no-acl --dbname <ฐานใหม่> <snapshot.dump>` กำหนด host/user และรหัสผ่านผ่าน prompt หรือ `PGPASSFILE` สิทธิ์ 0600 ตรวจ schema version, row counts, สิทธิ์และไฟล์ก่อนเปลี่ยน URL ห้าม restore ทับฐานที่มีข้อมูลเพื่อทดลอง

หากยังไม่มี write ใหม่หลัง cutover ให้หยุด service แล้วกลับ SQLite snapshot พร้อมโค้ด/config ที่จับคู่กันได้ หาก PostgreSQL รับ write ใหม่แล้ว **ห้ามกลับ SQLite เก่าทันที** ต้องสำรองและ reconcile ข้อมูลใหม่ก่อน งาน API ที่ส่งแล้วไม่ย้อนกลับด้วย DB restore

ผลทดสอบในเครื่องไม่รับรอง networking, systemd/Caddy, TLS, IAM, EBS หรือ permissions ของ EC2 จริง ต้องตรวจบนเครื่องเป้าหมายก่อนรับมอบ

## การรับช่วงดูแลและปัญหา API

- แยก Retry สายที่ AI ล้มเหลว (เรียก Typhoon ใหม่ มีค่าใช้จ่าย; STT ใช้ checkpoint ได้เมื่อถูกต้อง) จาก Retry Case Linking (ใช้แผนที่เก็บไว้ ไม่เรียก AI) ห้ามลบ checkpoint เพื่อแก้ timeout โดยไม่ตรวจสถานะงานผู้ให้บริการ
- `AI_API_TIMEOUT=120` วินาทีเป็น timeout ของ request ไม่ใช่ SLA ต่อสาย และ `AI_JOB_TIMEOUT` คุมเวลารอ STT job แยกกัน เมื่อ connection/timeout ให้ตรวจเวลาที่เกิด ชนิด error, เครดิต/สถานะผู้ให้บริการ และ network โดยไม่เผย payload/key แล้วให้ผู้ดูแลตัดสินใจ Retry ไม่ควรวน Retry แบบไม่จำกัด
- เก็บหลักฐานผลแต่ละรายการและเวลาทดสอบพร้อม release SHA; การดู readiness/key หรือ `systemctl status` ไม่แทน live API test, quality acceptance หรือ restore drill
- ก่อน Limited Pilot ต้องมีผู้รับผิดชอบช่วงทดลอง เกณฑ์ตรวจคุณภาพและคนทบทวนผล AI, ขอบเขตผู้ใช้/ปริมาณงาน, งบ API, การแจ้งปัญหา/หยุดรับงาน และ retention ของข้อมูลที่ได้รับอนุมัติ
- ก่อน Production ต้องมีสภาพแวดล้อมที่รับประกันความต่อเนื่องแทน Learner Lab, monitoring/alert, แผน capacity/recovery และ RPO/RTO ที่ทดสอบแล้ว รวมการกู้ไฟล์เสียง/หลักฐาน/checkpoints คู่กับ DB; ผล restore DB ด้วยข้อมูลทดสอบยังไม่ครอบคลุมทั้งหมดนี้

## รายการไฟล์ deployment

| ไฟล์ | หน้าที่ |
|---|---|
| `install.sh` | ติดตั้ง/อัปเดตทั้งหมด (รันด้วย root) |
| `smartvoice.service` | systemd service ของเว็บแอป — ฟังเฉพาะ 127.0.0.1, เขียนได้เฉพาะ `data/` และ `.env` |
| `Caddyfile.template` | HTTPS reverse proxy (`__DOMAIN__` ถูกแทนตอนติดตั้ง) |
| `backup.sh`, `smartvoice-backup.service`, `smartvoice-backup.timer` | backup ทุกคืนผ่าน `scripts/backup_db.py` แล้ว sync ไป S3 |
