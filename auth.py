from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta, timezone
import libsql_client

# 1. สร้างตัวเซิร์ฟเวอร์ FastAPI (Uvicorn จะวิ่งมาหาตัวแปร app ตัวนี้)
app = FastAPI(title="PTT Asset Protection API with Turso DB")

# 2. ตั้งค่า CORS ให้ฝั่ง Frontend (HTML) ยิงเข้าหาหลังบ้านได้โดยไม่โดนบล็อก
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. ☁️ ตั้งค่าการเชื่อมต่อ Turso Database 
# (อย่าลืมตรวจเช็ค URL และ Token ให้เป็นของโปรเจกต์คุณนะครับ)
TURSO_URL = "https://gsp-relay-db-thirdthanisorn2004-ctrl.aws-ap-northeast-1.turso.io"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODE4NTI0NzEsImlkIjoiMDE5ZWRlYWItNzMwMS03OGZmLWE2NjUtNjA5NWRlNjBmYzkyIiwicmlkIjoiNmM2MjZiODYtZTA2OS00YTkzLWFjZWQtNjZkMTUwYmQwZDU2In0.nWP5VYLr4a5ZbN220Rc5REVA3yf5dEpXYBdo1ls9JGFedcnHxJE0E84Z-nAgK2meRCvWN_DOKZS85XV6xqR9CQ"

def get_db_client():
    return libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)

# 4. 🛠️ ระบบรักษาความปลอดภัยและการออกตั๋ว Token 
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "PTT_GSP_SECRET_KEY_2026"
ALGORITHM = "HS256"

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=8) # ตั๋วหมดอายุใน 8 ชม.
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# 5. 📦 โครงสร้างรับข้อมูลจากหน้าเว็บ (Schema)
class UserAuthSchema(BaseModel):
    username: str
    password: str
    role: str = "user"

# 6. 🚀 API สำหรับสมัครสมาชิก (Sign Up) -> บันทึกลงคอลัมน์ password_hash ตรงๆ
@app.post("/api/register")
async def register(user: UserAuthSchema):
    client = get_db_client()
    try:
        # เช็คก่อนว่ามี Username นี้ในระบบหรือยัง
        check_res = client.execute("SELECT username FROM users WHERE username = ?", [user.username])
        if len(check_res.rows) > 0:
            raise HTTPException(status_code=400, detail="USERNAME ALREADY EXISTS")

        # เข้ารหัสผ่านก่อนบันทึกลงฐานข้อมูล
        hashed_pw = get_password_hash(user.password)
        
        # แก้ไขคอลัมน์เป็น password_hash ให้ตรงกับในตาราง Turso จริงแล้ว
        client.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            [user.username, hashed_pw, user.role]
        )
        return {"status": "success", "message": "STAFF REGISTERED SUCCESSFULLY"}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=f"DATABASE ERROR: {str(e)}")
    finally:
        client.close()

# 7. 🚀 API สำหรับเข้าสู่ระบบ (Sign In) -> ดึงข้อมูลจากคอลัมน์ password_hash มาตรวจ
@app.post("/api/login")
async def login(user: UserAuthSchema):
    client = get_db_client()
    try:
        # แก้ไขคอลัมน์เป็น password_hash ให้ตรงกับในตาราง Turso จริงแล้ว
        res = client.execute("SELECT password_hash, role FROM users WHERE username = ?", [user.username])
        if len(res.rows) == 0:
            raise HTTPException(status_code=401, detail="INVALID USERNAME OR PASSWORD")
        
        db_hashed_password = res.rows[0][0]
        db_role = res.rows[0][1]

        # ตรวจสอบรหัสผ่านที่กรอกเข้ามากับรหัสที่ถูกแฮชใน Database
        if not verify_password(user.password, db_hashed_password):
            raise HTTPException(status_code=401, detail="INVALID USERNAME OR PASSWORD")
        
        # ถ้ารหัสผ่านถูกต้อง ทำการออกตั๋ว Token ให้ทันที
        token = create_access_token({"sub": user.username, "role": db_role})
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": db_role
        }
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=f"LOGIN ERROR: {str(e)}")
    finally:
        client.close()

# หน้าแรกไว้ทดสอบสถานะ API
@app.get("/")
async def root():
    return {"message": "PTT GSP API WITH TURSO CONNECTED"}