from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
import pandas as pd
import os
import uvicorn

app = FastAPI(title="GSP1 API - Pro Version")

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

# --- Pydantic Model: ยามเฝ้าประตู (Whitelist & Type Validation) ---
class RelayUpdateSchema(BaseModel):
    Breaker: Optional[str] = None
    CT_Ratio: Optional[str] = None
    CT_Class: Optional[str] = None
    CT_Burden_VA: Optional[str] = None
    ZCT_Ratio: Optional[str] = None
    ZCT_Class: Optional[str] = None
    ZCT_Burden_VA: Optional[str] = None
    Relay_Manufacturer: Optional[str] = None
    Relay_Model: Optional[str] = None
    Phase_Curve: Optional[str] = None
    Phase_Pickup: Optional[float] = None
    Phase_Prim_Amps: Optional[float] = None
    Phase_Time_Dial: Optional[float] = None
    Phase_Inst_Pickup: Optional[float] = None
    Phase_Inst_Prim_Amps: Optional[float] = None
    Phase_Inst_Delay_s: Optional[float] = None
    Ground_Curve: Optional[str] = None
    Ground_Pickup: Optional[float] = None
    Ground_Prim_Amps: Optional[float] = None
    Ground_Time_Dial: Optional[float] = None
    Ground_Inst_Pickup: Optional[float] = None
    Ground_Inst_Prim_Amps: Optional[float] = None
    Ground_Inst_Delay_s: Optional[float] = None
    OLR_Trip: Optional[float] = None
    OLR_Prim_Amps: Optional[float] = None
    OLR_Time_Constant: Optional[float] = None
    Remark: Optional[str] = None

@app.get("/")
def home():
    return {"message": "GSP1 API is running!", "status": "success"}

@app.get("/api/relays")
def get_all_relays():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM relays", conn)
    conn.close()
    
    # แปลง NaN ของ Pandas กลับเป็น None (NULL ในฝั่ง Frontend)
    df = df.where(pd.notnull(df), None)
    return {"status": "success", "total": len(df), "data": df.to_dict(orient="records")}

@app.get("/api/relays/{plant}")
def get_relays_by_plant(plant: str):
    conn = get_db_connection()
    query = "SELECT * FROM relays WHERE Plant = ?"
    df = pd.read_sql_query(query, conn, params=(plant.upper(),))
    conn.close()
    
    if df.empty:
        return {"status": "error", "message": f"ไม่พบข้อมูลของ {plant}"}
        
    df = df.where(pd.notnull(df), None)
    return {"status": "success", "total": len(df), "data": df.to_dict(orient="records")}

# เปลี่ยนไปใช้ {relay_id} เป็น String (เช่น GSP1-R01) แทน rowid แล้ว!
@app.put("/api/relays/{relay_id}")
def update_relay(relay_id: str, updated_data: RelayUpdateSchema):
    # ใช้ exclude_unset=True ตามที่พี่เขาสะกิดมาเป๊ะๆ
    # (ถ้ารันแล้วพังเพราะ FastAPI เครื่องมึงเป็นเวอร์ชันเก่า ให้เปลี่ยน .model_dump เป็น .dict)
    update_dict = updated_data.model_dump(exclude_unset=True)
    
    if not update_dict:
        return {"status": "success", "message": "ไม่มีข้อมูลอัปเดต"}

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # เช็คก่อนว่ามีรหัส Relay_ID นี้จริงๆ ใช่ไหม
    cursor.execute("SELECT Relay_ID FROM relays WHERE Relay_ID = ?", (relay_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"ไม่พบข้อมูล Relay ID: {relay_id}")
    
    fields = list(update_dict.keys())
    values = list(update_dict.values())
    
    set_clause = ", ".join([f"{field} = ?" for field in fields])
    query = f"UPDATE relays SET {set_clause} WHERE Relay_ID = ?"
    
    try:
        cursor.execute(query, values + [relay_id])
        conn.commit()
        conn.close()
        return {"status": "success", "message": f"แก้ไขข้อมูล Relay ID: {relay_id} สำเร็จ!"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"เกิดข้อผิดพลาด: {str(e)}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)