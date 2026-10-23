# Home Assistant용 Atflee BLE

<!-- hass-standards:badges:start -->
[![Release](https://img.shields.io/github/v/release/eigger/hass-atflee?style=flat)](https://github.com/eigger/hass-atflee/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat)](#설치)
[![Home Assistant minimum](https://img.shields.io/badge/HA-%E2%89%A5%202025.8.0-41BDF5?style=flat)](hacs.json)
[![Tests](https://img.shields.io/github/actions/workflow/status/eigger/hass-atflee/tests.yml?branch=master&style=flat&label=Tests)](https://github.com/eigger/hass-atflee/actions/workflows/tests.yml)
[![Validate](https://img.shields.io/github/actions/workflow/status/eigger/hass-atflee/validate.yml?branch=master&style=flat&label=Validate)](https://github.com/eigger/hass-atflee/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/eigger/hass-atflee?style=flat)](LICENSE)
[![Downloads](https://img.shields.io/github/downloads/eigger/hass-atflee/total?style=flat&color=41BDF5&label=Downloads)](https://github.com/eigger/hass-atflee/releases)
<!-- hass-standards:badges:end -->

[English](README.md) | **한국어**

Atflee BLE 체중계의 데이터를 Home Assistant에서 직접 수신하는 HACS 커스텀 통합입니다. 사용자별 체중·체성분과 연결 진단을 제공합니다.

## 지원 기기

- Atflee iGrip 계열(iGripX, iGrip Pro 포함).
- Atflee T8 및 같은 프로토콜의 다른 모델은 **동작할 수 있으나 미검증**입니다.
- 개별 사용자 프로필, 체중 기반 사용자 식별, 활성 사용자 선택, 체성분 측정 스위치를 제공합니다. 제공 지표는 모델과 실제 수신 패킷에 따라 다릅니다.

## 최소 요구사항

**Home Assistant 2025.8.0 이상**, HACS(또는 수동 설치), HA가 관리하는 Bluetooth 어댑터나 GATT 연결 가능한 Bluetooth proxy가 필요합니다. 체중계를 잠깐 밟아 깨우고 설정·측정 중 깨어 있게 하세요. 연결 중인 다른 앱을 종료하세요.

## 설치

1. HACS **사용자 지정 저장소**에 `https://github.com/eigger/hass-atflee`를 **통합** 유형으로 추가하고 **Atflee**를 설치합니다.
2. HA를 재시작합니다. 수동 설치는 `custom_components/atflee/`를 HA 설정의 `custom_components/` 아래로 복사한 뒤 재시작합니다.
3. **설정 → 기기 및 서비스 → 통합 추가 → Atflee** 또는 Bluetooth 자동 발견 항목에서 설정합니다.
4. 첫 사용자의 이름·키·생년월일(`YYYY-MM-DD`)·성별·선택적 예상 체중을 입력하고 측정 완료까지 체중계에 머무릅니다.

예를 들어 **사용자 추가**로 두 번째 사람을 등록한 후 측정 전에 **활성 사용자**에서 선택하세요. 선택은 측정 1회 완료 또는 10분 뒤 `auto`로 돌아갑니다. [사용자 식별·엔티티 상세](docs/usage.ko.md)를 참고하세요.

## 중요 제한사항

- 소비자용 체성분·평가 값은 추정치이며 **의료 조언이 아닙니다**. 일부 계산식의 척도는 다른 기기와 비교 검증되지 않았습니다.
- **0.3.2 이하에서 업그레이드**했다면 사용자를 추가해야 체중을 기록합니다. 이전 프로필은 자동 이관되지 않습니다. [업그레이드 절차](docs/usage.ko.md#032-이하에서-업그레이드).
- 광고 발견과 GATT 연결 성공은 다릅니다. 공식 앱 연결을 해제하고 필요하면 휴대폰의 페어링을 지우세요. 정상 동작하는 로컬 어댑터를 사용할 수 있으며 가까운 proxy로 배치를 개선할 수 있습니다. [Bluetooth 프록시 설정](https://github.com/eigger/hass-repo-standards/blob/main/docs/bluetooth.ko.md) · [문제 해결](docs/troubleshooting.ko.md).
- 이번 공통화에서 새로운 실물 기기·펌웨어·proxy 보드를 검증하지 않았습니다.

## 문서

| 문서 | 내용 |
|---|---|
| [사용·설정](docs/usage.ko.md) / [English](docs/usage.md) | 프로필·사용자 식별·엔티티·평가 범위·이전 버전 업그레이드 |
| [문제 해결](docs/troubleshooting.ko.md) / [English](docs/troubleshooting.md) | 깨우기·proxy/GATT 오류·실제 진단 경로·개인정보 |
| [개발·테스트](docs/development.md) | Core 대응 구조·실제 HA 테스트·최소/current 환경 분리 |
| [공통 규칙 채택](STANDARDS.md) | 기준·체크리스트·검증 한계 |

Usage는 **HA Analytics 데이터 제공에 동의한 설치 집계**이며 전체 설치 수나 사람 수가 아닙니다. 미집계·조회 실패는 0 설치를 의미하지 않습니다.

## 지원·라이선스

버그는 [Issues](https://github.com/eigger/hass-atflee/issues), 질문·제안은 [Discussions](https://github.com/eigger/hass-atflee/discussions)를 사용하세요. 공개 로그에서 프로필·측정값·주소·인증정보를 제거하세요.

[MIT License](LICENSE)로 배포합니다.
