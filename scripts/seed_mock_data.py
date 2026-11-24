"""Build a standalone SmartVoice demonstration database."""
import argparse
import gc
import getpass
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from smartvoice import auth, db

DEMO_ID = 0x5356444D


def populate(password):
    db.init_db()
    for role in auth.ROLES:
        db.create_user("demo_" + role.lower(), "สาธิต " + role, role, auth.hash_password(password))
    day = date.today()
    for index, topic in enumerate(("แจ้งปัญหาสินค้า", "สอบถามการจัดส่ง"), 1):
        phone = f"DEMO-PHONE-{index}"
        customer = db.insert_customer("ลูกค้าสาธิต", f"กลุ่ม {index}", phone)
        order = f"DEMO-SO-{index}"
        item = f"DEMO-ITEM-{index}"
        db.save_sales_order({"so_number": order, "customer_id": customer, "currency": "THB",
                             "order_date": day.isoformat(), "grand_total": 1000, "net_amount": 1000,
                             "sell_to_name": f"ลูกค้าสาธิต กลุ่ม {index}"},
                            [{"item_no": item, "description": "ที่นอนสาธิต", "quantity": 1,
                              "uom": "ชิ้น", "unit_price": 1000, "amount": 1000}], actor="demo_admin")
        db.insert_warranty(f"DEMO-W-{index}", customer, brand="Omazz", model="รุ่นสาธิต",
                          sku=item, so_number=order, date_of_purchase=day.isoformat(),
                          expiry_date=day.replace(year=day.year + 10, day=28 if day.month == 2 and day.day == 29 else day.day).isoformat())
        case = None
        for turn in range(2 if index == 1 else 1):
            name = f"{day:%Y%m%d}{10 + turn}0000-DEMO.{index}-101-{phone}-Inbound.wav"
            call = db.insert_call(name, f"DEMO-{index}-{turn}", "", "demo_agent", "Agent")
            db.update_call_customer_phone(call, phone)
            db.auto_link_call_by_phone(call, phone)
            question = "ขอวันจัดส่ง"
            if index == 1:
                question = "ที่นอนยุบ ขอคุยกับหัวหน้า" if turn else "ซื้อที่นอน Omazz ผ่าน Shopee แจ้งที่นอนยุบ"
            answer = "จะติดตามผลให้ค่ะ"
            db.update_call_results(call, f"Customer: {question}\nAgent: {answer}", question,
                                   "negative" if index == 1 else "neutral", topic,
                                   topic_detail="สปริง/ฟองน้ำยุบ" if index == 1 else "",
                                   brand_mentions=json.dumps(["Omazz"] if "Omazz" in question else []),
                                   platform_mentions=json.dumps(["Shopee"] if "Shopee" in question else []),
                                   anomaly_detected=bool(turn), anomaly_reason="ขอคุยกับหัวหน้า" if turn else "",
                                   anomaly_severity="medium" if turn else "", keywords=json.dumps([topic]),
                                   agent_performance=json.dumps({"overall_score": 7, "politeness": 4,
                                                                 "problem_solving": 3, "next_action": answer,
                                                                 "next_action_owner": "ฝ่ายบริการลูกค้า"}))
            plan = {"customer_id": customer, "action": "create"}
            if case is not None:
                plan.update(action="link", case_id=case)
            db.save_case_link_plan(call, plan)
            if db.retry_case_link(call) != "linked":
                raise RuntimeError("Demo case linking failed")
            case = db.get_call_by_id(call)["case_id"]
        if index == 1:
            db.claim_case(case, "demo_agent", "สาธิต Agent")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo-dir", required=True, type=Path)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    directory = args.demo_dir.resolve()
    if directory.name != "smartvoice-demo" or directory.is_relative_to(ROOT / "data"):
        parser.error("Choose a separate directory named smartvoice-demo outside runtime data.")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "demo.sqlite3"
    if target.is_symlink():
        parser.error("Refusing a linked database.")
    exists = target.exists()
    if exists:
        with closing(sqlite3.connect(target.as_uri() + "?mode=ro", uri=True)) as conn:
            if conn.execute("PRAGMA application_id").fetchone()[0] != DEMO_ID:
                parser.error("This database was not created by the demo seed.")
    elif any(directory.iterdir()):
        parser.error("The initial demo directory must be empty.")
    os.environ.update(DATABASE_URL="", SMARTVOICE_USERS="", DISCORD_WEBHOOK_URL="",
                      PYANNOTE_API_KEY="", TYPHOON_API_KEY="", MOCK_STT="true",
                      STT_PROVIDER="pyannote_api", LLM_PROVIDER="typhoon")
    password = os.environ.pop("SMARTVOICE_DEMO_PASSWORD", "")
    if not exists or args.reset:
        password = password or getpass.getpass("Local demo password (all four roles): ")
        if auth.validate_password(password):
            parser.error("Choose a demo password of at least eight characters.")
        with tempfile.TemporaryDirectory(dir=directory.parent) as work:
            candidate = Path(work) / "candidate.db"
            os.environ["DB_PATH"] = str(candidate)
            populate(password)
            gc.collect()
            with closing(sqlite3.connect(candidate)) as built:
                built.execute(f"PRAGMA application_id={DEMO_ID}")
                if built.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or built.execute("PRAGMA foreign_key_check").fetchone():
                    raise RuntimeError("Demo database validation failed")
                if not exists:
                    target.touch(exist_ok=False)
                with closing(sqlite3.connect(target.as_uri() + "?mode=rw", uri=True)) as destination:
                    if exists and destination.execute("PRAGMA application_id").fetchone()[0] != DEMO_ID:
                        parser.error("Unrecognized destination")
                    built.backup(destination)
    print(f"Demo database ready: {target}")
    if args.serve:
        os.environ["DB_PATH"] = str(target)
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(ROOT / "Home.py"),
                        "--server.address=127.0.0.1"], cwd=directory, check=True)


if __name__ == "__main__":
    main()
