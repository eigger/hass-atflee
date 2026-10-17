# 적용한 공통 규칙

- 표준: https://github.com/eigger/hass-repo-standards/tree/ff46b0c8d9ba53b1d35ab9a4aa38f4db26c06870
- 참조 커밋 SHA: `ff46b0c8d9ba53b1d35ab9a4aa38f4db26c06870` (2026-10-17 원격 main 직접 확인)
- 채택일: 2026-10-17 착수; 독립 로컬 검증 완료; 기본 브랜치 게시·CI 대기
- profile: integration / ha
- 적용 점검표: [ADOPTION_CHECKLIST.md](ADOPTION_CHECKLIST.md)
- 중앙 현황표: https://github.com/eigger/hass-repo-standards/blob/main/docs/adoption-status.md
- 조율 / 구현 / 독립 리뷰·검증: root / atflee_implementation·atflee_docs / review_atflee
- 중앙 현황 갱신: 2026-10-17 진행 중, 시작 commit `451d78896e692d6bda13fdd6230db07759688bb9`; 최종 갱신 대기
- 실제 기본 브랜치: master
- domain / 테스트 경로: atflee / tests/components/atflee/
- 변경 전·후 지원 최소 HA: `hacs.json.homeassistant=2025.8.0` 유지. 기존 README/manifest에 다른 하한 없음. current 도구와 지원 선언 구분
- current 실제 로컬 환경: Python3.14.5 / HA2026.10.2 / pytest-homeassistant-custom-component0.13.373
- 정확한 최소 HA 실제 로컬 환경: Python3.13.14 / HA2025.8.0 / 플러그인0.13.269 (별도 환경)
- 최소 테스트 호환 제약: requirements_test_min.txt의 pycares==4.11.0 (HA2025.8.0/aiodns3.5의 4.x API; 런타임 의존성·지원 최소 변경 아님)
- 최소 package 검증 목표: blesession==0.9.0; manifest blesession>=0.9.0 유지
- 통합 배포 버전: 0.6.1 유지; 적용 작업으로 태그·릴리스 생성하지 않음

## 영향·이관

기존 사용자별 식별·센서/unique ID·entry 스키마·상태/통계 계약을 보존하면서 실제 HA 테스트·공통 CI와 docs 분리를 채택합니다. 사용자 요청의 최초 적용이며 기존 기준을 변경하는 후속 이관이 아닙니다. 이번 기준·문서/CI 실제 내용·미검증은 체크리스트에서 확인합니다. 과거0.3.2 이하 프로필 업그레이드는 [기존 안내](docs/usage.ko.md#032-이하에서-업그레이드)를 보존하며 새 자동 migration을 주장하지 않습니다.

## 예외·미완료

구현4환경 및 독립2환경의 실제 최소/current HA와 blesession0.9.0에서 각179passed(skip0)·pipcheck PASS입니다. 부분setup/GATT취소/최소pycares/options/privacy 지적 수정 후 재검증했습니다. 게시 commit·원격CI·중앙종료보고는 대기이므로 채택 완료로 표시하지 않습니다. 규칙별 상태와 실행 근거는 체크리스트를 따릅니다. 실물 체중계·새 proxy 보드·HA frontend UI는 이번 공통화에서 미검증입니다.

### 브랜드 확인 범위

기존 `custom_components/atflee/brand/icon.png`(PNG256×256 RGBA)·`logo.png`(PNG512×128 RGBA)를 보존합니다. 선택 2x/dark 미제공. 확인된 출처는 eigger가 추가한 [최초 커밋68c355c](https://github.com/eigger/hass-atflee/commit/68c355c97d2e65ee913c4b084c565f96bf50be1c)·[PR #1](https://github.com/eigger/hass-atflee/pull/1)이며 리포 [MIT License](LICENSE)는 Copyright2026eigger이고 별도 자산 제외 문서가 없습니다. 이 근거와 validator 결과를 구분하고 제3자 권리를 별도로 검증했다고 주장하지 않습니다. 최소 HA2025.8의 local brand UI 지원이나 이번 UI 렌더링을 검증했다고 주장하지 않습니다.
