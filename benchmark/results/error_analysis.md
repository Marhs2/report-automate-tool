# 오차 정성 분석 (모델별 최저 점수 케이스)

## nuextract3

### D22 (메신저체) — 케이스 F1 0.0%, parse=None

원문:
```
[18:05] 박서연: 마이페이지 프로필 영역 퍼블리싱 완료했습니다
[18:06] 박서연: 활동 내역 탭은 아직 작업 중이에요
[18:07] 팀장: 디자인 QA는 언제 가능해요?
[18:08] 박서연: 활동 내역까지 끝나면 목요일에 요청드릴 수 있을 것 같습니다
[18:09] 박서연: 그리고 기획팀에 마이페이지 노출 항목 최종 확정 부탁드립니다
```
정답:
```
  - projectName: '여우비'
      completedTasks: ['마이페이지 프로필 영역 퍼블리싱 완료']
      inProgressTasks: ['마이페이지 활동 내역 탭 작업 중']
      requests: ['기획팀에 마이페이지 노출 항목 최종 확정 요청']
      nextPlans: ['목요일 디자인 QA 요청 예정']
```
예측:
```
  - projectName: '마이페이지'
      completedTasks: ['프로필 영역 퍼블리싱 완료']
      inProgressTasks: ['활동 내역 탭 작업 중']
      requests: ['마이페이지 노출 항목 최종 확정 요청']
```

### D25 (한 줄) — 케이스 F1 0.0%, parse=None

원문:
```
Yak-Map monitoring dashboard 알림 규칙 설정 완료했습니다.
```
정답:
```
  - projectName: 'Yak-Map'
      completedTasks: ['monitoring dashboard 알림 규칙 설정 완료']
```
예측:
```
  - projectName: 'Yak-Map'
      completedTasks: ['모니터링 대시보드 알림 규칙 설정']
```

### D11 (줄글 + 영문 혼합) — 케이스 F1 22.2%, parse=None

원문:
```
Yak-Map CI pipeline에 dependency cache를 적용해서 build time을 8분에서 3분으로 줄였습니다. 여우비 staging Nginx 설정은 아직 진행 중이고, SSL 인증서 갱신은 인프라 담당자 회신 대기 중이라 blocked 상태입니다. 보안팀에 방화벽 정책 추가 승인 요청드립니다. 다음 주에는 monitoring dashboard를 구성할 계획입니다.
```
정답:
```
  - projectName: 'Yak-Map'
      completedTasks: ['CI pipeline dependency cache 적용으로 build time 8분에서 3분으로 단축']
  - projectName: '여우비'
      inProgressTasks: ['staging Nginx 설정 진행 중']
      issues: ['SSL 인증서 갱신이 인프라 담당자 회신 대기로 blocked [미해결]']
      requests: ['보안팀에 방화벽 정책 추가 승인 요청']
      nextPlans: ['다음 주 monitoring dashboard 구성 계획']
```
예측:
```
  - projectName: 'Yak-Map CI pipeline'
      completedTasks: ['dependency cache 적용']
  - projectName: '여우비 staging Nginx 설정'
      inProgressTasks: ['Nginx 설정 진행 중']
      issues: ['SSL 인증서 갱신 대기 [미해결]']
  - projectName: '보안팀 방화벽 정책 추가 승인 요청'
      requests: ['방화벽 정책 추가 승인 요청']
```

## google/gemma-4-e2b

### D22 (메신저체) — 케이스 F1 0.0%, parse=None

원문:
```
[18:05] 박서연: 마이페이지 프로필 영역 퍼블리싱 완료했습니다
[18:06] 박서연: 활동 내역 탭은 아직 작업 중이에요
[18:07] 팀장: 디자인 QA는 언제 가능해요?
[18:08] 박서연: 활동 내역까지 끝나면 목요일에 요청드릴 수 있을 것 같습니다
[18:09] 박서연: 그리고 기획팀에 마이페이지 노출 항목 최종 확정 부탁드립니다
```
정답:
```
  - projectName: '여우비'
      completedTasks: ['마이페이지 프로필 영역 퍼블리싱 완료']
      inProgressTasks: ['마이페이지 활동 내역 탭 작업 중']
      requests: ['기획팀에 마이페이지 노출 항목 최종 확정 요청']
      nextPlans: ['목요일 디자인 QA 요청 예정']
```
예측:
```
  - projectName: '마이페이지'
      completedTasks: ['프로필 영역 퍼블리싱 완료']
      inProgressTasks: ['활동 내역 작업 중']
      requests: ['기획팀에 마이페이지 노출 항목 최종 확정 부탁드립니다']
      nextPlans: ['목요일에 디자인 QA 요청 예정']
```

### D24 (줄글) — 케이스 F1 0.0%, parse=None

원문:
```
Yak-Map OCR 인식률 케이스 정리를 완료했습니다. 이미지 전처리로 대비를 높이면 인식률이 40%에서 72%까지 올라가는 것을 확인했으나, 정식 적용 여부는 개발팀 검토가 필요해 미결정 상태입니다. 여우비 포인트 적립/사용 시나리오 테스트는 진행 중입니다. 내일은 여우비 마이페이지 테스트 케이스를 작성할 예정입니다.
```
정답:
```
  - projectName: 'Yak-Map'
      completedTasks: ['OCR 인식률 케이스 정리 완료', '이미지 전처리로 대비 상향 시 인식률 40%에서 72%로 개선되는 것 확인']
      issues: ['이미지 전처리 정식 적용 여부가 개발팀 검토 필요로 미결정 [미해결]']
  - projectName: '여우비'
      inProgressTasks: ['포인트 적립/사용 시나리오 테스트 진행 중']
      nextPlans: ['내일 마이페이지 테스트 케이스 작성 예정']
```
예측:
```
  - projectName: '미분류 프로젝트'
      completedTasks: ['Yak-Map OCR 인식률 케이스 정리 완료']
      inProgressTasks: ['여우비 포인트 적립/사용 시나리오 테스트 진행 중']
      issues: ['이미지 전처리로 대비를 높이면 인식률이 40%에서 72%까지 올라가는 것을 확인했으나, 정식 적용 여부는 개발팀 검토가 필요해 미결정 상태입니다. [미해결]']
      nextPlans: ['내일 여우비 마이페이지 테스트 케이스 작성 예정']
```

### D05 (줄글) — 케이스 F1 20.0%, parse=None

원문:
```
여우비 포인트 사용 내역 화면 퍼블리싱을 시작했는데 디자인 시안이 확정되지 않아 일단 보류했습니다. 대신 회원가입 유효성 검사 문구를 수정 완료했습니다. Yak-Map 약국 지도 화면에서 위치 권한을 거부한 사용자에게 빈 화면이 나오는 버그가 있어 원인 확인 중입니다. 기획팀에 권한 거부 시 안내 문구 확정 요청드립니다.
```
정답:
```
  - projectName: '여우비'
      completedTasks: ['회원가입 유효성 검사 문구 수정 완료']
      issues: ['포인트 사용 내역 화면 퍼블리싱 디자인 시안 미확정으로 보류 [미해결]']
  - projectName: 'Yak-Map'
      inProgressTasks: ['약국 지도 화면 위치 권한 거부 시 빈 화면 버그 원인 확인 중']
      issues: ['위치 권한 거부 사용자에게 빈 화면이 표시되는 버그 [미해결]']
      requests: ['기획팀에 위치 권한 거부 시 안내 문구 확정 요청']
```
예측:
```
  - projectName: '여우비'
      completedTasks: ['회원가입 유효성 검사 문구 수정 완료']
      inProgressTasks: ['포인트 사용 내역 화면 퍼블리싱 시작']
      issues: ['Yak-Map 약국 지도 화면에서 위치 권한을 거부한 사용자에게 빈 화면이 나오는 버그 [미해결]']
      requests: ['기획팀에 권한 거부 시 안내 문구 확정 요청']
      nextPlans: ['디자인 시안 확정 대기']
```

## qwen3.5-4b

### D22 (메신저체) — 케이스 F1 0.0%, parse=None

원문:
```
[18:05] 박서연: 마이페이지 프로필 영역 퍼블리싱 완료했습니다
[18:06] 박서연: 활동 내역 탭은 아직 작업 중이에요
[18:07] 팀장: 디자인 QA는 언제 가능해요?
[18:08] 박서연: 활동 내역까지 끝나면 목요일에 요청드릴 수 있을 것 같습니다
[18:09] 박서연: 그리고 기획팀에 마이페이지 노출 항목 최종 확정 부탁드립니다
```
정답:
```
  - projectName: '여우비'
      completedTasks: ['마이페이지 프로필 영역 퍼블리싱 완료']
      inProgressTasks: ['마이페이지 활동 내역 탭 작업 중']
      requests: ['기획팀에 마이페이지 노출 항목 최종 확정 요청']
      nextPlans: ['목요일 디자인 QA 요청 예정']
```
예측:
```
  - projectName: '마이페이지'
      completedTasks: ['프로필 영역 퍼블리싱 완료']
      inProgressTasks: ['활동 내역 탭 작업 중']
      requests: ['기획팀 마이페이지 노출 항목 최종 확정 요청']
      nextPlans: ['목요일 활동 내역 완료 후 디자인 QA 요청']
```

### D25 (한 줄) — 케이스 F1 0.0%, parse=None

원문:
```
Yak-Map monitoring dashboard 알림 규칙 설정 완료했습니다.
```
정답:
```
  - projectName: 'Yak-Map'
      completedTasks: ['monitoring dashboard 알림 규칙 설정 완료']
```
예측:
```
  - projectName: 'Yak-Map'
      completedTasks: ['모니터링 대시보드 알림 규칙 설정 완료']
```

### D11 (줄글 + 영문 혼합) — 케이스 F1 20.0%, parse=None

원문:
```
Yak-Map CI pipeline에 dependency cache를 적용해서 build time을 8분에서 3분으로 줄였습니다. 여우비 staging Nginx 설정은 아직 진행 중이고, SSL 인증서 갱신은 인프라 담당자 회신 대기 중이라 blocked 상태입니다. 보안팀에 방화벽 정책 추가 승인 요청드립니다. 다음 주에는 monitoring dashboard를 구성할 계획입니다.
```
정답:
```
  - projectName: 'Yak-Map'
      completedTasks: ['CI pipeline dependency cache 적용으로 build time 8분에서 3분으로 단축']
  - projectName: '여우비'
      inProgressTasks: ['staging Nginx 설정 진행 중']
      issues: ['SSL 인증서 갱신이 인프라 담당자 회신 대기로 blocked [미해결]']
      requests: ['보안팀에 방화벽 정책 추가 승인 요청']
      nextPlans: ['다음 주 monitoring dashboard 구성 계획']
```
예측:
```
  - projectName: 'Yak-Map CI pipeline'
      completedTasks: ['dependency cache 적용으로 build time 8분에서 3분으로 줄임']
      inProgressTasks: ['Nginx 설정 진행 중']
      issues: ['SSL 인증서 갱신 대기 (인프라 담당자 회신 없음) [미해결]']
      requests: ['방화벽 정책 추가 승인 요청 (보안팀)']
      nextPlans: ['다음 주 monitoring dashboard 구성']
```

## nvidia/nemotron-3-nano-4b

### D03 (메신저체) — 케이스 F1 0.0%, parse=None

원문:
```
[17:58] 팀장: 준호님 오늘 Yak-Map 테스트 어디까지 됐어요?
[17:59] 이준호: 약품 검색 API 캐싱 적용분 회귀 테스트 완료했습니다.
[18:00] 이준호: 처방전 OCR 결과 저장 로직은 아직 확인 중입니다.
[18:01] 팀장: 영문 검색은요?
[18:02] 이준호: 영문 약품명 검색 정확도가 낮게 나와서 그건 미해결입니다.
[18:03] 이준호: 내일 테스트 케이스 추가해서 다시 돌려보겠습니다.
[18:04] 팀장: 네 수고하셨습니다
```
정답:
```
  - projectName: 'Yak-Map'
      completedTasks: ['약품 검색 API 캐싱 적용분 회귀 테스트 완료']
      inProgressTasks: ['처방전 OCR 결과 저장 로직 확인 중']
      issues: ['영문 약품명 검색 정확도가 낮음 [미해결]']
      nextPlans: ['내일 테스트 케이스 추가 후 재테스트 예정']
```
예측:
```
  - projectName: '미분류 프로젝트'
      completedTasks: ['약품 검색 API 캐싱 적용분 회귀 테스트 완료']
      inProgressTasks: ['처방전 OCR 결과 저장 로직 확인 중', '영문 약품명 검색 정확도 미해결']
      issues: ['영문 약품명 검색 정확도가 낮게 나와서 미해결 [미해결]']
      nextPlans: ['내일 테스트 케이스 추가해서 다시 돌려보겠습니다']
```

### D22 (메신저체) — 케이스 F1 0.0%, parse=None

원문:
```
[18:05] 박서연: 마이페이지 프로필 영역 퍼블리싱 완료했습니다
[18:06] 박서연: 활동 내역 탭은 아직 작업 중이에요
[18:07] 팀장: 디자인 QA는 언제 가능해요?
[18:08] 박서연: 활동 내역까지 끝나면 목요일에 요청드릴 수 있을 것 같습니다
[18:09] 박서연: 그리고 기획팀에 마이페이지 노출 항목 최종 확정 부탁드립니다
```
정답:
```
  - projectName: '여우비'
      completedTasks: ['마이페이지 프로필 영역 퍼블리싱 완료']
      inProgressTasks: ['마이페이지 활동 내역 탭 작업 중']
      requests: ['기획팀에 마이페이지 노출 항목 최종 확정 요청']
      nextPlans: ['목요일 디자인 QA 요청 예정']
```
예측:
```
  - projectName: '미분류 프로젝트'
      completedTasks: ['마이페이지 프로필 영역 퍼블리싱 완료']
      inProgressTasks: ['활동 내역 탭 작업 중', '목요일에 요청드릴 수 있을 것 같습니다']
      requests: ['디자인 QA 언제 가능해요?', '기획팀에 마이페이지 노출 항목 최종 확정 부탁드립니다']
```

### D25 (한 줄) — 케이스 F1 0.0%, parse=None

원문:
```
Yak-Map monitoring dashboard 알림 규칙 설정 완료했습니다.
```
정답:
```
  - projectName: 'Yak-Map'
      completedTasks: ['monitoring dashboard 알림 규칙 설정 완료']
```
예측:
```
  (없음)
```

## kanana-2-3b-instruct-i1

### D03 (메신저체) — 케이스 F1 0.0%, parse=None

원문:
```
[17:58] 팀장: 준호님 오늘 Yak-Map 테스트 어디까지 됐어요?
[17:59] 이준호: 약품 검색 API 캐싱 적용분 회귀 테스트 완료했습니다.
[18:00] 이준호: 처방전 OCR 결과 저장 로직은 아직 확인 중입니다.
[18:01] 팀장: 영문 검색은요?
[18:02] 이준호: 영문 약품명 검색 정확도가 낮게 나와서 그건 미해결입니다.
[18:03] 이준호: 내일 테스트 케이스 추가해서 다시 돌려보겠습니다.
[18:04] 팀장: 네 수고하셨습니다
```
정답:
```
  - projectName: 'Yak-Map'
      completedTasks: ['약품 검색 API 캐싱 적용분 회귀 테스트 완료']
      inProgressTasks: ['처방전 OCR 결과 저장 로직 확인 중']
      issues: ['영문 약품명 검색 정확도가 낮음 [미해결]']
      nextPlans: ['내일 테스트 케이스 추가 후 재테스트 예정']
```
예측:
```
  - projectName: '미분류 프로젝트'
      completedTasks: ['약품 검색 API 캐싱 적용분 회귀 테스트 완료']
      inProgressTasks: ['처방전 OCR 결과 저장 로직 확인 중']
      issues: ['영문 약품명 검색 정확도 저하 발생 [미해결]']
      nextPlans: ['내일 추가 테스트 예정']
```

### D08 (개조식) — 케이스 F1 0.0%, parse=None

원문:
```
Yak-Map 테스트
- 약국 검색 결과 정렬 테스트 케이스 12건 작성 완료
- 영문 약품명 검색 정확도 재측정 진행 중
- 처방전 OCR 인식률이 흐린 이미지에서 40% 이하로 떨어지는 문제
- 백엔드팀에 OCR 원본 로그 공유 요청
여우비
- 회원가입 시나리오 테스트 완료
```
정답:
```
  - projectName: 'Yak-Map'
      completedTasks: ['약국 검색 결과 정렬 테스트 케이스 12건 작성 완료']
      inProgressTasks: ['영문 약품명 검색 정확도 재측정 진행 중']
      issues: ['흐린 이미지에서 처방전 OCR 인식률이 40% 이하로 떨어지는 문제 [미해결]']
      requests: ['백엔드팀에 OCR 원본 로그 공유 요청']
  - projectName: '여우비'
      completedTasks: ['회원가입 시나리오 테스트 완료']
```
예측:
```
  - projectName: '약국'
      completedTasks: ['검색 결과 정렬 테스트 케이스 작성 완료']
      inProgressTasks: ['영문 약품명 검색 정확도 재측정 진행 중']
      requests: ['백엔드팀에 OCR 원본 로그 공유 요청']
  - projectName: '여우비'
      inProgressTasks: ['회원가입 시나리오 테스트 완료']
```

### D09 (한 줄) — 케이스 F1 0.0%, parse=None

원문:
```
여우비 포인트 사용 내역 화면 퍼블리싱 완료했습니다.
```
정답:
```
  - projectName: '여우비'
      completedTasks: ['포인트 사용 내역 화면 퍼블리싱 완료']
```
예측:
```
  - projectName: '미분류 프로젝트'
      completedTasks: ['포인트 사용 내역 화면 퍼블리싱 완료']
```

## lfm2.5-8b-a1b

### D01 (개조식) — 케이스 F1 0.0%, parse=None

원문:
```
[A사 MES]
- 설비 데이터 수집 배치 개발 완료
- 실시간 알림 이력 화면 개발 중
- PLC 연결이 2시간마다 끊기는 문제 발생, 원인 확인 필요
- 현장 담당자에게 PLC 로그 파일 전달 요청드립니다
- 내일 알림 조건 설정 화면 착수 예정
```
정답:
```
  - projectName: 'A사 MES'
      completedTasks: ['설비 데이터 수집 배치 개발 완료']
      inProgressTasks: ['실시간 알림 이력 화면 개발 중']
      issues: ['PLC 연결이 2시간마다 끊기는 문제 [미해결]']
      requests: ['현장 담당자에게 PLC 로그 파일 전달 요청']
      nextPlans: ['내일 알림 조건 설정 화면 착수 예정']
```
예측:
```
  - projectName: 'MES'
      completedTasks: ['로그인 오류 수정', 'API 연동 테스트 완료']
      inProgressTasks: ['결제 모듈은 스펙 확인 중']
      requests: ['QA 일정 공유 부탁드립니다']
      nextPlans: ['내일 스테이징 배포 예정']
```

### D03 (메신저체) — 케이스 F1 0.0%, parse=None

원문:
```
[17:58] 팀장: 준호님 오늘 Yak-Map 테스트 어디까지 됐어요?
[17:59] 이준호: 약품 검색 API 캐싱 적용분 회귀 테스트 완료했습니다.
[18:00] 이준호: 처방전 OCR 결과 저장 로직은 아직 확인 중입니다.
[18:01] 팀장: 영문 검색은요?
[18:02] 이준호: 영문 약품명 검색 정확도가 낮게 나와서 그건 미해결입니다.
[18:03] 이준호: 내일 테스트 케이스 추가해서 다시 돌려보겠습니다.
[18:04] 팀장: 네 수고하셨습니다
```
정답:
```
  - projectName: 'Yak-Map'
      completedTasks: ['약품 검색 API 캐싱 적용분 회귀 테스트 완료']
      inProgressTasks: ['처방전 OCR 결과 저장 로직 확인 중']
      issues: ['영문 약품명 검색 정확도가 낮음 [미해결]']
      nextPlans: ['내일 테스트 케이스 추가 후 재테스트 예정']
```
예측:
```
  (없음)
```

### D05 (줄글) — 케이스 F1 0.0%, parse=None

원문:
```
여우비 포인트 사용 내역 화면 퍼블리싱을 시작했는데 디자인 시안이 확정되지 않아 일단 보류했습니다. 대신 회원가입 유효성 검사 문구를 수정 완료했습니다. Yak-Map 약국 지도 화면에서 위치 권한을 거부한 사용자에게 빈 화면이 나오는 버그가 있어 원인 확인 중입니다. 기획팀에 권한 거부 시 안내 문구 확정 요청드립니다.
```
정답:
```
  - projectName: '여우비'
      completedTasks: ['회원가입 유효성 검사 문구 수정 완료']
      issues: ['포인트 사용 내역 화면 퍼블리싱 디자인 시안 미확정으로 보류 [미해결]']
  - projectName: 'Yak-Map'
      inProgressTasks: ['약국 지도 화면 위치 권한 거부 시 빈 화면 버그 원인 확인 중']
      issues: ['위치 권한 거부 사용자에게 빈 화면이 표시되는 버그 [미해결]']
      requests: ['기획팀에 위치 권한 거부 시 안내 문구 확정 요청']
```
예측:
```
  - projectName: '미분류 프로젝트'
      completedTasks: ['회원가입 유효성 검사 문구 수정 완료']
      issues: ['권한 거부 시 안내 문구 확정 요청드립니다 [미해결]']
      requests: ['플랜팀에 권한 거부 시 안내 문구 확정 요청드립니다']
```

## minicpm5-1b

### D03 (메신저체) — 케이스 F1 0.0%, parse=None

원문:
```
[17:58] 팀장: 준호님 오늘 Yak-Map 테스트 어디까지 됐어요?
[17:59] 이준호: 약품 검색 API 캐싱 적용분 회귀 테스트 완료했습니다.
[18:00] 이준호: 처방전 OCR 결과 저장 로직은 아직 확인 중입니다.
[18:01] 팀장: 영문 검색은요?
[18:02] 이준호: 영문 약품명 검색 정확도가 낮게 나와서 그건 미해결입니다.
[18:03] 이준호: 내일 테스트 케이스 추가해서 다시 돌려보겠습니다.
[18:04] 팀장: 네 수고하셨습니다
```
정답:
```
  - projectName: 'Yak-Map'
      completedTasks: ['약품 검색 API 캐싱 적용분 회귀 테스트 완료']
      inProgressTasks: ['처방전 OCR 결과 저장 로직 확인 중']
      issues: ['영문 약품명 검색 정확도가 낮음 [미해결]']
      nextPlans: ['내일 테스트 케이스 추가 후 재테스트 예정']
```
예측:
```
  - projectName: '미분류 프로젝트'
      completedTasks: ['로그인 오류 수정', 'API 연동 테스트 완료']
      inProgressTasks: ['결제 모듈 스펙 확인 중', 'LLM 연동 프로젝트별 업무 자동 추출 기능 개발']
      nextPlans: ['내일 스테이징 배포 예정']
```

### D05 (줄글) — 케이스 F1 0.0%, parse=None

원문:
```
여우비 포인트 사용 내역 화면 퍼블리싱을 시작했는데 디자인 시안이 확정되지 않아 일단 보류했습니다. 대신 회원가입 유효성 검사 문구를 수정 완료했습니다. Yak-Map 약국 지도 화면에서 위치 권한을 거부한 사용자에게 빈 화면이 나오는 버그가 있어 원인 확인 중입니다. 기획팀에 권한 거부 시 안내 문구 확정 요청드립니다.
```
정답:
```
  - projectName: '여우비'
      completedTasks: ['회원가입 유효성 검사 문구 수정 완료']
      issues: ['포인트 사용 내역 화면 퍼블리싱 디자인 시안 미확정으로 보류 [미해결]']
  - projectName: 'Yak-Map'
      inProgressTasks: ['약국 지도 화면 위치 권한 거부 시 빈 화면 버그 원인 확인 중']
      issues: ['위치 권한 거부 사용자에게 빈 화면이 표시되는 버그 [미해결]']
      requests: ['기획팀에 위치 권한 거부 시 안내 문구 확정 요청']
```
예측:
```
  - projectName: '여우비'
```

### D07 (줄글) — 케이스 F1 0.0%, parse=None

원문:
```
A사 MES 실시간 알림 이력 화면 개발을 완료했고, PLC 연결 끊김 문제는 현장에서 받은 로그를 분석해 네트워크 스위치 설정 문제로 확인해 해결했습니다. 알림 조건 설정 화면은 개발 중이며, 내일까지 마무리할 예정입니다. QA팀에 알림 이력 화면 테스트 일정 공유 부탁드립니다.
```
정답:
```
  - projectName: 'A사 MES'
      completedTasks: ['실시간 알림 이력 화면 개발 완료', 'PLC 연결 끊김 문제 원인을 네트워크 스위치 설정으로 확인하고 해결']
      inProgressTasks: ['알림 조건 설정 화면 개발 중']
      requests: ['QA팀에 알림 이력 화면 테스트 일정 공유 요청']
      nextPlans: ['알림 조건 설정 화면 내일까지 마무리 예정']
```
예측:
```
  - projectName: '미분류 프로젝트'
      completedTasks: ['MES 실시간 알림 이력 화면 개발 완료', 'PLC 연결 끊김 문제 해결']
      nextPlans: ['내일 마무리 예정']
```

