from tinydb import TinyDB, Query
from pathlib import Path
from app.config import settings
import os


def get_db() -> TinyDB:
    db_dir = os.path.dirname(settings.DB_PATH)
    Path(db_dir).mkdir(parents=True, exist_ok=True)
    db = TinyDB(settings.DB_PATH)
    return db


db = get_db()

users_table = db.table("users")
customers_table = db.table("customers")
cloth_categories_table = db.table("cloth_categories")
washing_lines_table = db.table("washing_lines")
batch_rules_table = db.table("batch_rules")
work_teams_table = db.table("work_teams")
qc_standards_table = db.table("qc_standards")
cloth_records_table = db.table("cloth_records")
qc_records_table = db.table("qc_records")
rewash_records_table = db.table("rewash_records")
sorting_records_table = db.table("sorting_records")

UserQuery = Query()
CustomerQuery = Query()
ClothCategoryQuery = Query()
WashingLineQuery = Query()
BatchRuleQuery = Query()
WorkTeamQuery = Query()
QcStandardQuery = Query()
ClothRecordQuery = Query()
QcRecordQuery = Query()
RewashRecordQuery = Query()
SortingRecordQuery = Query()
