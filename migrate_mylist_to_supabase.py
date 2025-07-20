import mysql.connector
from settings import get_supabase_client
import logging
from datetime import datetime, date
import json

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_mysql_data_to_supabase(mysql_row, table_type):
    """MySQL 데이터를 Supabase 형식으로 변환"""
    
    # 공통 처리: None 값과 날짜 처리
    converted_data = {}
    
    for key, value in mysql_row.items():
        if key == 'id':
            # Supabase는 auto-increment이므로 ID는 제외
            continue
        elif isinstance(value, date):
            # 날짜를 문자열로 변환
            converted_data[key] = value.isoformat() if value else None
        elif isinstance(value, float):
            # NaN 처리
            converted_data[key] = value if not (value != value) else None  # NaN 체크
        else:
            converted_data[key] = value
    
    return converted_data

def migrate_mylist_shop():
    """mylist_shop 테이블 마이그레이션"""
    
    print("🏪 mylist_shop 마이그레이션 시작")
    print("-" * 50)
    
    # MySQL 연결
    mysql_conn = None
    try:
        mysql_conn = mysql.connector.connect(
            host='localhost',
            database='mydb',
            user='root',
            password='a13030z0!!'
        )
        mysql_cursor = mysql_conn.cursor(dictionary=True)
        
        # Supabase 클라이언트
        supabase = get_supabase_client()
        if not supabase:
            print("❌ Supabase 클라이언트 초기화 실패")
            return False
        
        # 1. MySQL에서 데이터 조회
        print("📋 MySQL에서 데이터 조회 중...")
        mysql_cursor.execute("SELECT * FROM mylist_shop ORDER BY id ASC")
        mysql_rows = mysql_cursor.fetchall()
        
        print(f"📊 조회된 데이터: {len(mysql_rows)}개")
        
        if not mysql_rows:
            print("⚠️  마이그레이션할 데이터가 없습니다.")
            return True
        
        # 2. 기존 Supabase 데이터 확인
        print("🔍 Supabase 기존 데이터 확인...")
        existing_result = supabase.table('mylist_shop').select('id').execute()
        existing_count = len(existing_result.data)
        print(f"📊 Supabase 기존 데이터: {existing_count}개")
        
        # 3. 배치로 데이터 삽입
        batch_size = 100
        total_success = 0
        total_errors = 0
        
        for i in range(0, len(mysql_rows), batch_size):
            batch_data = mysql_rows[i:i + batch_size]
            
            # 데이터 변환
            converted_batch = []
            for row in batch_data:
                try:
                    converted_row = convert_mysql_data_to_supabase(row, 'shop')
                    converted_batch.append(converted_row)
                except Exception as e:
                    print(f"⚠️  데이터 변환 오류 (ID: {row.get('id')}): {e}")
                    total_errors += 1
                    continue
            
            # Supabase에 삽입
            if converted_batch:
                try:
                    result = supabase.table('mylist_shop').insert(converted_batch).execute()
                    batch_success = len(result.data)
                    total_success += batch_success
                    print(f"✅ 배치 {i//batch_size + 1}: {batch_success}개 삽입 성공")
                    
                except Exception as e:
                    print(f"❌ 배치 {i//batch_size + 1} 삽입 실패: {e}")
                    total_errors += len(converted_batch)
        
        print(f"\n🎉 mylist_shop 마이그레이션 완료!")
        print(f"✅ 성공: {total_success}개")
        print(f"❌ 실패: {total_errors}개")
        print(f"📊 성공률: {(total_success/(total_success+total_errors)*100):.1f}%")
        
        return total_success > 0
        
    except Exception as e:
        print(f"❌ mylist_shop 마이그레이션 오류: {e}")
        return False
        
    finally:
        if mysql_conn and mysql_conn.is_connected():
            mysql_conn.close()

def migrate_mylist_oneroom():
    """mylist_oneroom 테이블 마이그레이션"""
    
    print("\n🏠 mylist_oneroom 마이그레이션 시작")
    print("-" * 50)
    
    # MySQL 연결
    mysql_conn = None
    try:
        mysql_conn = mysql.connector.connect(
            host='localhost',
            database='mydb',
            user='root',
            password='a13030z0!!'
        )
        mysql_cursor = mysql_conn.cursor(dictionary=True)
        
        # Supabase 클라이언트
        supabase = get_supabase_client()
        if not supabase:
            print("❌ Supabase 클라이언트 초기화 실패")
            return False
        
        # 1. MySQL에서 데이터 조회
        print("📋 MySQL에서 데이터 조회 중...")
        mysql_cursor.execute("SELECT * FROM mylist_oneroom ORDER BY id ASC")
        mysql_rows = mysql_cursor.fetchall()
        
        print(f"📊 조회된 데이터: {len(mysql_rows)}개")
        
        if not mysql_rows:
            print("⚠️  마이그레이션할 데이터가 없습니다.")
            return True
        
        # 2. 기존 Supabase 데이터 확인
        print("🔍 Supabase 기존 데이터 확인...")
        existing_result = supabase.table('mylist_oneroom').select('id').execute()
        existing_count = len(existing_result.data)
        print(f"📊 Supabase 기존 데이터: {existing_count}개")
        
        # 3. 데이터 변환 및 삽입
        converted_data = []
        errors = 0
        
        for row in mysql_rows:
            try:
                converted_row = convert_mysql_data_to_supabase(row, 'oneroom')
                converted_data.append(converted_row)
            except Exception as e:
                print(f"⚠️  데이터 변환 오류 (ID: {row.get('id')}): {e}")
                errors += 1
                continue
        
        # Supabase에 삽입
        if converted_data:
            try:
                result = supabase.table('mylist_oneroom').insert(converted_data).execute()
                success_count = len(result.data)
                
                print(f"\n🎉 mylist_oneroom 마이그레이션 완료!")
                print(f"✅ 성공: {success_count}개")
                print(f"❌ 실패: {errors}개")
                print(f"📊 성공률: {(success_count/(success_count+errors)*100):.1f}%")
                
                return success_count > 0
                
            except Exception as e:
                print(f"❌ Supabase 삽입 실패: {e}")
                return False
        else:
            print("⚠️  변환할 수 있는 데이터가 없습니다.")
            return False
        
    except Exception as e:
        print(f"❌ mylist_oneroom 마이그레이션 오류: {e}")
        return False
        
    finally:
        if mysql_conn and mysql_conn.is_connected():
            mysql_conn.close()

def verify_migration():
    """마이그레이션 결과 검증"""
    
    print("\n🔍 마이그레이션 결과 검증")
    print("=" * 50)
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            print("❌ Supabase 클라이언트 초기화 실패")
            return False
        
        # mylist_shop 검증
        shop_result = supabase.table('mylist_shop').select('id, gu, dong, jibun').limit(5).execute()
        shop_count = len(shop_result.data)
        print(f"✅ mylist_shop: {shop_count}개 데이터 확인")
        
        if shop_count > 0:
            print("📝 샘플 데이터:")
            for i, row in enumerate(shop_result.data[:3], 1):
                print(f"   {i}. ID: {row.get('id')}, 주소: {row.get('gu')} {row.get('dong')} {row.get('jibun')}")
        
        # mylist_oneroom 검증
        oneroom_result = supabase.table('mylist_oneroom').select('id, gu, dong, jibun').limit(5).execute()
        oneroom_count = len(oneroom_result.data)
        print(f"✅ mylist_oneroom: {oneroom_count}개 데이터 확인")
        
        if oneroom_count > 0:
            print("📝 샘플 데이터:")
            for i, row in enumerate(oneroom_result.data[:3], 1):
                print(f"   {i}. ID: {row.get('id')}, 주소: {row.get('gu')} {row.get('dong')} {row.get('jibun')}")
        
        return shop_count > 0 or oneroom_count > 0
        
    except Exception as e:
        print(f"❌ 검증 오류: {e}")
        return False

def main():
    """메인 마이그레이션 함수"""
    
    print("🚀 마이리스트 데이터 마이그레이션 시작")
    print("=" * 60)
    print(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 1. mylist_shop 마이그레이션
        shop_success = migrate_mylist_shop()
        
        # 2. mylist_oneroom 마이그레이션  
        oneroom_success = migrate_mylist_oneroom()
        
        # 3. 마이그레이션 결과 검증
        verification_success = verify_migration()
        
        # 4. 최종 결과
        print(f"\n🏁 마이그레이션 완료")
        print("=" * 60)
        print(f"📅 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🏪 mylist_shop: {'✅ 성공' if shop_success else '❌ 실패'}")
        print(f"🏠 mylist_oneroom: {'✅ 성공' if oneroom_success else '❌ 실패'}")
        print(f"🔍 검증: {'✅ 통과' if verification_success else '❌ 실패'}")
        
        if shop_success and oneroom_success and verification_success:
            print("\n🎉 전체 마이그레이션 성공!")
            return True
        else:
            print("\n⚠️  일부 마이그레이션 실패")
            return False
            
    except Exception as e:
        print(f"\n❌ 전체 마이그레이션 오류: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 