from fastapi import APIRouter, HTTPException
import hashlib
import mysql.connector as mysql
from models import SignupData, LoginData # models.py에서 모델 임포트
from settings import get_db_connection, logger # settings.py에서 DB 연결 함수 및 로거 임포트

router = APIRouter()

@router.post("/signup")
def signup(data: SignupData):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # (A) password 해시 (단순 SHA256)
        pw_hash = hashlib.sha256(data.password.encode()).hexdigest()

        # (B) 중복 체크
        sql_check = "SELECT COUNT(*) FROM managers WHERE name=%s"
        cursor.execute(sql_check, (data.name,))
        (cnt,) = cursor.fetchone()
        if cnt > 0:
            raise HTTPException(status_code=409, detail="이미 존재하는 이름") # 409 Conflict

        # (C) INSERT
        sql_ins = "INSERT INTO managers (name, password, role, contact) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql_ins, (data.name, pw_hash, data.role, data.contact))
        conn.commit()
        logger.info(f"New user signed up: {data.name} (role: {data.role})")
        return {"status":"ok", "message":"가입완료", "role": data.role}

    except mysql.Error as e:
        logger.error(f"Signup DB error for user {data.name}: {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except HTTPException as http_ex:
        # 중복 체크에서 발생한 HTTPException은 그대로 전달
        raise http_ex
    except Exception as e:
        logger.error(f"Signup unexpected error for user {data.name}: {e}")
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.post("/login")
def login(data: LoginData):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        sql = "SELECT id, name, password, role, contact FROM managers WHERE name=%s"
        cursor.execute(sql, (data.name,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="해당 이름 없음") # 404 Not Found

        # SHA256 해시 비교
        pw_hash = hashlib.sha256(data.password.encode()).hexdigest()
        if row["password"] != pw_hash:
            raise HTTPException(status_code=401, detail="비밀번호 불일치") # 401 Unauthorized

        logger.info(f"User logged in: {data.name}")
        # 로그인 성공
        return {
            "status": "ok",
            "id": row["id"],
            "name": row["name"],
            "role": row["role"],
            "contact": row["contact"]
        }

    except mysql.Error as e:
        logger.error(f"Login DB error for user {data.name}: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except HTTPException as http_ex:
        # 자격 증명 실패 등 예상된 HTTP 예외는 그대로 전달
        raise http_ex
    except Exception as e:
        logger.error(f"Login unexpected error for user {data.name}: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    finally:
        if cursor: cursor.close()
        if conn: conn.close() 