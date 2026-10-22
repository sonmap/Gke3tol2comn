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

## 0. 변수 정의

본 장은 **외부 개발환경 원본의 0~8단계 순서를 복원**한 설치 절차입니다. 신규 터미널에서는 0단계 변수를 다시 선언합니다. 실제 고객 환경에서 명령을 실행하기 전 IP·IAM·보안 정책 승인이 필요하며, 기존 자원이 존재하면 create 명령을 실행하지 않습니다.

~~~bash
# ── 프로젝트 ─────────────────────────────────────────────
export HOST_PROJECT="gcp-prod-edp-hub-vpchost"
export SVC_PROJECT="gcp-sbx-edp-comn-509423"

# ── 네트워크 ─────────────────────────────────────────────
export REGION="asia-northeast3"
export NETWORK="vpc-prod-edp-hub"
export NODE_SUBNET="subnet-prod-l2comn-gke"
export POD_RANGE="subnet-prod-l2comn-gke-pod"
export CP_SUBNET="subnet-prod-l2comn-gke-cp"

export NODE_CIDR="10.253.0.0/28"  # 총 16 IP, GCP 예약 4개 제외 가용 12
export POD_CIDR="10.253.1.0/24"   # 256 IP, Pod 256개를 뜻하는 것은 아님
export CP_CIDR="10.253.2.0/28"    # Private Endpoint 전용

export MGMT_VM_IP="172.32.10.2"

# ── GKE ─────────────────────────────────────────────────
export CLUSTER="gkea-prod-l2comn-batch"
export RELEASE_CHANNEL="regular"

# ── 실행 및 관리자 계정 ──────────────────────────────────
export EXEC_ACCOUNT="user01@sonmap.net"
export ADMIN_ACCOUNT="admin@sonmap.net"
export EXEC_USER="user:${EXEC_ACCOUNT}"

gcloud auth list
gcloud config set account "$EXEC_ACCOUNT"
gcloud config get-value account

# ── 프로젝트 번호 자동 조회 ─────────────────────────────
export SVC_PROJECT_NUM="$(gcloud projects describe "$SVC_PROJECT" \
  --format='value(projectNumber)')"
echo "SVC_PROJECT_NUM=${SVC_PROJECT_NUM}"
if ! [[ "$SVC_PROJECT_NUM" =~ ^[0-9]+$ ]]; then
  echo "ERROR: 프로젝트 번호 조회 실패 — 진행 중단" >&2
  return 1 2>/dev/null || exit 1
fi

# ── Google-managed Service Agents / Node SA ────────────
export GKE_AGENT="serviceAccount:service-${SVC_PROJECT_NUM}@container-engine-robot.iam.gserviceaccount.com"
export API_AGENT="serviceAccount:${SVC_PROJECT_NUM}@cloudservices.gserviceaccount.com"
export NODE_SA="${SVC_PROJECT_NUM}-compute@developer.gserviceaccount.com"

export NETWORK_URI="projects/${HOST_PROJECT}/global/networks/${NETWORK}"
export NODE_SUBNET_URI="projects/${HOST_PROJECT}/regions/${REGION}/subnetworks/${NODE_SUBNET}"
export CP_SUBNET_URI="projects/${HOST_PROJECT}/regions/${REGION}/subnetworks/${CP_SUBNET}"

printf '%s\n' "$EXEC_USER" "$GKE_AGENT" "$API_AGENT" "$NODE_SA"
printf 'NETWORK=%s\nNODE=%s\nCP=%s\n' "$NETWORK_URI" "$NODE_SUBNET_URI" "$CP_SUBNET_URI"
~~~

**IP 주의:** Node 10.253.0.0/28은 원본 주석의 128개가 아닌 **16개**입니다. Pod 10.253.1.0/24는 노드별 Pod IP 예약을 고려하면 확장 여력이 작을 수 있으므로 실제 Autopilot 용량 요구에 맞게 승인하십시오. Filestore 방화벽 요청의 Node /25와 현재 /28의 차이도 확인합니다.

## 1. API 활성화 — Service Project

Service Project의 API 활성화 권한을 가진 계정에서 수행합니다. 기존 활성 여부를 조회한 다음 필요한 경우에만 변경합니다.
gcloud config set account "$ADMIN_ACCOUNT"
gcloud config list account
~~~bash
gcloud services list --enabled --project="$SVC_PROJECT" \
  --filter="name:(container.googleapis.com OR compute.googleapis.com)"

gcloud services enable \
  container.googleapis.com \
  compute.googleapis.com \
  --project="$SVC_PROJECT"

gcloud beta services identity create \
  --service=container.googleapis.com \
  --project="$SVC_PROJECT"
~~~

## 2. 서브넷 생성 — Host Project

Host Project의 네트워크 관리자 권한이 필요합니다. 이미 존재하는 서브넷은 재생성하지 않고 Describe 값이 승인된 IP와 일치하는지 점검합니다.

### 2-1. Node Primary 및 Pod Secondary
gcloud config set account "$ADMIN_ACCOUNT"
gcloud config list account
~~~bash
# 먼저 조회 — 없을 때만 승인 후 아래 create 수행
gcloud compute networks subnets describe "$NODE_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --format="yaml(ipCidrRange,secondaryIpRanges,privateIpGoogleAccess)"

# 생성 승인·기존 서브넷 미존재 확인 후에만 실행
gcloud compute networks subnets create "$NODE_SUBNET" \
  --project="$HOST_PROJECT" \
  --region="$REGION" \
  --network="$NETWORK" \
  --range="$NODE_CIDR" \
  --secondary-range="$POD_RANGE=$POD_CIDR" \
  --enable-private-ip-google-access
~~~

### 2-2. Private Endpoint용 CP 서브넷

~~~bash
# 먼저 조회 — 없을 때만 승인 후 아래 create 수행
gcloud compute networks subnets describe "$CP_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --format="yaml(ipCidrRange,privateIpGoogleAccess)"

# 생성 승인·기존 서브넷 미존재 확인 후에만 실행
gcloud compute networks subnets create "$CP_SUBNET" \
  --project="$HOST_PROJECT" \
  --region="$REGION" \
  --network="$NETWORK" \
  --range="$CP_CIDR" \
  --enable-private-ip-google-access
~~~

### 2-3. 생성 결과 확인

~~~bash
gcloud compute networks subnets describe "$NODE_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --format="yaml(ipCidrRange,secondaryIpRanges,privateIpGoogleAccess)"
gcloud compute networks subnets describe "$CP_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --format="yaml(ipCidrRange,privateIpGoogleAccess)"
~~~

## 3. Shared VPC 연결

Host Project에 Service Project가 이미 연결된 경우 변경 없이 결과만 확인합니다. **Shared VPC 연결은 Compute Shared VPC Admin 권한 등 별도 상위 권한이 필요할 수 있으며, Service Project Owner만으로 충분하지 않습니다.**

~~~bash
# 현행 상태 확인 (연결되지 않았다면 오류 또는 빈 결과 가능)
gcloud compute shared-vpc get-host-project "$SVC_PROJECT" \
  --format="value(name)"

# 미연결 + 승인 및 권한이 있을 때만 실행
gcloud compute shared-vpc associated-projects add "$SVC_PROJECT" \
  --host-project="$HOST_PROJECT"

# 기대 값: gcp-prod-edp-hub-vpchost
gcloud compute shared-vpc get-host-project "$SVC_PROJECT" \
  --format="value(name)"
~~~

## 4. IAM 설정

### 4-0. 관리자 계정 전환 및 변수 확인

관리자의 Host Project/Service Project IAM 변경 권한을 각각 확인합니다. 이 명령은 해당 계정이 이미 gcloud에 인증된 경우에만 동작합니다.

~~~bash
gcloud config set account "$ADMIN_ACCOUNT"
gcloud config list account

: "${HOST_PROJECT:?0번 변수 정의를 실행하세요}"
: "${SVC_PROJECT:?0번 변수 정의를 실행하세요}"
: "${SVC_PROJECT_NUM:?프로젝트 번호 조회를 확인하세요}"
: "${EXEC_USER:?0번 변수 정의를 실행하세요}"
: "${GKE_AGENT:?Service Agent 변수 필요}"
: "${API_AGENT:?Google APIs Agent 변수 필요}"
~~~

### 4-1. user01 — Node/CP 서브넷 및 Node SA 사용 권한

~~~bash
gcloud compute networks subnets add-iam-policy-binding "$NODE_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --member="$EXEC_USER" --role="roles/compute.networkUser"

gcloud compute networks subnets add-iam-policy-binding "$CP_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --member="$EXEC_USER" --role="roles/compute.networkUser"


SVC_PROJECT 오너계정으로 수행

gcloud iam service-accounts add-iam-policy-binding "$NODE_SA" \
  --project="$SVC_PROJECT" \
  --member="$EXEC_USER" --role="roles/iam.serviceAccountUser"
~~~

### 4-2. GKE Service Agent — Host 및 Node/CP 권한

~~~bash
gcloud projects add-iam-policy-binding "$HOST_PROJECT" \
  --member="$GKE_AGENT" \
  --role="roles/container.hostServiceAgentUser" --condition=None

gcloud compute networks subnets add-iam-policy-binding "$NODE_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --member="$GKE_AGENT" --role="roles/compute.networkUser"

gcloud compute networks subnets add-iam-policy-binding "$CP_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --member="$GKE_AGENT" --role="roles/compute.networkUser"
~~~

Shared VPC 연결 시 GKE Host Service Agent User가 이미 자동 부여되었다면 기존 권한 확인 후 중복 적용하지 않습니다.

### 4-3. Google APIs Service Agent — Node/CP 권한

~~~bash
gcloud compute networks subnets add-iam-policy-binding "$NODE_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --member="$API_AGENT" --role="roles/compute.networkUser"

gcloud compute networks subnets add-iam-policy-binding "$CP_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --member="$API_AGENT" --role="roles/compute.networkUser"
~~~

### 4-4. user01 — GKE 생성·관리 권한

~~~bash
gcloud projects add-iam-policy-binding "$SVC_PROJECT" \
  --member="$EXEC_USER" \
  --role="roles/container.admin" --condition=None
~~~

### 4-5. Node SA 확인 및 기본 운영 권한

~~~bash
gcloud iam service-accounts describe "$NODE_SA" \
  --project="$SVC_PROJECT" --format="yaml(email,disabled)"

# Node SA가 존재하고 disabled: false인지 확인한 후 적용
gcloud projects add-iam-policy-binding "$SVC_PROJECT" \
  --member="serviceAccount:$NODE_SA" \
  --role="roles/container.defaultNodeServiceAccount" --condition=None
~~~

기존 업무 Pod의 .oefj 인증 키와 Node SA는 별개입니다. Node SA의 AR Repository Reader 권한은 뒤의 9단계에 보존했습니다.

## 5. IAM 확인

### 5-1. Node/CP 서브넷 IAM 바인딩

~~~bash
gcloud compute networks subnets get-iam-policy "$NODE_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --format="yaml(bindings)"

gcloud compute networks subnets get-iam-policy "$CP_SUBNET" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --format="yaml(bindings)"

printf '%s\n' "$EXEC_USER" "$GKE_AGENT" "$API_AGENT"
~~~

### 5-2. user01·GKE Agent·Node SA 권한

~~~bash
gcloud projects get-iam-policy "$SVC_PROJECT" \
  --flatten="bindings[].members" \
  --filter="bindings.members:$EXEC_ACCOUNT" \
  --format="table(bindings.role)"

gcloud iam service-accounts get-iam-policy "$NODE_SA" \
  --project="$SVC_PROJECT" --format="yaml(bindings)"

gcloud projects get-iam-policy "$HOST_PROJECT" \
  --flatten="bindings[].members" \
  --filter="bindings.members:$GKE_AGENT" \
  --format="table(bindings.role)"
~~~

서브넷의 compute.networkUser, Service Project의 container.admin, Node SA의 iam.serviceAccountUser, Host의 container.hostServiceAgentUser를 확인합니다. 상위 프로젝트/조직에서 상속되는 권한은 별도 조회가 필요할 수 있습니다.

## 6. 실행 계정 복귀

~~~bash
gcloud config set account "$EXEC_ACCOUNT"
gcloud config list account

: "${SVC_PROJECT:?0번 변수 정의를 실행하세요}"
: "${CLUSTER:?0번 변수 정의를 실행하세요}"
: "${NETWORK_URI:?0번 변수 정의를 실행하세요}"
: "${NODE_SUBNET_URI:?0번 변수 정의를 실행하세요}"
: "${CP_SUBNET_URI:?0번 변수 정의를 실행하세요}"

echo "PROJECT=$SVC_PROJECT"
echo "CLUSTER=$CLUSTER"
echo "NETWORK=$NETWORK_URI"
echo "MGMT_VM_IP=$MGMT_VM_IP"
echo "ACTIVE_ACCOUNT=$(gcloud config get-value account)"
~~~

## 7. 클러스터 생성 또는 설정 변경

클러스터 생성 이전에 IP/Shared VPC/IAM/Quota 및 기존 클러스터 존재 여부를 확인합니다.

### 7-1. 외부 개발환경의 원본 생성 명령 (승인 네트워크 제한 해제 포함)

**원본의 옵션을 누락 없이 보존한 예시**입니다. 승인 네트워크 제한을 해제하므로 실제 전환 대상 환경에서는 보안팀의 명시적인 승인이 있는 경우에만 사용합니다.

~~~bash
gcloud container clusters create-auto "$CLUSTER" \
  --project="$SVC_PROJECT" \
  --region="$REGION" \
  --network="$NETWORK_URI" \
  --subnetwork="$NODE_SUBNET_URI" \
  --cluster-secondary-range-name="$POD_RANGE" \
  --private-endpoint-subnetwork="$CP_SUBNET_URI" \
  --service-account="$NODE_SA" \
  --enable-private-nodes \
  --enable-private-endpoint \
  --enable-master-authorized-networks \
  --no-enable-authorized-networks-on-private-endpoint \
  --release-channel="$RELEASE_CHANNEL"
~~~

### 7-2. 1차 인프라 설치 검토용 명령 (원본의 제한 해제 옵션 제외)

**7-1과 7-2는 동일 클러스터에 대한 대안 명령입니다. 절대로 연속 실행하지 않습니다.** 이 예시는 단순히 원본의 제한 해제 옵션을 제외한 것으로, **Master Authorized Networks 강제 적용을 자동으로 보장하지 않습니다.** 조직 보안 정책에서 Private Endpoint CIDR 제한을 요구할 경우 승인된 CIDR과 함께 `--enable-master-authorized-networks`, `--enable-authorized-networks-on-private-endpoint` 등 적합한 옵션을 별도 검토해야 합니다. 특히 관리 VM 단일 `/32`를 임의로 허용 목록에 넣지 않고 네트워크팀의 승인 대역을 확인합니다.

~~~bash
# 승인된 신규 클러스터에서만 실행
gcloud container clusters create-auto "$CLUSTER" \
  --project="$SVC_PROJECT" \
  --region="$REGION" \
  --network="$NETWORK_URI" \
  --subnetwork="$NODE_SUBNET_URI" \
  --cluster-secondary-range-name="$POD_RANGE" \
  --private-endpoint-subnetwork="$CP_SUBNET_URI" \
  --service-account="$NODE_SA" \
  --enable-private-nodes \
  --enable-private-endpoint \
  --release-channel="$RELEASE_CHANNEL"
~~~

| 옵션 | 의미 |
|---|---|
| --enable-private-nodes | Node에 외부 IP 미할당 |
| --enable-private-endpoint | Control Plane의 외부 IP Endpoint 비활성화 |
| --no-enable-authorized-networks-on-private-endpoint | 내부 Endpoint Master Authorized Networks CIDR 제한 해제 — 보안 승인 필요 |
| --private-endpoint-subnetwork | Private Endpoint 배치용 CP 서브넷 |
| --cluster-secondary-range-name | 기존 Pod Secondary range 이름 |
| --service-account | Node SA |
| --release-channel | regular 채널 |

## 8. Internal IP 접속 확인

제공 자료상 VM은 172.32.10.2이고 CP 서브넷은 10.253.2.0/28입니다. 실제 전환 대상 환경에서 API 연결 검증이 불가능하면 명령은 보존하되 **미검증**으로 기록합니다.

### 8-1. 클러스터 설정 확인

~~~bash
gcloud container clusters describe "$CLUSTER" \
  --project="$SVC_PROJECT" --region="$REGION" \
  --format="yaml(status,autopilot.enabled,privateClusterConfig,masterAuthorizedNetworksConfig,controlPlaneEndpointsConfig)"
~~~

예상: RUNNING, Autopilot enabled, Private Endpoint 10.253.2.x, 외부 Endpoint 비활성화. privateEndpointEnforcementEnabled의 값은 7단계에서 최종 선택한 보안 정책에 따라 확인합니다.

### 8-2. kubeconfig 발급

~~~bash
mkdir -p "$HOME/.kube"
chmod 700 "$HOME/.kube"
export KUBECONFIG="$HOME/.kube/config_l2comn-autopilot"

gcloud container clusters get-credentials "$CLUSTER" \
  --project="$SVC_PROJECT" --region="$REGION" --internal-ip
~~~

### 8-3. Endpoint 확인

~~~bash
kubectl config current-context
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'
printf '\n'
~~~

예상: https://10.253.2.x. 다른 주소가 나올 경우 클러스터 Describe와 Kubeconfig Context를 비교합니다. 기존 kubeconfig는 삭제하지 않습니다.

### 8-4. 네트워크·인증 구분

| 오류 | 우선 점검 |
|---|---|
| TCP timeout | VM→Endpoint TCP443 라우팅·방화벽·VPC 연결 |
| TLS EOF | Private Endpoint 설정, TLS 검사, 프록시 |
| 403 Forbidden | user01 IAM 및 Kubernetes RBAC |
| 인증 플러그인 오류 | gke-gcloud-auth-plugin 설치 여부 |
| Not found | 프로젝트 ID/리전/클러스터명 |

### 8-5. Kubernetes API 읽기 전용 검증 (현재 불가하면 후속 2차 보류)

원본의 확인 명령을 유지합니다. 실제 대상 환경에서 테스트가 불가능하므로 성공으로 기록하지 않습니다.

~~~bash
kubectl cluster-info --request-timeout=15s
kubectl get nodes --request-timeout=15s
kubectl get pods -A --request-timeout=15s
~~~

## 9. Artifact Registry 연동 사전 준비 (실제 Pull은 2차)



먼저 권한추가
~~~bash
export AR_PROJECT="gcp-prod-edp-hub-vpchost"
export AR_REGION="asia-northeast3"
export AR_REPOSITORY="ar-l2comm-python"
export SVC_PROJECT="gcp-sbx-edp-comn-509423"

export SVC_NUM="$(gcloud projects describe "$SVC_PROJECT" \
  --format="value(projectNumber)")"

export NODE_SA="${SVC_NUM}-compute@developer.gserviceaccount.com"

 ① user01 — 저장소 조회용
gcloud artifacts repositories add-iam-policy-binding \
  "$AR_REPOSITORY" \
  --project="$AR_PROJECT" \
  --location="$AR_REGION" \
  --member="user:user01@sonmap.net" \
  --role="roles/artifactregistry.reader"

② GKE Node SA — 향후 이미지 Pull용
 실제 클러스터에 지정한 Node SA와 일치하는지 확인 후 실행
gcloud artifacts repositories add-iam-policy-binding \
  "$AR_REPOSITORY" \
  --project="$AR_PROJECT" \
  --location="$AR_REGION" \
  --member="serviceAccount:${NODE_SA}" \
  --role="roles/artifactregistry.reader"

~~~

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

## 10. Filestore 접근 정책 사전 준비 (실제 NFS Mount는 2차)

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

### 10-1. 1차 대체 검증: 관리 VM에서 NFS 마운트 및 /mnt 경로 확인

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

## 11. 1차 인프라 설치 완료조건 (실제 업무 검증 제외)

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
