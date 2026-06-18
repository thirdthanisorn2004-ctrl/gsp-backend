from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import pandas as pd
import os

app = FastAPI(title="GSP Relay API (SQL Ready)")

# อนุญาตให้เว็บอื่นเรียก API ได้
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ระบุที่อยู่ไฟล์ Database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "relay_data.db")

def get_db_connection():
    """เชื่อมต่อกับไฟล์ database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # ทำให้เรียกข้อมูลแบบคอลัมน์ได้
    return conn

@app.get("/api/relays")
def get_all_relays():
    """ดึงข้อมูล Relay ทั้งหมดจาก SQL"""
    conn = get_db_connection()
    # ดึงข้อมูลมาเป็น DataFrame แล้วแปลงเป็น list of dict
    df = pd.read_sql_query("SELECT * FROM relays", conn)
    conn.close()
    return {"status": "success", "data": df.to_dict(orient="records")}

@app.get("/api/relays/{plant}")
def get_relays_by_plant(plant: str):
    """ดึงข้อมูล Relay แยกตามชื่อ Plant"""
    conn = get_db_connection()
    # ใช้คอลัมน์ Plant ที่อยู่ใน SQL
    query = f"SELECT * FROM relays WHERE Plant = '{plant.upper()}'"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        return {"status": "error", "message": f"ไม่พบข้อมูลของ {plant}"}
    
    return {"status": "success", "data": df.to_dict(orient="records")}

if __name__ == "__main__":
    import uvicorn
    # รันบนพอร์ต 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)