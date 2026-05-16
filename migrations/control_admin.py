import json
import os
from utils.db.session import SessionLocal
from utils.db.models.control_admin import CommandControl

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def migrate(json_path: str = None):
    if json_path is None:
        json_path = os.path.join(BASE_DIR, "data","admin_json" , "control_admin.json")

    print(f"Lecture de : {json_path}")  # ← pour débugger

    with open(json_path) as f:
        data: dict[str, bool] = json.load(f)

    with SessionLocal() as session:
        for command_name, enabled in data.items():
            existing = session.query(CommandControl).filter_by(command_name=command_name).first()
            if existing:
                existing.enabled = enabled
            else:
                session.add(CommandControl(command_name=command_name, enabled=enabled))

        session.commit()
        print(f"✓ {len(data)} commandes migrées.")

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else None
    migrate(path)