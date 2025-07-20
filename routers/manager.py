from fastapi import APIRouter, HTTPException, Query
import mysql.connector as mysql
from settings import get_db_connection, logger

router = APIRouter()

@router.get("/get_managers")
def get_managers():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # 역할(role) 정보도 함께 조회할 수 있도록 수정 고려
        cursor.execute("SELECT `name`, `role` FROM `managers` ORDER BY name ASC") 
        rows = cursor.fetchall()
        if not rows:
            return {"managers": []}
        # managers = [row[0] for row in rows] # 이름만 반환
        managers_with_roles = [{"name": row[0], "role": row[1]} for row in rows] # 이름과 역할 반환
        return {"managers": managers_with_roles}

    except mysql.Error as e:
        logger.error(f"Get managers DB error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        logger.error(f"Get managers unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.post("/add_manager")
async def add_manager(data: dict):
    # 회원가입 API(/signup)와 기능이 중복되므로, 
    # 이 API를 유지할지, signup API를 사용할지 결정 필요.
    # 여기서는 일단 유지하되, signup처럼 password, role, contact도 받도록 확장 가능.
    manager_name = data.get("name")
    if not manager_name:
        raise HTTPException(status_code=400, detail="관리자 이름이 필요합니다.")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # 기본값으로 role='manager', password/contact는 빈 값으로 추가하는 예시
        sql_check = "SELECT COUNT(*) FROM managers WHERE name=%s"
        cursor.execute(sql_check, (manager_name,))
        (cnt,) = cursor.fetchone()
        if cnt > 0:
             raise HTTPException(status_code=409, detail="이미 존재하는 관리자 이름입니다.")
             
        default_pw_hash = ""
        default_role = "manager"
        default_contact = ""
        sql_ins = "INSERT INTO `managers` (`name`, `password`, `role`, `contact`) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql_ins, (manager_name, default_pw_hash, default_role, default_contact))
        conn.commit()
        logger.info(f"Added new manager: {manager_name} (role: {default_role}) via /add_manager endpoint.")
        return {"status": "success", "message": f"{manager_name} 관리자가 추가되었습니다."}

    except mysql.Error as e:
        logger.error(f"Add manager DB error for name '{manager_name}': {e}")
        if conn: conn.rollback()
        if e.errno == 1062:
             raise HTTPException(status_code=409, detail="이미 존재하는 관리자 이름입니다.")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except HTTPException as http_ex:
         raise http_ex
    except Exception as e:
        logger.error(f"Add manager unexpected error for name '{manager_name}': {e}", exc_info=True)
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close() 