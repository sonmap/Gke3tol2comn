# 03. 2026-10-22 운영 입력값 대조표

이 문서는 사용자가 제공한 Pasted text(20261022-100920).txt를 기준으로 작성했습니다.
문서 작성만 진행했으며 GCP 자원 생성·변경 또는 운영 배치 실행은 수행하지 않았습니다.

## 1. 원본 설정표

| 항목 | 첨부 설정 | 비고 |
|---|---|---|
| HOST_PROJECT | gcp-prod-edp-hub-vpchost | Shared VPC Host |
| SVC_PROJECT | gcp-sbx-edp-comn-509423 | 테스트 Service Project |
| REGION | asia-northeast3 | Seoul |
| NETWORK | vpc-prod-edp-hub | VPC |
| NODE_SUBNET | subnet-prod-l2comn-gke | Node Primary |
| POD_RANGE | subnet-prod-l2comn-gke-pod | Pod Secondary |
| CP_SUBNET | subnet-prod-l2comn-gke-cp | Private Endpoint Subnet |
| NODE_CIDR | 10.253.0.0/28 | 16개 중 GCP Primary 예약 4개 → 사용 가능 12개 |
| POD_CIDR | 10.253.1.0/24 | 총 256개 |
| CP_CIDR | 10.253.2.0/28 | 총 16개 |
| RELEASE_CHANNEL | regular | stable에서 변경 |
| CLUSTER | gkea-prod-l2comn-batch | 존재 시 describe |
| MGMT_VM_IP | 172.32.10.2 | 관리 VM |
| EXEC_ACCOUNT | chomap@sonmap.net | 로그인·권한 확인 |
| ADMIN_ACCOUNT | admin@sonmap.net | IAM 변경 주체 |
| Node SA | SVC_PROJECT_NUM-compute@developer.gserviceaccount.com | 실제 사용 SA 확인 |

## 2. RSVP 단일 과제 관련 값

| 항목 | 첨부 출력 |
|---|---|
| 과제 | GP_L2RSVP_001_1 |
| 스크립트 | /mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh |
| 기존 공통 링크 | /ssw/dlk/client_gke → client_gke_v1.0 |
| 신규 테스트 파일 | /ssw/dlk/client-gke-auto (별도 복제, 원본 링크 유지) |
| kubeconfig 실제 로그 | /home/admin_sonmap_net/.kube/config_l2comn-autopilot |
| namespace/KSA | l2comm-batch / ksa-l2comm-batch |
| 이미지 로그값 | asia-northeast3-docker.pkg.dev/gcp-prod-edp-hub-vpchost/ar-l2comm-python/python-bq-batch:v1 |
| CPU/MEM/GPU | 4 / 16Gi / 0 |
| NFS PATH | /batch_gke/l2/rsvp |
| Pod mount | /home/jupyter |
| key | /home/jupyter/.oefj |
| Query test | gcp-prod-edp-lake.DLKUDF.L2MQ_TL_SUBJ_H_TEST |
| PVC 예시 | 20Gi, ROX, Bound |
| 종료 로그 | Pending → Running → Succeeded, 삭제 완료 (제공 예시) |

## 3. 불일치 및 사전 검증 의무

| 우선순위 | 문제 | 조치 |
|---|---|---|
| 필수 | NODE_CIDR은 /28인데 주석은 128개, Filestore 허용 대역은 /25 | /28 = 16 IP, 가용 12. 실제 Primary와 방화벽 소스 범위 확인 |
| 필수 | 172.32.10.2는 MGMT_VM_IP와 NFS_SERVER 양쪽에 기재 | Filestore 실제 서버 IP 확인. 확인 전 Pod NFS 시험 금지 |
| 필수 | TEST_IMAGE 는 1a751e99d693:v1; 실행 로그는 python-bq-batch:v1 | AR images list로 실제 태그/이미지 확인 |
| 필수 | kubeconfig 이름은 config_new-autopilot, config_l2comn-autopilot, l2comn_gke로 혼재 | 실행 로그의 config_l2comn-autopilot을 기본으로, 실제 VM 경로 확인 |
| 중요 | 기존 Python config.py는 .oef, 신규 smoke는 .oefj | 실제 Pod 내 키 경로/프로그램별 환경 변수 대조 |
| 중요 | 기존 namespace nms-prd, 신규 l2comm-batch | client/Pod/KSA/RBAC 통일 |
| 중요 | 예전 테스트 YAML은 100Gi RWX, 이번 로그는 20Gi ROX | 현재 템플릿 20Gi ROX로 보정하되 실제 NFS export 권한 확인 |

## 4. 현장 검증 명령 (읽기 전용)

~~~bash
gcloud container clusters describe gkea-prod-l2comn-batch \
  --project=gcp-sbx-edp-comn-509423 --region=asia-northeast3 \
  --format="yaml(status,autopilot.enabled,releaseChannel,network,subnetwork,ipAllocationPolicy,privateClusterConfig)"

gcloud compute networks subnets describe subnet-prod-l2comn-gke \
  --project=gcp-prod-edp-hub-vpchost --region=asia-northeast3 \
  --format="yaml(ipCidrRange,secondaryIpRanges)"

gcloud artifacts docker images list \
  asia-northeast3-docker.pkg.dev/gcp-prod-edp-hub-vpchost/ar-l2comm-python \
  --project=gcp-prod-edp-hub-vpchost --include-tags

KUBECONFIG="$HOME/.kube/config_l2comn-autopilot" kubectl get pods -n l2comm-batch

ls -ld /mnt/batch_gke/l2/rsvp
test -s /mnt/batch_gke/l2/rsvp/.oefj && echo "key_file_exists"
~~~

## 5. 통신 및 권한 주체

| 흐름 | 적용 위치/주체 |
|---|---|
| 관리 VM → GKE API | Private Endpoint TCP443 및 실행 사용자 Kubernetes RBAC |
| GKE → Shared VPC | Host Project / GKE Service Agent 및 관련 subnet networkUser |
| GKE Node → AR | 실제 Node SA / AR repository Reader |
| GKE → Filestore | Host Project FW 및 Filestore 허용 네트워크 (실제 패킷 Source 확인) |
| Pod Python → BigQuery | JSON key의 SA / Job 실행 권한 + 테스트 테이블 읽기 |

### 적용 조건

실제 IP 중복·quota·Service Agent IAM·AR 이미지·NFS 서버 IP·GKE Private Endpoint 접근 정책을 검증한 뒤 GCP 변경을 승인해야 합니다.
--no-enable-authorized-networks-on-private-endpoint는 첨부 운영 설정에 있으나 보안팀 승인 없이 제한 해제하지 않습니다.
