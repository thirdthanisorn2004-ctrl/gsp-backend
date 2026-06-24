from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import libsql_client
import os
import uvicorn
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext

# --- 1. ตั้งค่าแอปพลิเคชันหลัก ---
app = FastAPI(title="GSP1 API - Production Grade with Auth")

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# --- 2. 🔐 ตั้งค่าระบบรักษาความปลอดภัยและการเข้ารหัส ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "PTT_GSP_SUPER_SECRET_KEY_2026")
ALGORITHM = "HS256"

# ☁️ ฐานข้อมูล Turso DB
TURSO_URL = "https://gsp-relay-db-thirdthanisorn2004-ctrl.aws-ap-northeast-1.turso.io"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODE4NTI0NzEsImlkIjoiMDE5ZWRlYWItNzMwMS03OGZmLWE2NjUtNjA5NWRlNjBmYzkyIiwicmlkIjoiNmM2MjZiODYtZTA2OS00YTkzLWFjZWQtNjZkMTUwYmQwZDU2In0.nWP5VYLr4a5ZbN220Rc5REVA3yf5dEpXYBdo1ls9JGFedcnHxJE0E84Z-nAgK2meRCvWN_DOKZS85XV6xqR9CQ"

def get_db_client():
    if not TURSO_URL or not TURSO_TOKEN:
        raise HTTPException(status_code=500, detail="Database credentials missing")
    return libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)

# --- 3. 👥 Pydantic Schemas ---
class UserAuthSchema(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user" 

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
    model_config = {"extra": "forbid"}

# --- 4. 🛂 ด่านตรวจสอบสิทธิ์ (Middleware Guards) ---
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="บัตรผ่านหมดอายุแล้ว กรุณาเข้าสู่ระบบใหม่")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="บัตรผ่าน (Token) ไม่ถูกต้อง")

def verify_admin_role(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="สิทธิ์ของคุณไม่เพียงพอ เฉพาะระดับผู้ดูแลระบบ (Admin) เท่านั้นที่เข้าถึงได้"
        )
    return current_user

# --- 5. 📌 ROUTES: Authentication ---
@app.post("/api/register")
def register(user_data: UserAuthSchema):
    with get_db_client() as client:
        res = client.execute("SELECT username FROM users WHERE username = ?", [user_data.username])
        if len(res.rows) > 0:
            raise HTTPException(status_code=400, detail="ชื่อผู้ใช้งานนี้ถูกใช้ไปแล้วในระบบ")
        
        hashed_password = pwd_context.hash(user_data.password)
        client.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            [user_data.username, hashed_password, user_data.role]
        )
        return {"status": "success", "message": "ลงทะเบียนผู้ใช้งานระบบสำเร็จแล้ว!"}

@app.post("/api/login")
def login(user_data: UserAuthSchema):
    with get_db_client() as client:
        res = client.execute("SELECT password_hash, role FROM users WHERE username = ?", [user_data.username])
        if len(res.rows) == 0:
            raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        
        db_password_hash = res.rows[0][0]
        db_role = res.rows[0][1]
        
        if not pwd_context.verify(user_data.password, db_password_hash):
            raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        
        expire = datetime.now(timezone.utc) + timedelta(hours=8)
        token_payload = {"username": user_data.username, "role": db_role, "exp": expire}
        token = jwt.encode(token_payload, SECRET_KEY, algorithm=ALGORITHM)
        
        return {
            "status": "success",
            "access_token": token,
            "token_type": "bearer",
            "role": db_role
        }

# --- 6. 📌 ROUTES: Relay Data Management ---
@app.get("/")
def home():
    return {"message": "GSP1 API Production Grade is running!", "status": "success"}

@app.get("/api/relays")
def get_all_relays(current_user: dict = Depends(get_current_user)):
    with get_db_client() as client:
        result = client.execute("SELECT * FROM relays")
        data = [dict(zip(result.columns, row)) for row in result.rows]
        return {"status": "success", "total": len(data), "data": data, "authorized_operator": current_user["username"]}

@app.get("/api/relays/{plant}")
def get_relays_by_plant(plant: str, current_user: dict = Depends(get_current_user)):
    with get_db_client() as client:
        result = client.execute("SELECT * FROM relays WHERE Plant = ?", [plant.upper()])
        data = [dict(zip(result.columns, row)) for row in result.rows]
        if not data:
            return {"status": "error", "message": f"ไม่พบข้อมูลของ {plant}"}
        return {"status": "success", "total": len(data), "data": data}

@app.put("/api/relays/{relay_id}")
def update_relay(relay_id: str, updated_data: RelayUpdateSchema, current_user: dict = Depends(verify_admin_role)):
    update_dict = updated_data.model_dump(exclude_unset=True)
    if not update_dict:
        return {"status": "success", "message": "ไม่มีข้อมูลอัปเดต"}
    
    fields = list(update_dict.keys())
    values = list(update_dict.values())
    set_clause = ", ".join([f"{field} = ?" for field in fields])
    query = f"UPDATE relays SET {set_clause} WHERE Relay_ID = ?"
    
    try:
        with get_db_client() as client:
            result = client.execute(query, values + [relay_id])
            if result.rows_affected == 0:
                raise HTTPException(status_code=404, detail=f"ไม่พบข้อมูล Relay ID: {relay_id}")
                
            return {
                "status": "success", 
                "message": f"แก้ไขข้อมูล Relay ID: {relay_id} สำเร็จโดย Admin!",
                "updated_by": current_user["username"]
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"เกิดข้อผิดพลาด: {str(e)}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)