# 공통 규칙 적용 체크리스트

이 파일은 hass-atflee의 최초 공통화 점검 기록입니다. 구현 commit의 기본 브랜치 반영·독립 로컬/원격 검증·중앙 구현 종료보고를 마쳤습니다. 이 마감 기록을 추가하는 후속 문서 commit의 CI는 별도로 확인합니다. 실제 근거가 확인되기 전에는 통과로 기록하지 않습니다. [사용법과 판정 기준](https://github.com/eigger/hass-repo-standards/blob/ff46b0c8d9ba53b1d35ab9a4aa38f4db26c06870/docs/checklist.md)을 읽고, 아래 규칙은 `STANDARDS.md`에 기록한 표준 커밋에서 확인합니다. 태그·릴리스 대신 `main`의 검토 커밋을 기준으로 합니다. 규칙·사용법 링크는 검토 SHA로 고정하고 중앙 현황은 최신 main을 확인합니다.

## 검토 대상

| 항목 | 값 |
|---|---|
| 통합 리포 / 실제 기본 브랜치 | eigger/hass-atflee / master (원격 확인) |
| domain / 구현 경로 | atflee / custom_components/atflee/ |
| 검토 대상 통합 커밋 / 채택 PR | 시작865b598 → 검증대상 구현 `4da5699c75021e272442165473ba6655f9f90e5c` master 직접 반영. 이 파일의 마감 기록은 후속 문서 commit으로 별도 게시·검증 |
| 검토한 표준 전체 커밋 SHA | `ff46b0c8d9ba53b1d35ab9a4aa38f4db26c06870` (git ls-remote로 main 확인) |
| 검토일 / 조율 담당 | 2026-10-17 / root |
| 구현 서브 에이전트 / 독립 리뷰·검증 서브 에이전트 | atflee_implementation·atflee_docs / review_atflee |
| 중앙 현황표 반영일 / 기록 | 2026-10-17 시작451d788·단계db1ea98·구현/검증 종료보고 `9941581fe3c4428ddef669a5db028c9dbef3a87a` main 반영. 마감 문서SHA 검증 후 중앙 전체 완료 상태 갱신 |
| 변경 전 지원 최소 HA / 근거 파일(hacs.json·manifest·README) | hacs.json.homeassistant=2025.8.0; 기존 README/manifest에 별도 HA 하한 없음 |
| 유지·변경할 지원 최소 / 변경 시 실제 비호환 근거·명시적 승인 | 2025.8.0 유지; 하한 상향 없음. 통합0.6.1·blesession>=0.9.0 유지 |
| current 테스트 HA / 호환 Python·플러그인 | HA2026.10.2 / Python3.14.5 / 플러그인0.13.373 실제 설치·독립179passed |
| 최소 테스트 HA / 호환 Python·플러그인 | HA2025.8.0 / Python3.13.14 / 플러그인0.13.269 별도 실제설치·독립179passed |
| profile / 테스트 경로 | integration / ha; tests/components/atflee/ |
| 이전 검토 기록 | 최초 채택; 기존 README 상세 내용을 docs/usage.md·usage.ko.md로 보존 |
| 채택 판정 | 구현4da5699 기준 적용 필수 PASS/N/A, 예외/TODO 없음. 이 마감 문서 commit 원격 CI와 중앙 최종 완료 상태는 게시 후 별도 확인 |

상태: `TODO` = 미확인·미충족, `PASS` = 근거로 확인, `EXCEPTION` = 적용 대상의 기록된 예외, `N/A` = 적용 조건에 해당 없음. 모든 항목은 미확인으로 시작합니다. `TODO`를 해당 없음으로 처리하지 않습니다. 묶은 규칙의 결과가 다르면 행을 나눕니다. 권장 항목은 별도로 표시했으며 미채택 이유를 기록합니다.

## 채택·구조·사용자 데이터

| 규칙 ID | 확인 항목 | 상태 | 근거 / 남은 작업 |
|---|---|---|---|
| GOV-01, GOV-02 | `STANDARDS.md`에 표준 SHA·profile·실제 기본 브랜치·예외 기록, workflow/action은 검토 SHA로 고정 | PASS | STANDARDS.md에 기준ff46b0c8d9ba53b1d35ab9a4aa38f4db26c06870·integration/ha·master·검증 범위 기록、3 caller full SHA고정 |
| GOV-03 | 새 표준 채택 변경의 영향·이관 방법과 명시적 채택 PR 확인. 규칙 자체를 변경하면 공통 CHANGELOG 기록 | PASS | 최초 채택이며 중앙 규칙 변경 없음. 기존 직접 push 권한에 따른 master4da5699 게시 완료; 기존 기준 후속 변경의 채택 PR 조건과 구분. 영향·이관은 STANDARDS/개발문서 기록 |
| GOV-04 | 중앙 표에 작업 시작·단계 변경·종료 상태, 담당·적용 내용·검증/리뷰 근거·남은 작업 갱신, 타 리포 기록 보존 | PASS | 중앙 시작451d788·단계db1ea98·[구현/검증 종료보고9941581](https://github.com/eigger/hass-repo-standards/commit/9941581fe3c4428ddef669a5db028c9dbef3a87a) main 반영. 구현4da5699의 Tests/Validate 실제 독립성공·담당/범위/실측/미검증 기록. 타리포행 불변. 이 마감 문서SHA의 CI 확인 후 중앙 최종상태 갱신 |
| GOV-05 | 구현과 독립 리뷰·검증을 별도 서브 에이전트에게 위임, 지적 수정·재검증 및 결과 취합 | PASS | 구현 atflee_implementation·문서 atflee_docs / 독립 review_atflee 분리. 부분 setup·GATT취소·최소pycares·options reload·privacy 지적 수정 후 양HA 각179passed 재검증 완료 |
| HA-01, HA-13 | `custom_components/<domain>/`와 domain 일치, 필요한 모듈·공개 API·생명주기는 Core 대응 구조 | PASS | custom_components/atflee와 domain/const 일치. config_flow/coordinator/entity/platform/atflee_ble 역할 유지; 실제 entry setup/unload·4플랫폼·registry 테스트 |
| HA-02 | manifest 필드·정렬·동작 선언 확인, 공식 품질 등급 자가 표기 없음 | PASS | manifest 정렬·device/local_push/config_flow/bluetooth 발견·runtime0.6.1 유지. 사용하는 HA manager domain을 dependencies bluetooth로 정정; 공식 quality_scale 주장 없음 |
| HA-03 (권장) | 공통 상수·설정·갱신·플랫폼 역할 및 프로토콜 경계에 맞게 모듈 구성 | PASS | 기존 const/config_flow/coordinator/platform/atflee_ble·평가/사용자 프로필 경계 유지. 실HA 및 기존 프로토콜 회귀 통과 |
| HA-04, HA-08 | UI 설정·중복·안정적 식별 및 기능별 options/reauth/reconfigure, entity 의미·registry 영향 확인 | PASS | 실 flow manager 성공·manual/discovery/no_devices/duplicate·options live/reload·사용자 subentry 추가/재설정, entity/device registry·사용자 격리·state/action 검증 |
| HA-01, HA-04, HA-08, REL-01, REL-03 | domain·unique ID·entry schema·상태/통계 계약 변경 시 migration 테스트와 사용자 조치 안내 | PASS | domain·uniqueID·entry schema·상태/통계 계약 변경 없음. test_existing_v1_entry_without_users 및 상태/registry·기존복원 회귀. 기존0.3.2 이하 수동 사용자 추가 안내 보존; 새 migration 만들지 않음 |
| HA-05, HA-06 | setup 실패 구분, unload/reload·부분 실패의 task/listener/연결 정리, async·timeout·취소 처리 | PASS | test_partial_start_cleanup 실패/취소·failed_first_refresh·partial_forward_failure·real_bluetooth_session_notification_and_unload. 장기세션 background task·device info task await·bounded disconnect·부분setup 정리 독립 양HA 검증 |
| HA-07 | 중복 polling·property I/O 방지, push 보존, unavailable/unknown·실패 후 복구 | PASS | local_push 보존, property I/O 없음. 실제 Bluetooth manager 광고→GATT notify→패킷·사용자별 HA상태·unload/복구 검사, 기존status unknown/raw 유지 |
| HA-11, HA-12 | 번역·action/schema 일치, 로그/diagnostics/fixture 비식별화와 제공 시 redaction 테스트 | PASS | 기존 strings/en/ko parity 회귀 유지. 통합 logger에서 주소/이름/체중/hex 제거, 외부예외는 type만. 기존 HA private entity state 계약 보존; privacy logger회귀로 제3자예외까지 재검증. diagnostics 다운로드 제공없음 |

## 실제 HA 테스트·호환성·의존성

| 규칙 ID | 확인 항목 | 상태 | 근거 / 남은 작업 |
|---|---|---|---|
| TEST-08 | `tests/components/<domain>/`에 구현과 대응하는 테스트·domain fixture 배치, discovery·CI 경로 일치 | PASS | 기존109 test함수(156 parametrized case) 전부 tests/components/atflee/로 보존, tests/conftest.py·pyproject/CI discovery 동일. 신규실HA23 포함 총179 |
| TEST-02, TEST-03, DEP-07 | 실제 HA·호환 플러그인과 `hass`/`enable_custom_integrations` fixture 사용, HA core stub/복사본/`--no-deps`로 대체하지 않음 | PASS | 실제 HA·호환 플러그인·hass/enable_custom_integrations/MockConfigEntry 사용. FakeHass·가짜homeassistant·--no-deps 없음. 4구현/2독립 환경 installer·pipcheck 및 테스트 PASS |
| TEST-09 | 실제 loader·config entry manager로 setup/플랫폼 로딩, HA 상태·registry·service/action으로 결과 검증 | PASS | test_init/config_flow/platforms에서 실제 hass.config_entries manager·loader·4platform·registry·state·switch/select action·사용자 subentry 로딩. 실제 HA Bluetooth manager와 외부GATT경계 응답 사용 |
| TEST-01, TEST-06, TEST-07 | 구현 기능별 성공·실패·중복·migration·unload·복구 회귀 검증, 외부 통신 경계만 mock, skip 사유 | PASS | 기존156+신규23 총179passed skip0 양HA. 설정 성공/실패/중복·options/subentry·setup/unload·부분실패취소·버전1·상태/개별사용자·동적bodyfat/status·persist/remove·GATT notify/취소·privacy회귀. 인증/reauth기능 없음 |
| TEST-04, HACS-01 | 변경 전 지원 최소·current·각 Python/플러그인 분리, 선언한 정확한 최소 검증, 상향 시 비호환 근거·명시적 승인 확인 | PASS | 지원최소 hacs2025.8.0 유지, 정확최소 Py3.13.14/HA2025.8.0/plugin.269; current Py3.14.5/HA2026.10.2/plugin.373. 독립 각179passed·pipcheck PASS. test requirements와 지원범위 분리 |
| TEST-05, HA-10, DEP-02, DEP-05 | imagespec·blesession 등 최소/현재 라이브러리 별도 환경, 실제 HA 테스트·정확한 설치값·API 경계 검증 | PASS | manifest blesession>=0.9.0 연산자 유지·공개 API. 구현 각HA current/minimum 4독립venv 각179passed; 독립 양HA minimum installer exact0.9.0 확인·각179passed. current resolver도0.9.0 선택; 축 구분 |
| DEP-01, DEP-06 | Python runtime은 manifest requirements, HA domain은 dependencies/after_dependencies, 테스트·린트 requirements는 별도 | PASS | runtime manifest blesession>=0.9.0; 실제 선행 HA domain bluetooth; 플러그인/HA·최소 호환 pycares 테스트requirements, Ruff requirements_lint로 분리 |
| DEP-07, CI-06 | 실제 사용하는 HA 구성요소의 requirements·필수 재귀 의존성·선택 로딩 경로 설치, resolver·`pip check` 통과 | PASS | 공통 installer가 실제 HA의 bluetooth recorder sensor binary_sensor select switch·재귀의존 설치. 구현4환경/독립2환경 resolver·pipcheck PASS; 최소 aiodns3.5와 pycares4.11 호환고정 |
| DEP-02, DEP-03, DEP-08 | 의존성 추가/변경의 버전·extras·marker·선언 위치·지원 플랫폼·라이선스 검토, 실제 HA 테스트와 문서 갱신 | PASS | 새runtime추가/하한/extra/marker변경없음. HA domain만 bluetooth 정정; 실제HA/플러그인·최소pycares4.11 테스트전용 설치. 기존HA전이의존 pycares의 테스트 호환값 고정이며 새 배포runtime 패키지 없음; 실제 macOS arm64/Python조합 설치확인; 배포runtime불변 |

독립 리뷰는 변경 전후 지원 최소와 current를 비교하고, 봇 PR이 과거 최소 requirements·constraints까지 갱신하거나 expected-ha-version·Python을 누락하지 않았는지 확인합니다. 최신 테스트 실패는 호환 수정 대상으로 처리합니다.

환경마다 아래 행을 복사합니다. 최소 HA와 최소 라이브러리 검증을 혼동하지 않고, marker가 활성인 환경에서 대상 패키지 설치값을 확인합니다. 실행하지 않은 조합은 `TODO` 또는 근거가 있는 `EXCEPTION`으로 남깁니다.

| 검증 축 / 상태 | 통합 커밋 | Python / HA / 플러그인 실제 버전 | 대상 패키지 실제 버전·extras·marker | 명령·테스트 결과·pip check / CI run·job | skip·제외·미검증 범위 |
|---|---|---|---|---|---|
| current HA / 로컬 PASS | 구현4da5699 | Python3.14.5 / HA2026.10.2 / 플러그인0.13.373 | blesession0.9.0 / pycares5.2.0 | 구현 current/minimum 별도 venv 각179passed; 독립 minimum installer 후179passed·pipcheck PASS | skip0; 실물/UI미검증 |
| 정확한 최소 HA / 로컬 PASS | 구현4da5699 | Python3.13.14 / HA2025.8.0 / 플러그인0.13.269 | blesession0.9.0 / pycares4.11.0 | 구현 current/minimum 별도 venv 각179passed; 독립 minimum installer 후179passed·pipcheck PASS | skip0; 실물/UI미검증 |
| 정확한 최소 라이브러리 / 로컬 PASS | 구현4da5699 | 위 두 HA 별도 환경 | blesession==0.9.0, extras/marker 없음 | INPUT_DEPENDENCY_MODE=minimum·INPUT_MINIMUM_PACKAGES='["blesession"]' installer 설치값 확인, 위179개 검사 | current resolver도0.9.0 선택; 독립2환경/구현4환경 구분 |

검증 명령은 `docs/development.md`의 freshvenv installer → `python -m pytest tests/components/atflee/ -v` → `python -m pip check`입니다. 독립 로그는 `/tmp/atflee-review-current-pytest-service-final.log`, `/tmp/atflee-review-min-pytest-service-final.log`의 최종179passed 결과입니다. 기존109함수·156case 누락0, 신규23개 포함. 초기156·177·178은 수정 전 중간 결과로 최종 근거를 대체하지 않습니다. 독립 Ruff check/format52files·actionlint·양언어badge·전체상대링크·diffcheck PASS. macOS asyncinotify 플랫폼 안내 및 기존 datetime.utcnow deprecation 경고는 기록하되 실패·skip을 숨기지 않습니다.

## 구현 commit 원격 독립 검증

구현 대상은 [4da5699c75021e272442165473ba6655f9f90e5c](https://github.com/eigger/hass-atflee/commit/4da5699c75021e272442165473ba6655f9f90e5c)입니다. 독립 review_atflee가 해당 head SHA와 실제 로그를 직접 확인했습니다.

- [Tests39039498134](https://github.com/eigger/hass-atflee/actions/runs/39039498134): lint2 + 최소/current HA × 최소/current blesession 4matrix, 각각 **179passed/skip0·pipcheck PASS**.
- 원격 current: Python3.14.8 / HA2026.10.2 / 플러그인0.13.373 / blesession0.9.0 / pycares5.2.0.
- 원격 최소: Python3.13.16 / HA2025.8.0 / 플러그인0.13.269 / blesession0.9.0 / pycares4.11.0.
- [Validate39039498020](https://github.com/eigger/hass-atflee/actions/runs/39039498020): HACS9checks(brands포함)·Hassfest PASS.
- [중앙 구현/검증 종료보고9941581](https://github.com/eigger/hass-repo-standards/commit/9941581fe3c4428ddef669a5db028c9dbef3a87a) main 반영. 이 마감 기록을 추가하는 후속 문서 commit 자체의 CI를 위 구현 CI와 동일하다고 주장하지 않으며 조율 담당이 별도 확인 후 중앙 최종상태를 갱신합니다.

## HACS·CI·의존성 업데이트

| 규칙 ID | 확인 항목 | 상태 | 근거 / 남은 작업 |
|---|---|---|---|
| HACS-01, HACS-02 | 루트 README/LICENSE/hacs.json, 검증한 최소 HA, 실제 배포 구조와 필요한 옵션 일치 | PASS | 루트 영한README/LICENSE/hacs.json 존재. custom_components/atflee 배포·content_in_root/zip추가없음; 지원최소2025.8.0 실제fixture검증 |
| HACS-03, HACS-05 | Default 여부는 목록 근거로 확인, [로컬 brand/icon.png 또는 원격 brands 근거](https://github.com/eigger/hass-repo-standards/blob/ff46b0c8d9ba53b1d35ab9a4aa38f4db26c06870/docs/hacs.md)와 HACS/Hassfest 실제 실행, ignore는 이유·해제 조건 기록 | PASS | HACS Custom 표시, 기존localicon256²RGBA/logo512×128RGBA·선택2x/dark없음. eigger 최초commit68c355c/PR1+repoMIT 근거는 STANDARDS에 기록(독립충분확인). 제3자보증/UI렌더링검증 주장없음. 구현4da5699의 [Validate39039498020](https://github.com/eigger/hass-atflee/actions/runs/39039498020): HACS9checks(brands포함)·Hassfest 독립 성공 확인; ignore 없음 |
| HACS-06 (권장) | description·topics·issue 경로·brands 및 사용하는 HACS 필드 지원 확인 | PASS | 원격 master·Issues/Discussions 활성·MIT·정식Release0.6.1 API확인. 기존localbrand 보존; localUI는 HA2026.3 이후여서 최소HA/UI표시 주장 없음. render_readme는 기존필드 유지 |
| CI-01, CI-02 | Validate/Python Tests 공통화, 확장 job 유지, PR·실제 기본 브랜치 push·dispatch 및 필요한 schedule | PASS | Tests current/minimum HA·dependency4matrix/Validate HACS/Hassfest·updater 공통SHA 호출. 실제master push/PR/dispatch 및 분산weeklyschedule, 특수확장job 없음 |
| CI-03, CI-05, CI-08 | 최소 권한·checkout 자격증명 비보존·timeout·concurrency, full SHA·갱신 관리, 비신뢰 입력·secrets 경계 | PASS | caller permissions read/업데이트job만 contents+pullrequests write, 중앙 checkout persistfalse·timeout/concurrency·SHA고정·비신뢰shell/secrets경계 재사용. Dependabot github-actions/currentpip 갱신 |
| CI-04, CI-07, CI-12 | 실패를 숨기지 않는 실제 `ha` 필수 테스트, 버전별 환경·cache·Ruff 설정과 required checks 이름 확인 | PASS | 실제ha profile·4환경·Ruff check/format52files PASS, 숨기는skip/continueonerror없음. 기본branch protection404/rulesets[] 독립확인, requiredcheck변경없음; 구현4da5699 원격4matrix·lint2 성공 확인 |
| DEP-03, DEP-04, CI-09 | updater의 선택 package·연산자/extras/marker 보존, 안정 버전·major 정책, 실제 기본 브랜치·단일 bot branch·PR만 제안 | PASS | update_dependencies.yml blesession만 선택·중앙fullSHA 재사용, 실제PyPI updater dryrun 변경없음. 연산자/extras/marker·stable/major검토·단일botbranch/기본branch API·PR제안 계약 유지 |
| CI-09, CI-10, DEP-08 | 변경 tree의 새 하한·실제 HA 검증 후 PR 동기화, 실패 시 중단·변경 없음 시 기존 PR 정리, 후속 required checks 충족 방식 확인 | PASS | 중앙workflow는 변경tree exact새하한·실HA+pipcheck·caller Ruff/pytest 성공 후만 PR동기화, 실패중단/변경없음정리. 토큰후속CI자동실행 가정없음. requiredcheck설정없음; 이번dryrun 새PR미생성 |

## README·Bluetooth·유지보수

| 규칙 ID | 확인 항목 | 상태 | 근거 / 남은 작업 |
|---|---|---|---|
| DOC-01, DOC-02, DOC-06 | 영어 README.md·한국어 README.ko.md·상호 링크·기존 내용 보존, 간결한 제목/소개/핵심지원/최소요구/빠른설치·설정/짧은예제/중요제한/문서목록, 상세옵션·긴YAML·참조·개발/실HA테스트·의존성/검증범위를 docs·examples 등으로 보존·분리하고 유효한 링크 제공, 실제 활성 Issues·Discussions 또는 대체 지원 경로·실제 LICENSE 링크 | PASS | README.md/README.ko.md 상호 링크·간결한 설치/지원최소2025.8.0·짧은 UI 예제·제한/지원/라이선스. 기존 본문/이미지/구버전 안내를 docs/usage.md·usage.ko.md로 보존; 개발/테스트 명령 docs/development.md. 독립 review_atflee가 상대링크 누락0·원문보존/한국어대응·Issues/Discussions 활성·MIT·정식Release0.6.1 API 확인. 실제 HA 로컬179passed, 구현4da5699 원격4matrix179pass, 이 마감 문서CI는 별도 확인 |
| DOC-03, DOC-04, DOC-05 | 제목 아래 관리 블록, flat-square·순서·실제 조건별 배지, CI 실제 기본 브랜치, 필수 동적 Usage·Analytics 참여 설치 의미·미집계/조회 실패와 0 설치 구분·이전 안내 보존 | PASS | .hass-standards.json·양 README 관리블록: HACS Custom→Release→HA minimum→Tests→Validate→License→Usage, flat-square·실제 master branch·domain atflee. 집계 사전 조회 없이 항상 Usage·참여설치 의미/조회실패≠0 안내. 독립 badge --check exit0·diffcheck PASS |
| HA-09, HA-10 | BLE 사용 시 HA Bluetooth API·라이브러리 공개 경계, 지원한 proxy 경로·재연결·취소·서비스 변경 검증 | PASS | 실제 HA Bluetooth manager·공개blesession 경계 및 connect/notify/disconnect·취소·boundedcleanup·unload 회귀. test_connection.test_service_change_swaps_profile_and_refreshes_optional_notify 추가: 서비스맵 notify/write 반전의 실제client autoswap·write, 재연결 시 변경맵/optional notify 재선택·이전listener정리·최종disconnect. 구현4환경/독립양HA 최종179passed 재검증. 물리proxy성능 검증 별도미수행 |
| DOC-07 | blesession/proxy 통합 README의 핵심조건·상세문서 링크, 공통 Bluetooth 설정·추천기기·active 스캔/GATT 차이, 통합별 troubleshooting 또는 공통 링크+모델고유조건·실제진단·민감정보 제거 제보 안내 | PASS | docs/troubleshooting.md·troubleshooting.ko.md: connect/arm/measure, 깨우기·타앱/본딩·실제 Connection Duration/Last Failure/Failure Count·공개제보 비식별. 공통Bluetooth 설정/추천XIAOW5500V1.2/AtomS3U·구매링크 원본 연결. active scan과 GATT 구분. 별도 diagnostics endpoint 주장 없음. 독립 review_atflee 확인 |
| DOC-07, HA-12 | 기기별 깨우기·인증·타 앱 연결·전송 제약, 실제 검증 경로와 미검증 범위, 공개 문제 로그 비식별화 | PASS | 기기별 깨우기·전원/타앱·인증 고유조건·실제 진단경로·프로필/측정/원시 payload 비식별 제보 안내, 실물/HA UI 미검증 고지. ESL 전용센서/Retry Count/Debounce 복사 없음. 독립 문서리뷰 지적(이미지·중앙링크) 수정 후 재확인 PASS; 구현 privacy 회귀 검증은 HA-12 행 별도 |
| HACS-04, REL-01, REL-02, REL-03, CI-11 | 통합 릴리스 시 같은 검증 commit/tag·manifest 버전·산출물·권한, 사용자 영향·지원 변경·제한 안내 | N/A | 이번은 채택 작업으로 통합버전0.6.1·기존Release/태그 유지; 새릴리스/산출물 없음. 릴리스는 검증한commit/tag·manifest일치와사용자영향 검토하는 별도작업 |
| REL-04 | 이전/중단 시 README 상단 경로·유지보수 상태·재등록 여부, 자동 이전으로 오인하지 않는 안내 | N/A | 이전/중단/통합 작업 아님; 기존 리포/domain 유지 |
| REL-05 (권장) | 의존성/HA API 변경과 기능 변경 분리, 표준 변경은 명시적 채택 PR로 반영 | PASS | 지원최소/통합버전/runtime하한불변, 기능추가 없이 테스트·CI·문서 공통화와 검증발견 lifecycle/privacy 호환수정. 향후 표준변경은 명시적채택검토 |

## 구현·문서 근거와 독립 검증

- README.md/README.ko.md: 상호 언어 링크·간결한 설치·최소2025.8.0·지원/라이선스·항상 동적 Usage. 원격 정식 Release0.6.1, Issues/Discussions 활성·MIT 확인. 배지 도구 --write 실행; 독립 --check exit0, 상대링크 누락0·diffcheck PASS.
- docs/usage.md·usage.ko.md: 기존 프로필·사용자 식별·범위·진단·구버전 업그레이드 상세 보존. docs/troubleshooting.md·troubleshooting.ko.md: 실제 세션 connect/arm/measure·진단 센서·비식별 제보 경로. 별도 diagnostics endpoint를 있다고 주장하지 않음.
- docs/development.md: 새 가상환경의 installer·packaging·RUNNER_TEMP·4조합 입력과 실제 HA 테스트 경계.
- 문서 범위는 review_atflee가 GH 메타데이터·양언어 링크/배지·기존 내용 보존·진단/한계를 독립 확인. 이미지 보존·중앙 최신 main 링크 지적 수정 후 재확인 PASS. 다른 규칙도 구현4da5699의 독립 실제 검증·원격 CI 근거에 따라 기록했습니다. 실물 기기·HA UI·새 proxy 보드는 미검증.

## 예외와 남은 작업

예외 원본은 `STANDARDS.md`입니다. 아래에 해당 위치를 연결하고, 예외가 실제 없음을 확인한 뒤에만 `없음`으로 바꿉니다.

| 규칙 ID | 예외 위치 / 이유 | 담당자 | 재검토 조건 |
|---|---|---|---|
| 없음 | 구현4da5699의 로컬·원격 독립 검증 완료, 적용 필수 PASS/N/A | root / review_atflee | 새 변경 시 재검토 |

| 규칙 ID / TODO | 남은 작업 / issue·PR | 담당자 | 완료 근거 |
|---|---|---|---|
| 마감 후속관리(구현 필수 TODO 아님) | 이 마감 문서 commit 게시·해당SHA CI 독립 확인·중앙 최종 완료 상태 갱신 | root / review_atflee | 게시 후 별도 확인; 구현4da5699 원격성공과 구분 |

최종 검토 시 적용 대상 필수 `TODO`와 `EXCEPTION`, 이유가 있는 `N/A`, 권장 미채택을 구분해 적습니다. CI 성공만으로 실물 기기 검증을 주장하지 않습니다. 실물 검증을 수행했다면 모델·펌웨어·어댑터/proxy·연결 경로와 결과를 별도로 기록합니다.

중앙 보고는 [적용 현황표](https://github.com/eigger/hass-repo-standards/blob/main/docs/adoption-status.md)의 자기 리포 행에 반영합니다. 리뷰 지적·수정·재검증 결과와 중앙 갱신 실패 사유가 있으면 남은 작업에도 기록합니다.
