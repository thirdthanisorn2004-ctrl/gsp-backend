from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import pandas as pd
import os
import uvicorn

app = FastAPI(title="GSP1 Prototype API")

# เปิด CORS ให้เพื่อนฝั่ง Frontend ดึงข้อมูลไปใช้ได้
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_methods=["*"], 
    allow_headers=["*"]
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "relay_data.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
def home():
    return {"message": "GSP1 Prototype API is running!", "status": "success"}

# ดึงข้อมูลทั้งหมด (ลิงก์หลัก)
@app.get("/api/relays")
def get_all_relays():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM relays", conn)
    conn.close()
    
    return {"status": "success", "total": len(df), "data": df.to_dict(orient="records")}

# ดึงข้อมูลแยกตาม Plant (ลิงก์ที่มี /GSP1 ต่อท้าย)
@app.get("/api/relays/{plant}")
def get_relays_by_plant(plant: str):
    conn = get_db_connection()
    query = f"SELECT * FROM relays WHERE Plant = '{plant.upper()}'"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        return {"status": "error", "message": f"ไม่พบข้อมูลของ {plant}"}
        
    return {"status": "success", "total": len(df), "data": df.to_dict(orient="records")}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)