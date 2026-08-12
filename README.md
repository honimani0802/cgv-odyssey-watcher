# CGV 용산 IMAX 《오디세이》 취소표 감시기

대상 날짜:
- 2026-08-14
- 2026-08-15
- 2026-08-16
- 2026-08-17
- 2026-08-22
- 2026-08-23

대상:
- CGV 용산아이파크몰
- 영화명: 오디세이
- 상영 포맷: IMAX

## 동작 방식

GitHub Actions가 약 5분마다 공개 CGV 시간표 API를 조회합니다.
잔여 좌석 수가 0석/미확인 상태에서 1석 이상으로 바뀌거나, 기존보다 좌석 수가 증가하면 GitHub Issue를 생성합니다.

GitHub 앱에서 해당 저장소의 Issue 알림을 켜두면 휴대폰 푸시 알림 용도로 사용할 수 있습니다.

> GitHub Actions의 schedule은 정확히 5분마다 보장되는 실시간 타이머가 아니며,
> GitHub 서버 상황에 따라 지연될 수 있습니다.

## 설치

1. 새 GitHub 저장소를 하나 만듭니다.
2. 이 폴더의 전체 파일을 저장소 루트에 업로드합니다.
3. 저장소의 `Settings → Actions → General → Workflow permissions`에서
   `Read and write permissions`를 허용합니다.
4. `Actions` 탭에서 `CGV Odyssey Seat Watcher`를 열고 `Run workflow`로 수동 테스트합니다.
5. 실행 후 `result.json`을 확인합니다.
6. GitHub 모바일 앱에서 이 저장소의 Issue 알림을 켭니다.

## 수동 테스트

```bash
pip install -r requirements.txt
python watcher.py
```

## 주의

- 사용하는 공개 API 서버는 IP당 일일 호출 제한이 있습니다.
- CGV 응답 형식이 바뀌면 파서 수정이 필요할 수 있습니다.
- 실제 예매 가능 여부는 CGV 공식 앱/웹에서 최종 확인해야 합니다.
- 이 프로그램은 예매/결제를 자동 수행하지 않고 좌석 변화만 감지합니다.
