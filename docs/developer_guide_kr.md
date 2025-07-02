## Korean: 개발자 빠른 시작 가이드

### 1. API 서버 실행

```bash
python run_local.py
```

* 환경 변수는 현재 PROFILE(`.env.*` 파일 참고)에 맞게 로드됩니다.

### 2. Celery 워커 실행

**일반 실행:**

```bash
python worker.py
```

* 백그라운드 작업을 처리하는 Celery 워커를 실행합니다.
* Redis가 필요하다면 로컬에서 반드시 실행되어야 합니다.

**디버깅(예: PyCharm 등)용:**

* IDE에서 `worker.py`를 엽니다.
* 브레이크포인트를 원하는 위치에 설정합니다.
* IDE에서 `worker.py`를 실행하거나 디버깅합니다.
* **주의:** 워커가 작업을 처리할 때만 브레이크포인트가 걸립니다(API 호출 시가 아님).

### 3. Swagger UI 접속

* [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) 접속
* "Try it out" 버튼이나 Postman/curl로 테스트

### 4. 백테스트 작업 제출

* `/backtest` 엔드포인트(Swagger UI 또는 Postman 사용)
* 구성 입력 후 제출
* API에서 `task_id` 반환

### 5. 작업 상태/결과 확인

* `/tasks/{task_id}` (GET)으로 상태/결과 확인
* 상태: `pending`, `started`, `success`, `failure`

### 6. 디버깅 및 로그

* 결과는 준비되면 브라우저나 Postman에서 확인
* **디버깅:**

    * IDE의 브레이크포인트는 Celery 워커가 작업을 실행할 때만 동작
    * 에러/스택트레이스는 워커가 실행 중인 터미널 또는 IDE 콘솔에 출력
    * 실패/대기 중인 작업은 워커 로그/콘솔을 확인
    * 에러 처리가 미흡하여 작업이 무한 대기하거나 최소한의 에러 정보만 표시될 수 있음

### 7. 참고 사항

* `/backtest`만 정상적으로 테스트 완료
* 더 견고한 에러 처리는 추후 업데이트 예정
* 문제 발생 시:

    * `run_local.py`와 `worker.py` 모두 실행중인지 확인
    * Redis, MongoDB 등 의존 서비스가 실행 중인지 확인
    * 워커 로그에서 에러/스택트레이스 확인
    * 작업이 멈출 경우 워커 재시작

---

피드백, 이슈 제보, PR 부탁
