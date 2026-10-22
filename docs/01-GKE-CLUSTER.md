# 01. 1차 인프라 설치 — GKE Autopilot 생성 및 기반 구성

**단계:** 1차 인프라 설치. 외부 개발환경 RSVP 시험 결과를 근거로 구성한 **설치 작업 절차서**입니다. 실제 대상 환경에서 업무 Pod, AR Pull, Filestore NFS Mount, BQ 인증·조회 시험은 이번 단계에서 수행하지 않습니다. 명령은 GCP 운영 담당자가 승인 후 실행합니다.

## 1차 작업의 설치 완료 기준과 테스트 보류

- **설치:** Shared VPC 및 Node/Pod/CP Subnet 승인·설정, Service Project API 및 IAM, GKE Autopilot 생성, Private Endpoint 및 kubeconfig(가능한 범위), AR/NFS 정책 사전 준비.
- **설치 증적:** 프로젝트/서브넷/클러스터 describe 출력, IAM 바인딩/연결 구성 기록, GKE RUNNING 확인.
- **후속 시험:** 컨테이너 이미지 Pull, PV/PVC Bound, NFS 실제 Mount, BQ SELECT, RSVP Pod Succeeded는 **2~3차**로 분리합니다.
- **외부 개발환경 참고:** 제공 자료에는 PV/PVC/Pod 생성, Pending→Running→Succeeded 및 리소스 삭제 예시가 있으나 대상 인프라의 검증 결과로 기재하지 않습니다.

상세 단계 및 승인 조건은 [00-PHASE1-INFRA-INSTALL.md](00-PHASE1-INFRA-INSTALL.md) 참조.

## 운영 입력값과 검증 보류

2026-10-22 첨부 파일을 기준으로 Sandbox Service Project/Host VPC/3개 CIDR/Regular 채널을 반영했습니다. **설정값은 명령의 입력 후보이며 GCP 생성 완료를 의미하지 않습니다.** `/28` Node 대역은 운영 자료 주석의 128개가 아니라 16개 주소이며 4개 예약 후 12개 사용 가능합니다. `/24` Pod CIDR의 노드 수용량도 현재 GKE Autopilot의 노드별 Pod CIDR 크기를 조회해 검증해야 합니다. 클러스터 및 서브넷 기존 존재 여부 확인 후 신규 생성이 필요한 경우에만 create 명령을 승인해 실행합니다.

관리 VM `172.32.10.2`와 원본 실행 로그 NFS_SERVER `172.32.10.2`는 동일 주소로 기록되어 있습니다. 이전 문서에 별도의 Filestore IP가 있었으므로 **NFS 서버 IP는 미확정**입니다. 올바른 NFS 주소를 확인하기 전에는 Pod Mount 테스트를 진행하지 않습니다.

## 1. 기본 파라미터

~~~bash
export HOST_PROJECT="gcp-prod-edp-hub-vpchost"
export SVC_PROJECT="gcp-sbx-edp-comn-509423"
export AR_PROJECT="gcp-prod-edp-hub-vpchost"
export REGION="asia-northeast3"
export NETWORK="vpc-prod-edp-hub"
export CLUSTER="gkea-prod-l2comn-batch"
export NODE_SUBNET="subnet-prod-l2comn-gke"
export POD_RANGE="subnet-prod-l2comn-gke-pod"
export CP_SUBNET="subnet-prod-l2comn-gke-cp"
export RELEASE_CHANNEL="regular"

# 반드시 IP팀 승인값으로 교체하고 중복성 점검:
export NODE_CIDR="10.253.0.0/28" # 총 16개, Primary 사용 가능 12개
export CP_CIDR="10.253.2.0/28"
export POD_CIDR="10.253.1.0/24" # Pod Secondary 총 256개
# GKE 생성·검증 및 RSVP 테스트는 user01@sonmap.net으로 수행
export EXEC_ACCOUNT="user01@sonmap.net"
export ADMIN_ACCOUNT="admin@sonmap.net"  # IAM 부여 등 관리자 승인 작업 전용
gcloud auth list
gcloud config set account "$EXEC_ACCOUNT"
test "$(gcloud config get-value account 2>/dev/null)" = "$EXEC_ACCOUNT" || exit 1

export SVC_PROJECT_NUM="$(gcloud projects describe "$SVC_PROJECT" --format='value(projectNumber)')"
export NODE_SA="$SVC_PROJECT_NUM-compute@developer.gserviceaccount.com"
export MGMT_VM_IP="172.32.10.2"
export GKE_AGENT="service-$SVC_PROJECT_NUM@container-engine-robot.iam.gserviceaccount.com"

echo "SVC_PROJECT_NUM=$SVC_PROJECT_NUM"
~~~

### CIDR 승인 필수

- NODE CIDR: GKE Node Primary(/28 입력값; 총 16개/사용 가능 12개 주소). 과거 /25 표기는 이 문서와 다름.
- POD CIDR: Pod Secondary 10.253.1.0/24 (첨부 설정값). 사내/타 클라우드 및 연결 네트워크 중복 확인 필수.
- CP CIDR: Private Endpoint 전용 10.253.2.0/28 서브넷.
- Services: 최신 Autopilot은 기본적으로 GKE 관리 대역 34.118.224.0/20 사용 가능. 네트워크 정책상 직접 지정해야 한다면 별도 Services Secondary 범위도 승인 후 설정.
- 기존 서브넷이 있으면 **재생성 금지**. 현재 대역과 네트워크 연결부터 확인.

## 2. 현재 설정 및 GKE 프로젝트 검증 (읽기 전용)

~~~bash
gcloud auth list
gcloud projects describe "$SVC_PROJECT" --format='yaml(projectId,projectNumber)'
gcloud compute shared-vpc get-host-project "$SVC_PROJECT"
gcloud compute networks subnets list --project="$HOST_PROJECT" --regions="$REGION"
gcloud container clusters list --project="$SVC_PROJECT" --region="$REGION"
gcloud container subnets list-usable --project="$SVC_PROJECT" --network-project="$HOST_PROJECT"
~~~

이미 클러스터가 존재하면 [03 검증](#5-gke-autopilot-생성-승인-후-최초-1회)에서 무조건 create 명령을 실행하지 않고 설정 비교 단계로 이동.

## 3. API · Shared VPC 권한 (담당자별 작업)

**실제 GKE 실행 계정은 `user01@sonmap.net`**입니다. API 활성화·네트워크 및 IAM 수정은 필요 권한을 가진 담당자만 수행합니다. `admin@sonmap.net`은 권한 부여 등 관리자 작업에만 사용하는 별도 계정이며, GKE 테스트 실행 주체로 대체하지 않습니다. 사용자 계정 및 Node Service Account·GKE Service Agent는 서로 다른 주체입니다.

승인 권한을 가진 담당자가 다음 API가 활성화되었는지 확인한 뒤, 비활성일 경우에만 실행.

~~~bash
gcloud services enable container.googleapis.com compute.googleapis.com --project="$SVC_PROJECT"
gcloud beta services identity create --service=container.googleapis.com --project="$SVC_PROJECT"
~~~

| 주체 | 어디에 권한 부여 | 역할/범위 | 점검 |
|---|---|---|---|
| GKE 생성 실행 사용자 | Service Project | roles/container.admin (생성 기간) | clusters.create/get |
| GKE 생성 실행 사용자 | Host Project Node/CP 서브넷 | roles/compute.networkUser | shared subnet 사용 |
| 실행 사용자 | Node SA | roles/iam.serviceAccountUser | serviceAccounts.actAs |
| GKE Service Agent | Host Project | roles/container.hostServiceAgentUser | Shared VPC 구성 |
| GKE Service Agent | 관련 공유 서브넷 | roles/compute.networkUser | Node/CP 서브넷 접근 |
| Node SA | Service Project | roles/container.defaultNodeServiceAccount 등 | 노드 기본 동작 |
| Node SA | 실제 Edge AR 리포지토리 | roles/artifactregistry.reader | 이미지 Pull |

IAM 수정 명령 예시 (Host Project 보안 담당자만, 현행 바인딩 먼저 확인). 관리자 계정으로 변경한 경우 끝나고 user01으로 복귀:

~~~bash
gcloud projects add-iam-policy-binding "$HOST_PROJECT" \
  --member="serviceAccount:$GKE_AGENT" \
  --role="roles/container.hostServiceAgentUser"

gcloud compute networks subnets add-iam-policy-binding "$NODE_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --member="serviceAccount:$GKE_AGENT" \
  --role="roles/compute.networkUser"
~~~

CP 서브넷도 별도 권한 검토. 별도 Google APIs Service Agent가 필요할 경우 해당 리소스에 필요한 권한만 추가. 실행 사용자/서비스 계정의 유형(user/group/serviceAccount)은 실계정에 맞춰야 함.

user01 생성·접속 권한은 실제 IAM 부여 후 점검합니다. `roles/container.admin`, 공유 서브넷 `roles/compute.networkUser`, 노드 SA에 대한 `roles/iam.serviceAccountUser` 등 필요한 범위를 확인해야 하며, **문서에 계정명을 쓰는 것만으로 권한이 생기지는 않습니다.**

~~~bash
# 권한 작업을 관리자 계정으로 진행했다면 이후 GKE 수행 계정을 되돌림
gcloud config set account "$EXEC_ACCOUNT"
gcloud config get-value account
~~~

## 4. Host Project 서브넷 (신규 필요할 때만)

~~~bash
# 관리자: 아래 명령은 실제 자원을 생성합니다. CIDR 승인·변수 검증 후 실행.
gcloud compute networks subnets create "$NODE_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --network="$NETWORK" --range="$NODE_CIDR" \
  --secondary-range="$POD_RANGE=$POD_CIDR" \
  --enable-private-ip-google-access

gcloud compute networks subnets create "$CP_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --network="$NETWORK" --range="$CP_CIDR" \
  --enable-private-ip-google-access
~~~

사전 확인:

~~~bash
gcloud compute networks subnets describe "$NODE_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --format='yaml(ipCidrRange,secondaryIpRanges,privateIpGoogleAccess)'
gcloud compute networks subnets describe "$CP_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --format='yaml(ipCidrRange,privateIpGoogleAccess)'
~~~

## 5. GKE Autopilot 생성 (승인 후 최초 1회)

~~~bash
# 이 단계부터 GKE 작업은 user01 계정으로 실행
gcloud config set account "$EXEC_ACCOUNT"
gcloud config get-value account
~~~



~~~bash
# 신규 클러스터 생성: 이미 존재하면 실행하지 않음
# 승인된 Node/Pod/CP CIDR 및 기존 자원 여부 확인 후만 실행
gcloud container clusters create-auto "$CLUSTER" \
  --project="$SVC_PROJECT" \
  --region="$REGION" \
  --network="projects/$HOST_PROJECT/global/networks/$NETWORK" \
  --subnetwork="projects/$HOST_PROJECT/regions/$REGION/subnetworks/$NODE_SUBNET" \
  --cluster-secondary-range-name="$POD_RANGE" \
  --private-endpoint-subnetwork="projects/$HOST_PROJECT/regions/$REGION/subnetworks/$CP_SUBNET" \
  --service-account="$NODE_SA" \
  --enable-private-nodes \
  --enable-private-endpoint \
  --release-channel="$RELEASE_CHANNEL"
~~~

- 위 구성은 Private Endpoint 사용. 네트워크 및 관리 VM 라우팅이 확보되어야 함.
- 외부 개발환경의 명령에는 `--no-enable-authorized-networks-on-private-endpoint`가 포함되었으나 **1차 설치 기본 명령에는 포함하지 않습니다**. 승인 네트워크 제한 해제가 실제 대상 환경에 필요한 경우 보안팀에서 별도 승인한 뒤 적용합니다. 네트워크 도달성 및 Kubernetes IAM/RBAC는 계속 분리 통제합니다.
- 서비스용 IP를 수동 관리하는 환경에서는 승인된 Services 범위 및 --services-secondary-range-name 옵션을 추가.
- 클러스터 생성이 프로젝트·API·조직 정책으로 실패하면 권한과 quota, GKE Service Agent, Shared VPC 상태를 점검.

## 6. VM → Private Endpoint 및 kubeconfig 발급

이 과정도 `user01@sonmap.net`으로 수행합니다. Kubeconfig 저장 위치는 명령을 실행하는 **Linux OS 사용자**의 `$HOME`으로 정해지므로 Google 계정 이메일과 OS 홈 디렉터리 이름이 같다고 가정하지 않습니다.

~~~bash
mkdir -p "$HOME/.kube"
chmod 700 "$HOME/.kube"
export KUBECONFIG="$HOME/.kube/config_l2comn-autopilot"
gcloud container clusters get-credentials "$CLUSTER" \
  --project="$SVC_PROJECT" --region="$REGION" --internal-ip

kubectl config current-context
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'
echo

# 2차 시스템 연동 검증 때에만 실제 Kubernetes API/Pod 조회:
# kubectl cluster-info --request-timeout=15s
# kubectl get nodes --request-timeout=15s
# kubectl get pods -A --request-timeout=15s
~~~

Kubeconfig는 사용자별 파일이며 소스 저장소 커밋 금지. **1차는 인증 설정 및 클러스터의 관리 API 조회 가능 범위까지만** 기록합니다. 실제 Kubernetes API 접속/Pod 동작 검증은 2차에서 수행하며, 연결 실패 시 Endpoint TCP443 도달성 → 인증 플러그인/로그인 → IAM/RBAC 순서로 분리 점검합니다.

## 7. Artifact Registry 연동 사전 준비 (실제 Pull은 2차)

외부 개발환경 스모크 테스트의 참고 이미지입니다. 이 단계에서는 실제 대상 환경 Pod Pull을 실행하지 않습니다:

~~~bash
export TEST_IMAGE="asia-northeast3-docker.pkg.dev/gcp-prod-edp-hub-vpchost/ar-l2comm-python/python-bq-batch:v1"  # 로그상의 이미지. 1a751e99d693:v1와 대조 필수
# 실제 RSVP의 운영 이미지는 run-gke.sh 안의 DOCKER_IMAGE/--docker-image 값을 확인 후 사용
gcloud artifacts docker images list "asia-northeast3-docker.pkg.dev/gcp-prod-edp-hub-vpchost/ar-l2comm-python" \
  --project="$AR_PROJECT" --include-tags
~~~

Edge AR 담당자가 실제 이미지가 담긴 리포지토리 대상으로 Node SA Reader 적용:

~~~bash
gcloud artifacts repositories add-iam-policy-binding ar-l2comm-python \
  --project="$AR_PROJECT" --location="$REGION" \
  --member="serviceAccount:$NODE_SA" \
  --role="roles/artifactregistry.reader"
~~~

**Node SA의 이미지 Pull 권한과 Pod 내부 .oefj BigQuery 권한은 서로 다릅니다.**
업무 이미지가 다른 AR 또는 dlk-lguplus-deeplearing-Tags에 있다면 이 명령의 대상 리포지토리를 실제 이름으로 변경.

## 8. Filestore 접근 정책 사전 준비 (실제 NFS Mount는 2차)

- 운영 자료에는 NFS_PATH=/batch_gke/l2/rsvp, Pod 마운트=/home/jupyter로 기록되어 있습니다.
- NFS_SERVER는 실행 로그상 `172.32.10.2`이나 이 주소가 MGMT_VM_IP에도 쓰여 있으므로 Filestore 담당자에게 실제 서버 IP를 필수 재확인. 검증 없이 NFS_SERVER를 MGMT_VM_IP로 대체하지 않음.
- Host VPC 방화벽과 Filestore 허용 클라이언트 범위 두 군데 확인.
- NFSv4.1이면 TCP 2049를 확인하고, NFSv3이면 rpcbind/mountd 등 실제 필요한 포트 추가 검토.
- 방화벽의 소스는 **관리 VM이 아닌 NFS 접속의 실제 Node/Pod 소스 주소**를 확인한 뒤 결정. 방화벽 전체 허용(0.0.0.0/0) 금지.
- 이번 **샘플 테스트**의 NFS PV/PVC는 첨부 로그와 맞춰 **20Gi ReadOnlyMany(ROX)**, Pod 마운트는 /home/jupyter/readOnly로 구성합니다. 실제 업무의 쓰기 필요 여부는 별도로 확인합니다.

~~~bash
# 실제 Filestore NFS 서버 주소/Export 확인 후, 2차 검증 시에만 실행:
# ls -ld /mnt/batch_gke/l2/rsvp
# find /mnt/batch_gke/l2/rsvp -maxdepth 1 -name '.oef*' -printf '%f %m %u:%g\n'

# 2차 시스템 테스트 승인 후(1차 설치 단계에서 실행하지 않음):
# kubectl describe pod <POD_NAME> -n l2comm-batch
# kubectl get pv,pvc -A
~~~

### 8-1. 1차 대체 검증: 관리 VM에서 NFS 마운트 및 /mnt 경로 확인

**실제 GKE Pod에서 Filestore NFS Mount 검증은 현재 수행하지 못합니다.** 위 Filestore 서버·방화벽·PV/PVC 구성 설명은 **그대로 유지**하되, 1차에는 Linux 관리 VM이 실제 NFS Export에 접속할 수 있는지 별도 점검합니다.

- 기존 VM에 NFS가 이미 마운트된 경우: `findmnt -t nfs,nfs4` 및 `findmnt /mnt/batch_gke`로 기존 연결을 확인하고 중복 마운트하지 않습니다.
- VM NFS 마운트 후보: 서버 Export `/batch_gke` → VM `/mnt/batch_gke` → RSVP `/mnt/batch_gke/l2/rsvp`. 실제 Export가 다르면 경로를 조정해야 합니다.
- VM 접근 확인 대상: `/mnt/batch_gke/l2/rsvp/GP_L2RSVP_001_1/python`, `/mnt/batch_gke/l2/rsvp/.oefj`(존재·권한만 확인), `/mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh`(같은 Export에 있는 경우).
- NFS 서버 IP는 운영 담당자가 실주소를 확정해야 합니다. 첨부자료에는 관리 VM과 NFS_SERVER가 동일 IP로 표기되어 혼동이 있으므로 무조건 `172.32.10.2`로 마운트하지 않습니다.
- 신규 VM 마운트는 먼저 별도 임시 디렉터리에서 **읽기 전용(ro)**으로 확인합니다. 실제 `/mnt/batch_gke` 경로에 기존 로컬 데이터가 있으면 덮거나 가리지 않습니다.
- **VM NFS 접속 성공은 GKE Node/Pod 접속 성공을 의미하지 않습니다.** GKE 방화벽·PV/PVC·Pod 마운트 및 BigQuery 호출은 후속 2차 검증에서 수행합니다.

<details>
<summary>VM에서 현재 NFS 상태를 빠르게 확인할 수 있는 명령</summary>

~~~bash
findmnt -t nfs,nfs4 -o TARGET,SOURCE,FSTYPE,OPTIONS
findmnt -T /mnt/batch_gke -o TARGET,SOURCE,FSTYPE,OPTIONS
mountpoint /mnt/batch_gke
ls -ld /mnt/batch_gke/l2/rsvp
ls -ld /mnt/batch_gke/l2/rsvp/GP_L2RSVP_001_1/python
~~~

</details>

임시 NFS 마운트, `/mnt/batch_gke` 정식 적용, 선택적 `fstab`, 진단·증적은 **[04. VM NFS 및 /mnt 마운트 절차](04-VM-NFS-MOUNT.md)**에 정리했습니다. 이 문서의 기존 Filestore/방화벽 요청과 GKE Pod 마운트 절차는 향후 사용을 위해 유지합니다.

Filestore 연결 장애는 Pod Events의 FailedMount, timeout, permission denied로 구분.

## 9. 1차 인프라 설치 완료조건 (실제 업무 검증 제외)

| 항목 | Go 조건 |
|---|---|
| 클러스터 | RUNNING, Autopilot enabled |
| Kubeconfig | 파일/Context 및 Private Endpoint 설정 확인 (kubectl API 통신 검증은 2차) |
| AR | 실제 AR Repository IAM 정책·이미지 식별 등 **연동 준비** |
| Filestore (VM) | 1차에 VM 기준 NFS 마운트·/mnt 경로·접근권한만 확인 가능(실제 수행 시 결과 기록) |
| Filestore (GKE) | 기존 GKE 연동 설계·FW 요청 유지, Pod Mount/PV/PVC는 2차 미검증 |
| BQ | SA JSON 키 위치·필요 권한 정리, **실제 SQL 테스트 제외** |
| Pod | 실제 배포/삭제 미수행 (2~3차 예정) |
| 운영 | 기존 Cron 및 GKE Standard 유지 |

참고: https://docs.cloud.google.com/kubernetes-engine/docs/how-to/cluster-shared-vpc
참고: https://docs.cloud.google.com/sdk/gcloud/reference/container/clusters/create-auto
참고: https://docs.cloud.google.com/kubernetes-engine/security/configure-node-service-accounts
