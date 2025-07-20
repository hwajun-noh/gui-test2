# Cursor Model Context Protocol (MCP) 설정 안내

## MCP란?

Model Context Protocol(MCP)은 Anthropic에서 개발한 개방형 프로토콜로, AI 시스템이 외부 도구, 데이터베이스, 파일 시스템 등 외부 리소스와 표준화된 방식으로 상호 작용할 수 있게 해줍니다.

Cursor IDE에서는 MCP를 통해 AI 코딩 도우미의 기능을 확장하고 다양한 외부 서비스와 연결할 수 있습니다.

## 설정된 MCP 서버

이 프로젝트에는 다음 MCP 서버가 설정되어 있습니다:

1. **GitHub**: GitHub 저장소와 상호 작용하여 코드 검색, 이슈 관리, PR 생성 등의 기능 제공
2. **Filesystem**: 파일 시스템에 안전하게 접근하여 파일 읽기, 쓰기, 검색 기능 제공
3. **Memory**: 지식 그래프 기반 영구 메모리 시스템으로 대화 컨텍스트 유지

## 설정 방법

### 1. GitHub MCP 설정

GitHub MCP를 사용하기 위해서는 개인 액세스 토큰이 필요합니다:

1. GitHub에서 [개인 액세스 토큰 생성](https://github.com/settings/tokens)
2. `.cursor/mcp/github.json` 파일에서 `GITHUB_PERSONAL_ACCESS_TOKEN` 값 업데이트

### 2. MCP 활성화

Cursor IDE에서 MCP 서버를 활성화하는 방법:

1. Cursor IDE 실행
2. 설정(⚙️) > 기능(Features) > MCP 메뉴로 이동
3. 설정된 MCP 서버가 목록에 표시되는지 확인
4. 필요한 경우 각 서버의 활성화 여부 설정

## MCP 사용 방법

MCP를 사용하여 AI 도우미와 대화할 때:

1. 채팅 창에서 직접 MCP 도구 사용을 언급:
   - "GitHub에서 이 코드의 문제점을 찾아줘"
   - "이 파일을 다음과 같이 수정해줘"
   - "이전 대화 내용을 기억해줘"

2. AI는 적절한 MCP 도구를 자동으로 선택하여 작업을 수행합니다.

3. 도구 승인:
   - 기본적으로 AI가 MCP 도구를 사용할 때는 사용자 승인이 필요합니다
   - 설정에서 자동 실행(Auto-run)을 활성화하면 승인 없이 자동 실행됩니다

## 추가 MCP 서버 설치

새로운 MCP 서버를 추가하는 방법:

1. `.cursor/mcp/` 디렉토리에 새 JSON 설정 파일 생성
2. 프로젝트 전체에 적용하려면 `.cursor/mcp.json` 파일 업데이트
3. 전역 설정을 위해서는 `%USERPROFILE%\.cursor\mcp.json` 파일 업데이트 (Windows)

## 참고 자료

- [Model Context Protocol 공식 문서](https://modelcontextprotocol.io/)
- [Cursor MCP 문서](https://docs.cursor.com/context/model-context-protocol)
- [MCP 서버 목록](https://github.com/modelcontextprotocol/servers) 