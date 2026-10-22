# Gke3tol2comn — GKE Autopilot 1차 RSVP 전환 검증

본 저장소는 기존 VM Cron → run-gke.sh → client_gke → GKE Standard 배치 구조를
신규 GKE Autopilot으로 이전하기 위한 **사전 검증 문서**입니다.

> 상태: 절차/샘플 코드 작성 단계. 저장소의 파일만으로 운영 GKE가 생성되거나
> 실제 전환된 것은 아닙니다. GCP 관리자 승인 및 현장 실행이 필요합니다.

## 단계와 범위

1. Shared VPC 기반 GKE Autopilot 생성 또는 기존 클러스터 상태 검증
2. Kubeconfig를 $HOME/.kube/config_l2comn-autopilot에 별도 저장
3. GKE → Edge Artifact Registry 이미지 Pull 검증
4. GKE → Filestore NFS Mount 검증
5. Pod 안에서 .oefj 서비스 계정 키로 BigQuery 읽기 전용 SELECT 검증
6. **1차 과제 GP_L2RSVP_001_1 한 개만** run-gke.sh → client-gke-auto 직접 호출 검증
7. 성공 후에만 공통 client_gke 심볼릭 링크 절체 여부 별도 승인

## 문서

- [01. GKE Autopilot 생성 및 사전 점검](docs/01-GKE-CLUSTER.md)
- [02. RSVP 한 개 과제 실행/전환/원복 RUNBOOK](docs/02-RSVP-CUTOVER.md)
- [운영 입력값 불일치 확인표](docs/03-OPERATING-INPUT-AUDIT.md)
- [BQ 읽기 전용 테스트](tests/sample_bq.py)
- [Git에 올리면 안 되는 파일 목록](.gitignore)

## 운영 입력값(2026-10-22) 반영 및 미확정 항목

| 구분 | 값 |
|---|---|
| 테스트 과제 | GP_L2RSVP_001_1 |
| Service Project | gcp-sbx-edp-comn-509423 |
| Shared VPC Host | gcp-prod-edp-hub-vpchost |
| Region | asia-northeast3 |
| Cluster 계획명 | gkea-prod-l2comn-batch |
| VPC | vpc-prod-edp-hub |
| Node/Pod/CP 후보 CIDR | 10.253.0.0/28 / 10.253.1.0/24 / 10.253.2.0/28 |
| Release Channel | regular |
| AR Project | gcp-prod-edp-hub-vpchost |
| 관리 VM (클러스터 접속) | 172.32.10.2 |
| Kubeconfig (본 문서 표준) | $HOME/.kube/l2comn_gke |
| Namespace | l2comm-batch |
| GKE Pod 마운트 | /home/jupyter |
| BQ 실행 프로젝트 (운영 예제) | gcp-prod-edp-lake |
| BQ Key (신규 테스트 기본값) | /home/jupyter/.oefj |

- 첨부 운영 설정에 나온 Node 10.253.0.0/28은 **16개 IP(사용 가능 12개)**로, 기존 설명의 128개는 오류입니다. 주소 충돌·확장성 및 노드 용량 검증이 필요합니다.
- Pod CIDR은 10.253.1.0/24, CP CIDR은 10.253.2.0/28로 기록되어 있습니다. 실제 생성 전에 IP 승인 여부를 확인하십시오.
- 운영 자료에는 Filestore 서버가 172.32.10.2로 출력되지만 같은 주소가 관리 VM이라고 명시되어 있습니다. **정확한 NFS 서버 IP 확정 전에는 NFS 단위 테스트 배포 금지**.
- AR 테스트 변수의 1a751e99d693:v1와 운영 로그의 python-bq-batch:v1가 다르므로 실제 이미지 경로/태그 조회 후 적용.
- 실제 RSVP 업무 컨테이너 이미지와 인자 형식은 운영 VM의 run-gke.sh를 조회해 확정합니다.
- 이전 실행 로그의 python-bq-batch:v1는 인증 스모크 테스트 이미지이며 실제 RSVP 업무 이미지와 혼동하지 않습니다.
- 기존 Python config.py 중 일부는 /home/jupyter/.oef를 사용합니다. 신규 스모크는 /home/jupyter/.oefj를 기본으로 하며 반드시 실경로를 확인합니다.

## 중요: 1차 단계에서 변경하지 말 것

- 기존 /ssw/dlk/client_gke 공통 심볼릭 링크
- 운영 Cron
- 기존 GKE Standard 클러스터
- 30개 과제 공통 실행 환경
- Filestore의 서비스 계정 키(.oefj) 원본

## 인증 및 보안

**공개 저장소에는 .oef, .oefj, JSON 개인 키, Kubeconfig, 환경의 비밀정보를 커밋하지 않습니다.**
GKE API 접속 권한과 Pod 내부 BigQuery 서비스 계정 인증은 별도 체계입니다.
