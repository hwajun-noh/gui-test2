import mysql.connector
import json
from datetime import datetime, date

def check_mysql_mylist_data():
    """MySQL의 mylist_shop과 mylist_oneroom 데이터 확인"""
    
    print("🔍 MySQL 마이리스트 데이터 확인 시작")
    print("=" * 60)
    
    connection = None
    try:
        # MySQL 연결
        connection = mysql.connector.connect(
            host='localhost',
            database='mydb',
            user='root',
            password='a13030z0!!'
        )
        
        if connection.is_connected():
            print("✅ MySQL 연결 성공")
            cursor = connection.cursor(dictionary=True)
            
            # 1. mylist_shop 테이블 확인
            print("\n📊 1. mylist_shop 테이블 분석:")
            print("-" * 40)
            
            try:
                # 테이블 존재 확인
                cursor.execute("SHOW TABLES LIKE 'mylist_shop'")
                if cursor.fetchone():
                    print("✅ mylist_shop 테이블 존재")
                    
                    # 데이터 개수 확인
                    cursor.execute("SELECT COUNT(*) as count FROM mylist_shop")
                    count_result = cursor.fetchone()
                    print(f"📈 데이터 개수: {count_result['count']}개")
                    
                    if count_result['count'] > 0:
                        # 컬럼 구조 확인
                        cursor.execute("DESCRIBE mylist_shop")
                        columns = cursor.fetchall()
                        print("📋 컬럼 구조:")
                        for col in columns:
                            print(f"   - {col['Field']}: {col['Type']} {col['Null']} {col['Key']}")
                        
                        # 샘플 데이터 3개 확인
                        cursor.execute("SELECT * FROM mylist_shop LIMIT 3")
                        sample_data = cursor.fetchall()
                        print(f"\n📝 샘플 데이터 ({len(sample_data)}개):")
                        for i, row in enumerate(sample_data, 1):
                            print(f"   샘플 {i}: ID={row.get('id')}, 구={row.get('gu')}, 동={row.get('dong')}, 지번={row.get('jibun')}")
                        
                        # 상태별 통계
                        cursor.execute("SELECT status_cd, COUNT(*) as count FROM mylist_shop GROUP BY status_cd")
                        status_stats = cursor.fetchall()
                        print(f"\n📊 상태별 통계:")
                        for stat in status_stats:
                            print(f"   - {stat['status_cd']}: {stat['count']}개")
                            
                else:
                    print("❌ mylist_shop 테이블이 존재하지 않습니다")
                    
            except Exception as e:
                print(f"❌ mylist_shop 조회 오류: {e}")
            
            # 2. mylist_oneroom 테이블 확인
            print("\n📊 2. mylist_oneroom 테이블 분석:")
            print("-" * 40)
            
            try:
                # 테이블 존재 확인
                cursor.execute("SHOW TABLES LIKE 'mylist_oneroom'")
                if cursor.fetchone():
                    print("✅ mylist_oneroom 테이블 존재")
                    
                    # 데이터 개수 확인
                    cursor.execute("SELECT COUNT(*) as count FROM mylist_oneroom")
                    count_result = cursor.fetchone()
                    print(f"📈 데이터 개수: {count_result['count']}개")
                    
                    if count_result['count'] > 0:
                        # 컬럼 구조 확인
                        cursor.execute("DESCRIBE mylist_oneroom")
                        columns = cursor.fetchall()
                        print("📋 컬럼 구조:")
                        for col in columns:
                            print(f"   - {col['Field']}: {col['Type']} {col['Null']} {col['Key']}")
                        
                        # 샘플 데이터 3개 확인
                        cursor.execute("SELECT * FROM mylist_oneroom LIMIT 3")
                        sample_data = cursor.fetchall()
                        print(f"\n📝 샘플 데이터 ({len(sample_data)}개):")
                        for i, row in enumerate(sample_data, 1):
                            print(f"   샘플 {i}: ID={row.get('id')}, 구={row.get('gu')}, 동={row.get('dong')}, 지번={row.get('jibun')}")
                        
                        # 상태별 통계
                        cursor.execute("SELECT status_cd, COUNT(*) as count FROM mylist_oneroom GROUP BY status_cd")
                        status_stats = cursor.fetchall()
                        print(f"\n📊 상태별 통계:")
                        for stat in status_stats:
                            print(f"   - {stat['status_cd']}: {stat['count']}개")
                            
                else:
                    print("❌ mylist_oneroom 테이블이 존재하지 않습니다")
                    
            except Exception as e:
                print(f"❌ mylist_oneroom 조회 오류: {e}")
            
            cursor.close()
            
    except mysql.connector.Error as error:
        print(f"❌ MySQL 연결 오류: {error}")
        
    finally:
        if connection and connection.is_connected():
            connection.close()
            print("\n✅ MySQL 연결 종료")

if __name__ == "__main__":
    check_mysql_mylist_data() 