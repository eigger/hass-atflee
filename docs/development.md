# 개발·실제 HA 테스트

[English README](../README.md) · [한국어 README](../README.ko.md) · [적용 체크리스트](../ADOPTION_CHECKLIST.md)

이 통합은 `custom_components/atflee/`로 배포하는 HACS 커스텀 통합입니다. Core에 대응하는 모듈·config entry 생명주기·공개 API 구조이며 공식 Core 포함/품질 등급을 주장하지 않습니다. 프로토콜은 `atflee_ble/`, 사용자 식별/평가는 `user_profile.py`·`evaluation.py`, BLE 보고는 `session_report.py`로 분리합니다.

## 테스트 경계·지원 정책

테스트는 Core와 같은 `tests/components/atflee/`에 배치하고 `tests/conftest.py`의 실제 HA·플러그인 fixture를 사용합니다. `hass`, `enable_custom_integrations`, 실제 HA 테스트 helper `MockConfigEntry`로 loader·entry·플랫폼·registry·상태·사용자 하위 항목을 검증하며 외부 Bluetooth 광고/GATT 통신 경계만 대체합니다. HA core stub·FakeHass·`--no-deps`로 대신하지 않습니다. 기존 패킷·계산·사용자 식별 회귀 검사는 유지합니다.

| 환경 | Python | HA | pytest-homeassistant-custom-component | requirements |
|---|---|---|---|---|
| 기존 지원 최소 보존 | 3.13 | 2025.8.0 | 0.13.269 | `requirements_test_min.txt` |
| current | 3.14 (3.14.2 이상) | 2026.10.2 | 0.13.373 | `requirements_test.txt` |

이 표는 목표 조합입니다. 실제 실행 버전·검증 결과·대상 commit은 체크리스트가 원본입니다. `hacs.json.homeassistant=2025.8.0`은 지원 선언이며 current 테스트 최신화와 별개입니다. 최신 HA 실패는 호환 문제를 수정하고 최소 테스트를 보존합니다. 실제 비호환 근거와 별도 명시적 사용자 승인 없이 하한을 올리지 않습니다. 최소 HA의 aiodns 3.5가 사용하는 pycares 4.x API를 보존하기 위해 `requirements_test_min.txt`에 테스트 전용 `pycares==4.11.0`을 고정합니다. 이는 런타임 manifest 의존성 추가나 지원 최소 상향이 아닙니다. 과거 최소 requirements와 `constraints/**`는 Dependabot에서 제외하고 current HA·플러그인을 호환 그룹으로 검토합니다. 최소 파일 혼합 갱신·다운그레이드·expected HA/Python 불일치를 자동 병합하지 않습니다.

## 새 가상환경에서 실행

최소/current HA와 최소/current 라이브러리의 네 조합은 각각 별도 환경으로 만드세요. 중앙 표준 checkout은 `STANDARDS.md`의 전체 SHA를 사용하고 `STANDARDS_CHECKOUT`을 실제 경로로 바꿉니다. 깨끗한 current 예시:

```bash
python3.14 -m venv .venv-current
source .venv-current/bin/activate
python -m pip install --upgrade pip packaging
STANDARDS_CHECKOUT=/path/to/hass-repo-standards
INPUT_DOMAIN=atflee \
INPUT_REQUIREMENTS=requirements_test.txt \
INPUT_HA_COMPONENTS='bluetooth recorder sensor binary_sensor select switch' \
INPUT_TEST_PROFILE=ha \
INPUT_EXPECTED_HA_VERSION=2026.10.2 \
INPUT_DEPENDENCY_MODE=current \
RUNNER_TEMP="$(mktemp -d)" \
python "$STANDARDS_CHECKOUT/actions/python-environment/install.py"
python -m pytest tests/components/atflee/ -v
python -m pip check
```

정확한 최소 HA는 Python 3.13의 새 환경에서 `INPUT_REQUIREMENTS=requirements_test_min.txt`, `INPUT_EXPECTED_HA_VERSION=2025.8.0`로 실행합니다. 각 HA의 라이브러리 최소 조합은 다시 새 환경을 만들고 위 installer에 `INPUT_DEPENDENCY_MODE=minimum`과 `INPUT_MINIMUM_PACKAGES='["blesession"]'`를 지정합니다. 최소/current 축을 한 환경의 재설치로 혼합하지 말고 각각 pytest·pip check를 수행합니다. manifest의 `blesession>=0.9.0` 하한은 **0.9.0** 실제 설치로 확인합니다. current resolver가 현재 같은 값을 선택해도 두 모드는 별도 검증입니다.

```bash
python -m pip install -r requirements_lint.txt
python -m ruff check .
python -m ruff format --check .
python -c "from importlib.metadata import version; print({p: version(p) for p in ('homeassistant', 'pytest-homeassistant-custom-component', 'blesession')})"
```

원격 [Tests](../.github/workflows/tests.yml)의 matrix/입력과 [Validate](../.github/workflows/validate.yml)의 HACS·Hassfest 결과를 대상 SHA별 확인합니다. CI 성공으로 실물 체중계·HA frontend UI·새 프록시 보드 검증을 주장하지 않습니다.

## 의존성·문서 변경

런타임 패키지는 manifest requirements, HA domain은 dependencies/after_dependencies, 테스트·린트 도구는 별도 requirements에 둡니다. [공통 의존성 추가 절차](https://github.com/eigger/hass-repo-standards/blob/ff46b0c8d9ba53b1d35ab9a4aa38f4db26c06870/docs/dependencies.md)에 따라 extras·marker·연산자·호환 플랫폼·라이선스와 최소/current HA 설치를 검토합니다. bot은 새 하한 tree를 검증한 후 PR로 제안하며 실패를 숨기지 않습니다.

README는 영어/한국어 빠른 시작을 유지하고 상세 사용·문제 해결은 docs에 보존합니다. 배지는 `.hass-standards.json`과 관리 주석으로 양쪽을 함께 갱신합니다. 중앙 checkout의 `python3 scripts/sync_badges.py /path/to/hass-atflee --check`로 확인합니다. Usage는 Analytics 조회 성공 여부와 무관하게 실제 domain `atflee`를 사용합니다. 로그·fixture 공개 전 주소/프로필/측정값을 제거하세요.

## 기존 브랜드 자산

기존 `custom_components/atflee/brand/icon.png`(PNG 256×256 RGBA), `logo.png`(PNG 512×128 RGBA)를 그대로 유지합니다. 선택 2x·dark 파일은 제공하지 않습니다. 확인한 출처는 eigger가 기존 자산을 추가한 [최초 커밋68c355c](https://github.com/eigger/hass-atflee/commit/68c355c97d2e65ee913c4b084c565f96bf50be1c)과 [PR #1](https://github.com/eigger/hass-atflee/pull/1)입니다. 리포 [MIT License](../LICENSE)는 Copyright2026eigger이며 별도 자산 제외 문서는 확인되지 않았습니다. 이는 확인한 리포 출처·라이선스 근거이며 제3자 권리를 별도로 검증했다는 뜻이 아닙니다. HACS의 경로 검사와 이미지/권리/렌더링 검증은 별개입니다. HA2025.8.0은 local brand UI 지원(2026.3 이후) 이전이므로 최소 HA에서 아이콘 표시를 검증했다고 기록하지 않습니다. 이번 HA UI 표시 검증도 수행하지 않았습니다.
