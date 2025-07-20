from settings import get_supabase_client
import sys

def check_supabase_tables():
    """Supabase에 존재하는 테이블들을 확인"""
    try:
        supabase = get_supabase_client()
        
        print("🔍 Supabase 테이블 확인")
        print("=" * 50)
        
        # naver_shop 테이블 확인
        print("1. naver_shop 테이블 확인:")
        try:
            result = supabase.table('naver_shop').select('*').limit(1).execute()
            print(f"   ✅ naver_shop 테이블 존재 - 데이터 {len(result.data)}개 확인")
        except Exception as e:
            print(f"   ❌ naver_shop 테이블 오류: {e}")
        
        # naver_shop_check_confirm 테이블 확인
        print("\n2. naver_shop_check_confirm 테이블 확인:")
        try:
            result = supabase.table('naver_shop_check_confirm').select('*').limit(1).execute()
            print(f"   ✅ naver_shop_check_confirm 테이블 존재 - 데이터 {len(result.data)}개 확인")
        except Exception as e:
            print(f"   ❌ naver_shop_check_confirm 테이블 오류: {e}")
        
        # 다른 관련 테이블들 확인
        related_tables = [
            'serve_shop_data',
            'serve_oneroom_data', 
            'customer',
            'mylist_shop',
            'completed_deal'
        ]
        
        print("\n3. 기타 관련 테이블들:")
        for table_name in related_tables:
            try:
                result = supabase.table(table_name).select('*').limit(1).execute()
                print(f"   ✅ {table_name} 테이블 존재 - 데이터 {len(result.data)}개 확인")
            except Exception as e:
                print(f"   ❌ {table_name} 테이블 오류: {e}")
                
        print("\n📝 결론:")
        print("   - naver_shop_check_confirm 테이블이 없는 경우")
        print("   - check_memo 기능을 제거하고 기본 데이터만 반환하도록 수정 필요")
        
    except Exception as e:
        print(f"❌ Supabase 연결 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_supabase_tables() 