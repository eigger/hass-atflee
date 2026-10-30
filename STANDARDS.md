# 적용한 공통 규칙

- 표준: https://github.com/eigger/hass-repo-standards/tree/v1.1.5
- 참조 커밋 SHA: f56987f7f765a774c926fb8005fe5df68bb32451
- Standards release: v1.1.5
- Resolved standards SHA: f56987f7f765a774c926fb8005fe5df68bb32451
- 채택일: 2026-10-17 착수; 구현4da5699 master 게시·독립 로컬/원격 검증 완료; 마감 문서 commit CI는 별도 확인
- profile: integration / ha
- 적용 점검표: [ADOPTION_CHECKLIST.md](ADOPTION_CHECKLIST.md)
- 중앙 현황표: https://github.com/eigger/hass-repo-standards/blob/main/docs/adoption-status.md
- 조율 / 구현 / 독립 리뷰·검증: root / atflee_implementation·atflee_docs / review_atflee
- 중앙 현황 갱신: 2026-10-17 진행 중, 시작 commit `451d78896e692d6bda13fdd6230db07759688bb9`; 구현/검증 종료보고9941581fe3c4428ddef669a5db028c9dbef3a87a main 반영; 마감 문서CI 후 최종상태 갱신
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

## 예외·검증 결과

구현4환경 및 독립2환경의 실제 최소/current HA와 blesession0.9.0에서 각179passed(skip0)·pipcheck PASS입니다. 부분setup/GATT취소/최소pycares/options/privacy 지적 수정 후 재검증했습니다. 구현 commit `4da5699c75021e272442165473ba6655f9f90e5c`의 [Tests](https://github.com/eigger/hass-atflee/actions/runs/39039498134) 4matrix 각179passed·pipcheck와 [Validate](https://github.com/eigger/hass-atflee/actions/runs/39039498020) HACS9checks·Hassfest를 독립 성공 확인했습니다. 중앙 [구현/검증 종료보고9941581](https://github.com/eigger/hass-repo-standards/commit/9941581fe3c4428ddef669a5db028c9dbef3a87a) main 반영 완료이며 적용 필수 PASS/N/A·현재 예외/TODO는 없습니다. 이 마감 문서를 추가하는 후속 commit의 CI는 별도로 확인한 뒤 중앙 최종상태를 갱신합니다. 규칙별 상태와 실행 근거는 체크리스트를 따릅니다. 실물 체중계·새 proxy 보드·HA frontend UI는 이번 공통화에서 미검증입니다.

### 브랜드 확인 범위

기존 `custom_components/atflee/brand/icon.png`(PNG256×256 RGBA)·`logo.png`(PNG512×128 RGBA)를 보존합니다. 선택 2x/dark 미제공. 확인된 출처는 eigger가 추가한 [최초 커밋68c355c](https://github.com/eigger/hass-atflee/commit/68c355c97d2e65ee913c4b084c565f96bf50be1c)·[PR #1](https://github.com/eigger/hass-atflee/pull/1)이며 리포 [MIT License](LICENSE)는 Copyright2026eigger이고 별도 자산 제외 문서가 없습니다. 이 근거와 validator 결과를 구분하고 제3자 권리를 별도로 검증했다고 주장하지 않습니다. 최소 HA2025.8의 local brand UI 지원이나 이번 UI 렌더링을 검증했다고 주장하지 않습니다.

## 2026-10-23 ZIP release and Downloads update

Base commit: `a568efe9d17d8ecee71d4308004afdf2a17ddafe`. HACS remains Custom. `hacs.json` now selects `atflee.zip`; publishing the next release builds and attaches that integration ZIP through the pinned central action. Analytics Usage is replaced by Downloads. The archive contains tracked integration files at its root. No existing release/tag/assets are modified.

Implementation and review: root; generated release caller reuses the independently reviewed central ZIP contract. Support minimum, manifest, code, dependencies, README body and prior adoption exceptions are preserved. Verification evidence is recorded in ADOPTION_CHECKLIST.md; this scoped update does not establish full standards compliance.

## 2026-10-25 중앙 검사기 갱신

- 검토한 중앙 main: `1863343638014adb8a4001afc8fddc1a27dc500f` (git ls-remote 확인). 이전 기본 기준 `ff46b0c8d9ba53b1d35ab9a4aa38f4db26c06870`의 채택 이력은 위 기록을 보존합니다.
- 모든 중앙 workflow/action pin과 reusable workflow의 standards-ref를 같은 검토 SHA로 맞춥니다. HACS-04는 actions/*의 full SHA 고정을 유지하면서 SHA 값 차이를 허용합니다.
- Validate에 중앙 템플릿의 무조건 실행 standards job을 추가합니다. 기존 HACS/Hassfest와 HA test job 이름·입력은 보존하며, 기본 브랜치를 사용하는 중앙 실행 조건을 적용합니다.
- 통합 코드·런타임 의존성·지원 최소·배포 버전은 이번 변경 대상이 아닙니다. 기존 채택 범위를 전체 완료로 바꾸지 않으며 실제 검증 결과와 남은 항목은 ADOPTION_CHECKLIST.md의 같은 날짜 기록을 참조합니다.


### 2026-10-25 Standards 파일·표시 이름 분리

- 기존 Validate의 중앙 검사 job을 `standards.yml`로 옮기고 workflow/job 표시 이름을 `Standards`로 줄였습니다. Validate의 HACS/Hassfest, 검사 항목·통과 기준·실행 단계·조건·권한은 유지합니다.
- 위치 인식과 중앙 명명 안내를 맞춘 검토 소스: `ca740d88b32fa5dcbc94c41fce2908450c76ed50` ([중앙 PR #24](https://github.com/eigger/hass-repo-standards/pull/24), 현재 이 PR의 의존 변경). 이전 기준 `1863343638014adb8a4001afc8fddc1a27dc500f`의 검증 이력은 앞 기록으로 보존합니다. 모든 중앙 pin·standards-ref는 같은 새 검토 소스로 맞춥니다.

### 2026-10-25 immutable central release reference migration

- User-requested partial migration: the current central caller references now use immutable `v1.0.0`, resolved to `44349ee5621eea5d80e5c427f7a2435d2c2491bb`. The prior scoped ZIP SHA `ca740d88b32fa5dcbc94c41fce2908450c76ed50` and its validation history above remain historical evidence; release-zip now follows the same current release.
