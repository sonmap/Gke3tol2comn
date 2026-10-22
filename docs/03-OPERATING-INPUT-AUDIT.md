# 03. 2026-10-22 외부 개발환경 입력값 대조표

이 문서는 사용자가 제공한 외부 개발환경 설치/RSVP 테스트 자료(Pasted text(20261022-103357).txt 등)를 기준으로 작성했으며, 변경 지시에 따라 **GKE 생성·조회 실행 계정을 user01@sonmap.net으로 통일**했습니다. RSVP 실제 배치 시험은 1차에서 제외하고 3차로 연기했습니다.
이번 작업은 1차 인프라 설치 계획 수정이며 GCP 자원 생성·변경 또는 실제 전환 대상 환경 배치 실행은 수행하지 않았습니다. 첨부 문서의 실행 로그는 외부 개발환경 참고 결과로 분류합니다.

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
| EXEC_ACCOUNT | user01@sonmap.net | 2026-10-22 변경 요청: GKE 생성·조회·RSVP 실행 계정 |
| ADMIN_ACCOUNT | admin@sonmap.net | IAM 변경 주체 |
| Node SA | SVC_PROJECT_NUM-compute@developer.gserviceaccount.com | 실제 사용 SA 확인 |

## 2. 외부 개발환경 RSVP 단일 과제 관련 값 (후속 2~3차 참고)

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
| NFS PATH (향후 Pod) | /batch_gke/l2/rsvp |
| VM NFS Export Root (확인 필요) | /batch_gke → /mnt/batch_gke |
| VM RSVP 경로 | /mnt/batch_gke/l2/rsvp |
| VM 실행기 경로 후보 | /mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh |
| Pod mount | /home/jupyter |
| key | /home/jupyter/.oefj |
| Query test | gcp-prod-edp-lake.DLKUDF.L2MQ_TL_SUBJ_H_TEST |
| PVC 예시 | 20Gi, ROX, Bound |
| 종료 로그 | Pending → Running → Succeeded, 삭제 완료 (외부 개발환경 제공 출력. 실제 대상 환경 미검증) |

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

## 4. 1차 인프라 및 VM NFS 마운트 상태 조회 (GKE Pod 시험 아님)

기존 Filestore/IP 불일치 항목은 유지합니다. GKE Pod에서 NFS 검증이 불가하므로, **VM에서 실제 NFS 서버·Export를 확인한 뒤 NFS 연결 상태와 /mnt 경로를 조회**합니다. 이미 NFS가 연결되어 있다면 재마운트하지 않습니다. 신규 VM 마운트 및 위험 통제는 [04. VM NFS /mnt 가이드](04-VM-NFS-MOUNT.md)를 참조하십시오.

**명령은 `user01@sonmap.net`으로 실행합니다.** 자료의 `admin@sonmap.net`은 IAM 변경 관리자 계정이며 RSVP 시험 실행에는 사용하지 않습니다.

~~~bash
gcloud auth list
gcloud config set account user01@sonmap.net
gcloud config get-value account
~~~

과거 로그의 `/home/admin_sonmap_net/.kube/config_l2comn-autopilot`은 당시 Linux 실행자의 위치를 나타냅니다. 이번 변경 이후에는 현재 로그인한 OS 사용자의 `$HOME/.kube/config_l2comn-autopilot`을 사용하며, 별도로 생성한 신규 Kubeconfig를 확인합니다.

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

## kubectl API 연결/Pod 조회는 2차 연동 검증 시 별도 수행:
# KUBECONFIG="$HOME/.kube/config_l2comn-autopilot" kubectl get pods -n l2comm-batch

findmnt -t nfs,nfs4 -o TARGET,SOURCE,FSTYPE,OPTIONS
findmnt -T /mnt/batch_gke -o TARGET,SOURCE,FSTYPE,OPTIONS
ls -ld /mnt/batch_gke/l2/rsvp
# 2차 검증 승인 후 key_file 유무만 확인 (키 원문 출력 금지):
# test -s /mnt/batch_gke/l2/rsvp/.oefj && echo "key_file_exists"
~~~

## 5. 통신 및 권한 주체

| 흐름 | 적용 위치/주체 |
|---|---|
| 관리 VM → GKE API | Private Endpoint TCP443 및 실행 사용자 Kubernetes RBAC |
| GKE → Shared VPC | Host Project / GKE Service Agent 및 관련 subnet networkUser |
| GKE Node → AR | 실제 Node SA / AR repository Reader |
| GKE → Filestore | Host Project FW 및 Filestore 허용 네트워크 (실제 패킷 Source 확인) |
| Pod Python → BigQuery | JSON key의 SA / Job 실행 권한 + 테스트 테이블 읽기 |

### 1차 적용 조건

1차는 Shared VPC/IP/IAM/GKE 설치와 구성 기록 및 **가능한 범위의 VM NFS Mount·/mnt 경로 확인**까지 수행합니다. 실제 GKE Pod의 AR Pull·Filestore Mount, BQ 인증/SQL, RSVP run-gke.sh 실행 검증은 2~3차입니다. **VM NFS 성공은 Pod Filestore 연결 검증 결과로 대체할 수 없습니다.**

### 적용 조건

실제 IP 중복·quota·Service Agent IAM·AR 이미지·NFS 서버 IP·GKE Private Endpoint 접근 정책을 검증한 뒤 GCP 변경을 승인해야 합니다.
--no-enable-authorized-networks-on-private-endpoint는 첨부 운영 설정에 있으나 보안팀 승인 없이 제한 해제하지 않습니다.
