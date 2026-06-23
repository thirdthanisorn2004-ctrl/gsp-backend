from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta, timezone

# เครื่องมือเข้ารหัสผ่าน
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# กุญแจลับสำหรับออกตั๋ว (ห้ามให้ใครรู้)
SECRET_KEY = "PTT_GSP_SECRET_KEY_2026"
ALGORITHM = "HS256"

# 1. ฟังก์ชันเอาไว้ "เข้ารหัส" ก่อนลง Database
def get_password_hash(password: str):
    return pwd_context.hash(password)

# 2. ฟังก์ชันเอาไว้ "ตรวจสอบ" รหัสตอน Login
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# 3. ฟังก์ชันเอาไว้ "ออกบัตรผ่าน (Token)" 
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=8) # ตั๋วหมดอายุใน 8 ชม.
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)