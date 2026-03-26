# eapproval (전자결재)

Django 기반의 사내 전자결재 샘플 프로젝트입니다.

## 주요 기능
- 문서 기안/상신
- 결재선 처리
  - 협의: 다중 사용자 동시 처리
  - 결재: 순차 처리
  - 수신/열람 처리
- 첨부파일 업로드 및 개별 다운로드
- 첨부파일 ZIP 일괄 다운로드
- 내 문서/결재 대기/수신/완료/반려 목록
- CSV 내보내기
- 상신 후 회수
  - 기안자가 상신 중 또는 반려 상태 문서를 회수하여 임시저장으로 전환
- 재기안
  - 회수한 임시저장 문서를 다시 상신
  - 재기안 전 문서 내용/결재선 수정 화면 제공
  - 재기안 수정 화면에서 기존 첨부파일 선택 삭제 지원

## 기술 스택
- Python
- Django
- SQLite (기본)

## 로컬 실행
1. 의존성 설치
```powershell
uv sync
```

2. 마이그레이션
```powershell
uv run python manage.py migrate
```

3. 실행
```powershell
uv run python manage.py runserver
```

## 핵심 도메인 규칙
- 문서 상태: `DRAFT` -> `SUBMITTED`/`IN_PROGRESS` -> `COMPLETED` 또는 `REJECTED`
- 회수: `SUBMITTED`, `IN_PROGRESS`, `REJECTED` 상태에서만 가능
- 재기안: `DRAFT` 상태에서만 가능

## 테스트
```powershell
uv run python manage.py test approvals
```
