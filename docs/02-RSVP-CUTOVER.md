# 02. 3차 RSVP 단일 과제 전환 검증 (GP_L2RSVP_001_1)

**단계 구분:** 1차 인프라 설치, **2차 수동 YAML 기반 AR/NFS/BigQuery 스모크 검증**, 3차 RSVP 실행기/업무 전환 검증. 2026-10-22 현장 로그에서 GKE 수동 Pod 생성, 이미지 Pull, PV/PVC Bound와 Pod 실행 및 이후 Completed 상태가 보고되었다. 하지만 tests/sample_bq.py의 테이블 SELECT 성공 로그와 서비스 계정 인증의 세부 증적은 추가 확인해야 한다. 기존 Cron·client_gke 공통 링크·GKE Standard는 유지한다.

## 외부 개발환경 수행 결과와 대상 환경 시험의 구분

| 항목 | 외부 개발환경에서 제공된 자료 | 실제 대상 환경 |
|---|---|---|
| 실행 프로그램 | run-gke.sh → client_gke 실행 출력 사례 | 3차 승인 후 직접 호출 |
| YAML/PV/PVC | created, 20Gi ROX Bound 출력 | 2026-10-22 현장 적용에서 PV/PVC Bound 확인 |
| Pod 결과 | Pending → Running → Succeeded 출력 | 초기 Pending/IP 부족 이후 재실행; Completed 관측, 실제 업무 Pod 미실행 |
| 로그 정리 | Pod/PVC/PV 삭제 및 정상 종료 출력 | 전용 Pod 삭제·재생성 수행; PV/PVC 유지 기록 |
| BigQuery | .oefj 인증 테스트 코드/출력 참고 | bq_auth_smoke.py 완료 상태 관측; sample_bq.py의 테이블 SELECT는 미검증 |

**현장 검증과 과거 예시 구분:** 2026-10-22 직접 제공된 명령 출력과 과거 외부 개발환경의 참고 로그를 혼합해 성공 처리하지 않는다. 특히 Completed 표시는 컨테이너 종료 상태이며, 실제 BQ 응답 문자열과 종료 코드 및 대상 테이블 조회는 별도 증적으로 확인한다.

[00. 1차 인프라 설치](00-PHASE1-INFRA-INSTALL.md)·[04. VM NFS 검증](04-VM-NFS-MOUNT.md)은 별도 문서로 유지한다. 이 문서 3번 절은 승인된 2차 수동 배포 시험을 재현하는 절차이며, 4번 이후의 실제 업무 실행·Cron 전환은 별도의 단계이다.

## 0. 사전 승인 및 검증 데이터

| 항목 | 설정/확인 |
|---|---|
| 과제 ID | GP_L2RSVP_001_1 |
| Cron/VM | 실제 VM/Linux 사용자 확인, GCP 실행 계정은 user01@sonmap.net |
| 실행 스크립트 | /mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh (VM NFS 마운트/파일 존재 확인 필요) |
| 1차 VM NFS Mount | /batch_gke → /mnt/batch_gke (Export 확인 후) |
| 1차 VM RSVP NFS Path | /mnt/batch_gke/l2/rsvp |
| Pod NFS /home/jupyter | 2차 Pod 실행까지 진행; 3번 절에서 NFS 원본과 파일 경로 확인 |
| 기존 실행 클라이언트 | /ssw/dlk/client_gke (Bash) |
| 신규 검증용 클라이언트 | /ssw/dlk/client-gke-auto (신규 복제/수정) |
| Kubeconfig | $HOME/.kube/config_l2comn-autopilot (첨부 로그 기준) |
| GKE Node/Pod/CP CIDR | Node 10.253.0.0/28 · Pod1 10.253.1.0/24 · 추가 Pod2 10.253.4.0/22 · CP 10.253.2.0/28 |
| Service Project | gcp-sbx-edp-comn-509423 |
| AR Project | gcp-prod-edp-hub-vpchost |
| 채널 | regular |
| 관리 VM/NFS 후보 | 172.32.10.2 (PV에서 NFS 서버로 지정됨. 실제 VM NFS Export 확인 필요) |
| GKE Namespace | l2comm-batch |
| KSA | ksa-l2comm-batch (존재 확인) |
| NFS Export | /batch_gke/l2/rsvp |
| Pod 마운트 | /home/jupyter |
| BQ SA Key | /home/jupyter/.oefj (NFS 상위 경로 파일이 매핑될 때) |
| Python | /home/jupyter/GP_L2RSVP_001_1/python/sample_bq.py (표준) · bq_auth_smoke.py (03-01 별도 간편 시험) |
| BQ 조회 | gcp-prod-edp-lake.DLKUDF.L2MQ_TL_SUBJ_H_TEST |
| 실행 로그상의 스모크 이미지 | asia-northeast3-docker.pkg.dev/gcp-prod-edp-hub-vpchost/ar-l2comm-python/python-bq-batch:v1 |
| 변수 정의의 또 다른 후보 | asia-northeast3-docker.pkg.dev/gcp-prod-edp-hub-vpchost/ar-l2comm-python/1a751e99d693:v1 (대조 필요) |

위 경로/이미지 중 PV 및 Image Pull은 2026-10-22 현장 출력에서 확인되었다. 실제 RSVP 업무 이미지(태그), 인자, Cron 일정은 별도 확정해야 한다. sample_bq.py는 03-01 원본에 없으므로 NFS로 배치하지 않으면 Errno 2로 종료된다.

## 운영 입력값 간 충돌 (생성/실행 전에 검증)

- Node 10.253.0.0/28은 총 16개, GCP 예약 주소 4개를 제외하면 12개 사용 가능. 이전 주석의 128개는 오류.
- 현장 PV는 NFS_SERVER=172.32.10.2, NFS_EXPORT=/batch_gke/l2/rsvp를 가리켰다. 관리형 Filestore가 아니라 03-01 VM NFSv4 PoC일 수 있으므로 실제 서버 주소, /srv/l2comm-nfs bind mount 및 exportfs를 확인한다.
- TEST_IMAGE 변수는 1a751e99d693:v1, 출력은 python-bq-batch:v1. 실제 업무 이미지는 따로 확인해야 함.
- Kubeconfig 경로가 config_new-autopilot, config_l2comn-autopilot, l2comn_gke 등으로 혼재함. 실행 로그에 명시된 config_l2comn-autopilot을 이 문서의 기본값으로 사용.
- 신규 smoke 인증은 .oefj. 과거 일부 Python config.py는 .oef이므로 전체 업무 전환 전에는 별도 호환성 확인.

## 1. (3차 단계 예정) 실행 VM에서 원본 조사 (읽기 전용)

**1차에는 VM NFS 마운트·경로 조회만 수행**할 수 있습니다. 경로 확인 후 실제 Pod 실행기 테스트는 3차에서만 진행합니다. 임시 또는 기존 VM 마운트 절차는 [04. VM NFS 검증](04-VM-NFS-MOUNT.md)을 참조하십시오.

GKE 접근과 RSVP 1차 검증의 **실제 gcloud 실행 계정은 `user01@sonmap.net`**입니다. IAM 변경은 승인된 관리자 계정이 별도 수행하며, 테스트 중 `admin@sonmap.net`으로 바꾸어 실행하지 않습니다. 이전 실행 로그의 Linux 계정 경로는 역사적 증적이므로 유지합니다.

~~~bash
export EXEC_ACCOUNT="user01@sonmap.net"
gcloud auth list
gcloud config set account "$EXEC_ACCOUNT"
test "$(gcloud config get-value account 2>/dev/null)" = "$EXEC_ACCOUNT" || exit 1

export RUN_SCRIPT="/mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh"
export CLIENT_AUTO="/ssw/dlk/client-gke-auto"
export KUBECONFIG="$HOME/.kube/config_l2comn-autopilot"
export NS="l2comm-batch"

ls -l "$RUN_SCRIPT" /ssw/dlk/client_gke /ssw/dlk/client_common
readlink -f /ssw/dlk/client_gke
file /ssw/dlk/client_gke
head -n 3 /ssw/dlk/client_gke
grep -nE 'client[_-]gke|CLIENT_GKE|DOCKER_IMAGE|KUBECONFIG|dry.run|PROGRAM_ID' "$RUN_SCRIPT"
grep -nE 'KUBECONFIG|kubectl apply|serviceAccountName|nfs|volumeMounts' /ssw/dlk/client_gke
kubectl get sa -n "$NS"
kubectl auth can-i create pods -n "$NS"
kubectl auth can-i create persistentvolumes
kubectl auth can-i create persistentvolumeclaims -n "$NS"
~~~

**중요:** client_gke는 현재 확보된 자료상 Python(.py)이 아니라 Bash 스크립트임. YAML은 script 내부 here-document로 생성될 수 있음. 실제 소스와 런처가 본 저장소에 없으므로 호출 인자·옵션 지원 여부는 위 조회로 확인해야 함.

## 2. (3차 단계 예정) 신규 client-gke-auto 준비 — 공통 링크 변경 금지

~~~bash
# 현장 운영 담당자가 기존 동작 파일을 바탕으로 복제
cd /ssw/dlk
cp -p "$(readlink -f client_gke)" client-gke-auto
chmod 750 client-gke-auto

# 편집 대상은 오직 client-gke-auto
# KUBECONFIG=$HOME/.kube/config_l2comn-autopilot
# Namespace=l2comm-batch / KSA=ksa-l2comm-batch
# NFS mount, 이미지, CPU·MEM·GPU, Pod/PV/PVC명과 환경변수/인자 확인
# exit code / trap / 키 복사·삭제 로직도 점검
~~~

복제본에 적용할 Kubeconfig 기본 설정 **예시**:

~~~bash
export KUBECONFIG="$HOME/.kube/config_l2comn-autopilot"
~~~

- 사용자 요청 경로인 $HOME/.kube/config_l2comn-autopilot를 사용.
- 기존 소스에 고정된 kubeconfig, nms-prd, nms-prd-sa, NFS 경로는 신규 값으로 교체할지 판단.
- 코드에 .oef/.oefj 복사·삭제가 있으면 다른 배치와 키 충돌이 없는지 점검. **키 원본 삭제 금지**.
- 기존 클러스터 실행 파일을 직접 덮어쓰지 않음.
- 이미 실행 중인 Cron과 같은 결과 테이블을 동시에 갱신하지 않도록 제한.

## 3. (2차) 수동 YAML 배포 및 RSVP AR/NFS/BigQuery 인증 테스트

**목적:** 기존 Cron과 `run-gke.sh`는 건드리지 않고, `tests/rsvp-smoke.yaml.template`을 직접 렌더링해 PV·PVC·Pod를 생성한다. Pod에서 `tests/sample_bq.py`를 실행하며, **기존 NFS에 저장된 서비스 계정 JSON 키 `.oefj`로 BigQuery에 인증**한다. 서비스 키의 `private_key` 값·JSON 전문·토큰은 GitHub, YAML, 터미널 출력 및 증적 파일에 절대 넣지 않는다.

### 3-1. 실행 구조와 현재 확인된 정보

~~~mermaid
flowchart LR
  VM["infra-son01 VM<br/>kubectl apply"] --> GKE["GKE Autopilot<br/>l2comm-batch / rsvp-bq-smoke"]
  AR["Artifact Registry<br/>python-bq-batch:v1"] -->|"GKE Node SA / AR Reader"| GKE
  NFS["172.32.10.2 NFSv4 서버<br/>/batch_gke/l2/rsvp"] -->|"PV/PVC 20Gi ROX"| GKE
  GKE --> PY["/home/jupyter/GP_L2RSVP_001_1/python/sample_bq.py"]
  PY --> KEY["/home/jupyter/.oefj<br/>기존 SA JSON 키"]
  KEY --> BQ["BigQuery SELECT<br/>읽기 전용"]
~~~

| 구분 | 적용 대상 / 현장 관측 | 해석 |
|---|---|---|
| GKE | `gcp-sbx-edp-comn-509423` / `gkea-prod-l2comn-batch` / `asia-northeast3` | 실제 수동 적용 대상 |
| Namespace / KSA | `l2comm-batch` / `ksa-l2comm-batch` | Pod 생성 시 필요 |
| Artifact Registry | `gcp-prod-edp-hub-vpchost/ar-l2comm-python/python-bq-batch:v1` | image-pull-test에서 실제 Pull 성공 |
| PV / PVC | `pv-rsvp-bq-smoke` / `pvc-rsvp-bq-smoke`, 20Gi, ROX | `Bound` 확인. 데이터 파일 존재 증명은 아님 |
| NFS | `172.32.10.2:/batch_gke/l2/rsvp` → `/home/jupyter` | PV 기록에 존재. 서버 Export 및 로컬 bind 경로 확인 필요 |
| Pod 자원 | `cpu: "4"`, `memory: "16Gi"` | 2026-10-22 초기 IP 부족/증설 실패 → Pod2 추가 이후 재시험 |
| 파일 | `sample_bq.py` | 초기 테스트에서 파일 없음으로 종료; 실제 NFS에 배치 필요 |
| SA Key | `/home/jupyter/.oefj` | **기존에 승인된 키**를 읽기 전용 마운트로 사용 |
| BigQuery | `gcp-prod-edp-lake.DLKUDF.L2MQ_TL_SUBJ_H_TEST` | `sample_bq.py` 기본 조회 테이블, 대상 존재/권한 사전 확인 |

**계정은 서로 다르다.** 사용자 `user01@sonmap.net`은 클러스터 작업자, **Node SA**는 이미지 Pull 주체, **KSA**는 Kubernetes Pod의 서비스 계정, **.oefj 안의 GCP 서비스 계정**은 `sample_bq.py`가 BigQuery API에 사용하는 인증 주체이다.

### 3-2. 실행 환경 및 Kubernetes 리소스 준비

~~~bash
export SVC_PROJECT="gcp-sbx-edp-comn-509423"
export HOST_PROJECT="gcp-prod-edp-hub-vpchost"
export REGION="asia-northeast3"
export CLUSTER="gkea-prod-l2comn-batch"
export NS="l2comm-batch"
export KSA="ksa-l2comm-batch"
export KUBECONFIG="$HOME/.kube/config_l2comn-autopilot"

gcloud config set account user01@sonmap.net
gcloud container clusters get-credentials "$CLUSTER" \
  --project="$SVC_PROJECT" --region="$REGION" --internal-ip
kubectl config current-context
kubectl get namespace "$NS" || kubectl create namespace "$NS"
kubectl get serviceaccount "$KSA" -n "$NS" || \
  kubectl create serviceaccount "$KSA" -n "$NS"

kubectl auth can-i create pods -n "$NS"
kubectl auth can-i create persistentvolumeclaims -n "$NS"
kubectl auth can-i create persistentvolumes
~~~

Namespace/KSA와 PV를 생성할 권한이 없으면 승인된 GKE 관리자가 수행한다. Artifact Registry 이미지 Pull을 위해서는 **GKE Node SA가 해당 AR 저장소에 `roles/artifactregistry.reader`**를 보유해야 한다. 폐쇄망은 Cloud NAT를 사용하지 않으며 Private Google Access·DNS·방화벽·VPC-SC 경로를 별도 확인한다.

### 3-3. NFS 원본에서 `sample_bq.py`와 서비스 계정 키 준비

이번 PV는 `172.32.10.2:/batch_gke/l2/rsvp`를 참조한다. **03-01 PoC의 `setup-nfs-server.sh`를 실제 적용했다면** Git 저장소의 `mnt/`가 `/srv/l2comm-nfs`에 bind mount되고 NFSv4의 루트(`fsid=0`)로 읽기 전용 Export된다.

| 경로 | 위치 / 목적 |
|---|---|
| `~/Gcp_Managed_GKE_L2Comm03-01/mnt/batch_gke/l2/rsvp/` | NFS 제공 VM의 Git 저장소 안 원본 (PoC 설정이 실제 적용된 경우) |
| `/srv/l2comm-nfs/batch_gke/l2/rsvp/` | VM NFS bind mount 아래 파일 |
| `172.32.10.2:/batch_gke/l2/rsvp` | GKE PV NFS Export Path |
| `/home/jupyter/` | GKE Pod 마운트 경로 |
| `/home/jupyter/GP_L2RSVP_001_1/python/sample_bq.py` | Pod에서 자동 또는 수동 실행할 소스 |
| `/home/jupyter/.oefj` | JSON 키 파일의 Pod 내 경로 |

**주의:** `~/Gcp_Managed_GKE_L2Comm03-01/mnt`와 `/mnt`는 서로 다른 경로다. 로컬 `/mnt/batch_gke`가 마운트되어 있지 않으면 해당 위치에 파일을 복사하지 않는다. 아래는 **실제 NFS Export 서버 VM에서 실행**하는 확인 예제다.

~~~bash
export REPO_0301="$HOME/Gcp_Managed_GKE_L2Comm03-01"
export RSVP_SRC="$REPO_0301/mnt/batch_gke/l2/rsvp"
export RSVP_PY_DIR="$RSVP_SRC/GP_L2RSVP_001_1/python"
export RSVP_KEY="$RSVP_SRC/.oefj"

ip -br -4 addr
findmnt --mountpoint /srv/l2comm-nfs
sudo exportfs -v
ls -ld "$RSVP_PY_DIR"
test -s "$RSVP_KEY" && echo ".oefj PRESENT" || echo ".oefj MISSING"
# 개인키 내용은 표시하지 않고 존재와 권한만 확인
test -f "$RSVP_KEY" && stat -c 'mode=%a owner=%U:%G' "$RSVP_KEY"
~~~

`sample_bq.py`는 **이 저장소 `sonmap/Gke3tol2comn/tests/sample_bq.py`**에 있으며, 03-01 저장소에 있던 파일은 `bq_auth_smoke.py`로 **서로 다른 파일**이다. 이 저장소가 NFS 제공 VM에 `$HOME/Gke3tol2comn`으로 내려받아져 있고, 서버 측 파일 배치가 승인되었을 때만 다음을 실행한다.

~~~bash
export DOC_REPO="$HOME/Gke3tol2comn"
test -f "$DOC_REPO/tests/sample_bq.py" || {
  echo "Gke3tol2comn/tests/sample_bq.py 파일을 먼저 확보해야 함"
  exit 1
}
test -d "$RSVP_PY_DIR" || { echo "실제 NFS 소스 경로 미확인"; exit 1; }

# Python 코드만 배치: JSON 서비스 계정 키는 복제하지 않음
install -m 0644 "$DOC_REPO/tests/sample_bq.py" \
  "$RSVP_PY_DIR/sample_bq.py"
ls -l "$RSVP_PY_DIR/sample_bq.py"
test -s "$RSVP_KEY" || { echo ".oefj가 없으므로 BigQuery 인증 시험 중단"; exit 1; }
~~~

실제 Export가 다른 서버 또는 관리형 Filestore에 있다면 **위의 로컬 경로 예시는 사용하지 말고**, 파일시스템 담당자가 확인한 실제 쓰기 가능한 경로에 소스만 배치한다. `.oefj`가 없다면 승인된 보안 절차로 키 존재 문제를 해결해야 하며, 공개 GitHub에 키를 올리거나 YAML `env.value`에 JSON 키를 직접 입력해서는 안 된다. 키 파일은 원본이 NFS에 있는 상태로 Pod에서 **읽기 전용**으로 사용한다. 장기적으로 공유 NFS 키 사용은 최소화하고 Workload Identity Federation for GKE를 검토한다.

### 3-4. YAML 템플릿 치환 → 사전 검증 → Pod 생성

본 저장소의 [`rsvp-smoke.yaml.template`](../tests/rsvp-smoke.yaml.template)는 `FILESTORE_IP`, `NFS_EXPORT`, `TEST_IMAGE` 환경변수를 사용한다. **`kubectl apply`만으로 이 세 변수가 자동 치환되지 않는다.**

~~~bash
cd "$DOC_REPO"
export FILESTORE_IP="172.32.10.2"
export NFS_EXPORT="/batch_gke/l2/rsvp"
export TEST_IMAGE="asia-northeast3-docker.pkg.dev/gcp-prod-edp-hub-vpchost/ar-l2comm-python/python-bq-batch:v1"

# IP가 실제 NFS 서버임을 확인한 후 실행할 것
: "${FILESTORE_IP:?}"
: "${NFS_EXPORT:?}"
: "${TEST_IMAGE:?}"
case "$NFS_EXPORT" in /*) ;; *) echo "NFS Export는 절대 경로여야 함"; exit 1 ;; esac

envsubst '${FILESTORE_IP} ${NFS_EXPORT} ${TEST_IMAGE}' \
  < tests/rsvp-smoke.yaml.template > /tmp/rsvp-smoke-rendered.yaml

grep -nE 'server:|path:|image:|sample_bq.py|BQ_KEY_PATH' \
  /tmp/rsvp-smoke-rendered.yaml
# 아래 명령은 아무 행도 출력하지 않아야 정상
grep -n '${' /tmp/rsvp-smoke-rendered.yaml || true
kubectl apply --dry-run=server -f /tmp/rsvp-smoke-rendered.yaml
~~~

검증해야 할 최종 값:

~~~yaml
nfs:
  server: 172.32.10.2
  path: /batch_gke/l2/rsvp
  readOnly: true

# Pod spec.containers[0]
command: ["/bin/sh", "-ec"]
args:
  - python /home/jupyter/GP_L2RSVP_001_1/python/sample_bq.py
env:
  - name: BQ_KEY_PATH
    value: /home/jupyter/.oefj
~~~

**BigQuery 대상:** [`sample_bq.py`](../tests/sample_bq.py)는 `BQ_KEY_PATH`의 서비스 계정 JSON 키를 읽고, 기본 `BQ_PROJECT=gcp-prod-edp-lake` / `BQ_TEST_TABLE=gcp-prod-edp-lake.DLKUDF.L2MQ_TL_SUBJ_H_TEST`에 대해 다음과 같은 **읽기 전용 쿼리**를 실행한다. 별도 대상 테이블이라면 렌더링된 YAML의 Pod 환경변수에 `BQ_PROJECT`와 `BQ_TEST_TABLE`을 추가한다(키 내용이 아니라 리소스 이름만). 해당 프로젝트의 `bigquery.jobs.create`와 테이블 읽기 권한, BigQuery API 및 VPC-SC 정책을 확인한다.

~~~sql
SELECT 1 AS connected
FROM `gcp-prod-edp-lake.DLKUDF.L2MQ_TL_SUBJ_H_TEST`
LIMIT 1;
~~~

~~~bash
# 이전 시험에서 생성된 전용 Pod 이름이 맞는지 먼저 확인
kubectl get pod rsvp-bq-smoke -n "$NS" --ignore-not-found
kubectl get pv pv-rsvp-bq-smoke
kubectl get pvc pvc-rsvp-bq-smoke -n "$NS"

# 이전 Completed/Error 전용 Pod만 재실행을 위해 삭제; PV/PVC는 유지
kubectl delete pod rsvp-bq-smoke -n "$NS" --ignore-not-found --wait=true
kubectl apply -f /tmp/rsvp-smoke-rendered.yaml

kubectl get pv pv-rsvp-bq-smoke
kubectl get pvc pvc-rsvp-bq-smoke -n "$NS"
kubectl get pod rsvp-bq-smoke -n "$NS" -o wide
# 상태 감시 (별도 터미널, Ctrl+C로 중지)
kubectl get pod rsvp-bq-smoke -n "$NS" -w
~~~

### 3-5. 로그, 서비스 계정 인증 및 BigQuery 결과 검증

~~~bash
# 실제 Pod가 수행하는 명령과 이미지 확인
kubectl get pod rsvp-bq-smoke -n "$NS" \
  -o jsonpath='{.spec.containers[0].image}{"\n"}{.spec.containers[0].command}{"\n"}{.spec.containers[0].args}{"\n"}'

# Python 및 BigQuery 결과
kubectl logs rsvp-bq-smoke -n "$NS" --timestamps
kubectl get pod rsvp-bq-smoke -n "$NS" \
  -o jsonpath='phase={.status.phase}{"\n"}exitCode={.status.containerStatuses[0].state.terminated.exitCode}{"\n"}reason={.status.containerStatuses[0].state.terminated.reason}{"\n"}'

# Pending/Error이면 최근 Events 확인
kubectl describe pod rsvp-bq-smoke -n "$NS" | sed -n '/Events:/$p'
~~~

`sample_bq.py` 성공 기준: 로그에 `[SUCCESS] BQ SELECT job_id=...`가 표시되고 `phase=Succeeded`, `exitCode=0`인 경우. `Completed`는 스크립트가 종료되었다는 뜻이며 **RSVP 본업무 SQL 및 Cron 전환 성공의 증거는 아니다**. 본 스크립트는 쿼리 최대 청구 바이트를 100MiB로 제한하지만 비용이 발생할 수 있다.

### 3-6. Python 자동 실행 없이 Pod만 유지: `sleep infinity`

이미지 Pull / NFS / 키 파일 존재를 먼저 확인하고 **나중에 Python을 수동 실행**하려면 원본 템플릿을 변경하지 않고 별도의 시험 YAML을 만든다.

~~~bash
cp /tmp/rsvp-smoke-rendered.yaml /tmp/rsvp-smoke-idle.yaml
python3 - <<'PY'
from pathlib import Path
p = Path("/tmp/rsvp-smoke-idle.yaml")
s = p.read_text()
before = """      command:
        - /bin/sh
        - -ec
      args:
        - python /home/jupyter/GP_L2RSVP_001_1/python/sample_bq.py"""
after = """      command:
        - /bin/sh
        - -c
      args:
        - sleep infinity"""
if before not in s:
    raise SystemExit("YAML command/args 예상 형식과 다름: 수동 검토 필요")
p.write_text(s.replace(before, after, 1))
PY

grep -nA 5 'command:' /tmp/rsvp-smoke-idle.yaml
kubectl apply --dry-run=server -f /tmp/rsvp-smoke-idle.yaml
kubectl delete pod rsvp-bq-smoke -n "$NS" --ignore-not-found --wait=true
kubectl apply -f /tmp/rsvp-smoke-idle.yaml
kubectl get pod rsvp-bq-smoke -n "$NS" -w
~~~

Pod가 `1/1 Running`이면 다음처럼 키 파일의 **존재만 확인**하고 Python을 실행한다. `kubectl exec` 출력은 호출한 터미널로 나오며 일반적으로 `kubectl logs`에 포함되지 않는다.

~~~bash
kubectl exec -n "$NS" rsvp-bq-smoke -- /bin/sh -c \
  'test -s /home/jupyter/.oefj && echo KEY_PRESENT || echo KEY_MISSING'
kubectl exec -n "$NS" rsvp-bq-smoke -- /bin/sh -c \
  'test -f /home/jupyter/GP_L2RSVP_001_1/python/sample_bq.py && echo PY_PRESENT || echo PY_MISSING'

kubectl exec -n "$NS" rsvp-bq-smoke -- \
  python /home/jupyter/GP_L2RSVP_001_1/python/sample_bq.py
echo "exec_exit_code=$?"
~~~

이 방법은 `sleep infinity` 프로세스가 유지되므로 Python 실행 후에도 Pod가 `Running`인 상태로 남는다. 4 vCPU / 16Gi 리소스에 대한 과금이 이어지므로 장시간 방치하지 않는다. `sleep infinity` 미지원 이미지에서는 `while :; do sleep 3600; done`로 대체할 수 있다.

### 3-7. 기존 03-01 `bq_auth_smoke.py`와 테스트 범위 차이

사용자가 03-01 저장소에서 실제 찾은 `mnt/batch_gke/l2/rsvp/GP_L2RSVP_001_1/python/bq_auth_smoke.py`는 **`sample_bq.py`와 다르다**. 기본 `BQ_JOB_PROJECT=pjt-c-admin`, `SA_KEY_PATH=/home/jupyter/.oefj`를 사용해 테이블 없이 `SELECT 'L2COMM' AS program_id, 'SUCCESS' AS result`를 실행한다.

idle Pod 안에 이 파일이 실제 존재할 경우 간편 인증 시험을 수행할 수 있다.

~~~bash
kubectl exec -n "$NS" rsvp-bq-smoke -- \
  python /home/jupyter/GP_L2RSVP_001_1/python/bq_auth_smoke.py
~~~

예상 메시지는 `L2COMM: SUCCESS`이며, 실제 로그와 종료 코드가 있어야 검증 완료로 판정한다. 테이블 SELECT와 실제 RSVP 업무 검증은 별도이다.

### 3-8. 오류별 점검 및 정리

| 로그 또는 증상 | 확인 및 조치 |
|---|---|
| `spec.nfs.path: "${NFS_EXPORT}" must be an absolute path` | 템플릿을 그대로 적용한 것. `envsubst` 후 적용 |
| Namespace 또는 KSA `NotFound` | `l2comm-batch` / `ksa-l2comm-batch` 존재 여부 및 권한 |
| PV/PVC `Pending` | PV/PVC `Bound` 먼저 확인. 과거 이벤트가 남을 수 있음 |
| `FailedScaleUp: IP space exhausted` | 기존 Pod1 `10.253.1.0/24` 사용률 1.0 관측. Pod2 `10.253.4.0/22` 등록 확인과 신규 노드 Pod CIDR 점검 |
| `Insufficient cpu/memory` | 4 vCPU / 16Gi 수용 가능 노드 및 Autopilot 증설 여부 |
| `ErrImagePull` | Node SA의 AR Reader, PGA, 사설 DNS, 방화벽/VPC-SC |
| `FailedMount` | `172.32.10.2` NFS Export/라우팅/TCP 2049/허용 IP |
| `sample_bq.py: No such file or directory` | `sample_bq.py`가 실제 NFS Export 경로에 배치됐는지 점검 |
| `.oefj` 없음 또는 BigQuery 403 | 키 파일 경로/권한, 키 SA의 BQ 작업/읽기 권한 |
| `Completed` | 일회성 Python 종료. 로그에 BQ 성공 문자열과 ExitCode 확인 |

~~~bash
# 시험 증적 (서비스 계정 JSON 키 내용 및 토큰 기록 금지)
kubectl describe pod rsvp-bq-smoke -n "$NS" > /tmp/rsvp-bq-smoke-describe.txt
kubectl logs rsvp-bq-smoke -n "$NS" > /tmp/rsvp-bq-smoke-log.txt

# 재시험/idle 전환 시 Pod만 삭제 (PV/PVC 유지)
kubectl delete pod rsvp-bq-smoke -n "$NS" --ignore-not-found --wait=true

# PV/PVC가 다른 업무와 무관한 이번 전용 자원이고 정리 승인을 받았을 때만:
# kubectl delete pvc pvc-rsvp-bq-smoke -n "$NS"
# kubectl delete pv pv-rsvp-bq-smoke
~~~

PV의 `Retain`은 NFS 원본 데이터를 자동 삭제하지 않는다. 별도로 원본 소스·`.oefj` 키 또는 공유 Export를 삭제하지 않는다.

## 4. (3차 단계 예정) RSVP run-gke.sh → client-gke-auto 연결 테스트

현재 실제 쉘 소스가 저장소에 없어 다음 두 방식 중 **실제 쉘 소스 확인 후 하나 선택**:

### A. run-gke.sh가 CLIENT_GKE 환경변수를 지원하는 경우

~~~bash
grep -n 'CLIENT_GKE' "$RUN_SCRIPT"
export CLIENT_GKE=/ssw/dlk/client-gke-auto
export GKE_KUBECONFIG="$HOME/.kube/config_l2comn-autopilot"

# 아래는 과거 테스트 이력의 인자 구조 예시.
# 실제 인자 순서 및 --dry-run 지원 여부 확인 후 실행.
# DRY_RUN=1 bash "$RUN_SCRIPT" --dry-run \
#   YYYYMMDD YYYYMMDD YYYYMMDD HHMMSS 0 4 16 \
#   /home/jupyter/GP_L2RSVP_001_1/python python sample_bq.py
~~~

### B. run-gke.sh가 고정된 /ssw/dlk/client_gke만 호출하는 경우

- 운영 원본 run-gke.sh를 보존하고 같은 디렉터리에 별도 run-gke-rsvp-test.sh 복제.
- **복제본의 실행기 호출 경로만** /ssw/dlk/client-gke-auto로 변경.
- 나머지 인자와 업무 이미지 태그는 기존과 동일하게 유지.
- DRY_RUN은 생성되는 Pod/PV/PVC YAML과 클러스터 컨텍스트 리뷰.
- 실 실행은 중복 실행/DB 변경에 대해 업무 담당 승인 후 수행.

**주의:** 기존 run-gke.sh가 지원하지 않는 --dry-run이나 CLIENT_GKE 인자를 억지로 적용하지 말 것.

## 5. (3차 단계 예정) 실제 RSVP 업무 전환 판정

| 검증 | 확인 | Go 기준 |
|---|---|---|
| 기존 | Cron 및 run-gke 원본 보존 | 변경 없음 |
| 접속 | 신규 Kubeconfig | Autopilot context |
| 이미지 | 업무용 Tag | Pull 성공 |
| Filestore | Pod /home/jupyter | mount 및 소스 파일 접근 |
| BQ | SA .oefj | SELECT 실행 및 정상 종료 |
| Pod | phase + exitCode | Succeeded + 0 |
| 업무 | 기간/결과/건수/로그 | 업무 담당 승인 |
| 데이터 | 중복 적재·변경 | 없음 |
| Cleanup | PV/PVC/Pod | 테스트 잔존 자원 없음 |

샘플 SELECT만으로 업무 SQL 전체가 검증되는 것은 아님. 실제 업무 실행 시 BigQuery APPEND/DROP 권한과 병렬 실행 리스크 별도 검증.

## 6. (4차 이후) 전체 과제 절체할 때만: 링크 교체 (1차~3차 금지)

**운영 승인을 받고 Cron 신규 시작 중지·기존 실행 작업 확인 후 진행.** 아래 명령은 1차 PoC에서 실행하지 말 것.

~~~bash
cd /ssw/dlk
test -L client_gke || { echo 'client_gke가 symlink가 아님'; exit 1; }
OLD_TARGET="$(readlink client_gke)"
printf '%s\n' "$OLD_TARGET" > /ssw/dlk/.client_gke_pre_cutover_target
test -x client-gke-auto || exit 1

ln -s client-gke-auto client_gke.next
mv -Tf client_gke.next client_gke
readlink -f client_gke
~~~

원복(신규 작업 중단 후 이전 링크 복원):

~~~bash
cd /ssw/dlk
OLD_TARGET="$(cat /ssw/dlk/.client_gke_pre_cutover_target)"
test -n "$OLD_TARGET" || exit 1
ln -s "$OLD_TARGET" client_gke.rollback
mv -Tf client_gke.rollback client_gke
readlink -f client_gke
~~~

공통 링크 절체는 30개 전체 신규 배치 실행에 영향을 줄 수 있으므로 RSVP만 성공한 상태에서 자동 절체하지 않는다.

## 7. 외부 개발환경 참고 실행 예 (첨부 기록)

이 절은 과거 외부 개발환경의 참고 자료다. 이번 2차 수동 YAML 현장 검증은 3번 절에 별도로 기술했으며 서로 다른 실행 기록을 혼동하지 않는다.

~~~bash
# 원본 run-gke.sh가 --dry-run을 지원하는 것으로 확인되면 사용
# bash /mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh \
#   --dry-run 20261016 20261016 20261016 180000 \
#   0 4 16 /home/jupyter/GP_L2RSVP_001_1/python python bq_auth_smoke.py
~~~

| 항목 | 외부 개발환경 참고 출력값 |
|---|---|
| KUBECONFIG (과거 첨부 로그) | /home/admin_sonmap_net/.kube/config_l2comn-autopilot |
| 이번 실행 사용자 | user01@sonmap.net (Kubeconfig는 현재 Linux 사용자의 $HOME 기준) |
| NAMESPACE | l2comm-batch |
| KSA | ksa-l2comm-batch |
| 이미지 | asia-northeast3-docker.pkg.dev/gcp-prod-edp-hub-vpchost/ar-l2comm-python/python-bq-batch:v1 |
| CPU/MEM/GPU | 4 / 16Gi / 0 |
| NFS_SERVER | 172.32.10.2 (관리 VM IP와 동일, 재확인 필요) |
| NFS_PATH / POD_MOUNT | /batch_gke/l2/rsvp / /home/jupyter |
| PVC | 20Gi / ROX / Bound |
| Pod | Pending → Running → Succeeded |
| 정리 | Pod / PVC / PV delete |
| 배치 반환 | SUCCESS 및 client_gke 정상 종료 (첨부 출력) |

## 8. 후속 단계에서 확보할 증적과 담당

- GKE: cluster describe, context/endpoint, kubectl nodes/pods/events — 플랫폼 담당
- AR: ImagePull 결과 및 이미지 태그 — Edge 담당
- NFS: PV/PVC 상태, Mount, 키 파일 이름·권한만 기록 — 네트워크/스토리지 담당
- BQ: Job ID, 프로젝트, 테이블, 성공 로그 — 데이터 담당
- 배치: Cron 인자, 실행 파일 checksum, 종료코드, 처리 건수 — Linux/업무 담당
- 실패하면 ImagePullBackOff, FailedMount, GKE API 403/EOF, BigQuery 403, 쿼리 오류를 분리 기록

**원칙:** 운영 GKE 생성, NFS 방화벽, IAM, 실행기 설치·절체는 관리자 승인 후 현장에서 수행.
