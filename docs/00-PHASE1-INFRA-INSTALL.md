# 00. 1차 인프라 설치계획 — 외부 개발환경 테스트 근거

작성 기준: 2026-10-22
작업 구분: 인프라 설치 계획 / 실제 전환 대상 환경 기능 테스트 보류

> 1차 단계는 Shared VPC, GKE Autopilot, 기본 IAM, IP, 관리 접속 구성입니다. 사용자가 제공한 외부 개발환경의 RSVP 단일 과제 실행 기록을 설계 참고자료로 사용합니다. 이 문서 작성만으로 실제 대상 환경에 GCP 자원을 생성한 것은 아닙니다.

## 1. 단계 분리

| 단계 | 범위 | 이번 작업 |
|---|---|---|
| **1차 인프라 설치** | Shared VPC, Node/Pod/CP IP, API/IAM, GKE Autopilot 설치, Private Endpoint, Kubeconfig, AR/Filestore 사전 설정 | **대상** |
| 2차 시스템 연동 테스트 | AR Pull, Filestore NFS Mount, SA JSON Key 및 BigQuery SELECT 검증 | 후속 |
| 3차 RSVP 단일 과제 시험 | GP_L2RSVP_001_1 run-gke.sh → client-gke-auto, Pod 결과 대조 | 후속 |
| 4차 전체 전환 | 30개 과제, 공통 심볼릭 링크, Cron 순차 절체/원복 | 후속 |

1차 제외: 실제 RSVP Pod 실행, 운영 BigQuery 조회, 운영 Cron 변경, 기존 client_gke 공통 링크 변경, .oefj 파일 복사·삭제, 운영 30개 업무 전환.

## 2. 외부 개발환경 검증 결과 활용

| 항목 | 제공된 외부 개발환경 기록 | 실제 대상 환경 미확인 항목 |
|---|---|---|
| YAML 배포 | PV/PVC/Pod created 출력 | 실제 환경 정책/RBAC |
| 컨테이너 실행 | Pending → Running → Succeeded | 실제 환경 노드 스케줄링/쿼터 |
| 스토리지 | 20Gi ROX PVC Bound, /home/jupyter | 실제 NFS 서버 주소/방화벽·Mount |
| 배치 | client_gke 정상 종료 및 리소스 삭제 출력 | 기존 Cron, run-gke.sh 호출 호환 |
| BQ | .oefj 인증 테스트 실행 사례 | 실제 BigQuery 권한·SQL 결과 |
| 이미지 | python-bq-batch:v1 출력 | 운영 이미지·태그 존재 및 Pull |

**증적 분류 원칙:** 제공받은 외부 개발환경 로그에 성공 출력이 있어도 실제 고객/설치 대상 환경에서 동일 작업을 검증했다고 쓰지 않습니다. 제공 자료에는 샘플·예상 출력도 포함될 수 있으므로 실제 수행 확인 자료(실행일시, 프로젝트, 클러스터, Job ID)와 별도 구분합니다.

## 3. 설치 입력(승인 전 후보값)

| 구분 | 첨부값 |
|---|---|
| GKE 실행 계정 | user01@sonmap.net |
| IAM 관리자 계정 | admin@sonmap.net |
| Host Project | gcp-prod-edp-hub-vpchost |
| Service Project | gcp-sbx-edp-comn-509423 |
| Region / Channel | asia-northeast3 / regular |
| Shared VPC | vpc-prod-edp-hub |
| Cluster | gkea-prod-l2comn-batch |
| Node Primary | subnet-prod-l2comn-gke / 10.253.0.0/28 |
| Pod Secondary | subnet-prod-l2comn-gke-pod / 10.253.1.0/24 |
| Control Plane | subnet-prod-l2comn-gke-cp / 10.253.2.0/28 |
| 접속 관리 VM | 172.32.10.2 |
| Kubeconfig | $HOME/.kube/config_l2comn-autopilot |
| 이후 테스트 Namespace/KSA | l2comm-batch / ksa-l2comm-batch |
| 이후 테스트 AR | gcp-prod-edp-hub-vpchost / ar-l2comm-python |
| 이후 테스트 NFS path | /batch_gke/l2/rsvp (NFS 서버 IP 미확정) |

**주의:** Node /28에는 전체 16 IP, GCP 예약 4개를 제외한 12개 IP가 있습니다. Pod /24는 256개 주소라는 뜻이며 256개 Pod나 충분한 노드 수를 보장하지 않습니다. Autopilot의 노드별 Pod CIDR 할당 크기와 자원량을 검토해야 합니다. 과거 허용망 /25는 현재 Node /28과 일치하지 않습니다.

## 4. 1차 설치 상세 작업

| 순서 | 항목 | 수행 주체 | 산출물 및 확인 |
|---|---|---|---|
| 1 | VPC/IP 설계 승인 | 네트워크팀 | Node/Pod/CP 범위 중복·확장 검토 |
| 2 | Host/Service Project 및 Shared VPC 확인 | GCP 인프라 | 프로젝트와 네트워크 연결 상태 |
| 3 | API 활성화 및 IAM | 관리자·네트워크 담당 | user01, GKE Agent, Node SA 권한 |
| 4 | Node/Pod/CP Subnet 구성 | Host 프로젝트 네트워크 담당 | Subnet describe 결과 |
| 5 | GKE Autopilot 생성 | user01 (승인 후) | Cluster RUNNING/Autopilot enabled |
| 6 | 관리접속 및 Kubeconfig 준비 | user01 | Context·Private Endpoint 구성 기록 |
| 7 | AR 연동 설정 준비 | AR 담당 | Node SA Reader/이미지명 확인 |
| 8 | Filestore 접속 정책 준비 | 네트워크·NFS 담당 | NFS 실제 서버 IP, 프로토콜, FW 검토 |
| 9 | 1차 설치 보고 | 플랫폼 담당 | 리소스 목록·차단 이슈·후속 테스트 계획 |

**설치 완료 기준:** 실제 설치 작업을 실행하여 GKE 및 Shared VPC 관련 자원이 생성/설정되었고 describe 조회로 확인되었을 때. 사용자 업무 Pod/BQ/Filestore 연동 성공은 1차 완료 기준에 포함하지 않습니다. 지금은 계획서 작성 및 GitHub 수정만 수행했으므로 설치 완료 상태가 아닙니다.

## 5. GCP 명령 — 설치 작업 승인 후 참고용

### 5-1. user01 실행 및 현황 조사

~~~bash
export HOST_PROJECT="gcp-prod-edp-hub-vpchost"
export SVC_PROJECT="gcp-sbx-edp-comn-509423"
export REGION="asia-northeast3"
export NETWORK="vpc-prod-edp-hub"
export CLUSTER="gkea-prod-l2comn-batch"
export NODE_SUBNET="subnet-prod-l2comn-gke"
export POD_RANGE="subnet-prod-l2comn-gke-pod"
export CP_SUBNET="subnet-prod-l2comn-gke-cp"

gcloud auth list
gcloud config set account user01@sonmap.net
gcloud config get-value account

gcloud compute shared-vpc get-host-project "$SVC_PROJECT"
gcloud compute networks subnets list --project="$HOST_PROJECT" --regions="$REGION"
gcloud container clusters list --project="$SVC_PROJECT" --region="$REGION"
~~~

### 5-2. 네트워크 및 IAM

Host Project와 Service Project 각각에 필요한 권한이 있는 승인자가 수행합니다. 기존 서브넷과 클러스터가 있으면 재생성하지 않습니다.

프로젝트 API, IAM, 공유 서브넷 구성 상세 명령은 [01-GKE-CLUSTER.md](01-GKE-CLUSTER.md)를 사용하십시오. user01은 실행자, admin@sonmap.net은 관리자 작업 담당 계정이며 Node SA/GKE Service Agent와 구분합니다.

### 5-3. 클러스터 생성 명령 샘플

~~~bash
# IP 검증/승인, IAM, subnet 생성 확인 후 *신규 클러스터에만* 실행
gcloud container clusters create-auto "$CLUSTER" \
  --project="$SVC_PROJECT" \
  --region="$REGION" \
  --network="projects/$HOST_PROJECT/global/networks/$NETWORK" \
  --subnetwork="projects/$HOST_PROJECT/regions/$REGION/subnetworks/$NODE_SUBNET" \
  --cluster-secondary-range-name="$POD_RANGE" \
  --private-endpoint-subnetwork="projects/$HOST_PROJECT/regions/$REGION/subnetworks/$CP_SUBNET" \
  --enable-private-nodes \
  --enable-private-endpoint \
  --release-channel="regular"
~~~

Node SA를 명시하는 환경이면 01 문서처럼 실제 확인된 Node SA를 --service-account에 지정합니다. 외부 개발환경의 --no-enable-authorized-networks-on-private-endpoint 설정은 승인 네트워크 제한을 해제할 수 있으므로 **보안팀 승인 없이는 기본 명령에 적용하지 않습니다**.

### 5-4. 설치 내역 조회 및 Kubeconfig

~~~bash
gcloud container clusters describe "$CLUSTER" \
  --project="$SVC_PROJECT" --region="$REGION" \
  --format="yaml(status,autopilot.enabled,releaseChannel,network,subnetwork,ipAllocationPolicy,privateClusterConfig)"

gcloud compute networks subnets describe "$NODE_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --format="yaml(ipCidrRange,secondaryIpRanges)"

# Private Endpoint 접속 승인이 된 환경에서만 실행
mkdir -p "$HOME/.kube"
chmod 700 "$HOME/.kube"
export KUBECONFIG="$HOME/.kube/config_l2comn-autopilot"
gcloud container clusters get-credentials "$CLUSTER" \
  --project="$SVC_PROJECT" --region="$REGION" --internal-ip
kubectl config current-context
~~~

Kubeconfig 발급 자체와 실제 Kubernetes API/Pod 연동 검증은 서로 다른 단계입니다. 접속이 막혀 있으면 미검증 사항으로 기록합니다.

## 6. 1차 설치 보고와 후속 검증 분리

| 구분 | 1차 설치 보고에 넣을 수 있는 값 | 넣지 말아야 할 주장 |
|---|---|---|
| GKE | 실제 생성 후 Cluster ID/설정/Status | 배치가 운영과 동일하게 동작함 |
| Network | 실제 VPC·서브넷·IP·IAM 반영 기록 | 실제 NFS Mount 성공 |
| AR | 권한 부여·이미지 식별 확인 | Pod의 AR Pull 성공 |
| BQ | 필요 인증 방식 및 역할 정리 | 실제 BigQuery SQL 성공 |
| RSVP | 외부 개발환경 테스트 내용 참고 | 실제 환경 RSVP 실행 성공 |

1차 설치 산출물: 구성표, 설치/변경 명령 실행 내역, 클러스터/네트워크 조회 결과, 권한 부여 명세, 후속 테스트 승인 요청서 및 미해결 항목.

## 7. 중요 위험

- Filestore IP: 이전 출력에는 NFS_SERVER와 MGMT_VM_IP가 모두 172.32.10.2로 기록됨. NFS 관리자에게 실제 Export 주소 확인.
- AR: 1a751e99d693:v1와 python-bq-batch:v1 불일치. 실제 이미지명·다이제스트 및 RSVP 업무 이미지 확정.
- Pod IP /24: Autopilot 확장성 불충분 가능성. 실제 노드별 할당/Workload 규모 기준 검토.
- Private Endpoint: TCP443, 승인 CIDR, IAM/RBAC를 별개로 검토. 보안 제한 자동 해제 금지.
- 키: .oef/.oefj, kubeconfig를 GitHub에 포함하지 않음.
- 운영 영향: Cron과 /ssw/dlk/client_gke 공통 심볼릭 링크는 1차에서 절대 변경하지 않음.

## 8. 완료보고 문구 (설치 실제 완료 후에만 사용)

외부 개발환경의 GKE Autopilot 및 RSVP 배치 테스트 결과를 참고하여 신규 환경의 Shared VPC 및 GKE Autopilot 1차 인프라 설치를 수행하였습니다. 실제 대상 환경의 AR Pull, Filestore Mount, BigQuery 인증/조회, RSVP 업무 실행 검증은 별도 승인 후 2~3차 단계에서 수행할 예정입니다.

**현재 상태:** 위 문구는 향후 완료보고 예시입니다. 실제 대상 환경에 대한 설치·접속·업무 테스트 결과는 아직 확인되지 않았습니다.
