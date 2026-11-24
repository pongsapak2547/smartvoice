# SmartVoice — สถานะสำหรับพัฒนาต่อ

## AWS Academy EC2 — Deploy และตรวจรับหลังอัปเดต (24 พฤศจิกายน 2026)

**สถานะ: Deployment completed; functional validation partially completed; ไม่ใช่ Production Ready.** ข้อมูลส่วนนี้บันทึกจากคำสั่ง Terminal และภาพหน้าจอที่ผู้ใช้ส่งในการสนทนา ไม่ใช่การรันตรวจสอบ AWS โดยตัวแก้เอกสารโดยตรง

- **Source/Deployment:** ผู้ใช้ยืนยัน local branch `test/phase6-e2e` clean ที่ commit `2480e5f` (`fix: enable case claiming for all roles and improve form UX`) และสร้าง `git archive` จาก commit นี้ ส่งขึ้น EC2 โดย SHA256 ฝั่ง Windows/EC2 ตรงกัน `db672382a6d2b13fa34422e67967f7323ec47b824b100d1d75ca35367fd1c7bf`. ติดตั้งด้วย `sudo bash /home/ubuntu/smartvoice-src/deploy/aws-ec2/install.sh --domain 44-221-132-254.sslip.io`; installer จบโดยไม่มี error ใน log ที่ส่งมา; release ใหม่ `/opt/smartvoice/releases/release-GXEX1Hi9`; `/opt/smartvoice/venv` ชี้ไปที่ release นี้
- **Infrastructure post-deploy:** `smartvoice`, `caddy`, `postgresql` และ `smartvoice-backup.timer` active; health `http://127.0.0.1:8501/_stcore/health` และ `https://44-221-132-254.sslip.io/_stcore/health` ตอบ `ok`; `journalctl -u smartvoice.service -n 30 -p err` ไม่พบรายการในช่วงที่ตรวจ ไม่เท่ากับรับรองว่าไม่มีปัญหาทั้งระบบ
- **Backup ก่อน Deploy:** PostgreSQL dump `smartvoice-20261123T162003Z.dump` ตรวจ `pg_restore --list` อ่านได้ (ไม่ได้ทดสอบ restore รอบนี้); archive ที่รวม dump กับ `data/raw_audio` ถูกดาวน์โหลดไป Windows และ SHA256 ทั้งสองฝั่งตรงกัน `aa9dd3389b0df2cf33007685a185f92df13de41570233aece68ac2fd2272bb9e`. ไม่ได้ commit/upload backup หรือข้อมูลลูกค้าเข้า GitHub; `S3_BUCKET` ยังไม่ได้ตั้งค่า และ backup ประจำเครื่องไม่ใช่ off-instance backup. ไฟล์พิเศษบน EC2 `scripts/seed_mock_business_data.py` ไม่มีใน release ใหม่ จึงเก็บสำเนา `/home/ubuntu/seed_mock_business_data.py.predeploy-20261123` พร้อม SHA256 ตรงกับต้นฉบับก่อนติดตั้ง (สำเนานี้ยังอยู่บน EC2)
- **Functional UI ที่ผู้ใช้ทดสอบหลัง Deploy:** Admin login, หน้า Users แสดงบัญชีเดิม และเลือก Role แล้วรายการสิทธิ์เปลี่ยนตามที่เลือก; Agent `agtest` รับ MOCK Case #15, QA `qatest` รับ #17, Supervisor `sptest` รับ #14, Admin รับ #16 สำเร็จ โดย UI แสดงข้อความยืนยันและชื่อผู้รับ; QA และ Admin เห็นว่า Case #15 มี `agtest` รับอยู่แล้ว และ UI ไม่แสดงปุ่มรับซ้ำ. เป็นหลักฐานการทำงานผ่านเว็บ ไม่ใช่การทดสอบ backend concurrency, transactional persistence หรือ security bypass โดยตรง
- **ยังไม่ทดสอบ / เลื่อนออกไป:** STT/AI end-to-end หลัง Deploy (ผู้ใช้เลือกเลื่อน), ความถูกต้อง Transcript/diarization/AI, การสร้างบัญชีจริง, การ restore ฐานข้อมูลรอบนี้, case-claim concurrency และการทดสอบโหลด; ต้องทำก่อนรับรอง Production
- **ขอบเขต:** AWS Academy Learner Lab ใช้สำหรับ Technical Pilot เท่านั้น; หลีกเลี่ยงข้อมูลลูกค้าจริง; ตรวจ Security/Secrets, backup/restore และการคงอยู่ของทรัพยากรก่อนใช้งานบริษัทจริง. Repository GitHub ณ รอบตรวจล่าสุดมี visibility เป็น **Public** แม้เอกสารประวัติเก่าเคยระบุ Private: ต้องตรวจ/เปลี่ยนเป็น Private ตามนโยบายโปรเจ็กต์ก่อนเผยแพร่ข้อมูลภายใน
- **Git handoff:** บันทึกรอบนี้แก้เฉพาะ `PROJECT_STATUS.md` บน branch `test/phase6-e2e` หลัง Deploy commit `2480e5f`; ไม่มีการแก้ application code, push deployment ใหม่ หรือ merge เข้า `master`. หลังจากนี้ local checkout ต้อง `git pull --ff-only` บน branch เดิมก่อนทำงานต่อ หากไม่มี local edits


## หลังการนำเสนอ (23 พฤศจิกายน 2026)

- ทั้ง 4 บทบาทที่มีสิทธิ์เปิดหน้าเคสรับเคสว่างที่ยังไม่ปิดได้ ระบบเก็บชื่อบัญชี ชื่อผู้รับ และเวลารับ โดยคงสถานะเคสเดิม
- ปรับคำอธิบายภาษาไทยในฟอร์มและตัวกรองให้ตรงกับกฎเดิม รวมถึงรูปแบบเบอร์โทร เลขทะเบียน เลขที่ SO และขนาดไฟล์เสียง
- ทดสอบเฉพาะส่วนที่เกี่ยวข้องผ่าน 309 กรณีบน SQLite ทดสอบและ API จำลอง รวมการกดรับผ่าน UI ทุกบทบาท การเพิกถอนสิทธิ์ การรับพร้อมกัน และการส่งฟอร์มด้วยค่าที่ถูกและผิด

## Omazz — เตรียมเดโมในเครื่อง (20 พฤศจิกายน 2026)

- ฐาน Git `test/phase6-e2e` ที่ `ae28f3c` พร้อม staged cleanup เดิม (baseline 739 passed, 17 skipped) รุ่นเสนออนุมัติยังไม่มี commit SHA
- AI: คงการแบ่ง chunk สองรอบและ fallback เดิม เพิ่มการตรวจว่าคำตอบตัดคำทั้งคำตรงกลางประโยค regression แสดงว่าคำสั้นที่หายไประหว่างคำอื่นเคยผ่านได้ `correct_speakers()` ยังรับทั้งสาย ไม่มีการเรียก API จริง
- Customer/Case: เบอร์สายที่ไม่มีลูกค้าตรงกันยังเป็น `not_required` Admin/Supervisor เชื่อมสายที่วิเคราะห์แล้วกับลูกค้า/ทะเบียนและเลือกเคสเดิมหรือสร้างใหม่ได้ในหน้า Admin บันทึกแผนพร้อมลิงก์ใน transaction และใช้การจัดเคสที่ตรวจสิทธิ์/บันทึก audit เดิม การกดซ้ำใช้ลิงก์เดิม มี tests สำหรับเป้าหมายข้ามลูกค้า
- เดโม: `scripts/seed_mock_data.py` สร้าง SQLite แยกด้วยบัญชี 4 roles, 2 ลูกค้า, 2 ทะเบียน, 3 สาย, 2 เคส และ 2 SO พร้อมสินค้า ทดสอบ seed ซ้ำและ reset ฐานที่มีเครื่องหมายเดโม ทดสอบ login/logout และจำนวนหน้าตามสิทธิ์ทั้ง 4 roles พร้อมเปิดหน้าแอปด้วยสิทธิ์ Admin ผ่าน Streamlit AppTest วิธีเปิดอยู่ใน README
- Export: PDF เดิมเพิ่มข้อค้นพบ สมมติฐาน ข้อเสนอ แผนกและ KPI ที่คำนวณจากสายภายใต้ตัวกรอง ไม่มี API เพิ่ม ตรวจ PDF ภาษาไทยที่เรนเดอร์ทั้ง 2 หน้าจากข้อมูลสาธิต และสร้าง CSV ทั้งสองชนิด เพิ่มการป้องกันข้อความสูตรที่มี whitespace นำหน้าหรือขึ้นต้นคล้ายจำนวนลบ
- ไฟล์งาน: config, ollama_client, pipeline และ tests ของ cleanup/processing เดิม; db และหน้า Admin; seed และ test_demo_seed; dashboard_report และ tests; test_case_linking/UI; README, CLAUDE, AWS runbook และ PROJECT_STATUS
- Full suite รอบสุดท้ายบน Python 3.11.9, SQLite ทดสอบ, API จำลอง, Git Bash และ `TYPHOON_MAX_TOKENS=8192` ผ่าน 750 ล้มเหลว 0 ข้าม 17 ใน 71.61 วินาที (ไม่มีฐาน PostgreSQL ทดสอบแยก) รวมเส้นทางเสียงสังเคราะห์ถึง Dashboard และ AppTest ผ่าน router จริง 13 หน้าด้วย Admin การทดสอบนี้ไม่ได้วัด latency/โหลดบน EC2
- สถานะ: พร้อมสาธิตในเครื่องด้วยข้อมูลจำลอง ส่วนการรับรอง production และสาธิตสายจริงยังรอ PostgreSQL, Typhoon และ AWS ตรวจรับแยก งานรอบนี้ไม่มี commit/push/deploy
- AWS: ผู้ใช้รายงานรุ่นเดิมสำเร็จ 8/10 หลัง Retry และ 14 สาย done ไม่มีลิงก์ลูกค้าหรือเคส รอบนี้ยังไม่ได้ตรวจ AWS, PostgreSQL schema v2 บนเครื่องเป้าหมาย, live AI หรือผลของ Call 8/13 ไม่มี migration หรือการเปลี่ยน installer/Caddy
- ก่อนอนุมัติ AWS: ระบุ SHA ทั้งรุ่นเดิมและรุ่นที่จะติดตั้ง ตรวจ backup/ไฟล์ประกอบและ Caddyfile ปัจจุบัน รอคิวว่าง ติดตั้งจาก clean checkout ตาม runbook ด้วย `--domain 44-221-132-254.sslip.io` ตรวจ HTTPS และ login ก่อนทดสอบสายที่ได้รับอนุญาต หากต้องคืนรุ่นให้ใช้ previous ของ release นั้นตาม runbook และตรวจ backend/config ก่อนเริ่ม service

## Transcript Cleanup — แก้กรณีข้อความสั้นหาย (20 พฤศจิกายน 2026)

- ตรวจและแก้บน branch `test/phase6-e2e` ฐาน `ae28f3c` เดิมข้อความสั้นกว่า 80 อักขระผ่านได้เพียงตอบรูปแบบถูกต้อง Regression test ยืนยันว่ากรณี 28 เหลือ 6 อักขระเก็บต้นฉบับทั้ง chunk แล้ว รวมถึงเมื่อคำตอบตัดคำปฏิเสธที่ตรวจจับหรือเปลี่ยนกลุ่มตัวเลข ทดสอบผ่านทั้งการแก้คำสะกดและลบป้ายเสียงรบกวนที่พบในต้นฉบับ
- Warning ของ cleanup ระบุ `call_id`, `cleanup_pass` และ `chunk_index` โดยไม่พิมพ์คำพูดหรือผลตอบกลับ ทดสอบว่า pipeline ส่งบริบททั้งสองรอบ และการใช้ต้นฉบับแทนคำตอบที่ถูกตัดยังคงลำดับกับ metadata
- ผลในเครื่อง Python 3.11.9, SQLite ทดสอบ, API จำลอง, Git Bash และ `TYPHOON_MAX_TOKENS=8192` ชุด cleanup ผ่าน 20 กรณี ชุด regression ที่รวม cleanup ผ่าน 92 กรณี ชุดเต็มผ่าน 739 ล้มเหลว 0 ข้าม 17 เพราะไม่มี PostgreSQL ทดสอบแยก ใช้เวลา 68.91 วินาที
- `correct_speakers()` ยังคงส่งบทสนทนาทั้งสายในคำขอเดียว ยังไม่มีผลทดสอบรุ่นนี้กับ Call ID 8 และ 13 ผ่าน Typhoon จริง และยังไม่มีการ deploy รุ่นนี้

## Typhoon transcript cleanup — ผลตรวจในเครื่อง (19 พฤศจิกายน 2026)

- ตรวจโค้ดที่ฐาน `ae28f3c` พบว่า cleanup ทั้งสองรอบส่งทุก segment ในคำขอเดียว ค่า `TYPHOON_MAX_TOKENS` ถูกส่งเป็นเพดานคำตอบ และ `finish_reason=length` ทำให้ pipeline หยุด โค้ดเดิมไม่ได้เก็บจำนวน token ของคำขอ
- Working tree แบ่งข้อความที่มี index และ speaker เป็นชุดตาม `TYPHOON_CLEANUP_CHUNK_CHARS` (ค่าเริ่มต้น 3,200 อักขระ รวมป้ายและตัวคั่น ไม่รวม prompt คงที่) และจำกัดจำนวนอักขระนี้ด้วยค่าตัวเลขของ `TYPHOON_MAX_TOKENS` อีกชั้น ตัวเลขอักขระเป็นเพียงงบประมาณโดยประมาณ จำนวน token ที่บันทึกมาจาก `usage.prompt_tokens` และ `usage.completion_tokens` เมื่อ API ส่งมา
- ทดสอบกับบทสนทนาสังเคราะห์แล้วว่า cleanup รวมข้อความกลับตามตำแหน่งเดิม รักษา speaker, timestamp และช่องว่างระหว่างช่วงที่แยก หากคำตอบถูกตัดหรือรูปแบบผิด จะคงต้นฉบับเฉพาะชุดนั้นและไปต่อโดยไม่ส่งซ้ำ ข้อความยาวเกินเพดานที่ไม่มีจุดแบ่งด้วยช่องว่างจะเก็บตามต้นฉบับ
- ผลเฉพาะ cleanup ผ่าน 14 กรณีบน Python 3.11.9 โดยใช้ API จำลอง การตรวจครั้งนี้ไม่มีการเรียก API จริงหรือประมวลผล Call ID 8 และ 13 ซ้ำ
- ชุดเต็ม `tests/` บน working tree ฐาน `ae28f3c` ใช้ SQLite ทดสอบ, API จำลอง และ Git Bash ผ่าน 733, ล้มเหลว 0, ข้าม 17 (ไม่มีฐาน PostgreSQL ทดสอบแยก) ใช้เวลา 68.19 วินาที

## อัปเดตล่าสุด — Elastic IP และ Stop/Start (19 พฤศจิกายน 2026)

**ผลที่ผู้ใช้ยืนยันเท่านั้น — ผู้จัดเอกสารไม่ได้เชื่อมต่อหรือตรวจ AWS ด้วยตนเองในรอบนี้**

- สภาพแวดล้อม: AWS Academy Learner Lab, EC2 Instance ชื่อ `SmartVoice`
- Elastic IP: `44.221.132.254`; URL ปัจจุบัน: [SmartVoice Technical Pilot](https://44-221-132-254.sslip.io)
- ผู้ใช้ตั้งค่า Caddy ให้ใช้โดเมน `44-221-132-254.sslip.io` สำเร็จและเปิด HTTPS ได้ โดยแก้ Caddyfile บน EC2 ด้วยมือ
- ทดสอบ Stop → Start EC2 แล้วกลับมาเปิดเว็บด้วย URL เดิมได้สำเร็จ
- **ก่อนทดสอบ Stop/Start** Dashboard แสดงข้อมูล 6 สาย วิเคราะห์เสร็จ 6 สาย ยังไม่มีผลยืนยันการเทียบข้อมูลทั้ง 6 สายหลัง Start ในรอบนี้ จึงไม่ถือว่าเป็นการตรวจความครบถ้วนของข้อมูลหลังเปิดเครื่องหรือ restore drill
- ผู้ใช้ยืนยันว่าไม่มีการแก้ Source Code, PostgreSQL Schema หรือ Deploy แอปใหม่ในการตั้งค่า Elastic IP ครั้งนี้

Elastic IP เป็นที่อยู่คงที่ตราบใดที่ยังจัดสรรและผูกกับ EC2 ที่ใช้บริการนี้ หากปล่อย IP หรือเปลี่ยนการผูก URL อาจไม่ชี้มาที่ SmartVoice เดิม AWS Academy **ไม่รับประกันการคงอยู่ของทรัพยากรระยะยาว** และ IP คงที่ไม่ได้ทำให้เว็บเปิดได้เมื่อ Lab/EC2 หยุดหรือรับประกัน uptime ระบบยังเป็น Technical Pilot ไม่ใช่ Production

**ก่อน Deploy รุ่นใหม่:** ตรวจโดเมนใน `/etc/caddy/Caddyfile` และค่า `--domain` ที่จะส่งให้ installer ให้ตรงกับ `44-221-132-254.sslip.io` (หรือโดเมนใหม่ที่อนุมัติภายหลัง) เพราะ installer สร้าง Caddyfile จาก template และเขียนทับไฟล์บน EC2 การใช้คำสั่งเก่าที่มีโดเมนเดิมอาจทำให้ URL กลับเป็นค่าเก่า ดู [ขั้นตอนเปิดใช้งานหลัง Start Lab/EC2](deploy/aws-ec2/README.md#lab-startup)

ตรวจ Git ก่อนแก้เอกสาร: branch `test/phase6-e2e`, HEAD `e724d93` (`docs: update SmartVoice Phase 6 pilot and developer handoff`), working tree สะอาด รอบนี้เพิ่มเฉพาะเอกสารสถานะและ runbook; ไม่แก้ `.env`, Source Code, schema หรือข้อมูลเดิม และไม่ Commit/Push/Merge/Deploy ข้อความวันที่ 17 พฤศจิกายนและประวัติ Phase 5/6 ด้านล่างคงไว้เป็นบันทึกเดิม รวมผล tests ณ วันที่ระบุ ไม่ใช่ผล AWS ที่ทดสอบซ้ำในรอบนี้

ผลตรวจ Local รอบเอกสารวันที่ 19 พฤศจิกายน 2026: รัน `tests/` ทั้งชุดด้วย SQLite/mock APIs, ปิด dotenv และใช้ฐานทดสอบแยกตาม README ได้ **709 passed, 27 skipped, 0 failed ใน 91.18 วินาที**; 17 รายการ skip เพราะไม่ได้ตั้ง PostgreSQL ทดสอบ และ 10 รายการเพราะไม่มี Bash ผลนี้ไม่ใช่การตรวจ AWS/HTTPS/PostgreSQL จริงหรือคุณภาพ AI และไม่แทนผล Stop/Start ที่ผู้ใช้ยืนยันข้างต้น

## สถานะล่าสุด — Phase 6 Technical Pilot บน AWS Academy (17 พฤศจิกายน 2026)

**Deploy Phase 6 บน AWS Academy Learner Lab สำเร็จตามผลที่ผู้ใช้ยืนยัน** เป้าหมายถัดไปคือ Limited Pilot สำหรับพนักงานกลุ่มเล็ก แต่ยังไม่รับรองความพร้อม Production หรือคุณภาพ AI ทั้งหมด

### ผลล่าสุดที่ผู้ใช้ยืนยัน (ไม่ได้ตรวจ AWS ซ้ำในรอบส่งต่อ)

- EC2 Ubuntu 24.04, PostgreSQL **schema v2**, Caddy/HTTPS และ SmartVoice ทำงานได้
- Multi-user / RBAC ผ่าน **6 รายการ**; ยังไม่มีรายละเอียดรายข้อแนบในรอบนี้ จึงไม่ขยายผลเป็นการผ่านทุกกรณีหรือ load test
- Case Linking / Retry / Audit ผ่านการทดสอบบน PostgreSQL
- PostgreSQL Backup/Restore ผ่านบน EC2 **ด้วยข้อมูลทดสอบ** ไม่ใช่หลักฐานกู้คืนข้อมูลจริงหรือไฟล์ประกอบทั้งหมด
- STT/AI ประมวลผลครบ **6/6 ไฟล์หลัง Retry** มี 2 ไฟล์เคยล้มเหลวจาก Typhoon API connection/timeout; ไม่ใช่การผ่านครบตั้งแต่ครั้งแรก และไม่ใช่หลักฐานว่าต้นเหตุ timeout หายแล้ว
- ใช้ `AI_API_TIMEOUT=120` วินาที (ตรงกับค่าเริ่มต้นในโค้ดและ `.env.example`); เป็น timeout ของคำขอ API ไม่ใช่เวลารวมสูงสุดต่อสาย
- **ความแม่นยำ STT, Speaker Diarization และ AI Analysis ยังไม่ได้ตรวจรับครบ** การประมวลผลสำเร็จไม่เท่ากับผลวิเคราะห์ถูกต้อง
- AWS Academy เป็น **Technical Pilot ไม่ใช่ Production** สถานะบัญชี Free Tier ที่ถูกระงับด้านล่างเป็นประวัติก่อนเปลี่ยนสภาพแวดล้อม

### จุดเริ่มต้นสำหรับ Developer

ตรวจ Git ในรอบส่งต่อ: branch `test/phase6-e2e`, HEAD `02eacfb` (`docs: update Phase 6 status and AWS blocker`), working tree สะอาดก่อนแก้เอกสาร ไม่ได้ยืนยันว่า HEAD นี้ตรงกับ commit ที่ deploy บน EC2 ให้เจ้าของระบบส่ง release SHA และหลักฐานทดสอบที่ปิดข้อมูลลับผ่านช่องทางที่เหมาะสม

อ่าน [Developer Setup](README.md#developer-setup) และ [คู่มือ Deployment](deploy/aws-ec2/README.md) ก่อนเริ่ม จากนั้นสร้าง branch งานแยกจาก revision ที่ทีมยืนยัน ไม่ใช้คำสั่งในประวัติด้านล่างเป็นคำสั่ง deploy ปัจจุบัน

Architecture ปัจจุบัน: Streamlit → pyannoteAI → Typhoon → `insight_rules` → SQLite หรือ PostgreSQL → Case Linking; `done` หมายถึง AI Analysis สำเร็จ ส่วนสถานะ Case Linking แยกต่างหาก ไฟล์เสียง/หลักฐาน/checkpoints และ background threads ยังอยู่บนเครื่องแอป ไม่ใช่ distributed worker หรือ object storage

### งานค้างตามลำดับก่อนเปิด Limited Pilot

1. ยืนยัน release SHA/schema/config ที่ใช้งานจริง และเก็บหลักฐาน 6 รายการ RBAC, Case Linking/Retry/Audit, backup/restore พร้อมวันที่และขอบเขต; เก็บเหตุผล PostgreSQL test ที่เคย deselected ไว้ด้วย ห้ามแนบ secrets/เสียง/ข้อความลูกค้าใน Git
2. ตรวจรับคุณภาพเสียงและผลวิเคราะห์กับชุดทดสอบที่ได้รับอนุญาต: transcript, ผู้พูด, สรุป, sentiment, QA, next action, anomaly และการเชื่อมเคส กำหนดเกณฑ์ยอมรับและให้คนตรวจผลก่อนนำไปตัดสินผลงานพนักงาน
3. เก็บอัตรา connection/timeout, latency และค่าใช้จ่ายต่อสาย/Retry; ค่า 120 วินาทีไม่แก้ปัญหาเครือข่ายหรือรับประกันความพร้อมผู้ให้บริการ การ Retry ประมวลผล AI เรียก Typhoon ใหม่และมีค่าใช้จ่าย ส่วน Retry Case Linking ใช้แผนเดิม ไม่เรียก AI
4. ทดสอบ regression บน revision ส่งต่อและ PostgreSQL ทดสอบแยก รวม session revalidation, concurrency และ recovery เมื่อรีสตาร์ท; แผน Case Linking missing/invalid/stale ยังต้องตรวจด้วยคน ไม่มี UI ยืนยันแผนใหม่ และ audit เป็น best-effort เมื่อ DB ขัดข้อง
5. ก่อนใช้กับบริษัทให้ตกลงเจ้าของระบบ/ผู้ดูแล, กลุ่มผู้ใช้และปริมาณงาน, การอนุมัติส่งข้อมูลให้ API, retention, งบ/เครดิต, วิธีแจ้งปัญหาและหยุดทดลอง พร้อมซ้อมคืน DB คู่กับไฟล์เสียง/หลักฐาน/checkpoints และกำหนด RPO/RTO

**ข้อจำกัดที่ยังคงอยู่:** Learner Lab ไม่รับประกันบริการต่อเนื่องและห้ามใส่ข้อมูลลูกค้าจริงตาม runbook; single EC2 ไม่มี failover, งานประมวลผลอยู่ในเว็บและหยุดเมื่อ process หยุด, login counters อยู่ในหน่วยความจำ, secrets อยู่ใน `.env`, ยังไม่มี distributed queue/worker หรือ monitoring/alert ครบถ้วน ผล 6/6 และ RBAC 6 รายการไม่รับรอง load, uptime หรือคุณภาพ AI สำหรับ Production

### การตรวจสอบรอบส่งต่อเอกสาร

แก้เฉพาะ `PROJECT_STATUS.md`, `README.md`, `deploy/aws-ec2/README.md`; ไม่แก้ source/architecture, `.env` หรือข้อมูลเดิม ไม่เรียก live APIs, ไม่เข้าถึง AWS, ไม่ Deploy/Merge/Commit/Push ผล local tests ที่รันจริงวันที่ 17 พฤศจิกายน 2026 บน Python 3.11.9, HEAD `02eacfb` พร้อมการแก้เอกสารนี้: `python -m pytest tests/ -q -ra --basetemp=.pytest_cache/work` ได้ **709 passed, 27 skipped, 0 failed ใน 91.23 วินาที** ใช้ SQLite/mock APIs และปิด dotenv ตาม README; 17 รายการ skip เพราะไม่ได้ตั้ง PostgreSQL ทดสอบแยก และ 10 รายการ skip เพราะไม่มี Bash ผลนี้ไม่รับรอง PostgreSQL/live APIs/AWS และยังต้องรันรายการที่ skip ในสภาพแวดล้อมพร้อมก่อนปิดเกณฑ์ทดสอบทั้งหมด `git diff --check` ผ่านและตรวจว่าประวัติ Phase 5/6 เดิมยังอยู่ครบ

## ประวัติ Phase 6 ก่อน Deploy — Milestones A/B และ Cloud blocker (17 พฤศจิกายน 2026)

ส่วนนี้คงข้อความเดิมเพื่อรักษาประวัติ สถานะ “ยังไม่ได้ Deploy” และ “Cloud Deployment หยุดชั่วคราว” ถูกแทนที่ด้วยสถานะล่าสุดด้านบน

เป้าหมายยังเป็น **Limited Pilot สำหรับพนักงานกลุ่มเล็ก** ไม่ใช่ Production Ready **Phase 6 ยังไม่ได้ Deploy ขึ้น AWS** และ **STT ยังเป็นปัญหาที่ยังไม่ได้ยืนยันว่าแก้สำเร็จ**

### Git และงานที่ตรวจพบจากไฟล์จริง

- Workspace: `C:\Users\Win10\Downloads\smartvoice-git`
- Branch ที่ตรวจจริง: `test/phase6-e2e`
- Commit ล่าสุดที่ตรวจสอบ: `2260fcb` — `feat: add case linking retry UI and audit`; Working Tree สะอาดก่อนแก้เอกสารครั้งนี้
- **Milestone A พัฒนาแล้ว** (`59b7d87`): schema v2 เพิ่มสถานะ/แผน/ข้อผิดพลาด/เวลาของ Case Linking แยกจาก AI Analysis; `done` หมายถึงวิเคราะห์สำเร็จ; สร้างเคสและเชื่อมสายแบบ transaction; retry ใช้แผนเดิมโดยไม่เรียก AI และป้องกันเคสซ้ำสำหรับสายเดียวกัน; แผนใช้ไม่ได้ต้องหยุดตรวจสอบ ไม่ลบหรือจับคู่ orphan เก่าอัตโนมัติ
- **Milestone B พัฒนาแล้ว** (`2260fcb`): warning แยกใน Admin/รายละเอียด Call Summaries, retry เฉพาะ Admin/Supervisor พร้อม session/authorization revalidation และ audit คำขอ/ผล; missing/invalid/stale plan ต้องตรวจสอบด้วยคน ยังไม่มี UI ยืนยันแผนใหม่
- ตรวจพบ implementation ใน `migrations/002_case_linking.sql`, `smartvoice/database_backend.py`, `db.py`, `pipeline.py`, `case_workflow.py`, `ui_helpers.py`, `audit.py` และ tests ที่เกี่ยวข้อง การมีโค้ดไม่ใช่หลักฐานว่า deploy หรือผ่าน live APIs แล้ว

### ผลทดสอบ Local และที่มาของหลักฐาน

- ผล targeted tests จากรอบพัฒนา Milestone A: **273 passed / 0 failed / 17 skipped**; Milestone B: **231 passed / 0 failed / 0 skipped** ใช้ SQLite ทดสอบแยก, mock AI และปิด external network ไม่ใช่ผล full suite ของ commit ล่าสุด และไม่ควรรวมจำนวนข้ามรอบ
- **PostgreSQL Integration Tests: 11 passed, 1 deselected** — ผลทดสอบ Local ที่ผู้ใช้รายงานยืนยันล่าสุด ไม่ใช่ผลรันซ้ำในรอบเอกสารนี้; ยังไม่ได้ระบุชื่อ/เหตุผลของ test ที่ deselected จึงไม่ถือว่ากรณีนั้นผ่านแล้ว
- **Local PostgreSQL Migration v1 → v2 ผ่านการทดสอบกับข้อมูลจำลอง** ตามผลที่ผู้ใช้ยืนยัน
- **Local PostgreSQL Backup/Restore ผ่านการทดสอบ และตรวจสอบข้อมูลหลัง Restore แล้ว** ตามผลที่ผู้ใช้ยืนยัน
- ผล PostgreSQL ล่าสุดขยายหลักฐานจากรอบที่ใช้ SQLite/mock แต่ไม่ได้ยืนยัน PostgreSQL ทุกเส้นทาง, load/concurrency ทุกกรณี, Phase 5 session tests บน PostgreSQL ทั้งชุด หรือ deployment บน AWS

### Cloud, STT และงานที่ยังเหลือ

- **AWS Free Tier Account ถูกระงับ ทำให้ Cloud Deployment หยุดชั่วคราว** ตามสถานะที่ผู้ใช้แจ้ง ไม่ได้เข้าตรวจ AWS ในรอบนี้ ผล Phase 5 บน AWS ด้านล่างเป็นประวัติ ไม่ใช่หลักฐานว่าบริการยังทำงานอยู่ในปัจจุบัน
- **Phase 6 ยังไม่ได้ Deploy ขึ้น AWS** ผล migration/restore ใน Local ไม่ใช่หลักฐานการ migrate หรือ restore ข้อมูลบน Cloud
- **STT ยังไม่ยืนยันว่าแก้สำเร็จ** ผล mock APIs, DB, retry และ UI ไม่รับรองคุณภาพ transcript/diarization หรือความสำเร็จของบริการเสียงจริง ต้องแยกตรวจปัญหา STT ด้วยข้อมูลและการเรียก API ที่ได้รับอนุญาตก่อนรับรอง
- งานถัดไป: เก็บคำสั่ง/ผลทดสอบ PostgreSQL และเหตุผล deselection ให้ตรวจย้อนกลับได้; ตรวจรับ A/B รวมข้อจำกัด audit เมื่อ DB ขัดข้องและแผนที่ต้องตรวจสอบด้วยคน; ยืนยันคุณภาพ STT; ทบทวนแผน Cloud เมื่อบัญชี/สภาพแวดล้อมพร้อมและได้รับอนุมัติ ไม่ถือว่าเอกสารนี้อนุมัติ deploy หรือค่าใช้จ่าย

รอบอัปเดตนี้ตรวจ Git, `PROJECT_STATUS.md`, `README.md`, `AGENTS.md` และตำแหน่ง implementation ที่เกี่ยวข้อง แล้วแก้เฉพาะ `PROJECT_STATUS.md` ไม่รัน tests/migration, ไม่แก้โค้ดหรือฐานข้อมูล, ไม่เรียก AI APIs/เชื่อม AWS และไม่ Commit หรือ Push

## ประวัติ Phase 5 — Pilot Validation Passed (16 พฤศจิกายน 2026)

ข้อความ Phase 5 และประวัติถัดจากนี้คงไว้เพื่ออ้างอิง ณ วันที่บันทึก รวมข้อความที่ระบุว่า Phase 6 ยังไม่ได้เริ่ม หากขัดกับสถานะปัจจุบัน ให้ยึดส่วนสถานะล่าสุดวันที่ 17 พฤศจิกายน 2026 ด้านบน

เป้าหมายปัจจุบันคือ **Limited Pilot สำหรับพนักงานกลุ่มเล็ก** ไม่ใช่ Production Ready งาน Phase 5 (Multi-user, Authentication, RBAC และ Session Management) ที่ commit `c0ed6c6` Deploy บน AWS สำเร็จแล้ว

### ผลทดสอบบน AWS ที่ผู้ใช้ยืนยัน

- HTTPS Health Check ได้ HTTP 200
- SmartVoice, Caddy, PostgreSQL และ Backup Timer ทำงานอยู่
- Admin และ Agent Login ผ่าน
- เปิดใช้งานพร้อมกัน 2 Sessions ผ่านเบื้องต้น
- บัญชี Disabled ถูกปฏิเสธ Login และ Session เดิมกลับหน้า Login ตามการทดสอบ
- การเปลี่ยน Agent → Supervisor และ Supervisor → Agent มีผลเมื่อ Streamlit Rerun

ผล AWS ข้างต้นเป็นผลทดสอบที่ผู้ใช้รายงานยืนยัน ไม่ใช่การเชื่อมต่อหรือตรวจ AWS ซ้ำในรอบอัปเดตเอกสารนี้ และไม่ใช่หลักฐานว่าทุกกรณีของระบบผ่านการทดสอบแล้ว

### ผล Automated Tests และข้อจำกัด

- SQLite Regression Tests เฉพาะ `tests/test_auth.py` และ `tests/test_login_page.py`: **59/59 passed, 0 failed** ใช้ฐานข้อมูลทดสอบแยกจาก Production
- **PostgreSQL Automated Integration Tests สำหรับ Phase 5 ยังไม่ได้รัน** ผล PostgreSQL ของงานก่อนหน้าที่บันทึกในประวัติด้านล่างไม่ยืนยัน Session Revalidation รุ่นนี้
- การใช้งานพร้อมกัน 2 Sessions เป็นการตรวจเบื้องต้น ยังไม่ใช่ load/stress test หรือการรับรองจำนวนผู้ใช้สูงสุด
- การตรวจ Role/Account จาก DB ซ้ำช่วยป้องกันสิทธิ์ค้าง แต่ยังไม่ได้วัดผลกระทบต่อ latency และจำนวน connections เมื่อมีผู้ใช้มากขึ้น
- Backup Timer ทำงานอยู่ไม่ได้ยืนยันว่า backup ทุกรอบหรือ restore ของ release นี้ผ่านแล้ว ต้องตรวจผล backup และคงแผนซ้อมกู้คืน
- AI/STT ยังต้องปรับปรุงคุณภาพ ไม่ถือว่าผลผ่านด้าน Login/RBAC รับรองความถูกต้องของ transcript หรือผลวิเคราะห์ AI

### งานถัดไป — Phase 6 (ยังไม่ได้เริ่ม)

กำหนด **Phase 6 เป็นงานถัดไป** โดยต้องตกลงขอบเขตและเกณฑ์ตรวจรับก่อน implementation ให้สอดคล้องกับเป้าหมาย Limited Pilot และรักษา Architecture/Security Fixes เดิม

งานที่ยังเหลือสำหรับวางแผนรอบถัดไป: PostgreSQL automated integration ของ Phase 5 บนฐานทดสอบแยก, การติดตามปัญหา/ประสิทธิภาพในการใช้พร้อมกัน, การยืนยัน backup/restore และการประเมินปรับปรุงคุณภาพ AI/STT การระบุรายการนี้ไม่ถือว่าเริ่มทำหรืออนุมัติ deploy/เรียก API จริงแล้ว

รอบนี้แก้เฉพาะเอกสารสถานะ ไม่ทำงาน Phase 6 ไม่แก้ source/tests และไม่ Commit, Push, Deploy หรือเชื่อม AWS/Production DB

## ประวัติสถานะก่อน Phase 5

ข้อความและคำสั่งส่งต่อด้านล่างเป็นประวัติ ณ วันที่บันทึก ไม่ใช่สถานะหรือคำสั่งให้เริ่มงานปัจจุบัน หากขัดกับส่วนล่าสุด ให้ยึดส่วนสถานะล่าสุดด้านบน โดยเฉพาะข้อความเดิมที่ระบุว่ายังไม่ Deploy หรือยังไม่มี PostgreSQL บน AWS


## T2 fixes และ PostgreSQL compatibility — 15 พฤศจิกายน 2026

งานใน branch `codex/aws-pilot-high-fixes` แยกจาก GitHub master `3e549ed` ผู้ใช้อนุมัติ commit/push เพื่อส่งต่อแล้ว โดยยังไม่อนุมัติ merge/deploy และไม่แก้ `.env` หรือ runtime data เดิม ผู้ใช้รายงานว่าเวอร์ชันก่อนเปิดเว็บ/login บน EC2 และทดลอง API ได้แล้ว; งานนี้ไม่ได้เข้าตรวจ EC2 หรือเรียก API จริง ผล push และ commit SHA ให้ตรวจจาก GitHub branch โดยตรง

- ปิดปัญหา ownership เมื่ออัปเดต, bootstrap password ว่าง/ขาดบน server, login race/capacity, DB_PATH ของ backup, traceback ที่เผย payload และการ rotate manual backup
- รองรับ SQLite เดิมและ PostgreSQL ผ่าน `DATABASE_URL`; schema version 1 อยู่ใน `migrations/001_postgresql.sql` ต้องรัน migration แยกก่อนเว็บเริ่ม ไม่สร้าง schema อัตโนมัติระหว่าง web rerun
- `scripts/migrate_postgres.py`: dry-run เป็นค่าเริ่มต้น, SQLite read-only, ตรวจ integrity/FKs, นำเข้า 9 ตารางและเทียบ row digests ภายใน transaction, รักษา IDs/ตั้ง sequences, ปฏิเสธปลายทางที่มีข้อมูล
- PostgreSQL คง TEXT สำหรับ JSON/วันที่และ double precision สำหรับตัวเลข พร้อม case-insensitive usernames, atomic case claim, concurrent customer/warranty inserts และการ serialize SO เลขเดียวกัน; ป้องกันลบ/ปิด/ลดสิทธิ์ Admin คนสุดท้ายใน transaction
- Backup รองรับ PostgreSQL custom dump และ SQLite; ซ้อม restore PostgreSQL ลงฐานใหม่แล้ว ไฟล์เสียง/หลักฐาน/checkpoint และ processing threads ยังอยู่ในเครื่องเดียว ไม่ใช่ distributed architecture
- ผลจริง: full suite **626 passed in 103.81s** บน Python 3.12.14 รวม PostgreSQL 17.12 จริงบน localhost, driver psycopg 3.3.9, mock AI APIs และ shell syntax tests; blocked external network attempts = 0
- รัน business-rule tests เดิมจาก test_db/auth/case_workflow/sales_orders/audit บน PostgreSQL เพิ่ม: **197 passed, 6 deselected in 83.09s** รายการที่แยกออกตรวจ schema/PRAGMA/migration ของ SQLite โดยเฉพาะและผ่านแล้วใน full suite ไม่ได้ลบหรือลด assertions ของ tests เดิม
- ยังต้องยืนยันบน EC2: Ubuntu/systemd/Caddy, ownership หลังอัปเดตจริง, TLS/SG/IAM, pg_dump version ให้ตรง server, disk space, backup timer และ restore บน target ก่อนรับมอบ ดู runbook PostgreSQL ใน `deploy/aws-ec2/README.md` ไม่ถือว่าการทดสอบ Windows นี้รับรอง production

ข้อความในส่วน T2 นี้เป็นประวัติ ณ 15 พฤศจิกายน 2026; สถานะล่าสุดให้ใช้ส่วนสถานะล่าสุดด้านบน

### ส่งต่อให้ ChatGPT web / ผู้พัฒนาถัดไป

1. เลือก branch `codex/aws-pilot-high-fixes` และตรวจ commit ล่าสุดก่อนทำงาน อย่าเริ่มจาก master เก่าหรือใช้เพียงข้อความสรุปเป็นหลักฐานว่า merge แล้ว
2. อ่าน AGENTS.md, สถานะส่วนนี้ และ runbook PostgreSQL ใน `deploy/aws-ec2/README.md` รีวิว diff เทียบ master ก่อนเสนอ merge
3. PostgreSQL บน EC2/RDS ยังไม่ได้เตรียม ผู้ใช้ยืนยันว่า deployment เดิมยังใช้ SQLite ต้องตกลง hosting และตรวจว่ามีข้อมูลเดิมที่ต้องเก็บหรือไม่ก่อนสร้างฐาน/ย้ายข้อมูล
4. ทดสอบ schema, migration, backup/restore และ permissions บน Ubuntu/สภาพแวดล้อมเป้าหมายด้วยข้อมูลสังเคราะห์ก่อน ผล PostgreSQL ในเครื่องนี้เป็น localhost Windows 17.12 ไม่ใช่หลักฐานว่า EC2/RDS ผ่านแล้ว
5. Full suite ใช้ mock AI APIs, ปิด dotenv และตั้ง DB_PATH/TEMP ไปฐานทดสอบ หากต้องการ PostgreSQL integration tests ให้ตั้ง SMARTVOICE_TEST_POSTGRES_URL ไปฐานชื่อ smartvoice_test บน localhost เท่านั้น (fixture ล้างข้อมูลในฐานทดสอบนี้) และมี pg_dump/pg_restore ใน PATH
6. ห้ามแนบ secrets/ข้อมูลลูกค้า ห้ามเรียก AI API จริง สร้าง AWS resources, deploy, merge หรือย้ายข้อมูลจริงโดยไม่ได้รับอนุมัติเพิ่ม การอนุมัติรอบนี้ครอบคลุม commit/push branch สำหรับส่งต่อเท่านั้น

## Stage 1: เตรียมขึ้น AWS EC2 ให้บริษัททดลองใช้ — 15 พฤศจิกายน 2026 (branch `feat/aws-pilot-stage1`)

เป้าหมาย: ทั้งระบบอยู่บน AWS (ไม่รันบนเครื่องพนักงาน) ให้ตัวแทนบริษัทเข้าทดลองผ่าน HTTPS — แบบ EC2 เครื่องเดียว ยังคง SQLite + ไฟล์บน EBS; PostgreSQL / S3 storage / worker ยังเป็นแผนขั้นถัดไป

**ทำแล้ว (มี tests, ทดสอบด้วย mock เท่านั้น):**
- กันเดารหัสผ่านฝั่ง server: `smartvoice/login_guard.py` — ผิด 5 ครั้ง/บัญชี → ล็อก 60 วินาที, ผิด 20 ครั้ง/IP → 5 นาที นับรวมทุก session (เดิมอยู่ใน `st.session_state` เปิดแท็บใหม่ก็นับใหม่) — IP มาจาก `X-Forwarded-For` hop สุดท้ายเมื่ออยู่หลัง Caddy
- รหัส bootstrap บน server: `SMARTVOICE_BOOTSTRAP_PASSWORD` (auth.py) — ตั้งไว้แล้วหน้า login ไม่แสดงรหัส, ค่าใช้ไม่ได้ (สั้นกว่า 8 / เป็น admin1234) จะไม่สร้างบัญชีเลย; preflight แจ้ง error; ไม่ตั้ง = พฤติกรรมเดิมในเครื่อง
- ไม่ log คำพูดลูกค้า: `correct_speakers()`, `sanitize_evidence()`, `extract_json()` log แค่ขนาด (ยืนยันว่า tests ใหม่ fail กับโค้ดเดิมทั้ง 5 ข้อ)
- `scripts/backup_db.py`: snapshot SQLite แบบ read-only + `integrity_check` + เก็บ N ชุดล่าสุด
- `deploy/aws-ec2/`: `install.sh` (Ubuntu 24.04: venv, ฟอนต์ไทย, Caddy HTTPS, systemd, รหัส bootstrap สุ่ม, ไม่แตะ data/.env ตอนอัปเดต), `smartvoice.service` (bind 127.0.0.1, เขียนได้เฉพาะ data/ และ .env), `Caddyfile.template`, backup timer ทุกคืน → S3 (SSE), คู่มือภาษาไทย `deploy/aws-ec2/README.md`; `.gitattributes` บังคับ LF
- **Tests: 596 passed** (เดิม 541 + ใหม่ 55) บน Python 3.12.10

**ยังไม่ได้ทำ / ยังไม่ยืนยัน:**
- ยังไม่เคยรัน `install.sh` บน EC2 จริง (ตรวจแค่ `bash -n` และ tests ของเนื้อไฟล์) — การติดตั้งจริงครั้งแรกต้องตรวจทีละขั้นตามคู่มือ
- ยังไม่เคยเรียก pyannoteAI / Typhoon จริง, ยังไม่ได้สร้าง AWS resource ใด ๆ, ยังไม่ซ้อม restore
- เรื่องที่ต้องตัดสินก่อนเปิดให้บริษัทใช้: บัญชี AWS (Learner Lab มีเวลา session จำกัด), ข้อมูลที่ใช้ทดลอง (อนุมัติส่งเสียงจริงไป API หรือใช้โหมดสาธิต), ชื่อโดเมน, งบ API
- ยังไม่ commit/push

## ตรวจรับช่วงงาน (ผู้พัฒนาใหม่) — 15 พฤศจิกายน 2026

ตรวจ branch `docs/cloud-migration-handover` ที่ `5ffd599` จาก clone ใหม่ อ่านเอกสารและ source แล้วรัน tests ซ้ำ ไม่ได้แก้ application code, `.env` หรือข้อมูล ไม่เรียก API จริง ไม่เข้า AWS

- ยืนยันจาก source: API-only (ไม่มี import ของ torch/whisper/transformers/pyannote/ollama), SQLite เป็นฐานข้อมูลเดียว, ไม่มีโค้ด PostgreSQL/object storage/worker, ไฟล์อยู่ใน `data/`, ประมวลผลด้วย daemon threads ในโปรเซสเว็บ — ตรงกับ handover ด้านล่าง
- ไฟล์กฎธุรกิจ (`db.py`, `prompts.py`, `insight_rules.py`, `auth.py`, `sales_orders.py`, `case_workflow.py`, `customer_entry.py`) ไม่เปลี่ยนตั้งแต่ `df0ef44` จนถึง `0c66644`
- **Tests รันซ้ำ: 541 passed in 26.04s** ทั้ง `tests/` รวม `test_config.py` บน Python 3.12.10 ใน `.venv` ใหม่ (`pip install -r requirements.txt pytest`, `pip check` ผ่าน) ด้วย environment เดียวกับคำสั่งด้านล่าง ทั้งหมดใช้ API จำลอง จึงไม่ใช่หลักฐานของ live API/PostgreSQL/Cloud
- แก้เอกสารที่ล้าสมัยให้ตรงกับโค้ด API-only: `CLAUDE.md`, `AGENTS.md` (คำสั่งทดสอบ, baseline 541, tech stack, ผังไฟล์ `stt/`, พฤติกรรมเมื่อ Typhoon ล้มเหลว, หน้า Settings, ตัวแปร env) และหมายเหตุในไฟล์นี้ที่ข้อความเดิมไม่ตรงกับโค้ดแล้ว
- ข้อสังเกตที่เพิ่มใน pitfalls ของ `CLAUDE.md`/`AGENTS.md`: การล็อกหลังใส่รหัสผิดอยู่ใน `st.session_state` (ไม่ใช่ฝั่ง server), บัญชี bootstrap `admin`/`admin1234` ถูกสร้างเมื่อฐานว่าง, คำตอบ LLM/traceback ที่อาจมีคำพูดลูกค้าเข้า log และ `calls.error_msg` — ต้องจัดการก่อนเปิดระบบสู่อินเทอร์เน็ต
- ยังไม่ commit/push การแก้เอกสารนี้

## Cloud migration handover — 15 พฤศจิกายน 2026

**สถานะ ณ รอบ handover เดิม: Phase 4 — PostgreSQL Migration Design (Planned / Not Implemented).** อ่าน [แผนส่งต่อฉบับเต็ม](docs/cloud_migration_plan.md) และ [architecture ปัจจุบัน](docs/architecture.md) ก่อนพัฒนาต่อ หมายเลข Phase เป็นหมวดงาน ไม่ใช่หลักฐานว่า Phase 1–3 เสร็จทั้งหมด

- ก่อนเริ่มเอกสาร: working tree สะอาด, branch `master`, local HEAD และ GitHub HEAD/master ตรงกันที่ `0c66644077e2d2e5fc930167a4116278d4eaa8d4`; ตรวจ remote ด้วย `git ls-remote origin HEAD refs/heads/master` สำเร็จ
- API-only migration อยู่ใน source แล้ว: pyannoteAI + Typhoon; SQLite 9 application tables, local runtime storage และ process-local background threads ยังอยู่ ไม่ได้เพิ่ม PostgreSQL หรือแก้ application code ในงานส่งต่อ
- ตรวจ source ยืนยัน SQLite coupling, customer/warranty check-then-insert, SO transaction รายใบ, case claim แบบ conditional atomic UPDATE, username NOCASE และ last-admin check ที่แยกจาก write; `call_customer_links` ไม่มี UNIQUE(call_id) แม้ใช้ INSERT OR REPLACE จึงต้องตกลงความหมายก่อนแปลงเป็น upsert
- PM แจ้งว่าเคยทดลอง AWS Academy EC2; รอบนี้ไม่ได้เข้าตรวจ AWS และยังไม่ยืนยัน deployment ของ API-only รุ่นล่าสุดหรือ Production Architecture ไม่มีการสร้าง/แก้ AWS resources
- Live API end-to-end, PostgreSQL integration/concurrency, cloud storage/workers และ multi-user cloud acceptance ยังไม่ได้ยืนยัน; 541 passed ในรายงานเดิมเป็น automated tests ที่ mock APIs
- เอกสารเปลี่ยนเฉพาะ `PROJECT_STATUS.md`, `docs/architecture.md`, `docs/cloud_migration_plan.md` บน branch `docs/cloud-migration-handover`; ผล commit/push ให้ดูรายงานส่งมอบ ไม่ถือว่า branch นี้ merge แล้ว

### Verification ของงานเอกสารนี้

อ่าน AGENTS/README/SETUP/CHANGELOG/architecture/database design และตรวจ source/tests ที่เกี่ยวข้อง เทียบ Git history เพื่อแยกการเปลี่ยน API จากกฎธุรกิจ ตรวจ `.gitignore` ว่าครอบคลุม secrets/runtime/backup และต้องตรวจ staged diff ก่อน commit ไม่อ่านหรือแนบฐานข้อมูล/เสียงลูกค้าจริง

ผล full suite รอบส่งต่อ: **541 passed in 89.25s** รวม `test_config.py` ใช้ API mocks และ environment เฉพาะ process โดยปิด dotenv และตั้ง DB_PATH/TEMP/TMP ไปยัง `.pytest_cache` ไม่เปลี่ยน `.env` ไม่มี live API หรือ Cloud test ในรอบนี้

คำสั่งที่รันจริง (PowerShell ที่ repository root):

```powershell
$env:STT_PROVIDER='pyannote_api'
$env:LLM_PROVIDER='typhoon'
$env:PYTHON_DOTENV_DISABLED='1'
$env:TYPHOON_API_KEY='test-only'
$env:PYANNOTE_API_KEY='test-only'
$env:DB_PATH=Join-Path $PWD '.pytest_cache/handover-runtime/test.db'
$env:TEMP=Join-Path $PWD '.pytest_cache/temp'
$env:TMP=$env:TEMP
& '.venv/Scripts/python.exe' -m pytest tests/ -q --basetemp=.pytest_cache/handover-verification
```

### งานถัดไปสำหรับ Claude Code / PM

อ่าน AGENTS.md และ cloud_migration_plan.md ก่อน ตรวจ Git status/latest commit แล้วเริ่ม **Phase 4 implementation preparation** ด้วยการยืนยัน DAL/driver/schema, link cardinality, SO concurrency, last-admin locking, audit guarantee และ authentication fallback เขียน contract/concurrency tests ก่อน implementation ไม่ทำ API-only migration ซ้ำ ไม่เปลี่ยนกฎธุรกิจ/สิทธิ์/soft-delete/audit เงียบ ๆ และไม่ deploy หรือย้ายข้อมูลลูกค้าจริงโดยไม่มี approval

ข้อความ API-only ด้านล่างเป็นรายงานรอบ implementation ก่อน handover; ส่วน Local รุ่นเก่าถูกเก็บไว้เป็นประวัติ

## ประวัติสถานะ — API เท่านั้น (15 พฤศจิกายน 2026)

ตามคำสั่ง PM ถอดการรันโมเดล AI Local ออก: Whisper/Pyannote บนเครื่อง, Ollama transport, GPU/CUDA helpers และ dependencies ที่เกี่ยวข้อง ตัวติดตั้ง `run.bat`/`run.sh`, `requirements.txt`, `pyproject.toml` ใช้ชุด API เท่านั้น

- เสียงใช้ pyannoteAI API (Whisper Turbo + Precision-2/3); ข้อความใช้ Typhoon API ค่าเริ่มต้น `STT_PROVIDER=pyannote_api`, `LLM_PROVIDER=typhoon`
- Settings ตัด Local provider, Whisper backend/device/compute, HuggingFace token และ Ollama URL/model ออก คง API keys/model, Discord และเสียงตัวอย่าง
- `.env` รุ่นเดิมที่ตั้ง `local`/`ollama` จะได้รับข้อความให้เปิด Settings และบันทึกโหมด API; ไม่มีการเปลี่ยน provider หรือแก้ `.env` จริงอัตโนมัติ
- `MOCK_STT=true` ใช้เสียงตัวอย่างแทน STT เท่านั้น การวิเคราะห์ยังเรียก Typhoon และมีค่าใช้บริการ
- `smartvoice/stt/transcribe.py` และ `scripts/compare_stt_models.py` ถูกถอดออก ส่วน helpers จัดข้อความ/label ที่ไม่โหลดโมเดลยังอยู่
- `scripts/compare_llm_models.py` เปลี่ยนเป็นเปรียบเทียบ Typhoon API และต้องใช้ `--allow-api` เพื่อส่ง transcript ไปยังบริการที่มีค่าใช้จ่าย
- คงชื่อโมดูล `ollama_client.py` เพื่อให้ imports เดิมทำงาน แต่ transport ใช้ Typhoon API เท่านั้น
- ฐานข้อมูล, pipeline, prompts, insight rules, สิทธิ์และข้อมูลลูกค้าไม่มีการเปลี่ยน ไม่มีการลบข้อมูล Local, `.env`, แพ็กเกจที่ติดตั้ง หรือ model cache
- ยังไม่ได้ deploy Cloud, ย้าย SQLite เป็น PostgreSQL, ย้ายไฟล์ไป Object Storage หรือเรียกบริการ AI จริง

### ผลตรวจสอบรอบนี้

- Tests ใหม่ก่อน implementation ล้มเหลวครบ 5 กรณีตามคาด จากค่าเริ่มต้น Local, การยอมรับ provider เก่า, imports และ dependencies Local
- หลังถอด Local: 532 passed (เว้น test_config.py ตามแนวทางเดิม)
- รอบสุดท้าย: **541 passed in 85.42s** รันทั้ง `tests/` รวม test_config.py ที่เหลือเฉพาะ pure helpers; ใช้ API จำลองและ keys สำหรับทดสอบ ไม่ใช่บัญชีจริง
- จำนวน tests เปลี่ยนจาก baseline เพราะถอด tests เฉพาะ Local inference/Whisper combo/Local STT benchmark และแทนด้วย API-only, readiness, legacy Settings migration, missing-key และ launcher checks ไม่ได้ลด tests ของกฎธุรกิจ
- `pip check`: No broken requirements found; Python source 49 ไฟล์ parse ผ่าน
- ไม่ได้รันตัวติดตั้งจริงหรือทดสอบ Python ทุกเวอร์ชัน/ทุก OS; launcher ตรวจผ่าน tests และการตรวจ source
- ตรวจ import ใน subprocess ที่บล็อกแพ็กเกจ Local AI แล้ว pipeline/preflight/STT ยัง import ได้

คำสั่งทดสอบ (กำหนดเฉพาะ environment ของ process โดยไม่แก้ .env):

```powershell
$env:STT_PROVIDER='pyannote_api'
$env:LLM_PROVIDER='typhoon'
$env:PYTHON_DOTENV_DISABLED='1'
$env:TYPHOON_API_KEY='test-only'
$env:PYANNOTE_API_KEY='test-only'
$env:TEMP=Join-Path $PWD '.pytest_cache/temp'
$env:TMP=$env:TEMP
& '.venv/Scripts/python.exe' -m pytest tests/ -q --basetemp=.pytest_cache/api-only-final
```

## ประวัติการส่งต่องานก่อนเปลี่ยนเป็น API เท่านั้น

ข้อความด้านล่างเป็นสถานะวันที่ 14 พฤศจิกายน 2026; แนวทาง Local ที่กล่าวถึงถูกยกเลิกโดยสถานะปัจจุบันด้านบน


อัปเดต 14 พฤศจิกายน 2026 (Asia/Bangkok)

## สถานะที่ยืนยันได้

งานเพิ่มทางเลือก API และเก็บงานที่ค้างผ่านการทดสอบอัตโนมัติแล้ว: **552 passed** บน Python 3.12.14 และ Streamlit 1.55.0; `pip check` ผ่าน ไม่มี dependency ขัดแย้ง

**ยังไม่ยืนยันการทำงานกับบริการ AI จริง**: การทดสอบ API ใช้คำตอบจำลอง ยังไม่ได้ตรวจ key, เครดิต, สิทธิ์โมเดล, ความแม่นยำภาษาไทย, latency หรือค่าใช้จ่ายจริง ไม่ได้ส่งเสียงลูกค้าหรือข้อความไปยังผู้ให้บริการ ไม่ได้ deploy หรือสร้างทรัพยากร AWS

GitHub repository **Private**: https://github.com/SojiKlay/smartvoice-master ผู้ใช้อนุญาตและ **push initial commit `df0ef44` สำเร็จแล้ว** บน branch `master` รวม 101 ไฟล์โค้ดและเอกสาร โดยไม่รวมข้อมูล runtime/credentials

## ภาพรวมและโครงสร้าง

SmartVoice เป็นระบบวิเคราะห์สาย call center ภาษาไทย สำหรับงานขายที่นอน/เฟอร์นิเจอร์ การร้องเรียน ติดตามส่งสินค้า และประกัน

Pipeline เดิม:

`audio → Whisper local → Pyannote local → LLM speaker correction → Thai speaker rules/splitters → transcript cleanup → LLM analysis → insight_rules → SQLite → Streamlit`

ทางเลือกใหม่:

`audio → pyannoteAI (Whisper Turbo + Precision diarization) → pipeline/rules เดิม → Typhoon API → insight_rules เดิม → SQLite → Streamlit`

การเปลี่ยนครั้งนี้เป็นการเปลี่ยน backend AI ไม่ใช่เขียนระบบ cloud ใหม่ เว็บ ฐานข้อมูล ไฟล์เสียง และ worker ยังคงอยู่ในเครื่องที่รันแอป สามารถใช้เครื่องสเปคต่ำสำหรับโหมด API ได้โดยไม่ต้องโหลดโมเดล AI ในเครื่อง แต่ยังต้องมี RAM/disk สำหรับเว็บและข้อมูล

ไฟล์หลัก:

| ส่วน | ตำแหน่ง |
|---|---|
| Login และ router ตามสิทธิ์ | `Home.py`, `smartvoice/auth.py`, `smartvoice/ui_helpers.py` |
| หน้าใช้งาน | `pages/` (บางชื่อไฟล์มี emoji ต้องรักษาชื่อจริง) |
| Orchestration / speaker rules | `smartvoice/pipeline.py`, `smartvoice/processing_control.py` |
| Speech backend | `smartvoice/stt/orchestrator.py`, `audio.py`, `transcribe.py`, `diarize.py` |
| LLM / prompts / ตรวจหลักฐาน | `smartvoice/ollama_client.py`, `prompts.py`, `insight_rules.py` |
| ตั้งค่า / ตรวจ readiness | `config.py`, `env_settings.py`, `preflight.py` ภายใน `smartvoice/` |
| SQLite / เคส / ลูกค้า / SO | `smartvoice/db.py`, `case_workflow.py`, `customer_entry.py`, `sales_orders.py` |
| การอัปโหลด / audit / รายงาน | `file_manager.py`, `audit.py`, `dashboard_report.py` ภายใน `smartvoice/` |
| Runtime ส่วนตัว (ห้ามอัปโหลด) | `data/`, `.env`, `.streamlit/secrets.toml` |
| Tests / คู่มือ | `tests/`, `SETUP.md`, `docs/`, `AGENTS.md` |

ตารางหลัก: calls, customers, warranty_registrations, sales_orders, sales_order_lines, call_customer_links, cases, users, audit_log

## เป้าหมายก่อนโควต้าหมดและสิ่งที่ตรวจพบ

ผู้ใช้ต้องการย้ายการประมวลผล AI ออกจากเครื่องสเปคต่ำ โดยคงตระกูลโมเดลเดิมและยอมเปลี่ยนรุ่นได้ เตรียมทดลองบน AWS Academy Learner Lab ภายหลัง

ตรวจประวัติแชต Codex และไฟล์จริงแล้วพบว่า API adapters, Settings, readiness, ชุด dependencies แบบเบา และ tests ถูกเขียนไว้แล้ว แต่ full suite หลังปรับ dependencies ยังไม่สำเร็จก่อนโควต้าหมด รอบนี้จึงตรวจและเก็บงานเดิมต่อ ไม่ได้เปลี่ยน prompts, insight rules หรือออกแบบฐานข้อมูลใหม่

ไม่มี initial commit ให้ใช้เทียบ diff รายการด้านล่างอ้างอิงประวัติแชตและโค้ดที่ตรวจ ไม่ใช่หลักฐานว่าการเปลี่ยนแปลงทั้งหมดในโปรเจ็กต์เกิดจากงาน API นี้

## งานที่เสร็จแล้วและไฟล์ที่เกี่ยวข้อง

| ไฟล์ | ผลงาน |
|---|---|
| `smartvoice/config.py` | เพิ่มการอ่าน provider, model, key, timeout และ token limit ผ่าน `api_settings()` |
| `smartvoice/ollama_client.py` | เพิ่ม Typhoon chat completions; รองรับชื่อรุ่นจาก config; error/429/คำตอบขาดหรือ JSON ไม่ถูกต้องไม่ถูกตีเป็นผลวิเคราะห์สำเร็จเงียบ ๆ |
| `smartvoice/stt/orchestrator.py` | เพิ่ม upload เสียง, สร้าง job, polling และแปลงผลรวม Whisper/Pyannote เป็น segment รูปแบบเดิม; มี checkpoint เพื่อ resume/reuse |
| `smartvoice/pipeline.py` | ตรวจ Typhoon key ก่อนเริ่มงานเสียงในโหมดที่ใช้ Typhoon; รักษา orchestration และกฎเดิม |
| `smartvoice/preflight.py` | readiness แยก local/API; API ไม่บังคับ Ollama หรือโมเดล local; ตรวจค่าที่ตั้งไว้โดยไม่เรียก API จริง |
| `smartvoice/env_settings.py` | preset สำหรับ local กำหนด provider กลับเป็น local/Ollama อย่างชัดเจน |
| `smartvoice/audit.py` | ปิดบังค่า API key ทั้งสองบริการใน audit |
| `smartvoice/file_manager.py` | เมื่อลบเสียงผ่านแอป ลบ checkpoint ของเสียงด้วย |
| `smartvoice/ui_helpers.py` | แสดงชื่อโมเดลตาม provider ใน sidebar |
| `pages/1_📤_Admin.py` | ใช้ readiness ตาม provider ก่อนประมวลผล |
| `pages/4_Settings.py` | เลือก provider/รุ่นและใส่ key ผ่านช่องรหัสผ่าน; เก็บ key เดิมเมื่อเว้นว่าง; รอบนี้แก้ไม่เตือน GPU/ตรวจ combo local เมื่อใช้ speech API และแก้คำแนะนำเปิดแอปใหม่ |
| `.env.example` | ตัวอย่างตัวแปร API ไม่มี key จริง; ค่าเริ่มต้นยังคง local/Ollama (ณ 14 พ.ย. — ตั้งแต่ `0c66644` ค่าเริ่มต้นเป็น `pyannote_api`/`typhoon` แล้ว) |
| `requirements-api.txt` | dependencies สำหรับ API โดยไม่ติดตั้ง torch/CUDA/transformers/Ollama; pin Streamlit 1.55.0 |
| `SETUP.md` | วิธีติดตั้ง API, ค่า config, ข้อจำกัด และวิธีกู้คืนงานจาก checkpoint |
| `tests/test_api_backends.py` | ทดสอบ provider/payload/errors/cache/resume/cancellation/redaction/Settings รวม regression คำเตือน GPU |
| `.gitignore` | กัน runtime/เสียง/ฐานข้อมูล/keys/secrets; จำกัด scratch pattern ให้เฉพาะ root เพื่อไม่ซ่อน `__init__.py` |
| `PROJECT_STATUS.md` | เอกสารส่งต่อฉบับนี้ สร้างตามคำขอผู้ใช้ |

## การตั้งค่า API และขอบเขตที่ต้องเข้าใจ

| ค่า | ค่าเริ่มต้นหรือค่าที่ใช้ในโหมด API |
|---|---|
| `STT_PROVIDER` | เปลี่ยนจาก `local` เป็น `pyannote_api` |
| `LLM_PROVIDER` | เปลี่ยนจาก `ollama` เป็น `typhoon` |
| `MOCK_STT` | ตั้ง `false` เมื่อต้องการเสียงจริง |
| `PYANNOTE_API_MODEL` | `precision-2`; backend รองรับ `precision-3` ด้วย |
| `STT_API_MODEL` | `faster-whisper-large-v3-turbo` |
| `TYPHOON_MODEL` | `typhoon-v2.5-30b-a3b-instruct`; เปลี่ยนรุ่นใน Settings/env ได้ |
| รุ่นเล็กที่เตรียมให้เลือก | `typhoon-v2.1-12b-instruct` ต้องตรวจสิทธิ์และ availability กับบัญชีจริง |
| `AI_API_TIMEOUT` / `AI_JOB_TIMEOUT` | 120 / 1800 วินาที |
| `TYPHOON_MAX_TOKENS` | 4096 |

ต้องตั้ง `PYANNOTE_API_KEY` และ `TYPHOON_API_KEY` ในเครื่อง/เซิร์ฟเวอร์เท่านั้น ไม่ส่งในแชตหรือ Git API ส่งเสียงต้นฉบับให้ pyannoteAI และส่ง transcript ให้ Typhoon จึงต้องใช้ข้อมูลที่ได้รับอนุญาต เครดิต API ของบริการเหล่านี้ไม่ใช่เครดิต AWS Academy

โมเดลเสียง API ไม่ใช่ `biodatlab/distill-whisper-th-large-v3` ตัว local เดิม และไม่ใช่ Pyannote Community-1; ต้องเทียบคุณภาพจริงก่อนรับรองผล ระบบไม่ได้เปลี่ยนรุ่นหรือ retry คำขอที่มีค่าใช้จ่ายอัตโนมัติ

Typhoon ใช้ prompts เดิมและ JSON parser ฝั่งแอป ไม่ได้บังคับ JSON schema ที่บริการ ค่า `json_mode` ของ local Ollama ไม่ได้แปลงเป็นคำสั่ง JSON mode ของ Typhoon

Checkpoint `<audio-path>.smartvoice-api.json` เก็บ job ID และผลเสียงต้นฉบับ ซึ่งเป็นข้อมูลส่วนตัว ห้ามอัปโหลด เมื่อ timeout แล้วลองใหม่จะติดตาม job เดิมหรือใช้ผลเดิม แต่ LLM จะรันใหม่และอาจมีค่าใช้จ่ายซ้ำ ถ้าส่ง job แล้วไม่ได้รับ ID ระบบกันส่งซ้ำอัตโนมัติ ให้ตรวจประวัติงานกับผู้ให้บริการก่อนลบ checkpoint การกดหยุดในแอปไม่ใช่ยกเลิกงานที่รับไปแล้วบนบริการ

## ผลการทดสอบ

- รอบแรกในสภาพแวดล้อมไฟล์ชั่วคราวเดิม: 543 passed / 9 failed มีปัญหา path และสิทธิ์ของไฟล์ชั่วคราว
- รอบสุดท้ายหลังแก้ Settings และกำหนด TEMP/TMP ภายในโปรเจ็กต์: **552 passed in 90.26s** ไม่มี tests ล้มเหลวในชุดที่รัน
- `python -m pip check`: **No broken requirements found**
- Tests ครอบคลุม API จำลอง, Settings ผ่าน Streamlit AppTest, pipeline และ business rules เดิม, DB/auth/audit และหน้าใช้งานตามชุดเดิม
- เว้น `tests/test_config.py` ตาม AGENTS เพราะมีผลข้างเคียงกับ environment และต้องใช้ torch ซึ่งไม่ได้ติดตั้งในชุด API (ณ 14 พ.ย. — ปัจจุบันไฟล์นี้ไม่ต้องใช้ torch และรันรวมในชุด 541 แล้ว)
- ไม่ได้ทดสอบ inference local/GPU, API keys จริง, คุณภาพเสียงจริง, provider rate limits จริง, cloud/network deployment หรือโหลดหลายผู้ใช้

คำสั่งทดสอบที่ผ่านบนเครื่องนี้ (PowerShell ที่ root โปรเจ็กต์):

```powershell
New-Item -ItemType Directory -Force .pytest_cache/temp | Out-Null
$env:TEMP = Join-Path $PWD '.pytest_cache/temp'
$env:TMP = $env:TEMP
& '.venv/Scripts/python.exe' -m pytest tests/ --ignore=tests/test_config.py -q --basetemp=.pytest_cache/work
& '.venv/Scripts/python.exe' -m pip check
```

ผลรันภายในเครื่องเก็บใน `.pytest_cache/test-results.txt` ซึ่ง Git ignore

## ติดตั้งและเปิดใช้งาน

ใช้ virtual environment แยก อย่าสร้างทับ environment ที่มีอยู่โดยไม่ตรวจสอบ บนเครื่องนี้มี `.venv` และติดตั้งชุด API แล้ว

```powershell
py -3.11 -m venv .venv
& '.venv/Scripts/python.exe' -m pip install -r requirements-api.txt
& '.venv/Scripts/python.exe' -m pip install pytest
& '.venv/Scripts/python.exe' -m streamlit run Home.py
```

ข้ามคำสั่งสร้าง venv ถ้ามีแล้ว เครื่องนี้ทดสอบด้วย Python 3.12.14; โหมด local ใช้ Python 3.10/3.11 ตามคู่มือเดิม โหมด API ให้ใช้คำสั่งเปิด Streamlit ด้านบน เพราะ `run.bat`/`run.sh` และ dependencies หลักยังเป็นชุด local เต็ม

> หมายเหตุ (ตรวจ 15 พ.ย. 2026): ข้อความย่อหน้าบนเป็นสถานะ 14 พ.ย. ตั้งแต่ `0c66644` `requirements.txt` ชี้ไป `requirements-api.txt` และ `run.bat`/`run.sh` ติดตั้งชุด API แล้ว ใช้ launcher ได้ตามปกติ; `preflight.py` รับ Python 3.10–3.12 เท่านั้น

เปิด `http://localhost:8501` ตั้ง provider/key ใน Settings แล้วบันทึกและเปิดแอปใหม่ หากยังไม่มีบัญชี แอปมีบัญชี bootstrap ตาม `SETUP.md`/`auth.py` ให้เปลี่ยนรหัสผ่านก่อนเปิดให้ผู้อื่นใช้งาน ไม่เก็บรหัสผ่านจริงในเอกสารนี้

## Git และ GitHub

- Local branch: `master` ติดตาม `origin/master`; initial commit `df0ef44` push สำเร็จแล้ว เอกสารสถานะนี้อัปเดตใน commit ถัดมา
- Remote `origin`: `https://github.com/SojiKlay/smartvoice-master.git`
- Repository บน GitHub ตรวจเห็นป้าย **Private** ในรอบที่สร้าง; ก่อน push ตรวจ remote แล้วไม่มีประวัติเดิม
- ส่งเฉพาะโค้ดและเอกสารที่ตรวจสอบ ไม่ส่งข้อมูล runtime และไม่สร้าง Codespace
- ตรวจ candidate files ก่อนสร้างรายงาน 100 ไฟล์: ไม่พบรูปแบบ token/private key/credential URL ที่สแกน; ตรวจ credential assignments ที่พบเป็นค่า test, label และ bootstrap ของระบบ
- `git check-ignore` ยืนยัน `.env`, `.env.production`, `.streamlit/secrets.toml`, หลักฐานใน `data/`, เสียง และ private key ถูก ignore; ไฟล์ `__init__.py` กลับมาอยู่ใน candidate list
- ตรวจเนื้อหา staged ทั้ง 101 ไฟล์ก่อน commit แล้ว ไม่พบรูปแบบ token/private key ที่ตรวจหา การสแกนรูปแบบไม่รับรองข้อมูลส่วนตัวในข้อความทั่วไปทั้งหมด; ไฟล์เสียง/ฐานข้อมูล/ข้อมูลลูกค้าไม่เป็นส่วนของชุดส่งต่อ
- `git diff --cached --check` พบ whitespace เดิมบางจุดในเอกสาร/pages/prompts/requirements จึงคงไว้เพื่อไม่แก้โค้ดนอกขอบเขต; ไม่ใช่ test failure
- ผล tests ล่าสุดยังเป็น 552 passed; รอบ push นี้เปลี่ยนเฉพาะเอกสารสถานะ ไม่มีการแก้ implementation เพิ่ม
- ไม่มีการแก้ไข `.env` จริงเพื่อเปิด API และไม่มีการย้าย/ล้างข้อมูลผู้ใช้

## งานค้างและขั้นตอนถัดไป

1. ผู้ใช้จัดเตรียม key/เครดิตของ pyannoteAI และ Typhoon ใน Settings หรือ `.env` เอง พร้อมอนุญาตค่าใช้จ่ายและเลือกเสียงทดสอบที่ส่งภายนอกได้ จึงจะทดสอบ live ได้
2. เริ่มเสียงสั้นหนึ่งสาย ตรวจ transcript, ผู้พูด, summary, sentiment, QA, next action และ anomaly กับเสียงจริง แล้วจึงทดสอบชุดตัวอย่างเพิ่มเติม ถ้าลดรุ่น LLM ให้เทียบคุณภาพใหม่
3. Push initial commit สำเร็จแล้ว: เชื่อม GitHub หรือแนบไฟล์โค้ดให้ ChatGPT บนเว็บ โดยให้สิทธิ์เข้าถึง private repository เฉพาะที่ต้องใช้
4. ประเมิน EC2 หลัง live test ผ่านเท่านั้น ต้องได้รับอนุญาตก่อน deploy/สร้างทรัพยากรที่มีค่าใช้จ่าย งานนี้ยังไม่ได้เตรียม deployment อัตโนมัติ
5. ก่อนใช้งานจริงต้องวางแผน HTTPS, เปลี่ยนรหัส bootstrap, backup SQLite/เสียง, พื้นที่ดิสก์, การเข้าถึงข้อมูล, restart/worker และ concurrent users ระบบปัจจุบันยังไม่ใช่ distributed worker/queue

## ส่งต่อให้ ChatGPT Project_Smartvoice บนเว็บ

แนบเอกสารนี้พร้อมโค้ดที่ผ่านการตรวจ หรือเชื่อม private repository ที่มีโค้ดแล้ว การส่งลิงก์อย่างเดียวไม่ทำให้ ChatGPT มีสิทธิ์อ่าน private repo อัตโนมัติ ห้ามแนบ `.env`, credentials, `data/`, เสียงลูกค้า, checkpoints หรือฐานข้อมูลจริง

อ่าน `AGENTS.md` ก่อนแก้โค้ด รักษา prompts, speaker correction multi-pass, evidence validation ใน `insight_rules.py`, role guards, soft delete และ audit trail อย่าลด test เพื่อให้ผ่าน ห้ามอ้างว่า API หรือ cloud ใช้งานจริงแล้วจากผล mock tests เป้าหมายถัดไปคือยืนยัน live integration ที่ได้รับอนุญาต ไม่ใช่ redesign ระบบทั้งหมด
