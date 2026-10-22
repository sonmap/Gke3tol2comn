# Gke3tol2comn — GKE Autopilot 1차 인프라 설치 계획

본 저장소는 기존 VM Cron → run-gke.sh → client_gke → GKE Standard 배치 구조를 신규 GKE Autopilot으로 이전하기 위한 작업 계획서입니다.

> **이번 범위는 '1차 인프라 설치'입니다.** 실제 전환 대상 환경에서 배치·연동 테스트를 수행할 수 없으므로, 사용자 제공 **외부 개발환경의 RSVP 단일 과제 테스트 결과**를 설계·준비의 근거로 사용합니다. 실제 대상 환경의 GKE/AR/NFS/BQ 검증 결과로 해석해서는 안 됩니다. GitHub 문서 작성 자체가 실제 인프라 설치 완료를 의미하지 않습니다.

## 단계와 범위

1. **1차 인프라 설치:** Shared VPC, 서브넷, GKE Autopilot, IAM, Private Endpoint, Kubeconfig 준비 + **VM NFS Mount와 /mnt 경로 조회** (이번 범위)
2. **2차 연동 검증:** GKE **Pod**에서 Artifact Registry Pull, Filestore NFS Mount, .oefj/BigQuery SELECT (실제 환경 테스트 허용 시)
3. **3차 단일 업무 검증:** GP_L2RSVP_001_1 → run-gke.sh → client-gke-auto 직접 호출 (별도 승인)
4. **4차 전체 전환:** 30개 과제 및 공통 client_gke 링크 절체 (3차 검증 후 별도 승인)

## 문서

- **[00. 1차 인프라 설치계획(외부 개발환경 테스트 기준)](docs/00-PHASE1-INFRA-INSTALL.md)**
- **[04. VM NFS 마운트 및 /mnt 경로 적용](docs/04-VM-NFS-MOUNT.md)**
- [01. GKE Autopilot 설치 및 구성 명령](docs/01-GKE-CLUSTER.md)
- [02. 후속 단계 RSVP 단일 과제 실행/전환/원복 RUNBOOK](docs/02-RSVP-CUTOVER.md)
- [운영 입력값 불일치 확인표](docs/03-OPERATING-INPUT-AUDIT.md)
- [BQ 읽기 전용 테스트](tests/sample_bq.py)
- [Git에 올리면 안 되는 파일 목록](.gitignore)

## 1차 설치 입력값(2026-10-22, 첨부 개발환경 자료 기준)

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
| 1차 VM NFS Mount 위치 | `/mnt/batch_gke` (실제 NFS Export 확인 후) |
| VM RSVP 폴더 | `/mnt/batch_gke/l2/rsvp` |
| Pod NFS 검증 | 1차 수행 불가, 2차 보류 |
| GKE 1차 설치 실행 계정 | user01@sonmap.net |
| RSVP 업무 실행 | 3차 이후 별도 승인 |
| 관리자 IAM 변경 계정 | admin@sonmap.net (별도, 필요할 때만) |
| Kubeconfig (첨부 실행 로그 기준) | $HOME/.kube/config_l2comn-autopilot |
| Namespace | l2comm-batch |
| GKE Pod 마운트 | /home/jupyter |
| BQ 실행 프로젝트 (운영 예제) | gcp-prod-edp-lake |
| BQ Key (신규 테스트 기본값) | /home/jupyter/.oefj |

- 첨부 운영 설정에 나온 Node 10.253.0.0/28은 **16개 IP(사용 가능 12개)**로, 기존 설명의 128개는 오류입니다. 주소 충돌·확장성 및 노드 용량 검증이 필요합니다.
- Pod CIDR은 10.253.1.0/24, CP CIDR은 10.253.2.0/28로 기록되어 있습니다. 실제 생성 전에 IP 승인 여부를 확인하십시오.
- 운영 자료에는 Filestore 서버가 172.32.10.2로 출력되지만 같은 주소가 관리 VM이라고 명시되어 있습니다. **정확한 NFS 서버 IP 확인 전에는 VM에서도 임의 NFS 마운트 금지**. VM의 기존 NFS 연결 조회는 가능합니다.
- AR 테스트 변수의 1a751e99d693:v1와 운영 로그의 python-bq-batch:v1가 다르므로 실제 이미지 경로/태그 조회 후 적용.
- 실제 RSVP 업무 컨테이너 이미지와 인자 형식은 운영 VM의 run-gke.sh를 조회해 확정합니다.
- 이전 실행 로그의 python-bq-batch:v1는 인증 스모크 테스트 이미지이며 실제 RSVP 업무 이미지와 혼동하지 않습니다.
- 기존 Python config.py 중 일부는 /home/jupyter/.oef를 사용합니다. 신규 스모크는 /home/jupyter/.oefj를 기본으로 하며 반드시 실경로를 확인합니다.

## 1차 VM NFS 경로 점검

실제 GKE Pod NFS Mount는 검증할 수 없으므로, **VM에 연결된 NFS의 마운트 지점과 파일 경로부터 확인**합니다. 기본 구조는 NFS `/batch_gke` → VM `/mnt/batch_gke`이며, `/mnt/batch_gke/l2/rsvp` 및 `/mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh` 경로를 조사합니다. .oefj는 존재·권한만 확인하고 키는 읽거나 업로드하지 않습니다.

~~~bash
findmnt -t nfs,nfs4 -o TARGET,SOURCE,FSTYPE,OPTIONS
findmnt -T /mnt/batch_gke -o TARGET,SOURCE,FSTYPE,OPTIONS
ls -ld /mnt/batch_gke/l2/rsvp 2>&1 || true
~~~

신규 NFS 마운트는 실제 서버·Export 승인 후 임시 read-only 검사부터 수행하며, **VM에서 성공해도 GKE Pod 접근 성공으로 판정하지 않습니다**. 상세 명령은 [04. VM NFS 가이드](docs/04-VM-NFS-MOUNT.md)에 수록했습니다.

## 실행 계정 통일

GKE 클러스터 생성 및 구성 조회는 **`user01@sonmap.net`**으로 진행하도록 계획합니다. 실제 업무 Pod 및 RSVP 단일 과제 테스트는 이번 1차 인프라 설치에서 제외합니다. 필요한 IAM 권한은 관리자 `admin@sonmap.net`이 별도로 부여합니다.

~~~bash
gcloud auth list
gcloud config set account user01@sonmap.net
gcloud config get-value account
export KUBECONFIG="$HOME/.kube/config_l2comn-autopilot"
~~~

`$HOME`은 **Linux OS 사용자 홈 디렉터리**입니다. Google 계정이 user01이라고 OS 사용자 이름도 user01인 것은 아니므로, 이전 로그의 `/home/admin_sonmap_net` 경로를 기계적으로 바꾸지 않습니다.

## 중요: 1차 인프라 설치에서는 변경하지 말 것

- 기존 /ssw/dlk/client_gke 공통 심볼릭 링크
- 운영 Cron
- 기존 GKE Standard 클러스터
- 30개 과제 공통 실행 환경
- Filestore의 서비스 계정 키(.oefj) 원본
- 실제 업무 Pod 생성 또는 BigQuery Job 실행

## 인증 및 보안

**공개 저장소에는 .oef, .oefj, JSON 개인 키, Kubeconfig, 환경의 비밀정보를 커밋하지 않습니다.**
GKE API 접속 권한과 Pod 내부 BigQuery 서비스 계정 인증은 별도 체계입니다.
